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
    rejected=[x for x in errors if x["tool"]=="receive_update"]
    if rejected:
        mark("revision_gate_rejections",{"count":len(rejected),"errors":sorted(set(str(x["error"]) for x in rejected))})
        gate_events=[(i,e) for i,e in enumerate(tool_events) if e.get("tool")=="receive_update"]
        first_rejection=next((i for i,e in gate_events if (e.get("result") or {}).get("ok") is False),None)
        success_index=next((i for i,e in gate_events if i>first_rejection and (e.get("result") or {}).get("ok") is True),None) if first_rejection is not None else None
        corrections=[{"index":i,"tool":e.get("tool")} for i,e in enumerate(tool_events)
                     if first_rejection<i and (success_index is None or i<success_index)
                     and e.get("tool") in ("read_sheet","write_summary","save_workbook","write_report")]
        reasons=sorted({reason.strip() for x in rejected
                        for reason in str(x["error"]).split("stage_one_failed:")[-1].split(",")
                        if reason.strip() in ("workbook_not_saved","summary_mismatch","report_mismatch")})
        mark("revision_gate_recovery",{"recovered":success_index is not None,
              "rejections":len(rejected),"first_rejection_index":first_rejection,
              "success_index":success_index,"correction_actions":corrections,
              "diagnostic_reasons":reasons})
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

def inspect_workspace(path):
    """Independently compare final disk artifacts with case requirements."""
    from openpyxl import load_workbook
    from .real_file_dynamic import expected, final_report_matches
    root=Path(path)
    case=json.loads((root/"candidate.json").read_text(encoding="utf-8"))
    if case.get("family")!="real_file_dynamic":
        raise ValueError("workspace inspector currently supports real_file_dynamic")
    book=load_workbook(root/case["input"]["workbook"],read_only=True,data_only=True)
    try:
        decision=book["Decision"]
        budget=decision["B2"].value
        cities=decision["B3"].value
        actual=[str(decision[x].value or "") for x in ("B4","B5","B6")]
        desired=list(expected(book,130000,["Beijing","Shenzhen"]))
        vendors=[str(row[0]) for row in list(book["Vendors"].values)[1:]]
        baseline=expected(book,160000,["Beijing"])
    finally:
        book.close()
    report_path=root/"report.txt"
    report=report_path.read_text(encoding="utf-8") if report_path.is_file() else ""
    checks={
        "revised_budget":str(budget)=="130000",
        "revised_cities":str(cities)=="Beijing,Shenzhen",
        "recommendation":actual[0]==desired[0],
        "price":actual[1]==desired[1],
        "eligible_count":actual[2]==desired[2],
        "report_consistent":final_report_matches(report,desired[0],desired[1],int(desired[2]),vendors),
    }
    trace_path=root/"run_result.json"
    trace=diagnose(json.loads(trace_path.read_text(encoding="utf-8"))) if trace_path.is_file() else None
    return {"workspace":str(root),"candidate_id":case["id"],"expected":desired,
            "actual":actual,"initial_expected":list(baseline),
            "checks":checks,"artifact_consistent":all(checks.values()),
            "trace_diagnosis":trace,"paid_requests":0}
