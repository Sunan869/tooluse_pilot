"""Run staged SpreadsheetBench XLSX tasks with a local OpenAI-compatible model.

No grading or golden data are provided to the model. Docker is mandatory.
"""
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone

from openai import OpenAI
from tooluse_pilot.sandbox import DockerTools

TOOLS = [
    {"type": "function", "function": {"name": "execute_python",
      "description": "Execute Python inside the isolated workspace. openpyxl is installed. Read workbook from input/; save edited XLSX to output/.",
      "parameters": {"type": "object", "properties": {"code": {"type": "string"}},
                     "required": ["code"], "additionalProperties": False}}},
    {"type": "function", "function": {"name": "execute_shell",
      "description": "Execute shell inside the isolated workspace; no network access.",
      "parameters": {"type": "object", "properties": {"command": {"type": "string"}},
                     "required": ["command"], "additionalProperties": False}}}
]

def make_client(base_url):
    return OpenAI(base_url=base_url, api_key=os.getenv("MODEL_API_KEY") or os.getenv("LOCAL_MODEL_API_KEY", "not-needed"),
                  timeout=180, max_retries=0)

def probe(client, model):
    resp = client.chat.completions.create(
        model=model, temperature=None, stream=False,
        messages=[{"role":"user", "content":"调用 execute_python 工具计算 2+3，不要直接给出答案。"}],
        tools=[TOOLS[0]], tool_choice="auto",
        **({"extra_body":{"chat_template_kwargs":{"enable_thinking":False}}} if model.lower().startswith("qwen") else {})
    calls = getattr(resp.choices[0].message, "tool_calls", None) or []
    return {"model":model, "tool_calls_supported":bool(calls),
            "tool_names":[call.function.name for call in calls],
            "response":(resp.choices[0].message.content or "")[:300]}

def checksum(path):
    h=hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda:file.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()

def run_case(client, model, case_dir, max_requests, max_tools, image, workflow_hint=False):
    case_dir=Path(case_dir).resolve()
    inputs=list((case_dir/"input").glob("*.xlsx"))
    if len(inputs)!=1 or not (case_dir/"instruction.md").is_file():
        raise ValueError(f"Expected exactly one input workbook and an instruction: {case_dir}")
    out=case_dir/"output"
    if any(out.iterdir()):
        raise FileExistsError(f"Output not empty; use a fresh staged workspace: {out}")
    run_id=str(uuid4())
    instructions=(case_dir/"instruction.md").read_text(encoding="utf-8")
    messages=[
        {"role":"system","content":"You are editing an Excel workbook. Inspect the provided input XLSX using Python/shell tools. Apply the user's requested changes, preserve unrelated content, and save the updated XLSX under output/ with the SAME filename as the input file. Never claim success unless the file exists. The workspace has input/ and output/ directories. Files saved under /work or /tmp persist across tool calls, but Python process variables do not. Inspect only relevant cells and formulas, avoid dumping entire sheets to stdout. Do not read private files or access the network."},
        {"role":"user","content":instructions}
    ]
    if workflow_hint:
        messages[0]["content"] += (" Workflow guidance: inspect the workbook systematically, "
            "identify concrete suspect cells or formatting defects, apply justified edits, "
            "and save an output XLSX. Avoid endlessly inspecting the same area. "
            "Do not invent errors or change unrelated cells.")
    record={"condition":"workflow_hint" if workflow_hint else "baseline",
            "run_id":run_id,"model":model,"workspace":str(case_dir),
            "input_sha256":checksum(inputs[0]),"events":[],"state":"max_requests",
            "requests":0,"tool_calls":0,"output_files":[]}
    docker=DockerTools(case_dir,image=image,timeout=120)
    record["first_output_turn"]=None
    record["output_seen_during_run"]=False
    print(f"[start] {case_dir.name}, input={inputs[0].name}", flush=True)
    try:
        for turn in range(max_requests):
            response=client.chat.completions.create(
                model=model,messages=messages,tools=TOOLS,tool_choice="auto",stream=False,
                extra_body={"chat_template_kwargs":{"enable_thinking":False}})
            record["requests"]+=1
            print(f"[turn {turn+1}/{max_requests}] requests={record['requests']}", flush=True)
            message=response.choices[0].message
            calls=message.tool_calls or []
            messages.append(message.model_dump(exclude_none=True))
            record["events"].append({"turn":turn+1,"assistant":(message.content or "")[:3000],
                                     "calls":[x.function.name for x in calls],
                                     "usage":response.usage.model_dump(exclude_none=True) if response.usage else None})
            if not calls:
                record["state"]="finished"
                break
            for call in calls:
                if record["tool_calls"]>=max_tools:
                    record["state"]="max_tools"
                    break
                record["tool_calls"]+=1
                try:
                    args=json.loads(call.function.arguments or "{}")
                    if call.function.name=="execute_python" and set(args)=={"code"}:
                        result=docker.execute_python(args["code"])
                    elif call.function.name=="execute_shell" and set(args)=={"command"}:
                        result=docker.execute_shell(args["command"])
                    else:
                        result={"exit_code":1,"stderr":"Invalid tool call"}
                except Exception as exc:
                    result={"exit_code":1,"stderr":str(exc)[:500]}
                record["events"].append({"turn":turn+1,"tool":call.function.name,
                                         "arguments":args if isinstance(args,dict) else {},
                                         "exit_code":result.get("exit_code"),
                                         "stdout":str(result.get("stdout",""))[:2500],
                                         "stderr":str(result.get("stderr",""))[:1000]})
                # Bound tool feedback in the model context but retain evidence in trace.
                feedback={"exit_code":result.get("exit_code",1),
                          "stdout":str(result.get("stdout",""))[:1500],
                          "stderr":str(result.get("stderr",""))[:700]}
                print(f"  {call.function.name} exit={feedback['exit_code']}", flush=True)
                messages.append({"role":"tool","tool_call_id":call.id,
                                 "content":json.dumps(feedback,ensure_ascii=False)})
            # Detect a real submitted workbook without treating it as correct.
            submitted=list((docker.root/"output").glob("*.xlsx"))
            if submitted:
                record["output_seen_during_run"]=True
                if record["first_output_turn"] is None:
                    record["first_output_turn"]=turn+1
            if record["state"]=="max_tools":
                break
        # Save only regular XLSX files in the isolated output folder.
        source_output=docker.root/"output"
        for candidate in source_output.iterdir():
            if candidate.is_symlink() or not candidate.is_file() or candidate.suffix.lower()!=".xlsx":
                continue
            if candidate.stat().st_size>100*1024*1024:
                continue
            dest=out/candidate.name
            shutil.copy2(candidate,dest)
            record["output_files"].append({"path":str(dest),"sha256":checksum(dest),
                                           "bytes":dest.stat().st_size})
        record["artifact_created"]=bool(record["output_files"])
        record["input_unchanged"]=checksum(inputs[0])==record["input_sha256"]
        return record
    finally:
        docker.close()
        folder=case_dir/"runs"
        folder.mkdir(exist_ok=True)
        (folder/f"{run_id}.json").write_text(json.dumps(record,ensure_ascii=False,indent=2),
                                            encoding="utf-8")

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=["probe","run"])
    parser.add_argument("--base-url",default=os.getenv("MODEL_BASE_URL","http://10.10.23.7:5610/v1"))
    parser.add_argument("--model",default=os.getenv("MODEL_ID","Qwen3.8-Flash-Next-AWQ-INT4"))
    parser.add_argument("--batch",type=Path,default=Path("runs/ssb2-debugging-baseline"))
    parser.add_argument("--case",type=Path)
    parser.add_argument("--max-requests",type=int,default=25)
    parser.add_argument("--max-tools",type=int,default=80)
    parser.add_argument("--workflow-hint",action="store_true",help="Separate assisted condition; not baseline")
    parser.add_argument("--sandbox-image",default="tooluse-pilot-sandbox:py311-openpyxl")
    args=parser.parse_args()
    client=make_client(args.base_url)
    if args.action=="probe":
        result=probe(client,args.model)
    else:
        if not args.case:
            parser.error("run requires --case")
        target=args.case.resolve()
        if not target.is_dir() or not target.is_relative_to(args.batch.resolve()):
            parser.error("case must be a directory under --batch")
        result=run_case(client,args.model,target,args.max_requests,args.max_tools,args.sandbox_image,args.workflow_hint)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
