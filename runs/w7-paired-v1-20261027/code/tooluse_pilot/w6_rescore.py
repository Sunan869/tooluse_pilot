"""Immutable-source W6 offline rescoring: preserve the original run and evidence."""
import hashlib
import json
from pathlib import Path
from .w6_run_audit import audit

def digest(path):
    p=Path(path)
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None

def rescore(workspace):
    root=Path(workspace)
    facts=audit(root)
    run=json.loads((root/"run_result.json").read_text(encoding="utf-8"))
    original=run.get("score") or {}
    checks=dict(original.get("checks") or {})
    if not checks:
        raise ValueError("original run lacks scored checks; do not infer missing stage evidence")
    if "report" in checks:
        checks["report"]=bool(facts["report_matches_disk_policy"]) and bool(facts["revised_policy_on_disk"])
        # Keep evidence that phase one and phase two reports differ if recorded.
        writes=[e for e in run.get("events",[]) if e.get("event")=="tool_call" and e.get("tool")=="write_report" and (e.get("result") or {}).get("ok") is True]
        if len(writes)<2:
            checks["report"]=False
        else:
            def text_arg(item):
                try:return json.loads(item.get("arguments") or "{}").get("text")
                except (ValueError,TypeError):return None
            first=text_arg(writes[0]);last=text_arg(writes[-1])
            checks["report"]=checks["report"] and first is not None and last is not None and first!=last
    if "result" in checks:checks["result"]=bool(facts["summary_matches_disk_policy"])
    # Never upgrade a trace that failed to reach a legitimate transition or failed other checks.
    success=bool(checks) and all(checks.values()) and run.get("invalid_tool_actions",0)==0
    return {"schema_version":"w6-offline-rescore-v1","candidate_id":facts["candidate_id"],
            "original_score":original,"revised_score":{"success":success,"checks":checks},
            "changed_checks":{k:{"original":original["checks"][k],"revised":v}
                              for k,v in checks.items() if k in original["checks"] and original["checks"][k]!=v},
            "evidence_sha256":{name:digest(root/name) for name in
                               ("candidate.json","run_result.json","reconciliation.xlsx","report.txt")},
            "limitations":["Historical stage checks remain as recorded; no hidden runtime state is reconstructed.",
                           "An offline rescore is not a new model execution."],
            "model_requests_executed":0}

def export(workspace,destination):
    p=Path(destination)
    if p.exists():raise FileExistsError(p)
    result=rescore(workspace)
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result
