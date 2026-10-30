"""Export reproducible research records from real file workspaces, offline."""
import hashlib
import json
from pathlib import Path
from .failure_attribution import inspect_workspace

def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def export_one(workspace):
    root=Path(workspace)
    audit=inspect_workspace(root)
    trace=audit.get("trace_diagnosis")
    report_file=root/"report.txt"
    workbook=root/"procurement.xlsx"
    record={
      "schema_version":"research-case-v1",
      "candidate_id":audit["candidate_id"],
      "source_workspace":str(root),
      "artifact_checks":audit["checks"],
      "expected_final":audit["expected"],
      "observed_final":audit["actual"],
      "artifact_consistent":audit["artifact_consistent"],
      "trace_available":trace is not None,
      "failure_categories":trace["category_names"] if trace else [],
      "failure_origin":trace["origin"] if trace else "unclassified",
      "tool_calls":trace["tool_calls"] if trace else None,
      "invalid_tool_actions":trace["invalid_tool_actions"] if trace else None,
      "evidence_sha256":{
          "workbook":_digest(workbook),
          "report":_digest(report_file) if report_file.exists() else None,
          "trace":_digest(root/"run_result.json") if (root/"run_result.json").exists() else None},
      "model_requests_executed":0,
      "limitation":"A single run documents an observed behavior; it does not establish failure frequency."
    }
    return record

def export_batch(workspaces,outdir):
    target=Path(outdir)
    if target.exists():raise FileExistsError(target)
    records=[export_one(path) for path in workspaces]
    target.mkdir(parents=True)
    for i,record in enumerate(records):
        (target/f"case-{i:03d}.json").write_text(
            json.dumps(record,ensure_ascii=False,indent=2),encoding="utf-8")
    summary={"schema_version":"research-batch-v1","count":len(records),
       "failing_artifacts":sum(not x["artifact_consistent"] for x in records),
       "with_trace":sum(x["trace_available"] for x in records),
       "model_requests_executed":0}
    (target/"summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    return summary
