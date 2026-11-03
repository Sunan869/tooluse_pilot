"""Research calibration from already-generated candidates, without regeneration.

Dry-run by default. Paid runs require explicit --execute via CLI.
"""
import json
from pathlib import Path

def discover(roots, per_family=2):
    chosen=[]
    counts={}
    for root in roots:
        root=Path(root)
        if not root.exists():
            raise FileNotFoundError(root)
        for path in sorted(root.rglob("candidate.json")):
            case=json.loads(path.read_text(encoding="utf-8"))
            family=case.get("family","unknown")
            if counts.get(family,0)>=per_family:
                continue
            chosen.append({"candidate_id":case["id"],"family":family,
                           "path":str(path)})
            counts[family]=counts.get(family,0)+1
    return chosen

def plan(roots, per_family=2):
    candidates=discover(roots,per_family)
    return {"mode":"offline_plan","candidate_count":len(candidates),
            "families":sorted({c["family"] for c in candidates}),
            "candidates":candidates,"paid_requests":0}

def analyze(results):
    by_family={}
    seen=set()
    for report in results:
        cid=report["candidate_id"]
        model=report.get("model","unknown")
        key=(cid,model)
        if key in seen: raise ValueError(f"duplicate result {key}")
        seen.add(key)
        family=report.get("family") or cid.split("-")[0]
        group=by_family.setdefault(family,{"n":0,"success":0,"incomplete":0,
                                          "api_errors":0,"invalid_actions":0,
                                          "requests":0,"tool_calls":0,
                                          "known_cost":0.0,"unpriced_runs":0})
        group["n"]+=1
        status=report.get("state")
        passed=bool(report.get("score",{}).get("success"))
        if status=="finished" and passed:group["success"]+=1
        elif status=="api_error":group["api_errors"]+=1
        else:group["incomplete"]+=1
        group["requests"]+=report.get("requests",0)
        group["tool_calls"]+=report.get("tool_calls",0)
        group["invalid_actions"]+=report.get("invalid_tool_actions",0)
        if report.get("estimated_cost") is None:group["unpriced_runs"]+=1
        else:group["known_cost"]+=report["estimated_cost"]
    for group in by_family.values():
        valid=group["n"]-group["api_errors"]
        group["observed_pass_rate"]=round(group["success"]/valid,4) if valid else None
        group["sample_size_warning"]=valid<5
    return {"family_metrics":by_family,"total_runs":len(results),
            "note":"API errors excluded from pass-rate denominator; samples are not population estimates"}

def read_results(paths):
    output=[]
    for item in paths:
        p=Path(item)
        if p.is_dir():
            files=sorted(p.rglob("result.json"))
        else:files=[p]
        for f in files:
            obj=json.loads(f.read_text(encoding="utf-8"))
            if isinstance(obj,list):output.extend(obj)
            else:output.append(obj)
    return output

def execute(roots,output_dir,config,model,per_family=2,max_requests=20,max_tools=60,db="runs/usage.sqlite"):
    from .executable_runner import run_candidate
    candidates=discover(roots,per_family)
    dest=Path(output_dir)
    dest.mkdir(parents=True,exist_ok=False)
    runs=[]
    for i,candidate in enumerate(candidates):
        result=run_candidate(candidate["path"],config,model,db,max_requests,max_tools)
        result["family"]=candidate["family"]
        run_dir=dest/f"{i:03d}-{candidate['candidate_id']}"
        run_dir.mkdir()
        (run_dir/"result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        runs.append(result)
        (dest/"summary.json").write_text(json.dumps(analyze(runs),ensure_ascii=False,indent=2),encoding="utf-8")
    return analyze(runs)
