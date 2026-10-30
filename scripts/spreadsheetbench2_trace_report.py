"""Analyze existing five-task Qwen traces without model calls or golden access."""
import argparse
import json
from collections import Counter
from pathlib import Path

READ_HINTS=("load_workbook","iter_rows","sheetnames","print(","unzip","head ","sed ","ls ","grep ","cat ")
WRITE_HINTS=(".save(","save_workbook(","to_excel(","shutil.copy","copyfile(","write_bytes(")

def analyze(path):
    data=json.loads(path.read_text(encoding="utf-8"))
    events=data.get("events",[])
    actions=[e for e in events if "tool" in e]
    first_write=None
    actions_by_name=Counter()
    errors=[]
    possible_edits=[]
    for e in actions:
        actions_by_name[e["tool"]]+=1
        arg=e.get("arguments") or {}
        command=str(arg.get("code",arg.get("command","")))
        if any(token in command for token in WRITE_HINTS):
            possible_edits.append({"turn":e.get("turn"),"tool":e["tool"],
                                   "exit_code":e.get("exit_code"),"snippet":command[:160]})
            if e.get("exit_code")==0 and first_write is None:
                first_write=e.get("turn")
        if e.get("exit_code",0)!=0:
            errors.append({"turn":e.get("turn"),"tool":e.get("tool"),
                           "exit_code":e.get("exit_code"),"error":e.get("stderr","")[:200]})
    usage=[e.get("usage") or {} for e in events if "usage" in e]
    return {"file":str(path),"case":path.parent.parent.name,
            "run_id":data.get("run_id"),"state":data.get("state"),
            "requests":data.get("requests"),"tool_calls":data.get("tool_calls"),
            "tools":dict(actions_by_name),
            "artifact_created":data.get("artifact_created",False),
            "first_successful_write_like_turn":first_write,
            "write_like_actions":possible_edits[:20],
            "errors":errors,
            "last_prompt_tokens":usage[-1].get("prompt_tokens") if usage else None,
            "total_completion_tokens":sum(u.get("completion_tokens") or 0 for u in usage),
            "note":"Write detection uses string heuristics, not proof of edits. Not an official score."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("batch",type=Path)
    p.add_argument("--out",type=Path)
    a=p.parse_args()
    if not a.batch.exists(): p.error("Batch directory does not exist")
    results=[]
    for case in sorted(a.batch.iterdir()):
        if not case.is_dir() or not (case/"runs").is_dir(): continue
        traces=sorted((case/"runs").glob("*.json"),key=lambda x:x.stat().st_mtime)
        if traces: results.append(analyze(traces[-1]))
    summary={"cases":len(results),"completed":sum(x["state"]=="finished" for x in results),
             "artifacts":sum(x["artifact_created"] for x in results),
             "max_requests":sum(x["state"]=="max_requests" for x in results),
             "results":results}
    if a.out:
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
