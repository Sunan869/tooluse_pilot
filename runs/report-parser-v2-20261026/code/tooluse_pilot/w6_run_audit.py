"""Read-only W6 failure audit grounded in the workbook and tool trajectory."""
import json
from pathlib import Path
from openpyxl import load_workbook
from .real_w6_reconciliation import oracle,report_valid
from .failure_attribution import diagnose

def audit(path):
    root=Path(path)
    case=json.loads((root/"candidate.json").read_text(encoding="utf-8"))
    if case.get("family")!="real_w6_reconciliation":
        raise ValueError("requires a real_w6_reconciliation workspace")
    run=json.loads((root/"run_result.json").read_text(encoding="utf-8"))
    book=load_workbook(root/case["input"]["workbook"],read_only=True,data_only=True)
    try:
        policy=str(book["Policy"]["B3"].value)
        revised=policy=="Beijing,Shenzhen"
        correct=oracle(book)
        actual=tuple(str(book["Summary"][cell].value or "") for cell in ("B2","B3","B4","B5"))
    finally:book.close()
    text=(root/"report.txt").read_text(encoding="utf-8") if (root/"report.txt").is_file() else ""
    tool_events=[e for e in run.get("events",[]) if e.get("event")=="tool_call"]
    attempts=[(i,e) for i,e in enumerate(tool_events) if e.get("tool")=="receive_update"]
    successes=[i for i,e in attempts if (e.get("result") or {}).get("ok") is True]
    rejected=[i for i,e in attempts if (e.get("result") or {}).get("ok") is False]
    first_gate=attempts[0][0] if attempts else None
    first_save=next((i for i,e in enumerate(tool_events) if e.get("tool")=="save_workbook"
                     and (e.get("result") or {}).get("ok") is True),None)
    # Historical traces contain failed calls in events, not in env.calls.
    gate_errors=[str((e.get("result") or {}).get("error","")) for _,e in attempts
                 if (e.get("result") or {}).get("ok") is False]
    return {"candidate_id":case["id"],"state":run.get("state"),"revised_policy_on_disk":revised,
            "expected_from_disk":list(correct),"actual_on_disk":list(actual),
            "summary_matches_disk_policy":actual==correct,
            "report_matches_disk_policy":report_valid(text,correct),
            "gate_attempts":len(attempts),"gate_rejections":len(rejected),
            "gate_successes":len(successes),"recovered_after_gate_failure":any(i>rejected[0] for i in successes) if rejected else False,
            "first_gate_before_successful_save":first_gate is not None and (first_save is None or first_gate<first_save),
            "gate_errors":gate_errors,"diagnosis":diagnose(run),
            "note":"Read-only forensic audit. A gate rejection is not automatically a dynamic-replanning failure.",
            "model_requests_executed":0}
