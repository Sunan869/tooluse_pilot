"""Deterministic adversarial W6 checks using real XLSX outputs, without a model."""
import json
import shutil
import tempfile
from pathlib import Path
from .real_file_dynamic import Environment,expected,reference

def _write(env,answer):
    for cell,value in zip(("B4","B5","B6"),answer):
        env.call("write_cell",{"sheet":"Decision","cell":cell,"value":value})

def _report(answer):
    return f"Recommended {answer[0]} for {answer[1]} CNY; {answer[2]} eligible."

def mutant(case,folder,kind):
    env=Environment(case,folder)
    try:
        first=expected(env.workbook,160000,["Beijing"])
        second=expected(env.workbook,130000,["Beijing","Shenzhen"])
        _write(env,first)
        env.call("save_workbook",{})
        env.call("write_report",{"text":_report(first)})
        env.call("receive_update",{})
        if kind=="stale_both":
            _write(env,first)
            env.call("write_report",{"text":_report(first)})
        elif kind=="stale_workbook":
            _write(env,first)
            env.call("write_report",{"text":_report(second)})
        elif kind=="stale_report":
            _write(env,second)
            env.call("write_report",{"text":_report(first)})
        elif kind=="wrong_count":
            _write(env,(second[0],second[1],str(int(second[2])+1)))
            env.call("write_report",{"text":_report(second)})
        elif kind=="wrong_price":
            _write(env,(second[0],str(int(second[1])+1),second[2]))
            env.call("write_report",{"text":_report(second)})
        elif kind=="no_report_update":
            _write(env,second)
        else:raise ValueError("unknown mutant")
        env.call("save_workbook",{})
        env.call("finish",{})
        return env.score()
    finally:env.close()

MUTANTS=("stale_both","stale_workbook","stale_report",
         "wrong_count","wrong_price","no_report_update")

def verify_case(case,source):
    with tempfile.TemporaryDirectory() as temp:
        root=Path(temp)
        ref=root/"reference";shutil.copytree(source,ref)
        baseline=reference(case,ref)
        if not baseline["success"]:
            raise AssertionError("reference did not pass")
        results={}
        for kind in MUTANTS:
            dest=root/kind;shutil.copytree(source,dest)
            scored=mutant(case,dest,kind)
            if scored["success"]:
                raise AssertionError(f"mutant unexpectedly passed: {kind}")
            results[kind]=scored["checks"]
        return {"reference_passed":True,"mutants_rejected":len(results),
                "mutants":results,"model_requests":0}

def verify_batch(paths):
    items=[]
    for path in paths:
        root=Path(path)
        case=json.loads((root/"candidate.json").read_text(encoding="utf-8"))
        items.append({"id":case["id"],**verify_case(case,root)})
    return {"verified_cases":len(items),"mutants_per_case":len(MUTANTS),
            "cases":items,"model_requests":0}
