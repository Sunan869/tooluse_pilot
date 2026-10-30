"""Run the five existing staged SpreadsheetBench Debugging tasks against local Qwen.

Each run uses a new workspace. Never expose private/ to the model. The result is
an artifact/behavior baseline, NOT an official SpreadsheetBench score.
"""
import argparse
import json
import shutil
from pathlib import Path
from spreadsheetbench2_local_qwen import make_client, run_case

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,default=Path("runs/ssb2-debugging-baseline"))
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--limit",type=int,default=5)
    p.add_argument("--max-requests",type=int,default=25)
    p.add_argument("--max-tools",type=int,default=60)
    p.add_argument("--base-url",default="http://10.10.23.7:5610/v1")
    p.add_argument("--model",default="Qwen3.8-Flash-Next-AWQ-INT4")
    p.add_argument("--sandbox-image",default="tooluse-pilot-sandbox:py311-openpyxl")
    a=p.parse_args()
    if not 1 <= a.limit <= 5: p.error("--limit must be 1..5")
    source=a.source.resolve()
    cases=sorted(x for x in source.iterdir() if x.is_dir() and x.name.startswith(tuple(f"{i:02d}_" for i in range(1,6))))[:a.limit]
    if len(cases)!=a.limit: p.error(f"Expected {a.limit} staged cases; found {len(cases)}")
    out=a.out.resolve()
    if out.exists(): p.error(f"Output already exists: {out}")
    out.mkdir(parents=True)
    client=make_client(a.base_url)
    results=[]
    try:
        for i,case in enumerate(cases,1):
            target=out/case.name
            target.mkdir()
            for section in ("input","private"):
                shutil.copytree(case/section,target/section)
            (target/"instruction.md").write_bytes((case/"instruction.md").read_bytes())
            (target/"output").mkdir()
            print(f"CASE {i}/{len(cases)}: {case.name}",flush=True)
            try:
                report=run_case(client,a.model,target,a.max_requests,a.max_tools,a.sandbox_image)
                result={k:report.get(k) for k in ("run_id","state","requests","tool_calls","artifact_created","output_files")}
                result["case"]=case.name
            except Exception as exc:
                result={"case":case.name,"state":"runner_error","error":str(exc)[:500]}
            results.append(result)
            (out/"summary.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
    finally:
        (out/"summary.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(results,ensure_ascii=False,indent=2))

if __name__=="__main__":main()
