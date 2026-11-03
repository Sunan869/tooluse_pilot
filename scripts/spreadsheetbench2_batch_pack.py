"""Pack a generated XLSX fault batch into standalone Chinese-Prompt cases.

Each case:
  prompt.md, input.xlsx, metadata.json,
  private/answer.xlsx, private/oracle.json, private/validate.py

Never share the private/ directory with the tested model. Purely offline.
"""
from __future__ import annotations
import argparse,hashlib,json,shutil,sys
from pathlib import Path

SCRIPTS=Path(__file__).resolve().parent
ROOT=SCRIPTS.parent
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(SCRIPTS))
from spreadsheetbench2_case_validate import validate

PROMPT_ZH="""# 任务：修复财务工作簿中人为引入的公式错误

附件 `input.xlsx` 是一份包含企业经营预测、并购、利润表和杠杆收购测算的 Excel 工作簿。

出题时，仅对其中**部分计算公式**进行了人为修改。错误所在的工作表、单元格、类型和数量均未告知。

请使用提供的 Excel / Python / Shell 工具，自行检查工作簿中的业务关系、相邻公式和跨表引用，找出并恢复**本题人为引入的公式错误**。

## 操作要求

1. 必须实际修改 XLSX，不接受仅文字说明或公式列表。
2. **只恢复本题被人为修改的公式**。其他原有公式、数据、样式、工作表、特殊 Excel 结构均保持不变；不要顺便重构或优化其他内容。
3. 将完成的工作簿保存到 `output/input.xlsx`，保持 XLSX 格式。
4. 不会提供错误数量、位置、标准公式或其他答案提示。

## 验收

评分程序会将你提交的文件与预先保存的标准答案 XLSX 进行严格比较：全部人为错误必须恢复，且不得发生额外修改。未预先声明的数学等价表达式也按严格公式比较执行。
"""

SHEET_PARTS={
    "Ex 1 - LBO":"xl/worksheets/sheet1.xml",
    "Ex 3 - PF P&L":"xl/worksheets/sheet3.xml",
    "Ex 4 - Organic Operating Model":"xl/worksheets/sheet4.xml",
    "Ex 5 - M&A":"xl/worksheets/sheet5.xml"}

def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda:f.read(1<<20),b""):h.update(block)
    return h.hexdigest()

def source_info(source):
    source=Path(source).resolve()
    manifest=json.loads((source/"manifest.json").read_text(encoding="utf-8"))
    tasks=json.loads((source/"private"/"oracle.json").read_text(encoding="utf-8"))
    reference=source/"private"/"normalized_baseline.xlsx"
    if not reference.is_file():raise FileNotFoundError(reference)
    if manifest.get("generated") is not None and manifest["generated"]!=len(tasks):
        raise ValueError("Case count mismatch")
    if manifest.get("baseline_sha256") and sha(reference)!=manifest["baseline_sha256"]:
        raise ValueError("Reference baseline hash mismatch")
    if len({x["id"] for x in tasks})!=len(tasks):
        raise ValueError("Duplicate case identifiers")
    return source,tasks,reference,manifest

def pack(source,out,limit=0):
    source,tasks,reference,manifest=source_info(source)
    out=Path(out).resolve()
    if out.exists():raise FileExistsError(out)
    if limit<0:raise ValueError("limit must not be negative")
    if limit:tasks=tasks[:limit]
    if not tasks:raise ValueError("No tasks to package")
    script=SCRIPTS/"spreadsheetbench2_case_validate.py"
    if not script.is_file():raise FileNotFoundError(script)
    out.mkdir(parents=True)
    batch=out.name
    published=[]
    for task in tasks:
        case_id=task["id"]
        if case_id in (".","..") or Path(case_id).name!=case_id:
            raise ValueError("Unsafe task ID")
        source_input=(source/task["input_path"]).resolve()
        if not source_input.is_relative_to(source):
            raise ValueError("Unsafe source input path")
        if sha(source_input)!=task["input_sha256"]:
            raise ValueError("Input XLSX hash mismatch: "+case_id)
        case_dir=out/case_id
        case_dir.mkdir()
        hidden=case_dir/"private"
        hidden.mkdir()
        shutil.copyfile(source_input,case_dir/"input.xlsx")
        shutil.copyfile(reference,hidden/"answer.xlsx")
        shutil.copyfile(script,hidden/"validate.py")
        (case_dir/"prompt.md").write_text(PROMPT_ZH,encoding="utf-8")
        public={
            "id":case_id,"batch_id":batch,"language":"zh-CN",
            "task_type":"controlled_formula_repair",
            "prompt_file":"prompt.md","input_file":"input.xlsx",
            "output_file":"output/input.xlsx",
            "input_sha256":sha(case_dir/"input.xlsx"),
            "parent_workbook_sha256":task.get("source_parent_sha256"),
            "status":"candidate_requires_review"}
        (case_dir/"metadata.json").write_text(
            json.dumps(public,ensure_ascii=False,indent=2),encoding="utf-8")
        hidden_answer={
            "id":case_id,"batch_id":batch,
            "input_sha256":public["input_sha256"],
            "answer_sha256":sha(hidden/"answer.xlsx"),
            "validator_version":"strict_golden_v1",
            "injections":[{
                "sheet":entry["sheet"],
                "sheet_part":SHEET_PARTS[entry["sheet"]],
                "cell":entry["cell"],
                "original_formula":entry["correct"],
                "injected_formula":entry["mutated"],
                "mechanism":entry["mechanism"],
            } for entry in task["faults"]]}
        (hidden/"oracle.json").write_text(
            json.dumps(hidden_answer,ensure_ascii=False,indent=2),encoding="utf-8")
        published.append({"id":case_id,"path":case_id,"language":"zh-CN",
                          "input_sha256":public["input_sha256"]})
    index={
        "batch_id":batch,"format_version":"case_bundle_v1",
        "language":"zh-CN","case_count":len(published),"cases":published,
        "model_visible_files":["prompt.md","input.xlsx","metadata.json"],
        "private_files":["private/answer.xlsx","private/oracle.json","private/validate.py"],
        "note":"All candidate cases share one parent workbook; not statistically independent."}
    (out/"batch_manifest.json").write_text(
        json.dumps(index,ensure_ascii=False,indent=2),encoding="utf-8")
    return {"batch":str(out),"case_count":len(published),"language":"zh-CN",
            "per_case_files":index["model_visible_files"]+index["private_files"]}

def selftest(out):
    out=Path(out).resolve()
    index=json.loads((out/"batch_manifest.json").read_text(encoding="utf-8"))
    failed=[]
    for row in index["cases"]:
        case=out/row["path"]
        positive=validate(case,case/"private"/"answer.xlsx")
        negative=validate(case,case/"input.xlsx")
        if not positive["pass"] or negative["pass"]:
            failed.append({"case":row["id"],"golden_pass":positive["pass"],
                           "unfixed_input_rejected":not negative["pass"]})
    result={"batch_id":index["batch_id"],"case_count":len(index["cases"]),
            "positive_negative_passed":len(index["cases"])-len(failed),
            "failures":failed,"warning":"Oracle selftest is not proof of independent business correctness"}
    (out/"batch_selftest.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=["pack","selftest","grade"])
    parser.add_argument("--source",type=Path,default=Path("runs/ssb2-discovered-v2"))
    parser.add_argument("--out",type=Path,default=Path("runs/batches/ssb2-20261103-01"))
    parser.add_argument("--limit",type=int,default=0)
    parser.add_argument("--case")
    parser.add_argument("--submission",type=Path)
    args=parser.parse_args()
    if args.action=="pack":result=pack(args.source,args.out,args.limit)
    elif args.action=="selftest":result=selftest(args.out)
    else:
        if not args.case or not args.submission:
            parser.error("grade requires --case and --submission")
        result=validate(args.out/args.case,args.submission)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if args.action=="selftest" and result["failures"]:raise SystemExit(1)
    if args.action=="grade" and not result["pass"]:raise SystemExit(1)

if __name__=="__main__":
    main()
