"""Map official SpreadsheetBench 2 tasks to inspected workbook candidates."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

CATEGORIES = {"Debugging", "Financial_Model", "Template", "Visualization"}

def resolve(root, reference):
    if not isinstance(reference, str) or not reference:
        return None
    normalized = reference.replace("\\", "/").lstrip("./")
    parts = normalized.split("/")
    if ".." in parts:
        return None
    variants = [normalized]
    for i, part in enumerate(parts):
        if part in CATEGORIES:
            variants += ["/".join(parts[i:]), "/".join(parts[i+1:])]
            break
    for base in [root, *[p for p in root.rglob("dataset.json") if p.parent.name in CATEGORIES]]:
        folder = base.parent if base.is_file() else base
        for name in variants:
            target = (folder / name).resolve()
            if target.is_relative_to(root.resolve()) and target.is_file():
                return target
    return None

def load_tasks(root):
    root = root.resolve()
    tasks = []
    for source in sorted(root.rglob("dataset.json")):
        if source.parent.name not in CATEGORIES:
            continue
        obj = json.loads(source.read_text(encoding="utf-8-sig"))
        rows = obj if isinstance(obj, list) else next((obj[k] for k in ("data", "tasks", "dataset") if isinstance(obj.get(k), list)), None)
        if rows is None:
            raise ValueError(f"Unknown dataset structure: {source}")
        for item in rows:
            if not isinstance(item, dict):
                continue
            input_path = resolve(root, item.get("spreadsheet_path"))
            gold_path = resolve(root, item.get("golden_response_path"))
            tasks.append({
                "id": str(item.get("id", "")), "category": source.parent.name,
                "instruction": item.get("instruction", ""),
                "input_ref": item.get("spreadsheet_path"),
                "gold_ref": item.get("golden_response_path"),
                "input_path": input_path.relative_to(root).as_posix() if input_path else None,
                "gold_path": gold_path.relative_to(root).as_posix() if gold_path else None,
                "source": source.relative_to(root).as_posix()})
    return tasks

def match(root):
    root = root.resolve()
    shortlist = json.loads((root / "shortlist.json").read_text(encoding="utf-8"))
    candidates = {item["path"] for item in shortlist.get("cases", [])}
    tasks = load_tasks(root / "raw")
    selected = [item for item in tasks if item["input_path"] in candidates]
    used_inputs = {item["input_path"] for item in selected}
    result = {
        "scanned_candidates": len(candidates),
        "official_tasks": len(tasks),
        "matched": len(selected),
        "matched_input_workbooks": len(used_inputs),
        "category_counts": {cat: sum(item["category"] == cat for item in selected)
                            for cat in sorted(CATEGORIES)},
        "missing_golden": sum(not item["gold_path"] for item in selected),
        "unmatched": sorted(candidates - used_inputs),
        "cases": selected}
    (root / "matched_cases.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def select_tasks(root, per_category=5):
    """Balanced deterministic task selection, independent of structural shortlist."""
    root = root.resolve()
    tasks = load_tasks(root / "raw")
    result = {"total_official": len(tasks), "per_category": per_category,
              "categories": {}, "cases": []}
    for category in sorted(CATEGORIES):
        group = [t for t in tasks if t["category"] == category]
        eligible = [t for t in group if t["input_path"] and t["gold_path"]
                    and isinstance(t["instruction"], str) and t["instruction"].strip()
                    and t["input_path"] != t["gold_path"]]
        # Stable ordering and unique input workbooks for first-pass diversity.
        unique = []
        seen = set()
        for item in sorted(eligible, key=lambda t: (t["id"], t["input_path"])):
            if item["input_path"] not in seen:
                unique.append(item)
                seen.add(item["input_path"])
        chosen = unique[:per_category]
        result["categories"][category] = {
            "official_tasks": len(group),
            "eligible_tasks": len(eligible),
            "unique_eligible_inputs": len(unique),
            "selected": len(chosen)}
        result["cases"].extend(chosen)
    output = root / "balanced_cases.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result

def stage(root, category, case_id, out):
    root = root.resolve()
    rows = load_tasks(root / "raw")
    matches = [x for x in rows if x["category"] == category and x["id"] == case_id]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one matching task, found {len(matches)}")
    item = matches[0]
    if not item["input_path"] or not item["gold_path"] or not isinstance(item["instruction"], str) or not item["instruction"]:
        raise ValueError("Task must have resolvable input, golden and instruction")
    source = (root / "raw" / item["input_path"]).resolve()
    golden = (root / "raw" / item["gold_path"]).resolve()
    if not source.is_file() or not golden.is_file():
        raise FileNotFoundError("Input or golden workbook missing")
    out.mkdir(parents=True, exist_ok=False)
    for dirname in ("input", "output", "private"):
        (out / dirname).mkdir()
    shutil.copy2(source, out / "input" / source.name)
    shutil.copy2(golden, out / "private" / golden.name)
    (out / "instruction.md").write_text(item["instruction"], encoding="utf-8")
    def sha(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    metadata = {
        "task_id": case_id, "category": category, "source_sha256": sha(source),
        "gold_sha256": sha(golden), "source": item["source"],
        "warning": "Do not mount private/ in any agent execution environment"}
    (out / "private" / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["match", "stage", "select"])
    parser.add_argument("--root", type=Path, default=Path("datasets/spreadsheetbench2"))
    parser.add_argument("--per-category", type=int, default=5)
    parser.add_argument("--category", choices=sorted(CATEGORIES))
    parser.add_argument("--id")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if args.action == "match":
        result = match(args.root)
        print(json.dumps({k: v for k, v in result.items() if k != "cases"}, ensure_ascii=False, indent=2))
    elif args.action == "select":
        selection = select_tasks(args.root, args.per_category)
        print(json.dumps({k: v for k, v in selection.items() if k != "cases"}, ensure_ascii=False, indent=2))\n    else:
        if not args.category or not args.id or not args.out:
            parser.error("stage requires --category --id --out")
        print(json.dumps(stage(args.root, args.category, args.id, args.out), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
