"""Probe Responses API tool calling using the current PowerShell environment."""
import json
import os
from openai import OpenAI

required=("MODEL_BASE_URL","MODEL_API_KEY","MODEL_ID")
missing=[key for key in required if not os.getenv(key)]
if missing:
    raise SystemExit("Missing environment variables: "+", ".join(missing))
client=OpenAI(base_url=os.environ["MODEL_BASE_URL"],api_key=os.environ["MODEL_API_KEY"],timeout=180,max_retries=0)
tools=[{
    "type":"function",
    "name":"execute_python",
    "description":"Execute Python code in an isolated environment.",
    "parameters":{
        "type":"object",
        "properties":{"code":{"type":"string"}},
        "required":["code"],
        "additionalProperties":False
    },
    "strict":False
}]
try:
    response=client.responses.create(
        model=os.environ["MODEL_ID"],
        input=[{"role":"user","content":"请调用 execute_python 计算 2+3，不要直接给出答案。"}],
        tools=tools,tool_choice="auto",store=False
    )
except Exception as exc:
    detail={"type":type(exc).__name__,"status":getattr(exc,"status_code",None),"message":str(exc)[:1200]}
    print(json.dumps(detail,ensure_ascii=False,indent=2))
    raise SystemExit(1)
calls=[{"name":item.name,"arguments":item.arguments}
       for item in response.output if item.type=="function_call"]
print(json.dumps({"model":response.model,"status":response.status,
    "tool_calls_supported":bool(calls),"tool_calls":calls,
    "output_text":response.output_text[:300],
    "usage":response.usage.model_dump(exclude_none=True) if response.usage else None},
    ensure_ascii=False,indent=2))
