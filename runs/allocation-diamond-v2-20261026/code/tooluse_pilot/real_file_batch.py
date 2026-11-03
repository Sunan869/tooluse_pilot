"""Offline counterfactual XLSX batch with independent reference and stale-answer mutants."""
import json
import shutil
import tempfile
from pathlib import Path
from openpyxl import load_workbook
from .real_file_dynamic import generate,reference,expected,Environment

def facts(root):
    wb=load_workbook(Path(root)/"procurement.xlsx",read_only=True,data_only=True)
    try:
        return {"initial":list(expected(wb,160000,["Beijing"])),
                "updated":list(expected(wb,130000,["Beijing","Shenzhen"]))}
    finally:wb.close()

def stale_mutant(case,root):
    """Deliver stage one, then retain the obsolete recommendation at stage two."""
    env=Environment(case,root)
    try:
        initial=expected(env.workbook,160000,["Beijing"])
        for cell,value in zip(("B4","B5","B6"),initial):
            env.call("write_cell",{"sheet":"Decision","cell":cell,"value":value})
        env.call("save_workbook",{})
        env.call("write_report",{"text":f"Recommended {initial[0]} for {initial[1]} CNY; {initial[2]} eligible."})
        env.call("receive_update",{})
        env.call("save_workbook",{})
        env.call("write_report",{"text":f"Recommended {initial[0]} for {initial[1]} CNY; {initial[2]} eligible."})
        env.call("finish",{})
        return env.score()
    finally:env.close()

def validate(case,root):
    with tempfile.TemporaryDirectory() as td:
        good=Path(td)/"good";bad=Path(td)/"bad"
        shutil.copytree(root,good);shutil.copytree(root,bad)
        passed=reference(case,good)
        rejected=stale_mutant(case,bad)
        result=facts(root)
        if not passed["success"] or rejected["success"]:
            raise ValueError(f"invalid task or oracle: {case['id']}")
        if result["initial"]==result["updated"]:
            raise ValueError(f"no material decision change: {case['id']}")
        return {"reference_success":True,"stale_mutant_rejected":True,
                "initial":result["initial"],"updated":result["updated"]}

def make_batch(root,seeds=(0,1,2)):
    target=Path(root)
    if target.exists():raise FileExistsError(target)
    seeds=list(seeds)
    if not seeds or len(set(seeds))!=len(seeds):raise ValueError("unique seeds required")
    with tempfile.TemporaryDirectory() as td:
        stage=Path(td)/"cases";stage.mkdir()
        rows=[]
        for seed in seeds:
            folder=stage/f"case-{seed}"
            case=generate(seed,folder)
            status=validate(case,folder)
            rows.append({"id":case["id"],"seed":seed,**status})
        winners={r["updated"][0] for r in rows}
        if len(winners)<min(len(rows),3):
            raise ValueError("batch lacks distinct final recommendations")
        shutil.copytree(stage,target)
    manifest={"count":len(rows),"distinct_final_winners":len(winners),
              "candidates":rows,"paid_requests":0}
    (target/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return manifest

def verify(root):
    folder=Path(root)
    manifest=json.loads((folder/"manifest.json").read_text(encoding="utf-8"))
    for item in manifest["candidates"]:
        p=folder/f"case-{item['seed']}"
        case=json.loads((p/"candidate.json").read_text(encoding="utf-8"))
        check=validate(case,p)
        if check["initial"]!=item["initial"] or check["updated"]!=item["updated"]:
            raise ValueError(f"changed input or oracle: {case['id']}")
    return {"verified":True,"count":len(manifest["candidates"]),"paid_requests":0}
