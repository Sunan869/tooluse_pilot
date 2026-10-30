"""Run one derived XLSX repair case and grade it on the trusted host.

Usage (PowerShell env): MODEL_BASE_URL MODEL_API_KEY MODEL_ID.
The model sandbox only sees input and instruction, not private oracle.
"""
import argparse,json,os,shutil,sys
from pathlib import Path
from openai import OpenAI
from spreadsheetbench2_responses_runner import run_case_responses
from spreadsheetbench2_derive import validate

def main():
 p=argparse.ArgumentParser()
 p.add_argument("--case",type=Path,default=Path("runs/ssb2-derived-01/repair"))
 p.add_argument("--out",type=Path,required=True)
 p.add_argument("--max-requests",type=int,default=25)
 p.add_argument("--max-tools",type=int,default=60)
 p.add_argument("--sandbox-image",default="tooluse-pilot-sandbox:py311-openpyxl")
 a=p.parse_args()
 for key in ("MODEL_BASE_URL","MODEL_API_KEY","MODEL_ID"):
  if not os.getenv(key):p.error(f"Missing environment variable: {key}")
 source=a.case.resolve()
 oracle=json.loads((source/"private"/"oracle.json").read_text(encoding="utf-8"))
 if oracle["kind"]!="minimal_repair":p.error("This runner currently supports only XLSX repair tasks, not locate JSON")
 dest=a.out.resolve()
 if dest.exists():p.error(f"Destination exists: {dest}")
 dest.mkdir(parents=True)
 for section in ("input","private"):shutil.copytree(source/section,dest/section)
 (dest/"instruction.md").write_bytes((source/"instruction.md").read_bytes())
 (dest/"output").mkdir()
 client=OpenAI(base_url=os.environ["MODEL_BASE_URL"],api_key=os.environ["MODEL_API_KEY"],
               timeout=180,max_retries=0)
 report=run_case_responses(client,os.environ["MODEL_ID"],dest,a.max_requests,a.max_tools,a.sandbox_image)
 outputs=list((dest/"output").glob("*.xlsx"))
 grade=validate(dest,outputs[0]) if len(outputs)==1 else {"pass":False,"reason":"no_single_xlsx_output"}
 result={"model":os.environ["MODEL_ID"],"condition":"derived_minimal_repair",
         "case":source.name,"run_id":report["run_id"],"requests":report["requests"],
         "tool_calls":report["tool_calls"],"state":report["state"],
         "artifact_created":report["artifact_created"],"oracle":grade,
         "warning":"Candidate Oracle, not official SpreadsheetBench grading"}
 (dest/"trusted_result.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
 print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
