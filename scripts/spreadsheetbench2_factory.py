"""SpreadsheetBench 2 01_01 derived-task factory.

Uses read-only stdlib OOXML inspection and never overwrites source files.
Derived tasks are research candidates, not independent benchmark examples.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import random
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path

S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS = {"m": S, "r": R}
SHEET = "Ex 5 - M&A"
SOURCE_SHA = "e6d8eb78c3c91d352c054a5c043493861954ffa1cf75f80076a1b2d062709c10"
GOLD_SHA = "4ea318ac60b4266a0b752d92d8174c7e526c99570d987764e20bcacfde68c151"
ROWS = {42:(36,41,"Total Revenue"),52:(46,51,"Total Gross Profit"),
        62:(56,61,"Total EBITDA"),72:(66,71,"Total Synergized EBITDA")}
COLS = "DEFG"
TARGETS = {f"{c}{r}":f"=SUM({c}{lo}:{c}{hi})"
           for r,(lo,hi,_) in ROWS.items() for c in COLS}
CROSS_REF = re.compile(r"(?:'((?:[^']|'')+)'|([A-Za-z0-9_ .\-]+))!\$?([A-Z]{1,3})\$?(\d+)")

def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def workbook(path):
    """Extract formulas and explicit cross-sheet references without re-saving."""
    with zipfile.ZipFile(path) as z:
        names=set(z.namelist())
        root=ET.fromstring(z.read("xl/workbook.xml"))
        relations=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets={x.attrib["Id"]:x.attrib["Target"].lstrip("/") for x in relations}
        sheets=[]
        cells={}
        for item in root.findall("m:sheets/m:sheet",NS):
            name=item.attrib["name"]
            target=targets[item.attrib[f"{{{R}}}id"]]
            if not target.startswith("xl/"):
                target="xl/"+target
            if target not in names:
                raise ValueError(f"Missing worksheet part: {target}")
            sheets.append(name)
            sheet_cells={}
            xml=ET.fromstring(z.read(target))
            for c in xml.findall(".//m:sheetData/m:row/m:c",NS):
                f=c.find("m:f",NS)
                v=c.find("m:v",NS)
                inline=c.find("m:is",NS)
                sheet_cells[c.attrib["r"]]={
                    "formula":"="+f.text if f is not None and f.text else None,
                    "formula_attrs":f.attrib if f is not None else {},
                    "value":v.text if v is not None else (
                        "".join(inline.itertext()) if inline is not None else None
                    ),
                    "type":c.attrib.get("t")
                }
            cells[name]=sheet_cells
        defined=root.find("m:definedNames",NS)
        return {"sheets":sheets,"cells":cells,
                "defined_names":sorted(x.attrib.get("name","") for x in defined) if defined is not None else [],
                "zip_parts":sorted(names)}

def canonical(formula):
    return re.sub(r"\s+","",str(formula)).upper().replace("=+","=")

def check_evidence(source,golden):
    if sha(source)!=SOURCE_SHA or sha(golden)!=GOLD_SHA:
        raise ValueError("Input/Golden SHA-256 differs from vetted 01_01 pair")
    original=workbook(source)
    reference=workbook(golden)
    if original["sheets"]!=reference["sheets"]:
        raise ValueError("Sheet list differs")
    evidence=[]
    for addr,wanted in TARGETS.items():
        before=original["cells"][SHEET][addr]["formula"]
        after=reference["cells"][SHEET][addr]["formula"]
        if not before or not after or canonical(after)!=canonical(wanted):
            raise ValueError(f"Golden repair not found at {addr}")
        if canonical(before)==canonical(after):
            raise ValueError(f"Source already repaired at {addr}")
        row=int(re.search(r"\d+",addr).group())
        evidence.append({"cell":addr,"before":before,"after":after,
                         "business_metric":ROWS[row][2]})
    return original,evidence

def scope(name):
    if name=="all":
        return list(TARGETS)
    if name.startswith("row"):
        row=int(name[3:])
        return [f"{c}{row}" for c in COLS]
    if name=="revenue_ebitda":
        return [a for a in TARGETS if a.endswith(("42","62"))]
    if name=="gross_synergy":
        return [a for a in TARGETS if a.endswith(("52","72"))]
    raise ValueError(name)

def direct_consumers(book,address):
    result=set()
    for sheet,cells in book["cells"].items():
        for cell,v in cells.items():
            for m in CROSS_REF.finditer(v["formula"] or ""):
                target=(m.group(1) or m.group(2)).replace("''","'")
                if target==SHEET and m.group(3)+m.group(4)==address:
                    result.add(f"{sheet}!{cell}")
                    break
    return sorted(result)

def make_tasks(book):
    """38 variants, seven families; overlapping evidence, not 38 independent failures."""
    scopes=["all","row42","row52","row62","row72","revenue_ebitda","gross_synergy"]
    tasks=[]
    def add(family,scope_id,instruction,oracle,grading,confidence="static_grounded",exposure="none"):
        tasks.append({
            "task_id":f"SSB2-01_01-{len(tasks)+1:03}",
            "parent_workbook_sha256":SOURCE_SHA,
            "family":family,"scope":scope_id,"instruction":instruction,
            "grading":grading,"oracle":oracle,"confidence":confidence,
            "hint_exposure":exposure,
            "independence_group":"SSB2-01_01_double_counting",
            "review_status":"candidate_requires_review"
        })
    for sc in scopes:
        if sc=="all":
            region="the entire workbook"
        elif sc.startswith("row"):
            region=f"row {sc[3:]} of the M&A worksheet"
        elif sc=="revenue_ebitda":
            region="revenue and EBITDA summary lines in the M&A worksheet"
        else:
            region="gross profit and synergized EBITDA lines in the M&A worksheet"
        add("repair_xlsx",sc,
            f"Audit {region} for independently demonstrable double counting. Repair confirmed subtotal errors and preserve unrelated formulas and values. Save a corrected XLSX to output/.",
            {"targets":scope(sc),"allowed_edits":scope(sc),
             "required_formulas":{a:TARGETS[a] for a in scope(sc)}},
            "xlsx_minimal_repair",exposure="none" if sc=="all" else "location_or_category")
    for sc in scopes:
        region="the entire workbook" if sc=="all" else (
            f"M&A cohort subtotal row {sc[3:]}" if sc.startswith("row")
            else "the relevant M&A financial subtotal groups")
        add("localize",sc,
            f"Independently find subtotal double-counting errors in {region}. Return only JSON with a cells array of affected cell addresses. Do not change the XLSX.",
            {"expected_cells":scope(sc)},"json_exact_cell_set",
            exposure="none" if sc=="all" else "location_or_category")
    for sc in scopes:
        cell=scope(sc)[0]
        add("propose_formula",sc,
            f"Audit the workbook and propose a correct dynamically updating formula for {SHEET}!{cell}. Return JSON with cell and formula. Do not edit the XLSX.",
            {"cell":cell,"formula":TARGETS[cell]},"json_formula",exposure="target_cell")
    for sc in scopes:
        cell=scope(sc)[0]
        col=cell[0];row=int(cell[1:])
        lo,hi,_=ROWS[row]
        add("identify_inputs",sc,
            f"In {SHEET}, identify the six individual cohort contribution cells required for subtotal {cell}. Return JSON with inputs as the six cell addresses.",
            {"inputs":[f"{col}{r}" for r in range(lo,hi+1)]},
            "json_exact_cell_set",exposure="target_cell")
    for row in ROWS:
        cell=f"D{row}"
        add("direct_dependency",f"row{row}",
            f"Which cells in other worksheets directly reference '{SHEET}'!{cell}? Return JSON with cells as Sheet!Address labels; exclude indirect references.",
            {"expected_cells":direct_consumers(book,cell),"source_cell":cell},
            "json_exact_cell_set",confidence="static_explicit_refs_only",exposure="target_cell")
    rng=random.Random(20261030)
    for row,(lo,hi,label) in ROWS.items():
        vals=[rng.randint(3,40)*100 for _ in range(6)]
        add("counterfactual_check",f"row{row}",
            f"For a stand-alone hypothetical stress test of the {label} subtotal, the six active cohort values in E{lo}:E{hi} are {vals} in order. If these already represent this year's contributions, what is the current-year subtotal? Return JSON with integer total.",
            {"total":sum(vals),"cohort_inputs":vals},"json_numeric",
            confidence="arithmetic_fixture",exposure="numeric_fixture")
    add("business_reasoning","revenue",
        "Explain how cohort revenue aggregation in M&A can propagate to the consolidated profit and loss statement. Identify supporting workbook links and avoid assuming prior-year carry-forward is appropriate.",
        {"evidence":["Ex 5 - M&A!D42","Ex 3 - PF P&L!D14"]},
        "human_review",confidence="requires_business_review")
    add("business_reasoning","debt",
        "Evaluate which exit-debt definition is appropriate in the LBO model using labels and linked calculations. Explain reasoning; do not edit the workbook.",
        {"evidence":["Ex 1 - LBO!Y20","Ex 1 - LBO!Q91"]},
        "human_review",confidence="unresolved_debt_semantics")
    return tasks

def validate_json(task,submission):
    if task["grading"]=="human_review":
        return {"status":"review_required","pass":None}
    try:
        data=json.loads(Path(submission).read_text(encoding="utf-8"))
    except (OSError,json.JSONDecodeError) as error:
        return {"status":"invalid_json","pass":False,"error":str(error)[:180]}
    oracle=task["oracle"]
    grade=task["grading"]
    if grade=="json_exact_cell_set":
        key="inputs" if task["family"]=="identify_inputs" else "cells"
        wanted=oracle["inputs"] if key=="inputs" else oracle["expected_cells"]
        actual=data.get(key,[])
        good=(isinstance(actual,list) and all(isinstance(x,str) for x in actual)
              and len(actual)==len(set(actual)) and set(actual)==set(wanted))
        return {"status":"graded","pass":good,"expected_count":len(wanted)}
    if grade=="json_numeric":
        value=data.get("total")
        return {"status":"graded","pass":type(value) in (int,float) and value==oracle["total"]}
    if grade=="json_formula":
        return {"status":"graded","pass":data.get("cell")==oracle["cell"]
                and canonical(data.get("formula"))==canonical(oracle["formula"])}
    raise ValueError(f"Unsupported grading type: {grade}")

def validate_xlsx(task,source,submission):
    if task["grading"]!="xlsx_minimal_repair":
        raise ValueError("Task does not accept XLSX")
    original=workbook(source);edited=workbook(submission)
    oracle=task["oracle"]
    issues=[]
    if original["sheets"]!=edited["sheets"]:
        issues.append("sheet_names_or_order_changed")
    if original["defined_names"]!=edited["defined_names"]:
        issues.append("defined_names_changed")
    modified=[]
    for sheet in set(original["cells"])|set(edited["cells"]):
        old=original["cells"].get(sheet,{})
        new=edited["cells"].get(sheet,{})
        for address in set(old)|set(new):
            a=old.get(address) or {}
            b=new.get(address) or {}
            if a.get("formula")!=b.get("formula") or a.get("value")!=b.get("value"):
                modified.append(f"{sheet}!{address}")
    wrong=[]
    for address,formula in oracle["required_formulas"].items():
        actual=edited["cells"].get(SHEET,{}).get(address,{}).get("formula")
        if canonical(actual)!=canonical(formula):
            wrong.append({"cell":address,"expected":formula,"actual":actual})
    permitted={f"{SHEET}!{address}" for address in oracle["allowed_edits"]}
    extras=sorted(set(modified)-permitted)
    return {"status":"graded","pass":not wrong and not extras and not issues,
            "required_count":len(oracle["required_formulas"]),
            "wrong_targets":wrong,"unauthorized_count":len(extras),
            "unauthorized_examples":extras[:30],"structure_issues":issues,
            "limitations":"No recalculation, formula equivalence, or full OOXML preservation check"}

def write_ref_patch(source,destination,patch):
    """Create trusted positive/negative fixtures by surgically patching XML."""
    with zipfile.ZipFile(source) as zin,zipfile.ZipFile(destination,"w") as zout:
        for info in zin.infolist():
            content=zin.read(info.filename)
            if info.filename=="xl/worksheets/sheet5.xml":
                root=ET.fromstring(content)
                cells={c.attrib.get("r"):c for c in root.findall(".//m:sheetData/m:row/m:c",NS)}
                for address,formula in patch.items():
                    c=cells[address]
                    f=c.find("m:f",NS)
                    if f is None:
                        raise ValueError(f"Missing formula at {address}")
                    f.text=formula.lstrip("=")
                    v=c.find("m:v",NS)
                    if v is not None:
                        c.remove(v)
                content=ET.tostring(root,encoding="utf-8",xml_declaration=True)
            zout.writestr(info,content)

def produce(source,golden,out,count_limit=0):
    source=Path(source).resolve()
    golden=Path(golden).resolve()
    out=Path(out).resolve()
    if out.exists():
        raise FileExistsError(out)
    original,evidence=check_evidence(source,golden)
    tasks=make_tasks(original)
    if count_limit:
        tasks=tasks[:count_limit]
    out.mkdir(parents=True)
    for section in ("private","public","fixtures"):
        (out/section).mkdir()
    public=[]
    for task in tasks:
        identifier=task["task_id"]
        (out/"private"/f"{identifier}.json").write_text(
            json.dumps(task,ensure_ascii=False,indent=2),encoding="utf-8")
        public.append({key:value for key,value in task.items() if key!="oracle"})
    (out/"public"/"tasks.jsonl").write_text(
        "".join(json.dumps(task,ensure_ascii=False)+"\n" for task in public),
        encoding="utf-8")
    (out/"private"/"source_evidence.json").write_text(
        json.dumps(evidence,ensure_ascii=False,indent=2),encoding="utf-8")
    (out/"private"/"oracle.json").write_text(
        json.dumps({task["task_id"]:task for task in tasks},ensure_ascii=False,indent=2),
        encoding="utf-8")
    (out/"manifest.json").write_text(json.dumps({
        "parent_input_sha256":sha(source),"parent_golden_sha256":sha(golden),
        "task_count":len(tasks),"family_counts":dict(Counter(t["family"] for t in tasks)),
        "parent_independent_problem_count":"not_established",
        "oracle_status":"candidate_requires_review",
        "note":"Task variants share overlapping evidence and are not independent benchmark examples"
    },ensure_ascii=False,indent=2),encoding="utf-8")
    return tasks

def selftest(source,out):
    source=Path(source)
    out=Path(out)
    tasks=json.loads((out/"private"/"oracle.json").read_text(encoding="utf-8"))
    results=[]
    for identifier,task in tasks.items():
        grade=task["grading"]
        if grade=="human_review":
            results.append({"task_id":identifier,"status":"review_required"})
            continue
        fixture=out/"fixtures"/f"{identifier}.json"
        if grade=="xlsx_minimal_repair":
            fixture=out/"fixtures"/f"{identifier}.xlsx"
            patch=task["oracle"]["required_formulas"]
            write_ref_patch(source,fixture,patch)
            positive=validate_xlsx(task,source,fixture)
            negative=validate_xlsx(task,source,source)
            wrong=out/"fixtures"/f"{identifier}-wrong.xlsx"
            wrong_patch=dict(patch)
            wrong_patch[next(iter(wrong_patch))]="=1"
            write_ref_patch(source,wrong,wrong_patch)
            wrong_result=validate_xlsx(task,source,wrong)
            extra=out/"fixtures"/f"{identifier}-extra.xlsx"
            write_ref_patch(source,extra,{**patch,"E43":"=1"})
            extra_result=validate_xlsx(task,source,extra)
            mutation_pass=not wrong_result["pass"] and not extra_result["pass"]
        else:
            oracle=task["oracle"]
            if grade=="json_exact_cell_set":
                key="inputs" if task["family"]=="identify_inputs" else "cells"
                values=oracle["inputs"] if key=="inputs" else oracle["expected_cells"]
                good={key:values}
                bad={key:[] if values else ["Ex 1 - LBO!A1"]}
            elif grade=="json_formula":
                good={"cell":oracle["cell"],"formula":oracle["formula"]}
                bad={"cell":oracle["cell"],"formula":"=1"}
            elif grade=="json_numeric":
                good={"total":oracle["total"]}
                bad={"total":oracle["total"]+1}
            else:
                raise ValueError(grade)
            fixture.write_text(json.dumps(good),encoding="utf-8")
            wrong=out/"fixtures"/f"{identifier}-incorrect.json"
            wrong.write_text(json.dumps(bad),encoding="utf-8")
            positive=validate_json(task,fixture)
            negative=validate_json(task,wrong)
            mutation_pass=True
        results.append({
            "task_id":identifier,"family":task["family"],
            "positive_pass":positive["pass"] is True,
            "negative_rejected":negative["pass"] is False,
            "mutation_negative_rejected":mutation_pass,
            "pass":positive["pass"] is True and negative["pass"] is False and mutation_pass
        })
    report={
        "tasks":len(results),"auto_scored":sum("pass" in row for row in results),
        "oracle_selftests_passed":sum(row.get("pass",False) for row in results),
        "review_required":sum(row.get("status")=="review_required" for row in results),
        "failures":[row for row in results if row.get("pass") is False]
    }
    (out/"selftest_report.json").write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=("generate","selftest","grade"))
    parser.add_argument("--source",type=Path,default=Path("Double Counting_input.xlsx"))
    parser.add_argument("--golden",type=Path,default=Path("01_golden.xlsx"))
    parser.add_argument("--out",type=Path,default=Path("runs/ssb2-family-01"))
    parser.add_argument("--limit",type=int,default=0)
    parser.add_argument("--id")
    parser.add_argument("--submission",type=Path)
    args=parser.parse_args()
    if args.action=="generate":
        tasks=produce(args.source,args.golden,args.out,args.limit)
        result={"generated":len(tasks),"family_counts":dict(Counter(t["family"] for t in tasks)),
                "out":str(args.out),"status":"candidate_requires_review"}
    elif args.action=="selftest":
        result=selftest(args.source,args.out)
    else:
        if not args.id or not args.submission:
            parser.error("grade requires --id and --submission")
        tasks=json.loads((args.out/"private"/"oracle.json").read_text(encoding="utf-8"))
        task=tasks[args.id]
        result=(validate_xlsx(task,args.source,args.submission)
                if task["grading"]=="xlsx_minimal_repair"
                else validate_json(task,args.submission))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if args.action=="selftest" and result["failures"]:
        raise SystemExit(1)

if __name__=="__main__":
    main()
