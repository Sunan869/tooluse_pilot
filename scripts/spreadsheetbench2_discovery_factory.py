"""Discover and inject additional source-verified business formula faults.

Uses one existing normalized SpreadsheetBench 2 01_01 baseline. Produces new
workbooks, not paraphrases. All private fault sets and reference formulas stay
outside model-visible case folders. Candidate research data, not official score.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import random
import re
import sys
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from spreadsheetbench2_fault_factory import (
    PARTS, evaluate, replace_formulas, sha, workbook)
from spreadsheetbench2_financial_constraints import eval_excel, UnsupportedExpression

LBO = "Ex 1 - LBO"
PF = "Ex 3 - PF P&L"
ORG = "Ex 4 - Organic Operating Model"
MA = "Ex 5 - M&A"
PARTS[LBO] = "xl/worksheets/sheet1.xml"

PROMPT = (
    "任务：修复附带的财务工作簿中人为引入的计算公式错误。"
    "请利用业务关系、相邻公式及跨表引用自主定位这些错误。"
    "只恢复本次人为改动的公式；其他原有公式、数据、样式、工作表结构均不得改动。"
    "请将修复后的完整 XLSX 保存到 output/，文件名必须与 input/ 内的原文件一致。"
    "不能仅提供文字解释，也不会提供错误位置、数量或正确公式。"
)

RANGE = re.compile(r"(?<![A-Za-z0-9_])\$?([A-Z]{1,3})\$?(\d+):\$?([A-Z]{1,3})\$?(\d+)")
CELL = re.compile(r"(?<![A-Za-z0-9_!])\$?([A-Z]{1,3})\$?(\d+)")


def rulebook(book):
    """Each rule is independently anchored to an actually observed formula."""
    rules = []

    def add(mechanism, sheet, cell, expected, broken, rationale):
        actual = book["cells"].get(sheet, {}).get(cell, {}).get("formula")
        if actual is None or actual.replace("=+", "=") != expected.replace("=+", "="):
            raise ValueError(f"Source verification failed: {mechanism} {sheet}!{cell}; {actual!r} != {expected!r}")
        if broken.replace("=+", "=") == expected.replace("=+", "="):
            raise ValueError("Mutation leaves formula unchanged")
        rules.append({"mechanism": mechanism, "sheet": sheet, "cell": cell,
                      "correct": actual, "mutated": broken, "rule": rationale})

    for c in "CDEFG":
        for row, low, high, mechanism in (
            (15, 13, 14, "pf_total_revenue_omission"),
            (21, 19, 20, "pf_total_gross_profit_omission"),
            (27, 25, 26, "pf_total_ebitda_omission"),
        ):
            add(mechanism, PF, f"{c}{row}", f"=+SUM({c}{low}:{c}{high})",
                f"=+SUM({c}{low}:{c}{low})", "The consolidated subtotal includes both organic and acquired contributions.")
        add("pf_gross_margin_denominator", PF, f"{c}22",
            f"=+{c}21/{c}15", f"=+{c}21/{c}13",
            "Consolidated gross margin divides consolidated gross profit by consolidated revenue.")
        add("pf_ebitda_margin_denominator", PF, f"{c}28",
            f"=+{c}27/{c}15", f"=+{c}27/{c}13",
            "Consolidated EBITDA margin uses consolidated, not standalone, revenue.")
    for c in "CDEGH":
        add("organic_gross_profit_wrong_cost", ORG, f"{c}28",
            f"=+{c}18-{c}27", f"=+{c}18-{c}31",
            "Gross profit is revenue minus cost of revenue, not R&D.")
        add("organic_opex_component_omission", ORG, f"{c}33",
            f"=+SUM({c}31:{c}32)", f"=+SUM({c}31:{c}31)",
            "Adjusted operating expenses include both R&D and SG&A.")
    for c in "CDEF":
        add("organic_services_split", ORG, f"{c}17",
            f"=+{c}14-{c}16", f"=+{c}14-{c}27",
            "Services revenue is total revenue less recurring software revenue.")
    for c in "JKLMN":
        add("ma_purchase_consideration_metric", MA, f"{c}79",
            f"=+$J$75*{c}33*$J$19", f"=+$J$75*{c}33*$J$13",
            "Acquisition enterprise consideration is based on EBITDA multiple, not revenue.")
        add("ma_target_gross_profit_margin", MA, f"{c}16",
            f"=+{c}13*{c}17", f"=+{c}13*{c}20",
            "Target gross profit uses gross profit margin rather than EBITDA margin.")
        add("ma_target_ebitda_margin", MA, f"{c}19",
            f"=+{c}20*{c}13", f"=+{c}17*{c}13",
            "Target EBITDA uses EBITDA margin, not gross profit margin.")
        add("ma_equity_consideration_fraction", MA, f"{c}81",
            f"=+{c}79*$J$77", f"=+{c}79*$J$76",
            "Equity funding must apply the equity financing share, not debt share.")
    for c in "DEFG":
        add("ma_gross_margin_wrong_denominator", MA, f"{c}53",
            f"=+{c}52/{c}42", f"=+{c}52/{c}62",
            "M&A gross margin uses acquired revenue rather than EBITDA.")
    for c in "QRSTU":
        previous = chr(ord(c) - 1)
        add("lbo_senior_loan_rollforward", LBO, f"{c}76",
            f"=SUM({c}73:{c}75)", f"=SUM({c}73:{c}74)",
            "Senior loan ending balance includes accelerated repayments.")
        add("lbo_interest_aggregation", LBO, f"{c}92",
            f"=SUM({c}87,{c}78,{c}67)", f"=SUM({c}87,{c}78)",
            "Total interest expenses include PIK, senior and revolving debt.")
        add("lbo_revolver_balance_change", LBO, f"{c}65",
            f"={c}63+{c}64", f"={c}63",
            "Revolver ending balance reflects draws or repayments.")
        add("lbo_revenue_forecast_driver", LBO, f"{c}17",
            f"=+{previous}17*(1+{c}41)", f"=+{previous}17*(1+{c}42)",
            "Revenue forecast uses revenue growth, not gross margin.")
        add("lbo_ebitda_forecast_margin", LBO, f"{c}23",
            f"=+{c}43*{c}17", f"=+{c}42*{c}17",
            "EBITDA forecast uses EBITDA margin, not gross profit margin.")
    if len(rules) != 88 or len({(r["sheet"], r["cell"]) for r in rules}) != 88:
        raise AssertionError("Expected 18 distinct mechanisms and 88 nonoverlapping sites")
    if len({r["mechanism"] for r in rules}) != 18:
        raise AssertionError("Expected 18 independent mechanism families")
    return rules


def col_number(value):
    result = 0
    for c in value:
        result = result * 26 + ord(c) - 64
    return result


def col_name(value):
    letters = ""
    while value:
        value, rem = divmod(value - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def formula_inputs(formula, sheet):
    """Build all local referenced cells, including ranges, for bounded witnesses."""
    if "!" in formula:
        raise ValueError("Cross-sheet expressions need explicitly authored witness rules")
    addresses = {(c, int(row)) for c, row in CELL.findall(formula)}
    for c0, r0, c1, r1 in RANGE.findall(formula):
        x, y = col_number(c0), col_number(c1)
        lo, hi = int(r0), int(r1)
        if x > y or lo > hi or (y-x+1)*(hi-lo+1) > 50:
            raise ValueError("Unsupported range in probe")
        for col in range(x,y+1):
            for row in range(lo,hi+1):
                addresses.add((col_name(col),row))
    return {(sheet, f"{c}{r}") for c,r in addresses}


def witness(rule, trials=5):
    """Demonstrate changed arithmetic under synthetic inputs; not business proof."""
    refs = formula_inputs(rule["correct"],rule["sheet"]) | formula_inputs(rule["mutated"],rule["sheet"])
    differences = []
    for i in range(trials):
        rng = random.Random(20261103+i*7907)
        inputs = {key: rng.randint(12,120)*1.7 + i for key in sorted(refs)}
        try:
            expected = eval_excel(rule["correct"],rule["sheet"],inputs)
            damaged = eval_excel(rule["mutated"],rule["sheet"],inputs)
        except (UnsupportedExpression, TypeError, ZeroDivisionError) as error:
            raise ValueError(f"Cannot evaluate {rule['mechanism']} {rule['cell']}: {error}") from error
        if abs(expected-damaged) > 1e-7:
            differences.append({"scenario":i,"correct":expected,"mutated":damaged})
    if not differences:
        raise ValueError(f"No distinguishing numeric witness for {rule['mechanism']} {rule['cell']}")
    return {"synthetic_trials":trials,"distinguishing_trials":len(differences),
            "first_counterexample":differences[0],
            "warning":"Arbitrary precedent values prove non-equivalence, not correct real-world policy"}


def make_cases(rules, count, seed):
    cases = [[x] for x in rules]
    rng = random.Random(seed)
    seen = {tuple(sorted((x["sheet"],x["cell"]) for x in group)) for group in cases}
    by_mechanism = collections.defaultdict(list)
    for entry in rules:
        by_mechanism[entry["mechanism"]].append(entry)
    names = sorted(by_mechanism)
    tries = 0
    while len(cases) < len(rules)+count and tries < 50000:
        tries += 1
        choose = rng.sample(names, rng.choice((2,3,3,4)))
        group = [rng.choice(by_mechanism[m]) for m in choose]
        if len({g["sheet"] for g in group}) < 2:
            continue
        signature = tuple(sorted((x["sheet"],x["cell"]) for x in group))
        if signature not in seen:
            seen.add(signature)
            cases.append(group)
    if len(cases) != len(rules)+count:
        raise RuntimeError("Unable to generate requested distinct cross-sheet combinations")
    return cases


def ensure_integrity(reference, changed, expected_parts):
    """Require a clean XLSX ZIP and exactly the intended changed worksheet parts."""
    with zipfile.ZipFile(reference) as z0, zipfile.ZipFile(changed) as z1:
        if z1.testzip() is not None or set(z0.namelist()) != set(z1.namelist()):
            raise ValueError("Corrupt XLSX or package parts changed")
        actual = {part for part in z0.namelist() if z0.read(part) != z1.read(part)}
        if actual != expected_parts:
            raise ValueError(f"Unexpected OOXML changes: {sorted(actual ^ expected_parts)}")


def generate(dataset, out, compound=48, seed=20261103):
    dataset, out = Path(dataset).resolve(), Path(out).resolve()
    baseline = dataset/"private"/"normalized_baseline.xlsx"
    manifest = json.loads((dataset/"manifest.json").read_text(encoding="utf-8"))
    if sha(baseline) != manifest["baseline_sha256"]:
        raise ValueError("Original normalized workbook SHA mismatch")
    if out.exists():
        raise FileExistsError(out)
    rules = rulebook(workbook(baseline))
    evidence = {f'{r["sheet"]}!{r["cell"]}':witness(r) for r in rules}
    groups = make_cases(rules,compound,seed)
    out.mkdir(parents=True)
    for folder in ("cases","public","private"):
        (out/folder).mkdir()
    # Keep the reference private and exact, never place it in an agent workspace.
    import shutil
    shutil.copy2(baseline,out/"private"/"normalized_baseline.xlsx")
    public, private, hashes = [], [], set()
    for index, group in enumerate(groups,1):
        identity=f"SSB2-NEW-{index:04}"
        folder=out/"cases"/identity
        (folder/"input").mkdir(parents=True)
        (folder/"output").mkdir()
        dest=folder/"input"/"Double Counting_mutated.xlsx"
        replace_formulas(baseline,dest,
            {(r["sheet"],r["cell"]):r["mutated"] for r in group})
        ensure_integrity(baseline,dest,{PARTS[x["sheet"]] for x in group})
        digest=sha(dest)
        if digest in hashes:
            raise ValueError("Two tasks generated the same input workbook")
        hashes.add(digest)
        (folder/"instruction.md").write_text(PROMPT,encoding="utf-8")
        item={"id":identity,"input_sha256":digest,
              "baseline_sha256":sha(baseline),
              "input_path":str(dest.relative_to(out)),
              "faults":group,
              "source_parent_sha256":manifest["source_sha256"]}
        private.append(item)
        public.append({"id":identity,"instruction":PROMPT,
                       "workbook_sha256":digest,
                       "status":"candidate_requires_review"})
    (out/"public"/"tasks.jsonl").write_text(
        "".join(json.dumps(x,ensure_ascii=False)+"\n" for x in public),encoding="utf-8")
    (out/"private"/"oracle.json").write_text(
        json.dumps(private,ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"private"/"witnesses.json").write_text(
        json.dumps(evidence,ensure_ascii=False,indent=2),encoding="utf-8")
    result={
        "generated":len(groups),"single_faults":len(rules),
        "cross_sheet_compounds":compound,"mechanisms":len({r["mechanism"] for r in rules}),
        "unique_workbooks":len(hashes),"oracle_status":"candidate_requires_review",
        "mechanism_counts":dict(sorted(collections.Counter(r["mechanism"] for r in rules).items())),
        "privacy":"private oracle and baseline never copied into agent workspaces",
        "caveat":"Synthetic formula difference witnesses, not full workbook business validation"}
    (out/"manifest.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result


def load_case(out, identifier):
    cases=json.loads((Path(out)/"private"/"oracle.json").read_text(encoding="utf-8"))
    matches=[r for r in cases if r["id"]==identifier]
    if len(matches)!=1:
        raise KeyError(identifier)
    return matches[0]


def score(out,case,submission):
    """Strict injection-repair verification, not exhaustive financial auditing."""
    return evaluate(Path(out),case,Path(submission))


def selftest(out):
    out=Path(out)
    cases=json.loads((out/"private"/"oracle.json").read_text(encoding="utf-8"))
    baseline=out/"private"/"normalized_baseline.xlsx"
    passed=0
    failures=[]
    with tempfile.TemporaryDirectory() as tmp:
        for c in cases:
            clean=score(out,c,baseline)
            untouched=score(out,c,out/c["input_path"])
            extra=Path(tmp)/"extra.xlsx"
            replace_formulas(baseline,extra,{(LBO,"X18"):"=123"})
            extra_rejected=not score(out,c,extra)["pass"]
            extra.unlink()
            partial_rejected=True
            if len(c["faults"])>1:
                partial=Path(tmp)/"partial.xlsx"
                replace_formulas(baseline,partial,{
                    (r["sheet"],r["cell"]):r["mutated"] for r in c["faults"][1:]})
                partial_rejected=not score(out,c,partial)["pass"]
                partial.unlink()
            works=clean["pass"] and not untouched["pass"] and extra_rejected and partial_rejected
            if works:
                passed += 1
            else:
                failures.append({"case":c["id"],"positive":clean["pass"],
                                 "negative":untouched["pass"],
                                 "extra_rejected":extra_rejected,
                                 "partial_rejected":partial_rejected})
    result={"case_count":len(cases),"selftest_passed":passed,
            "failures":failures,"note":"Reference restoration and mutation rejection, not official grading"}
    (out/"selftest_report.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result


def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=["generate","selftest","grade","list"])
    p.add_argument("--dataset",type=Path,default=Path("runs/ssb2-injected-01"))
    p.add_argument("--out",type=Path,default=Path("runs/ssb2-discovered-v2"))
    p.add_argument("--compound",type=int,default=48)
    p.add_argument("--seed",type=int,default=20261103)
    p.add_argument("--batch-out",type=Path,help="Also package a standalone Chinese batch after generation")
    p.add_argument("--id")
    p.add_argument("--submission",type=Path)
    args=p.parse_args()
    if args.action=="generate":
        result=generate(args.dataset,args.out,args.compound,args.seed)
        if args.batch_out:
            from spreadsheetbench2_batch_pack import pack
            result["packaged_batch"]=pack(args.out,args.batch_out)
    elif args.action=="selftest":
        result=selftest(args.out)
    elif args.action=="list":
        result=json.loads((args.out/"manifest.json").read_text(encoding="utf-8"))
    else:
        if not args.id or not args.submission:
            p.error("grade requires --id and --submission")
        result=score(args.out,load_case(args.out,args.id),args.submission)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if args.action=="selftest" and result["failures"]:
        raise SystemExit(1)


if __name__=="__main__":
    main()
