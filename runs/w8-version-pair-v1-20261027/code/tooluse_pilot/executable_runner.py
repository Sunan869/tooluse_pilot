"""Model-facing runner for executable research environments.

Uses the shared gateway's protocol/retry helpers and the existing immutable
per-attempt SQLite usage ledger. The tool environment is never allowed access
to any private oracle beyond the candidate's exposed environment metadata.
"""
import json
import os
import random
import time
import shutil
from pathlib import Path
from uuid import uuid4
from .executable import Environment, tool_specs
from .state_profiles import StateProfile
from .compound import CompoundEnvironment, specs as compound_specs
from .enterprise import Environment as EnterpriseEnvironment, specs as enterprise_specs
from .enterprise_v2 import Environment as EnterpriseV2Environment, specs as enterprise_v2_specs
from .evidence_conflict import Environment as EvidenceEnvironment, specs as evidence_specs
from .evidence_decision import Environment as DecisionEnvironment, specs as decision_specs
from .real_file_task import Environment as FileEnvironment, specs as file_specs
from .real_file_dynamic import Environment as DynamicEnvironment, specs as dynamic_specs
from .real_multisheet import Environment as MultiSheetEnvironment, specs as multisheet_specs
from .real_w6_reconciliation import Environment as W6Environment, specs as w6_specs
from .allocation_task import Environment as AllocationEnvironment, specs as allocation_specs
from .w8_task import Environment as W8Environment, specs as w8_specs
from .w7_task import Environment as W7Environment, specs as w7_specs
from .reservation_task import Environment as ReservationEnvironment, specs as reservation_specs
from .gateway import _config, _is_retryable, _usage_dict, get_responses_calls, to_responses_tools
from .ledger import record, usage_fields, calculate_cost


def run_candidate(path, config_path, model_alias, db_path="runs/usage.sqlite",
                  max_requests=12, max_tools=30, client_factory=None):
    case=json.loads(Path(path).read_text(encoding="utf-8"))
    file_workspace=None
    if case["family"] in ("real_w8","real_w7","real_reservation","real_allocation","real_file_procurement","real_file_dynamic","real_multisheet_audit","real_w6_reconciliation"):
        file_workspace=Path("runs/file_workspaces")/str(uuid4())
        file_workspace.parent.mkdir(parents=True,exist_ok=True)
        shutil.copytree(Path(path).parent,file_workspace)
    workbook=None
    if case["family"]=="workbook_layout":
        workbook=Path(path).parent/"input"/"sales.xlsx"
        if not workbook.is_file():raise FileNotFoundError(workbook)
    profile=case.get("profile")
    if profile is not None and case["family"] != "state_change":
        raise ValueError("Profiles supported only for state_change")
    env=(W8Environment(case,file_workspace) if case["family"]=="real_w8" else
         W7Environment(case,file_workspace) if case["family"]=="real_w7" else
         ReservationEnvironment(case,file_workspace) if case["family"]=="real_reservation" else
         AllocationEnvironment(case,file_workspace) if case["family"]=="real_allocation" else
         W6Environment(case,file_workspace) if case["family"]=="real_w6_reconciliation" else
         MultiSheetEnvironment(case,file_workspace) if case["family"]=="real_multisheet_audit" else
         DynamicEnvironment(case,file_workspace) if case["family"]=="real_file_dynamic" else
         FileEnvironment(case,file_workspace) if case["family"]=="real_file_procurement" else
         DecisionEnvironment(case) if case["family"]=="evidence_decision" else
         EvidenceEnvironment(case) if case["family"]=="evidence_conflict" else
         EnterpriseV2Environment(case) if case["family"]=="enterprise_settlement_v2" else
         EnterpriseEnvironment(case) if case["family"]=="enterprise_settlement" else
         CompoundEnvironment(case) if case["family"]=="compound_settlement"
         else StateProfile(case,profile) if profile else Environment(case,workbook_path=workbook))
    cfg=_config(config_path)
    modelcfg=cfg["models"][model_alias]
    api_type=modelcfg.get("api_type","chat_completions")
    if api_type not in ("responses","chat_completions"):
        raise ValueError("Unsupported model protocol")
    if client_factory is None:
        from openai import OpenAI
        client=OpenAI(api_key=modelcfg.get("api_key") or os.environ[cfg.get("api_key_env","MODEL_API_KEY")],
                      base_url=os.environ[modelcfg.get("base_url_env",cfg.get("base_url_env","MODEL_BASE_URL"))],
                      timeout=cfg.get("timeout_sec",180),max_retries=0)
    else:
        client=client_factory()
    run_id=str(uuid4())
    definitions=(w8_specs() if case["family"]=="real_w8" else
                 w7_specs() if case["family"]=="real_w7" else
                 reservation_specs() if case["family"]=="real_reservation" else
                 allocation_specs() if case["family"]=="real_allocation" else
                 w6_specs() if case["family"]=="real_w6_reconciliation" else
                 multisheet_specs() if case["family"]=="real_multisheet_audit" else
                 dynamic_specs() if case["family"]=="real_file_dynamic" else
                 file_specs() if case["family"]=="real_file_procurement" else
                 decision_specs() if case["family"]=="evidence_decision" else
                 evidence_specs() if case["family"]=="evidence_conflict" else
                 enterprise_v2_specs() if case["family"]=="enterprise_settlement_v2" else
                 enterprise_specs() if case["family"]=="enterprise_settlement" else
                 compound_specs() if case["family"]=="compound_settlement" else tool_specs(case["family"]))
    if profile:
        definitions=[*definitions,{
            "type":"function","function":{
                "name":"read_replica","description":"Read a potentially delayed replica snapshot",
                "parameters":{"type":"object","properties":{},"required":[],"additionalProperties":False}
            }}]

    system="Complete the business task with the available tools. Never claim success if tools rejected the action."
    if profile:
        system += " Data may change concurrently. Use versioned evidence and handle conflicts safely."
    history=[{"role":"user","content":case["task"]}] if api_type=="responses" else [
        {"role":"system","content":system},{"role":"user","content":case["task"]}]
    if api_type=="responses": definitions=to_responses_tools(definitions)
    retry_limit=max(0,min(int(modelcfg.get("retry_limit",cfg.get("retry_limit",2))),3))
    events=[]; attempts=0; calls=0; state="max_requests"
    cost_total=0.0; cost_complete=True
    prices=modelcfg.get("pricing")
    for turn in range(1,max_requests+1):
        if attempts>=max_requests:break
        response=None; msg=None; output=[]; function_calls=[]
        failure=None
        for retry_index in range(retry_limit+1):
            start=time.monotonic()
            rid=None; usage=None; error=None; caught=None
            try:
                if api_type=="responses":
                    response=client.responses.create(
                        model=modelcfg["model"],instructions=system,input=history,
                        tools=definitions,tool_choice="auto",
                        **modelcfg.get("request_options",{}))
                    output=[item.model_dump(exclude_none=True) for item in (response.output or [])]
                    function_calls=get_responses_calls(response)
                else:
                    response=client.chat.completions.create(
                        model=modelcfg["model"],messages=history,tools=definitions,
                        tool_choice="auto",stream=False,**modelcfg.get("request_options",{}))
                    if not response.choices:raise ValueError("No model choices returned")
                    msg=response.choices[0].message
                    function_calls=msg.tool_calls or []
                rid=response.id
                usage=_usage_dict(response)
            except Exception as exc:
                caught=exc;error=str(exc)[:1000];function_calls=[]
            u=usage_fields(usage)
            cost=calculate_cost(u,prices)
            if cost is None:cost_complete=False
            else:cost_total+=float(cost)
            attempts+=1
            record(db_path,run_id=run_id,task_id=case["id"],mode="structured",
                   provider=modelcfg.get("provider","gateway"),model=modelcfg["model"],
                   attempt=attempts,status="error" if caught else "ok",error=error,
                   gateway_request_id=rid,duration_ms=int((time.monotonic()-start)*1000),
                   tool_calls=len(function_calls),estimated_cost=cost,
                   currency=(prices or {}).get("currency"),pricing_key=model_alias,
                   raw_usage=usage,**u)
            events.append({"event":"api_attempt","turn":turn,"attempt":attempts,
                           "retry_index":retry_index,"error":error,"usage":u})
            if caught is None:break
            failure=error
            if attempts>=max_requests or retry_index==retry_limit or not _is_retryable(caught):break
            time.sleep(min(10,2**retry_index+random.random()/2))
        if failure and caught is not None:
            state="api_error";break
        failure=None
        if api_type=="responses":history.extend(output)
        else:history.append(msg.model_dump(exclude_none=True))
        if not function_calls:
            state="model_stopped" if getattr(env,"terminal_stops_runner",False) else "finished";break
        for call in function_calls:
            if calls>=max_tools:
                state="max_tools";break
            calls+=1
            try:
                args=json.loads(call.function.arguments)
                answer=env.call(call.function.name,args)
                payload=json.dumps({"ok":True,"result":answer})
            except Exception as exc:
                env.invalid_actions=getattr(env,"invalid_actions",0)+1
                payload=json.dumps({"ok":False,"error":str(exc)[:300]})
            if api_type=="responses":
                history.append({"type":"function_call_output","call_id":call.id,"output":payload})
            else:
                history.append({"role":"tool","tool_call_id":call.id,"content":payload})
            events.append({"event":"tool_call","tool":call.function.name,"tool_call_id":call.id,
                           "arguments":getattr(call.function,"arguments",None),
                           "result":json.loads(payload)})
            if getattr(env,"terminal_stops_runner",False) and getattr(env,"finished",False):
                state="task_completed";break
        if state in ("max_tools","task_completed"):break
    result={"run_id":run_id,"candidate_id":case["id"],"model":modelcfg["model"],
            "protocol":api_type,"state":state,"requests":attempts,"tool_calls":calls,
            "score":env.score(),"invalid_tool_actions":getattr(env,"invalid_actions",0),"profile":profile,"estimated_cost":cost_total if cost_complete else None,
            "events":events,"calls":env.calls,"usage_db":str(db_path)}
    if getattr(env,"terminal_stops_runner",False):
        result.update(stop_reason=state,budget_exhausted=state in ("max_requests","max_tools"),task_completed=bool(env.finished))
    if file_workspace is not None:
        result["artifact_dir"]=str(file_workspace)
        (file_workspace/"run_result.json").write_text(
            json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    if hasattr(env,"close"):env.close()
    return result
