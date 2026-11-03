"""Offline evidence-based selection of real-file benchmark failures."""
import json
from pathlib import Path
from .research_records import export_one

def select(workspaces):
    cases=[]
    for path in workspaces:
        record=export_one(path)
        audit=record["artifact_checks"]
        categories=set(record["failure_categories"])
        meaningful=bool(record["trace_available"] and not record["artifact_consistent"])
        if not record["trace_available"]:
            decision="insufficient_trace"
        elif record["failure_origin"]=="transport":
            decision="exclude_transport"
        elif record["failure_origin"]=="environment_or_oracle":
            decision="needs_adjudication"
        elif record["artifact_consistent"]:
            decision="control_success"
        else:
            decision="research_candidate"
        # Tool errors and artifact errors are different axes.
        cases.append({
            "candidate_id":record["candidate_id"],
            "workspace":str(path),
            "decision":decision,
            "has_model_trace":record["trace_available"],
            "tool_error_categories":sorted(c for c in categories if c in
                ("sheet_discovery_errors","cell_argument_errors")),
            "failed_artifact_checks":sorted(k for k,v in audit.items() if not v),
            "expected_final":record["expected_final"],
            "observed_final":record["observed_final"],
            "evidence_sha256":record["evidence_sha256"],
            "candidate_evidence":meaningful,
        })
    summary={}
    for c in cases:summary[c["decision"]]=summary.get(c["decision"],0)+1
    return {"schema_version":"candidate-screen-v1","count":len(cases),
        "by_decision":summary,"candidates":cases,"model_requests_executed":0,
        "caveat":"Decisions are from one run and independent artifact checks, not a population failure rate."}

def export(workspaces,out):
    output=Path(out)
    if output.exists():raise FileExistsError(output)
    report=select(workspaces)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return {"count":report["count"],"by_decision":report["by_decision"],
            "output":str(output),"model_requests_executed":0}
