"""Source-grounded, OOXML-preserving fault-injection experiments.

From one vetted SpreadsheetBench 2 01_01 workbook build 32 single-defect and
24 multi-mechanism mutated XLSX candidates. Not independent benchmark samples.
"""
from __future__ import annotations
import argparse
import html
import json
import random
import re
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from spreadsheetbench2_factory import workbook,sha,check_evidence,SHEET,TARGETS

SHEETS={"ma":"Ex 5 - M&A","organic":"Ex 4 - Organic Operating Model","pf":"Ex 3 - PF P&L"}
PARTS={"Ex 5 - M&A":"xl/worksheets/sheet5.xml",
       "Ex 4 - Organic Operating Model":"xl/worksheets/sheet4.xml",
       "Ex 3 - PF P&L":"xl/worksheets/sheet3.xml"}
PROMPT=("The supplied workbook is a financial acquisition and operating model. "
        "Audit its calculation formulas for internally inconsistent business relationships, "
        "repair errors you can substantiate, and save the corrected XLSX to output/ "
        "using the original filename. Preserve all unrelated information and formatting. "
        "Do not return only an explanation.")

def norm(value):
    return re.sub(r"\s+","",(value or "")).upper().replace("=+","=")

def specs(book):
    entries=[]
    def add(mechanism,sheet,address,original,damaged,rationale):
        real=book["cells"][sheet][address]["formula"]
        if norm(real)!=norm(original):
            raise ValueError(f"Unverified rule {sheet}!{address}: {real!r} != {original!r}")
        if norm(real)==norm(damaged):
            raise ValueError(f"Mutation has no effect: {sheet}!{address}")
        entries.append({"mechanism":mechanism,"sheet":sheet,"cell":address,
                        "correct":real,"mutated":damaged,"rule":rationale})
    ma=SHEETS["ma"];org=SHEETS["organic"];pf=SHEETS["pf"]
    for col,scenario in zip("DEFG",["K13,R13,Y13","L13,S13,Z13","M13,T13,AA13","N13,U13,AB13"]):
        add("scenario_selector",ma,f"{col}13",f"=+CHOOSE($C$4,{scenario})",
            f"=+CHOOSE($C$3,{scenario})","Scenario selector uses C4, not C3")
    for row,metric in [(37,13),(47,16),(57,19),(67,25)]:
        add("cohort_vintage_shift",ma,f"K{row}",f"=+$K33*J${metric}*J$28",
            f"=+$K33*K${metric}*K$28","New acquisition cohort starts at first-year assumptions")
    for col in "JKLM":
        add("synergy_definition",ma,f"{col}25",f"=+{col}22+{col}19",
            f"=+{col}22+{col}16","Synergized EBITDA = EBITDA plus synergies")
    for col in "JKLM":
        add("debt_equity_allocation",ma,f"{col}80",f"=+{col}79*$J$76",
            f"=+{col}79*$J$77","Debt consideration uses debt fraction")
    for col in "DEFG":
        add("organic_revenue_composition",org,f"{col}18",f"=+SUM({col}16:{col}17)",
            f"=+SUM({col}16:{col}16)","Total revenue = software plus services")
    for col in "DEFG":
        add("organic_ebitda_bridge",org,f"{col}40",f"=+{col}28-{col}33",
            f"=+{col}28-{col}31","Adjusted EBITDA subtracts total operating expenses")
    for col in "DEFG":
        add("pf_revenue_source",pf,f"{col}14",f"=+$C$5*'Ex 5 - M&A'!{col}42",
            f"=+$C$5*'Ex 5 - M&A'!{col}52","PF M&A revenue links revenue, not gross profit")
    for col in "DEFG":
        add("pf_synergy_source",pf,f"{col}26",f"=+$C$5*'Ex 5 - M&A'!{col}72",
            f"=+$C$5*'Ex 5 - M&A'!{col}62","PF EBITDA with synergy links synergized EBITDA")
    if len(entries)!=32 or len({(x["sheet"],x["cell"]) for x in entries})!=32:
        raise AssertionError("Expected 32 unique, source-confirmed injection sites")
    return entries

def replace_formulas(src,dst,modifications):
    """Surgically patch existing formula text, preserving untouched OOXML part bytes."""
    per_part={}
    for (sheet,address),formula in modifications.items():
        per_part.setdefault(PARTS[sheet],{})[address]=formula
    dst=Path(dst)
    if dst.exists():raise FileExistsError(dst)
    with zipfile.ZipFile(src) as zin,zipfile.ZipFile(dst,"w") as zout:
        for info in zin.infolist():
            raw=zin.read(info.filename)
            if info.filename in per_part:
                for address,formula in per_part[info.filename].items():
                    regex=rb'(<c\b[^>]*\br="'+re.escape(address.encode())+rb'"[^>]*>)(.*?)(</c>)'
                    matches=list(re.finditer(regex,raw,re.S))
                    if len(matches)!=1:
                        raise ValueError(f"Expected one XML cell {address}, found {len(matches)}")
                    match=matches[0]
                    body=match.group(2)
                    updated,count=re.subn(rb'<f(?:\s[^>]*)?>.*?</f>',
                        lambda _:b'<f>'+html.escape(formula.lstrip("="),quote=False).encode()+b'</f>',
                        body,count=1,flags=re.S)
                    if count!=1:raise ValueError(f"Formula not patchable: {address}")
                    updated=re.sub(rb'<v(?:\s[^>]*)?>.*?</v>',b'<v></v>',updated,flags=re.S)
                    raw=raw[:match.start(2)]+updated+raw[match.end(2):]
            zout.writestr(info,raw)

def select_cases(entries,seed,compound):
    rng=random.Random(seed)
    cases=[[x] for x in entries]
    seen={tuple((x["sheet"],x["cell"]) for x in group) for group in cases}
    attempts=0
    while len(cases)<len(entries)+compound and attempts<10000:
        attempts+=1
        count=rng.choice([2,2,3,3,4])
        mechanisms=rng.sample(sorted({e["mechanism"] for e in entries}),count)
        group=[rng.choice([e for e in entries if e["mechanism"]==m]) for m in mechanisms]
        identity=tuple(sorted((e["sheet"],e["cell"]) for e in group))
        if identity not in seen:
            seen.add(identity);cases.append(group)
    if len(cases)!=len(entries)+compound:
        raise RuntimeError("Cannot sample enough distinct fault combinations")
    return cases

def generate(source,golden,out,seed=20261103,compound=24):
    source=Path(source).resolve()
    golden=Path(golden).resolve()
    out=Path(out).resolve()
    if out.exists():raise FileExistsError(out)
    if compound<0 or compound>500:
        raise ValueError("compound must be 0..500")
    check_evidence(source,golden)
    out.mkdir(parents=True)
    for name in ("private","public","cases"):(out/name).mkdir()
    baseline=out/"private"/"normalized_baseline.xlsx"
    replace_formulas(source,baseline,{(SHEET,a):formula for a,formula in TARGETS.items()})
    clean=workbook(baseline)
    for addr,expected in TARGETS.items():
        if norm(clean["cells"][SHEET][addr]["formula"])!=norm(expected):
            raise ValueError(f"Parent baseline normalization failed: {addr}")
    entries=specs(clean)
    cases=select_cases(entries,seed,compound)
    private=[];public=[]
    for index,group in enumerate(cases,1):
        identifier=f"SSB2-MUT-{index:04d}"
        folder=out/"cases"/identifier
        (folder/"input").mkdir(parents=True)
        (folder/"output").mkdir()
        path=folder/"input"/"Double Counting_mutated.xlsx"
        replace_formulas(baseline,path,{(e["sheet"],e["cell"]):e["mutated"] for e in group})
        mutated=workbook(path)
        for e in group:
            if norm(mutated["cells"][e["sheet"]][e["cell"]]["formula"])!=norm(e["mutated"]):
                raise ValueError(f"Failed injection {identifier}: {e['cell']}")
        (folder/"instruction.md").write_text(PROMPT,encoding="utf-8")
        item={"id":identifier,"input_sha256":sha(path),
              "baseline_sha256":sha(baseline),"source_parent_sha256":sha(source),
              "instruction":PROMPT,"grading":"xlsx_minimal_repair",
              "fault_count":len(group),
              "independence_group":"SSB2_01_01_parent",
              "difficulty_proxy":"multi_mechanism" if len(group)>1 else "single_fault",
              "status":"candidate_requires_review"}
        private.append({**item,"faults":group,"input_path":str(path.relative_to(out))})
        public.append(item)
    (out/"public"/"tasks.jsonl").write_text(
        "".join(json.dumps(x,ensure_ascii=False)+"\n" for x in public),encoding="utf-8")
    (out/"private"/"oracle.json").write_text(
        json.dumps(private,ensure_ascii=False,indent=2),encoding="utf-8")
    result={"candidate_count":len(cases),"single_fault":len(entries),
            "compound_fault":compound,
            "fault_mechanisms":dict(Counter(x["mechanism"] for x in entries)),
            "baseline_sha256":sha(baseline),"source_sha256":sha(source),
            "status":"candidate_requires_review",
            "note":"Same parent workbook: dependent candidates, no numerical Excel recalculation"}
    (out/"manifest.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result

def evaluate(out,task,submission):
    out=Path(out)
    original=workbook(out/task["input_path"])
    edited=workbook(submission)
    baseline=workbook(out/"private"/"normalized_baseline.xlsx")
    issues=[]
    if original["sheets"]!=edited["sheets"]:issues.append("sheet_list_changed")
    if original["defined_names"]!=edited["defined_names"]:issues.append("defined_names_changed")
    if set(original["zip_parts"])!=set(edited["zip_parts"]):
        issues.append("zip_package_parts_changed")
    faults={(x["sheet"],x["cell"]) for x in task["faults"]}
    wrong=[];extras=[]
    for sheet in baseline["sheets"]:
        clean=baseline["cells"][sheet]
        actual=edited["cells"].get(sheet,{})
        for address in set(clean)|set(actual):
            want=clean.get(address,{})
            got=actual.get(address,{})
            if (sheet,address) in faults:
                if norm(got.get("formula"))!=norm(want.get("formula")):
                    wrong.append(f"{sheet}!{address}")
            elif (want.get("formula")!=got.get("formula")
                  or want.get("value")!=got.get("value")
                  or want.get("type")!=got.get("type")
                  or want.get("formula_attrs")!=got.get("formula_attrs")):
                extras.append(f"{sheet}!{address}")
    return {"pass":not issues and not wrong and not extras,
            "wrong_fixes":sorted(wrong),"extra_count":len(extras),
            "extra_edits":sorted(extras)[:30],"integrity_issues":issues,
            "scope":"Target formula and non-target cell comparison, not Excel recalc or full OOXML audit"}

def load_task(out,identifier):
    data=json.loads((Path(out)/"private"/"oracle.json").read_text(encoding="utf-8"))
    matches=[x for x in data if x["id"]==identifier]
    if len(matches)!=1:raise ValueError(f"Unknown case {identifier}")
    return matches[0]

def selftest(out):
    out=Path(out)
    items=json.loads((out/"private"/"oracle.json").read_text(encoding="utf-8"))
    baseline=out/"private"/"normalized_baseline.xlsx"
    checks=[]
    with tempfile.TemporaryDirectory() as tmp:
        for item in items:
            good=evaluate(out,item,baseline)
            bad=evaluate(out,item,out/item["input_path"])
            extra=Path(tmp)/"extra.xlsx"
            replace_formulas(baseline,extra,{(SHEETS["organic"],"D14"):"=1"})
            extra_bad=not evaluate(out,item,extra)["pass"]
            extra.unlink()
            partial_bad=True
            if len(item["faults"])>1:
                partial=Path(tmp)/"partial.xlsx"
                replace_formulas(baseline,partial,{
                    (x["sheet"],x["cell"]):x["mutated"] for x in item["faults"][1:]})
                partial_bad=not evaluate(out,item,partial)["pass"]
                partial.unlink()
            passed=good["pass"] and not bad["pass"] and extra_bad and partial_bad
            checks.append({"id":item["id"],"positive_pass":good["pass"],
                           "untouched_rejected":not bad["pass"],
                           "extra_edit_rejected":extra_bad,
                           "partial_fix_rejected":partial_bad,"pass":passed})
    report={"candidate_count":len(items),
            "selftest_passed":sum(x["pass"] for x in checks),
            "failures":[x for x in checks if not x["pass"]],
            "warning":"Oracle selftest, not independent economic ground-truth evaluation"}
    (out/"selftest_report.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=["generate","selftest","grade"])
    p.add_argument("--source",type=Path,default=Path("Double Counting_input.xlsx"))
    p.add_argument("--golden",type=Path,default=Path("01_golden.xlsx"))
    p.add_argument("--out",type=Path,default=Path("runs/ssb2-injected-01"))
    p.add_argument("--compound",type=int,default=24)
    p.add_argument("--seed",type=int,default=20261103)
    p.add_argument("--id");p.add_argument("--submission",type=Path)
    p.add_argument("--review-evidence",type=Path,help="Optional SHA-bound trusted audit annotations; never mount in model workspace")
    p.add_argument("--report",type=Path,help="Write complete trusted grading JSON to file")
    p.add_argument("--summary-only",action="store_true",help="Show compact three-axis grading summary")
    p.add_argument("--lbo-scenarios",action="store_true",help="Add optional five-year synthetic LBO replay; no Excel recalc")
    args=p.parse_args()
    if args.action=="generate":
        result=generate(args.source,args.golden,args.out,args.seed,args.compound)
    elif args.action=="selftest":
        result=selftest(args.out)
    else:
        if not args.id or not args.submission:p.error("grade requires --id and --submission")
        from spreadsheetbench2_oracle_v3 import evaluate_v3
        golden_file=args.golden if args.golden.is_file() else None
        result=evaluate_v3(args.out,load_task(args.out,args.id),args.submission,
                           golden=golden_file,review_evidence=args.review_evidence)
        if args.lbo_scenarios:
            from spreadsheetbench2_lbo_replay import compare_books, summary
            replay=compare_books(args.out/"private"/"normalized_baseline.xlsx",args.submission)
            result["lbo_scenario_evidence"]={"summary":summary(replay),"cases":replay["cases"],
                                           "limitations":replay["limitations"]}
    if args.action=="grade" and args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    if args.action=="grade" and args.summary_only:
        view={"grading_version":result["grading_version"],"pass":result["pass"],
              "injected_faults":result["injected_faults"],
              "extra_changes":{"count":result["extra_changes"]["count"],
                               "evidence_tiers":result["extra_changes"]["evidence_tiers"]},
              "artifact_integrity":{"preservation_pass":result["artifact_integrity"]["preservation_pass"],
                                    "issues":result["artifact_integrity"]["issues"],
                                    "warnings":result["artifact_integrity"]["warnings"]},
              "financial_constraints":{"rule_count":result["financial_constraints"]["rule_count"],
                                      "pass":result["financial_constraints"]["pass"],
                                      "fail":result["financial_constraints"]["fail"],
                                      "unverified":result["financial_constraints"]["unverified"]},
              "supplemental_business_evidence":{"evaluated_extra_cells":result["supplemental_business_evidence"]["evaluated_extra_cells"],
                                                "improved_under_synthetic_witnesses":result["supplemental_business_evidence"]["improved_under_synthetic_witnesses"]},
              "verdict":result["verdict"]}
    else:
        view=result
    if args.action=="grade" and args.summary_only and args.lbo_scenarios:
        view["lbo_scenario_evidence"]=result["lbo_scenario_evidence"]["summary"]
    print(json.dumps(view,ensure_ascii=False,indent=2))
    if args.action=="selftest" and result["failures"]:
        raise SystemExit(1)

if __name__=="__main__":main()
