"""Responses API XLSX agent. Trusted grading stays outside this tool runner."""
import json
import shutil
from pathlib import Path
from uuid import uuid4

from tooluse_pilot.sandbox import DockerTools
from spreadsheetbench2_local_qwen import TOOLS, checksum

RESPONSE_TOOLS = [
    {"type":"function","name":t["function"]["name"],
     "description":t["function"]["description"],
     "parameters":t["function"]["parameters"],"strict":False}
    for t in TOOLS
]

def run_case_responses(client,model,case_dir,max_requests,max_tools,image,workflow_hint=False,focus_hint=False):
    root=Path(case_dir).resolve()
    inputs=list((root/"input").glob("*.xlsx"))
    if len(inputs)!=1 or not (root/"instruction.md").is_file():
        raise ValueError("Expected one input XLSX and instruction.md")
    output=root/"output"
    if any(output.iterdir()):
        raise FileExistsError(f"Use a fresh workspace: {output}")
    run_id=str(uuid4())
    system=("You are editing an Excel workbook. Inspect the provided input XLSX using Python/shell tools. "
        "Apply the user's requested changes, preserve unrelated content, and save the updated XLSX under "
        "output/ with the SAME filename as the input file. Never claim success unless the file exists. "
        "The workspace has input/ and output/ directories. Files saved under /work or /tmp persist across "
        "tool calls, but Python process variables do not. Inspect only relevant cells and formulas, "
        "avoid dumping entire sheets to stdout. Do not read private files or access the network.")
    if workflow_hint:
        system+=(" Workflow guidance: inspect the workbook systematically, identify concrete suspect cells "
            "or formatting defects, apply justified edits, and save an output XLSX. "
            "Avoid endlessly inspecting the same area. Do not invent errors or change unrelated cells.")
    instruction=(root/"instruction.md").read_text(encoding="utf-8")
    if focus_hint:
        instruction += (chr(10)*2 + "Diagnostic focus (additional information, not the answer): "
            "Prioritize auditing the cumulative calculations in the 'Ex 5 - M&A' worksheet. "
            "Determine independently whether any amounts are double counted; if justified, "
            "repair the formulas and save the workbook. Do not invent fixes.")
    history=[{"role":"user","content":instruction}]
    report={"run_id":run_id,"model":model,"api_type":"responses",
            "condition":"focus_hint" if focus_hint else ("workflow_hint" if workflow_hint else "baseline"),
            "workspace":str(root),"input_sha256":checksum(inputs[0]),
            "requests":0,"tool_calls":0,"state":"max_requests","events":[],
            "output_files":[],"first_output_turn":None,"output_seen_during_run":False}
    docker=DockerTools(root,image=image,timeout=120)
    print(f"[start] {root.name}, input={inputs[0].name}, api=responses",flush=True)
    try:
        for turn in range(1,max_requests+1):
            response=client.responses.create(model=model,instructions=system,
                input=history,tools=RESPONSE_TOOLS,tool_choice="auto",store=False)
            report["requests"]+=1
            items=[item.model_dump(exclude_none=True) for item in response.output]
            calls=[x for x in response.output if x.type=="function_call"]
            history.extend(items)
            report["events"].append({"turn":turn,"assistant":response.output_text[:3000],
                "calls":[c.name for c in calls],
                "usage":response.usage.model_dump(exclude_none=True) if response.usage else None})
            print(f"[turn {turn}/{max_requests}] calls={len(calls)}",flush=True)
            if not calls:
                report["state"]="finished" if response.status=="completed" else str(response.status)
                break
            for call in calls:
                if report["tool_calls"]>=max_tools:
                    report["state"]="max_tools"
                    break
                report["tool_calls"]+=1
                args={"_raw_arguments":str(call.arguments or "")[:2000]}
                exception_type=None
                try:
                    args=json.loads(call.arguments or "{}")
                    if call.name=="execute_python" and set(args)=={"code"}:
                        result=docker.execute_python(args["code"])
                    elif call.name=="execute_shell" and set(args)=={"command"}:
                        result=docker.execute_shell(args["command"])
                    else:
                        result={"exit_code":1,"stdout":"","stderr":"Invalid tool call"}
                except Exception as exc:
                    exception_type=type(exc).__name__
                    result={"exit_code":1,"stdout":"","stderr":str(exc)[:500]}
                feedback={"exit_code":result.get("exit_code",1),
                    "stdout":str(result.get("stdout",""))[:1500],
                    "stderr":str(result.get("stderr",""))[:700]}
                report["events"].append({"turn":turn,"tool":call.name,"arguments":args,
                    "exit_code":feedback["exit_code"],"exception_type":exception_type,
                    "stdout":str(result.get("stdout",""))[:2500],
                    "stderr":str(result.get("stderr",""))[:1000]})
                history.append({"type":"function_call_output","call_id":call.call_id,
                    "output":json.dumps(feedback,ensure_ascii=False)})
                print(f"  {call.name} exit={feedback['exit_code']}",flush=True)
            if list((docker.root/"output").glob("*.xlsx")):
                report["output_seen_during_run"]=True
                if report["first_output_turn"] is None:
                    report["first_output_turn"]=turn
            if report["state"]=="max_tools":
                break
        for candidate in (docker.root/"output").iterdir():
            if (candidate.is_symlink() or not candidate.is_file()
                or candidate.suffix.lower()!=".xlsx" or candidate.stat().st_size>100*1024*1024):
                continue
            target=output/candidate.name
            shutil.copy2(candidate,target)
            report["output_files"].append({"path":str(target),
                "sha256":checksum(target),"bytes":target.stat().st_size})
        report["artifact_created"]=bool(report["output_files"])
        report["input_unchanged"]=checksum(inputs[0])==report["input_sha256"]
        return report
    finally:
        docker.close()
        folder=root/"runs"
        folder.mkdir(exist_ok=True)
        (folder/f"{run_id}.json").write_text(
            json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
