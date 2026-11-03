"""Read-only paired comparison of old/new W6 attempts; never calls a model."""
import json
from pathlib import Path
from .w6_run_audit import audit

def compare(old_workspace,new_workspace):
    old=audit(old_workspace)
    new=audit(new_workspace)
    if old["candidate_id"]!=new["candidate_id"]:
        raise ValueError("Candidate IDs differ; a paired comparison requires the same seed")
    def metrics(item):
        diag=item["diagnosis"]
        return {"state":item["state"],"score_passed":diag["passed"],
                "gate_rejections":item["gate_rejections"],
                "gate_successes":item["gate_successes"],
                "recovered_after_gate_failure":item["recovered_after_gate_failure"],
                "initial_stage_passed":item["gate_successes"]>0,
                "tool_calls":diag["tool_calls"],"invalid_tool_actions":diag["invalid_tool_actions"],
                "disk_summary_matches_policy":item["summary_matches_disk_policy"],
                "disk_report_matches_policy":item["report_matches_disk_policy"]}
    a=metrics(old);b=metrics(new)
    if b["score_passed"] and not a["score_passed"]: outcome="improved_completion"
    elif a["score_passed"] and not b["score_passed"]:outcome="regressed_completion"
    elif b["initial_stage_passed"] and not a["initial_stage_passed"]:outcome="improved_stage_progress"
    elif a["initial_stage_passed"] and not b["initial_stage_passed"]:outcome="regressed_stage_progress"
    else:outcome="no_observed_stage_improvement"
    return {"schema_version":"w6-paired-v1","candidate_id":old["candidate_id"],
            "old":a,"new":b,"outcome":outcome,
            "invalid_action_delta":b["invalid_tool_actions"]-a["invalid_tool_actions"],
            "gate_rejection_delta":b["gate_rejections"]-a["gate_rejections"],
            "limitations":["One old/new run cannot prove the feedback change caused any improvement.",
                           "Different sampling, model versions or backend settings may affect the result."],
            "model_requests_executed":0}

def export(old_workspace,new_workspace,out_path):
    p=Path(out_path)
    if p.exists():raise FileExistsError(p)
    result=compare(old_workspace,new_workspace)
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return result
