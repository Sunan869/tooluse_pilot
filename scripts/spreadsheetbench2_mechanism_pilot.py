"""Mechanism-balanced pilot selection and opt-in batch execution for new XLSX faults.

PLAN and REPORT are offline and make zero model calls.
RUN requires explicit --execute and a prepared manifest, calls the configured
model API, and never mounts private/ or reference answers in Docker.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Prioritize this checkout over stale editable installs on PYTHONPATH.
PROJECT_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT_ROOT))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from spreadsheetbench2_discovery_factory import load_case, score
from spreadsheetbench2_fault_factory import sha

DEFAULT_DATASET = Path("runs/ssb2-discovered-v2")



def infrastructure_error(error):
    """Classify transport/server failures separately from benchmark failures."""
    status=getattr(error,"status_code",None)
    text=str(error)
    if status is None:
        match=re.search(r"(?:Error code:|status(?: code)?[: =])\s*(\d{3})",text,re.I)
        status=int(match.group(1)) if match else None
    if status in (429,500,502,503,504):
        return f"upstream_http_{status}"
    if status in (401,403,404):
        return f"api_configuration_http_{status}"
    if error.__class__.__name__ in ("APIConnectionError","APITimeoutError","ConnectError","TimeoutException"):
        return "model_transport_error"
    return None


def model_preflight(client,model,api_type):
    """One small model/tool-call smoke request. No workbook or private answers."""
    if api_type=="chat_completions":
        from spreadsheetbench2_local_qwen import TOOLS
        response=client.chat.completions.create(
            model=model,stream=False,
            messages=[{"role":"user","content":"Call execute_python to calculate 2+3. Do not solve directly."}],
            tools=[TOOLS[0]],tool_choice="auto",
            **({"extra_body":{"chat_template_kwargs":{"enable_thinking":False}}}
               if model.lower().startswith("qwen") else {}))
        calls=response.choices[0].message.tool_calls or []
        supported=any(c.function.name=="execute_python" for c in calls)
    else:
        from spreadsheetbench2_responses_runner import RESPONSE_TOOLS
        response=client.responses.create(
            model=model,instructions="Use the provided function to calculate 2+3.",
            input=[{"role":"user","content":"Call execute_python to calculate 2+3."}],
            tools=[RESPONSE_TOOLS[0]],tool_choice="auto",store=False)
        supported=any(x.type=="function_call" and x.name=="execute_python" for x in response.output)
    if not supported:
        raise RuntimeError("preflight_no_tool_call: model endpoint responded but did not call execute_python")
    return {"model_reachable":True,"tool_calls_supported":True,"api_type":api_type}

def read_cases(dataset):
    data=json.loads((dataset/"private"/"oracle.json").read_text(encoding="utf-8"))
    manifest=json.loads((dataset/"manifest.json").read_text(encoding="utf-8"))
    if len(data)!=manifest["generated"]:
        raise ValueError("Case count doesn't match dataset manifest")
    ids=[x["id"] for x in data]
    if len(ids)!=len(set(ids)):
        raise ValueError("Duplicate task IDs")
    return data


def make_plan(dataset, out, singles=6, compounds=2):
    dataset=Path(dataset).resolve()
    out=Path(out).resolve()
    if out.exists():
        raise FileExistsError(f"Plan exists: {out}")
    if singles<0 or compounds<0 or singles+compounds==0:
        raise ValueError("Need nonnegative counts and at least one selected case")
    tasks=read_cases(dataset)
    single=[c for c in tasks if len(c["faults"])==1]
    compound=[c for c in tasks if len(c["faults"])>1]
    groups=defaultdict(list)
    for case in single:
        groups[case["faults"][0]["mechanism"]].append(case)
    selected=[]
    seen_mechs=set()
    # Deterministic broad coverage across four business worksheets, no answer leakage.
    for sheet in ("Ex 1 - LBO", "Ex 3 - PF P&L", "Ex 4 - Organic Operating Model", "Ex 5 - M&A"):
        candidates=sorted((c for c in single if c["faults"][0]["sheet"]==sheet
                           and c["faults"][0]["mechanism"] not in seen_mechs),
                          key=lambda c:(len(groups[c["faults"][0]["mechanism"]]),
                                        c["faults"][0]["mechanism"],c["id"]))
        if candidates and len(selected)<singles:
            choice=candidates[0]
            selected.append(choice)
            seen_mechs.add(choice["faults"][0]["mechanism"])
    for mechanism in sorted(groups):
        if len(selected)>=singles:break
        if mechanism not in seen_mechs:
            selected.append(sorted(groups[mechanism],key=lambda c:c["id"])[0])
            seen_mechs.add(mechanism)
    if len(selected)<singles:
        raise ValueError("Insufficient single-fault cases")
    # Prefer compound samples that cover as-yet-unsampled mechanisms while
    # spanning separate sheets, rather than randomly choosing hardest-looking IDs.
    selected_compound=[]
    remaining=compound[:]
    covered=set(seen_mechs)
    while len(selected_compound)<compounds and remaining:
        remaining.sort(key=lambda c:(-len({f["mechanism"] for f in c["faults"]}-covered),
                                     -len(c["faults"]),c["id"]))
        choice=remaining.pop(0)
        if len({f["sheet"] for f in choice["faults"]})<2:
            raise ValueError("Compound case does not span sheets")
        selected_compound.append(choice)
        covered.update(f["mechanism"] for f in choice["faults"])
    if len(selected_compound)!=compounds:
        raise ValueError("Insufficient compound cases")
    chosen=selected+selected_compound
    rows=[]
    for c in chosen:
        src=dataset/c["input_path"]
        if sha(src)!=c["input_sha256"]:
            raise ValueError(f"Source hash mismatch: {c['id']}")
        rows.append({"id":c["id"],"input_sha256":c["input_sha256"],
                     "fault_count":len(c["faults"]),
                     "mechanism_group":[f["mechanism"] for f in c["faults"]],
                     "parent_group":"SSB2_01_01_parent"})
    out.parent.mkdir(parents=True,exist_ok=True)
    result={"dataset":str(dataset),"selection_method":"deterministic_mechanism_balanced_v1",
            "case_count":len(rows),"cases":rows,
            "statistical_note":"Cases share same parent workbook and are not independent samples",
            "run_confirmation_required":True}
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    return {"selected":len(rows),"singles":len(selected),"compounds":len(selected_compound),
            "mechanisms_covered":len(covered),"plan":str(out),
            "cases":[r["id"] for r in rows],"calls_model_api":False}


def _create_agent_workspace(dataset,case,destination):
    src=dataset/case["input_path"]
    if sha(src)!=case["input_sha256"]:
        raise ValueError("Workbook changed after creating selection plan")
    destination.mkdir(parents=True,exist_ok=False)
    (destination/"input").mkdir()
    (destination/"output").mkdir()
    shutil.copy2(src,destination/"input"/src.name)
    prompt=dataset/"cases"/case["id"]/"instruction.md"
    (destination/"instruction.md").write_bytes(prompt.read_bytes())
    if (destination/"private").exists():
        raise AssertionError("Private oracle leaked into model workspace")


def _summary_item(case, result, error=None):
    if error is not None:
        return {"case_id":case["id"],"state":"runner_error","error":str(error)[:400],
                "infrastructure_error":infrastructure_error(error),
                "pass":None,"artifact_created":False}
    oracle=result.get("oracle",{})
    return {"case_id":case["id"],"state":result.get("state"),
            "requests":result.get("requests"),"tool_calls":result.get("tool_calls"),
            "artifact_created":result.get("artifact_created"),
            "pass":oracle.get("pass",False),
            "wrong_fixes_count":len(oracle.get("wrong_fixes",[])),
            "extra_count":oracle.get("extra_count"),
            "integrity_issues":oracle.get("integrity_issues",[])}


def run_plan(plan_file, out, *, api_type, max_requests, max_tools,
             sandbox_image, max_cases, execute):
    if not execute:
        raise ValueError("Explicit --execute required to call model API")
    plan=json.loads(Path(plan_file).read_text(encoding="utf-8"))
    dataset=Path(plan["dataset"]).resolve()
    tasks={c["id"]:c for c in read_cases(dataset)}
    cases=plan["cases"][:max_cases]
    if not cases:
        raise ValueError("No selected cases")
    for name in ("MODEL_BASE_URL","MODEL_ID"):
        if not os.getenv(name):
            raise ValueError(f"Missing {name}")
    destination=Path(out).resolve()
    if destination.exists():
        raise FileExistsError(destination)
    from openai import OpenAI
    from spreadsheetbench2_local_qwen import run_case
    from spreadsheetbench2_responses_runner import run_case_responses
    client=OpenAI(base_url=os.environ["MODEL_BASE_URL"],
                  api_key=os.getenv("MODEL_API_KEY") or os.getenv("LOCAL_MODEL_API_KEY","not-needed"),
                  max_retries=0,timeout=180)
    runner=run_case_responses if api_type=="responses" else run_case
    try:
        from spreadsheetbench2_host_io_probe import sandbox_io_preflight
        io_check=sandbox_io_preflight(sandbox_image)
        if not io_check["pass"]:
            return {"status":"preflight_failed","infrastructure_error":"sandbox_io_failure",
                    "error":"DockerTools UTF-8/malformed-byte IO preflight failed",
                    "checks":io_check["checks"],"cases":0,"model_evaluations":0,
                    "note":"No model API request or benchmark task attempted"}
    except Exception as error:
        return {"status":"preflight_failed","infrastructure_error":"sandbox_io_failure",
                "error":str(error)[:400],"cases":0,"model_evaluations":0,
                "note":"No model API request or benchmark task attempted"}
    try:
        check=model_preflight(client,os.environ["MODEL_ID"],api_type)
    except Exception as error:
        return {"status":"preflight_failed","infrastructure_error":infrastructure_error(error),
                "error":str(error)[:400],"cases":0,"model_evaluations":0,
                "note":"No benchmark task attempted; check the model endpoint, proxy and upstream service"}
    print("SANDBOX IO PREFLIGHT OK; MODEL PREFLIGHT OK: tool calling supported",flush=True)
    destination.mkdir(parents=True)
    records=[]
    for index, row in enumerate(cases,1):
        task=tasks[row["id"]]
        if task["input_sha256"]!=row["input_sha256"]:
            raise ValueError("Case does not match planned source hash")
        workspace=destination/task["id"]
        _create_agent_workspace(dataset,task,workspace)
        print(f"CASE {index}/{len(cases)} {task['id']} API={api_type}",flush=True)
        try:
            run=runner(client,os.environ["MODEL_ID"],workspace,max_requests,max_tools,sandbox_image)
            produced=list((workspace/"output").glob("*.xlsx"))
            if len(produced)==1 and produced[0].name=="Double Counting_mutated.xlsx":
                result=score(dataset,task,produced[0])
            else:
                result={"pass":False,"reason":"no_valid_xlsx_output"}
            item={"case_id":task["id"],"model":os.environ["MODEL_ID"],
                  "api_type":api_type,"state":run.get("state"),"requests":run.get("requests"),
                  "tool_calls":run.get("tool_calls"),
                  "artifact_created":run.get("artifact_created"),
                  "oracle":result,"warning":"Candidate exact-repair Oracle, not official financial correctness"}
            (workspace/"trusted_result.json").write_text(
                json.dumps(item,ensure_ascii=False,indent=2),encoding="utf-8")
            records.append(_summary_item(task,item))
        except Exception as error:
            failed=_summary_item(task,{},error)
            records.append(failed)
            if failed["infrastructure_error"]:
                (destination/"summary.json").write_text(
                    json.dumps(records,ensure_ascii=False,indent=2),encoding="utf-8")
                print(f"STOP: infrastructure error {failed['infrastructure_error']}; remaining cases not attempted",flush=True)
                break
        (destination/"summary.json").write_text(
            json.dumps(records,ensure_ascii=False,indent=2),encoding="utf-8")
    return aggregate(records)


def aggregate(records):
    states=Counter(c.get("state") for c in records)
    infra=sum(bool(c.get("infrastructure_error")) for c in records)
    return {"cases":len(records),"valid_model_evaluations":len(records)-infra,
            "infrastructure_errors":infra,
            "delivered_xlsx":sum(bool(c.get("artifact_created")) for c in records),
            "strict_passes":sum(bool(c.get("pass")) for c in records),
            "states":dict(states),"results":records,
            "note":"Descriptive pilot metrics, not independent model benchmark accuracy"}


def report(run_directory):
    file=Path(run_directory)/"summary.json"
    records=json.loads(file.read_text(encoding="utf-8"))
    return aggregate(records)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=["plan","run","report"])
    p.add_argument("--dataset",type=Path,default=DEFAULT_DATASET)
    p.add_argument("--plan",type=Path,default=Path("runs/ssb2-pilot-plan-01.json"))
    p.add_argument("--out",type=Path)
    p.add_argument("--singles",type=int,default=6)
    p.add_argument("--compounds",type=int,default=2)
    p.add_argument("--max-cases",type=int,default=2,
                   help="Safety limit for actual API run; default only two cases")
    p.add_argument("--api-type",choices=["chat_completions","responses"],default="chat_completions")
    p.add_argument("--max-requests",type=int,default=25)
    p.add_argument("--max-tools",type=int,default=60)
    p.add_argument("--sandbox-image",default="tooluse-pilot-sandbox:py311-openpyxl")
    p.add_argument("--execute",action="store_true",
                   help="Required explicit opt-in to call model API")
    args=p.parse_args()
    if args.action=="plan":
        result=make_plan(args.dataset,args.plan,args.singles,args.compounds)
    elif args.action=="run":
        if not args.out:p.error("run requires --out")
        if args.max_cases<1:p.error("max-cases must be at least 1")
        result=run_plan(args.plan,args.out,api_type=args.api_type,
                        max_requests=args.max_requests,max_tools=args.max_tools,
                        sandbox_image=args.sandbox_image,max_cases=args.max_cases,
                        execute=args.execute)
    else:
        if not args.out:p.error("report requires --out")
        result=report(args.out)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
