"""Offline failure attribution from persisted tool-use traces; never calls models."""
import json
from pathlib import Path

def diagnose(run):
    score=run.get("score") or {}
    checks=score.get("checks") or {}
    events=run.get("events") or []
    calls=run.get("calls") or []
    tool_events=[e for e in events if e.get("event")=="tool_call"]
    errors=[]
    for i,e in enumerate(tool_events):
        response=e.get("result") or {}
        if response.get("ok") is False:
            errors.append({"index":i,"tool":e.get("tool"),"arguments":e.get("arguments"),
                           "error":response.get("error") or (response.get("result") or {}).get("reason")})
    # Older traces may have no event payload. Use environment calls as fallback.
    if not tool_events:
        for i,c in enumerate(calls):
            response=c.get("response") or {}
            if response.get("ok") is False:
                errors.append({"index":i,"tool":c.get("tool"),"arguments":c.get("args"),
                               "error":response.get("reason") or response.get("error")})
    categories=[]
    def mark(name,detail):
        categories.append({"category":name,"evidence":detail})
    unknown=[x for x in errors if x["tool"]=="inspect_sheet" and "unknown sheet" in str(x["error"]).lower()]
    malformed=[x for x in errors if x["tool"]=="write_cell"]
    if unknown:mark("sheet_discovery_errors",{"count":len(unknown),"examples":unknown[:4]})
    if malformed:mark("cell_argument_errors",{"count":len(malformed),"examples":malformed[:4]})
    for name in ("initial_delivered","update_received","requirements","result","report","finished"):
        if name in checks and checks[name] is False:
            mark("failed_"+name,{"check":name})
    if run.get("state")=="api_error":mark("transport_failure",{"state":"api_error"})
    if run.get("state") in ("max_requests","max_tools"):mark("execution_limit",{"state":run["state"]})
    invalid=run.get("invalid_tool_actions",score.get("invalid_actions",len(errors)))
    origin=("transport" if run.get("state")=="api_error" else
            "environment_or_oracle" if run.get("evaluation_issue") else
            "model_behavior" if categories or not score.get("success") else "none")
    return {"origin":origin,"run_id":run.get("run_id"),"candidate_id":run.get("candidate_id"),
            "model":run.get("model"),"passed":bool(score.get("success")),
            "state":run.get("state"),"tool_calls":run.get("tool_calls",len(tool_events)),
            "invalid_tool_actions":invalid,"categories":categories,
            "category_names":[x["category"] for x in categories],
            "failed_tools":errors,"paid_requests":0}

def load(path):
    p=Path(path)
    if p.is_dir():p=p/"run_result.json"
    return json.loads(p.read_text(encoding="utf-8"))

def batch(paths):
    reports=[diagnose(load(path)) for path in paths]
    counts={}
    for report in reports:
        for category in set(report["category_names"]):
            counts[category]=counts.get(category,0)+1
    origins={}
    for report in reports:
        origin=report["origin"]
        origins[origin]=origins.get(origin,0)+1
    return {"runs":len(reports),"category_run_counts":counts,"origin_run_counts":origins,
            "reports":reports,"paid_requests":0}
