"""Run a single injected XLSX case with a private, host-side Oracle.

Model workspace contains ONLY instruction.md, input/ and output/. This is an
opt-in network API operation; generation/selftest are completely offline.
"""
import argparse
import json
import os
import shutil
from pathlib import Path

from openai import OpenAI
from spreadsheetbench2_fault_factory import evaluate,load_task,sha
from spreadsheetbench2_local_qwen import run_case as run_chat
from spreadsheetbench2_responses_runner import run_case_responses as run_responses

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--dataset",type=Path,default=Path("runs/ssb2-injected-01"))
    parser.add_argument("--id",required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--api-type",choices=["responses","chat_completions"],default="responses")
    parser.add_argument("--max-requests",type=int,default=25)
    parser.add_argument("--max-tools",type=int,default=60)
    parser.add_argument("--sandbox-image",default="tooluse-pilot-sandbox:py311-openpyxl")
    args=parser.parse_args()
    missing=[name for name in ("MODEL_BASE_URL","MODEL_ID") if not os.getenv(name)]
    if missing:parser.error("Missing environment variables: "+", ".join(missing))
    dataset=args.dataset.resolve()
    task=load_task(dataset,args.id)
    dest=args.out.resolve()
    if dest.exists():parser.error(f"Output already exists: {dest}")
    src=dataset/task["input_path"]
    if sha(src)!=task["input_sha256"]:
        raise ValueError("Injected workbook hash mismatch; refusing to test")
    dest.mkdir(parents=True)
    (dest/"input").mkdir()
    (dest/"output").mkdir()
    shutil.copy2(src,dest/"input"/src.name)
    instruction=dataset/"cases"/args.id/"instruction.md"
    (dest/"instruction.md").write_bytes(instruction.read_bytes())
    client=OpenAI(base_url=os.environ["MODEL_BASE_URL"],
                  api_key=os.getenv("MODEL_API_KEY") or os.getenv("LOCAL_MODEL_API_KEY","not-needed"),
                  timeout=180,max_retries=0)
    runner=run_responses if args.api_type=="responses" else run_chat
    report=runner(client,os.environ["MODEL_ID"],dest,args.max_requests,
                  args.max_tools,args.sandbox_image)
    artifacts=sorted((dest/"output").glob("*.xlsx"))
    if len(artifacts)==1 and artifacts[0].name==src.name:
        grade=evaluate(dataset,task,artifacts[0])
    else:
        grade={"pass":False,"reason":"expected_exactly_one_output_xlsx_with_original_filename",
               "output_files":[p.name for p in artifacts]}
    result={"case_id":args.id,"api_type":args.api_type,"model":os.environ["MODEL_ID"],
            "condition":"blind_mutated_workbook","run_id":report.get("run_id"),
            "state":report.get("state"),"requests":report.get("requests"),
            "tool_calls":report.get("tool_calls"),"artifact_created":report.get("artifact_created"),
            "oracle":grade,"warning":"Candidate Oracle, no calculation engine or full OOXML integrity check"}
    (dest/"trusted_result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
