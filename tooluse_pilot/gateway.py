"""ToolUse Pilot gateway (Chat Completions + Responses).

Never expose private/oracle.json or evaluator source to the model.
Every HTTP attempt, including explicit retries, is recorded in the SQLite ledger.
"""

import json
import os
import random
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from .ledger import record, usage_fields, calculate_cost
from .tools import StructuredTools
from .sandbox import DockerTools

DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "list_sheets",
            "description": "List available Excel worksheet names",
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_rows",
            "description": "Read paginated rows from an Excel worksheet",
            "parameters": {
                "type": "object",
                "properties": {
                    "sheet": {"type": "string"},
                    "offset": {"type": "integer", "minimum": 0},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 500},
                },
                "required": ["sheet"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_csv",
            "description": "Write anomaly rows to output/anomalies.csv; each row contains order_id, expected_cents, net_paid_cents, issues",
            "parameters": {
                "type": "object",
                "properties": {
                    "rows": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "order_id": {"type": "string"},
                                "expected_cents": {"type": "integer"},
                                "net_paid_cents": {"type": "integer"},
                                "issues": {"type": "string"},
                            },
                            "required": [
                                "order_id",
                                "expected_cents",
                                "net_paid_cents",
                                "issues",
                            ],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["rows"],
                "additionalProperties": False,
            },
        },
    },
]

CODE_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "execute_python",
            "description": "Run a Python script in an isolated Docker workspace at /work. Python openpyxl available. Files input/procurement.xlsx and output/ exist.",
            "parameters": {
                "type": "object",
                "properties": {"code": {"type": "string"}},
                "required": ["code"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "execute_shell",
            "description": "Run a shell command inside the same isolated Docker workspace; no network.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
                "additionalProperties": False,
            },
        },
    },
]


def _safe_tool(tools, name, args):
    if not isinstance(args, dict):
        raise ValueError("tool arguments must be object")
    if name == "list_sheets" and not args:
        return tools.list_sheets()
    if (
        name == "read_rows"
        and set(args) <= {"sheet", "offset", "limit"}
        and "sheet" in args
    ):
        rows = tools.read_rows(**args)
        # Pagination metadata helps the model avoid wasteful empty-page reads.
        limit = args.get("limit", 100)
        offset = args.get("offset", 0)
        return {
            "rows": rows,
            "returned": len(rows),
            "has_more": len(rows) == limit,
            "next_offset": offset + len(rows) if len(rows) == limit else None,
        }
    if name == "write_csv" and set(args) == {"rows"}:
        return tools.write_csv(args["rows"])
    raise ValueError("Unknown tool or invalid arguments")


def _config(path):
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    if "models" not in cfg:
        raise ValueError("models required")
    return cfg


def to_responses_tools(definitions):
    return [
        {
            "type": "function",
            "name": item["function"]["name"],
            "description": item["function"].get("description", ""),
            "parameters": item["function"]["parameters"],
            "strict": False,
        }
        for item in definitions
    ]


def get_responses_calls(response):
    calls = []
    for item in response.output or []:
        if getattr(item, "type", None) == "function_call":
            calls.append(
                SimpleNamespace(
                    id=item.call_id,
                    function=SimpleNamespace(name=item.name, arguments=item.arguments),
                )
            )
    return calls


def _is_retryable(exc):
    """Retry transport failures and *specific* transient upstream gateway errors."""
    try:
        from openai import APIConnectionError, APITimeoutError, APIStatusError
    except ImportError:
        return False
    if isinstance(exc, (APIConnectionError, APITimeoutError)):
        return True
    if not isinstance(exc, APIStatusError):
        return False
    if exc.status_code in (408, 409, 429, 500, 502, 503, 504):
        return True
    if exc.status_code == 424:
        try:
            body = exc.response.json()
            err = body.get("error", {})
            code = str(err.get("code", ""))
            msg = str(err.get("message", "")).lower()
            return code == "2002" and (
                "connection reset" in msg or "timed out" in msg or "timeout" in msg
            )
        except (ValueError, TypeError, AttributeError):
            return False
    return False


def _usage_dict(response):
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return (
        usage.model_dump(exclude_none=True) if hasattr(usage, "model_dump") else usage
    )


def run_gateway(
    case_dir,
    config_path,
    model_alias,
    db_path="runs/usage.sqlite",
    max_requests=25,
    max_tool_calls=100,
    budget=None,
    mode="structured",
    sandbox_image="tooluse-pilot-sandbox:py311-openpyxl",
    client_factory=None,
):
    """Run one trial. max_requests limits logical model turns, not HTTP retry attempts.

    retries are only for the same model request; tools are never re-executed on retry.
    No-usage HTTP failures retain NULL token/cost fields pending gateway billing.
    """
    root = Path(case_dir)
    cfg = _config(config_path)
    modelcfg = cfg["models"][model_alias]
    model = modelcfg["model"]
    provider = modelcfg.get("provider", "gateway")
    api_type = modelcfg.get("api_type", "chat_completions")
    if api_type not in ("chat_completions", "responses"):
        raise ValueError(f"Unsupported api_type: {api_type}")
    if mode not in ("structured", "python_shell"):
        raise ValueError("invalid mode")

    if client_factory is None:
        key = os.getenv(cfg.get("api_key_env", "MODEL_API_KEY"))
        url = os.getenv(cfg.get("base_url_env", "MODEL_BASE_URL"))
        if not url or not key:
            raise ValueError("Gateway URL and API key environment variables required")
        from openai import OpenAI

        # Disable SDK retries: otherwise invisible HTTP attempts evade the ledger.
        client = OpenAI(
            api_key=key,
            base_url=url,
            timeout=cfg.get("timeout_sec", 180),
            max_retries=0,
        )
    else:
        client = client_factory()

    retry_limit = int(modelcfg.get("retry_limit", cfg.get("retry_limit", 2)))
    retry_limit = max(0, min(retry_limit, 5))
    run_id = str(uuid4())
    task = json.loads((root / "task.json").read_text(encoding="utf-8"))
    system = (
        "You are an Excel operations agent. Use tools as needed. "
        "Never claim a file was written without writing it. "
        "Private evaluation data is inaccessible."
    )
    if mode == "python_shell":
        system += (
            " Run code using execute_python or execute_shell. "
            "Working directory /work. Save output/anomalies.csv."
        )
    instruction = (root / "instruction.md").read_text(encoding="utf-8")
    # In Responses, send system instructions outside the input history.
    messages = (
        [{"role": "user", "content": instruction}]
        if api_type == "responses"
        else [
            {"role": "system", "content": system},
            {"role": "user", "content": instruction},
        ]
    )
    tools = (
        DockerTools(root, image=sandbox_image)
        if mode == "python_shell"
        else StructuredTools(root)
    )
    definitions = CODE_DEFINITIONS if mode == "python_shell" else DEFINITIONS
    if api_type == "responses":
        definitions = to_responses_tools(definitions)

    num_tools = 0
    requests = 0  # Physical HTTP attempts, including retries
    trace = []
    spent = 0.0
    cost_complete = True
    state = "max_requests"
    prices = modelcfg.get("pricing")
    try:
        old_output = root / "output" / "anomalies.csv"
        if old_output.exists():
            old_output.unlink()

        for turn in range(1, max_requests + 1):
            if num_tools >= max_tool_calls:
                state = "max_tool_calls"
                break
            response = None
            calls = []
            msg = None
            response_items = []
            error = None
            for retry_index in range(retry_limit + 1):
                start = time.monotonic()
                rid = None
                usage = None
                error = None
                caught = None
                try:
                    if api_type == "responses":
                        response = client.responses.create(
                            model=model,
                            instructions=system,
                            input=messages,
                            tools=definitions,
                            tool_choice="auto",
                            **modelcfg.get("request_options", {}),
                        )
                        rid = response.id
                        calls = get_responses_calls(response)
                        response_items = [
                            item.model_dump(exclude_none=True)
                            for item in response.output or []
                        ]
                    else:
                        response = client.chat.completions.create(
                            model=model,
                            messages=messages,
                            tools=definitions,
                            tool_choice="auto",
                            stream=False,
                            **modelcfg.get("request_options", {}),
                        )
                        rid = response.id
                        if not response.choices:
                            raise ValueError("Gateway returned no choices")
                        msg = response.choices[0].message
                        calls = msg.tool_calls or []
                    usage = _usage_dict(response)
                    status = "ok"
                except Exception as exc:
                    caught = exc
                    error = str(exc)[:1000]
                    status = "error"
                    calls = []
                u = usage_fields(usage)
                cost = calculate_cost(u, prices)
                if cost is None:
                    cost_complete = False
                else:
                    spent += float(cost)
                requests += 1
                record(
                    db_path,
                    run_id=run_id,
                    task_id=task["task_id"],
                    mode=mode,
                    provider=provider,
                    model=model,
                    attempt=requests,
                    status=status,
                    error=error,
                    gateway_request_id=rid,
                    duration_ms=int((time.monotonic() - start) * 1000),
                    tool_calls=len(calls),
                    estimated_cost=cost,
                    currency=(prices or {}).get("currency"),
                    pricing_key=model_alias,
                    raw_usage=usage,
                    **u,
                )
                trace.append(
                    {
                        "event": "api_attempt",
                        "turn": turn,
                        "retry_index": retry_index,
                        "attempt": requests,
                        "status": status,
                        "error": error,
                        "request_id": rid,
                        "tool_calls": len(calls),
                        "usage": u,
                    }
                )
                if caught is None:
                    break
                if retry_index >= retry_limit or not _is_retryable(caught):
                    break
                delay = min(15.0, 2.0**retry_index + random.uniform(0, 0.5))
                trace.append(
                    {
                        "event": "retry",
                        "turn": turn,
                        "retry_index": retry_index + 1,
                        "sleep_seconds": round(delay, 2),
                    }
                )
                time.sleep(delay)

            if error:
                state = "api_error"
                trace.append(
                    {"event": "api_error", "attempt": requests, "error": error}
                )
                break

            if api_type == "responses":
                messages.extend(response_items)
            else:
                messages.append(msg.model_dump(exclude_none=True))
            if not calls:
                state = "finished"
                break

            for call in calls:
                if num_tools >= max_tool_calls:
                    state = "max_tool_calls"
                    break
                num_tools += 1
                try:
                    args = json.loads(call.function.arguments)
                    if mode == "structured":
                        result = _safe_tool(tools, call.function.name, args)
                    elif call.function.name == "execute_python" and set(args) == {
                        "code"
                    }:
                        result = tools.execute_python(args["code"])
                    elif call.function.name == "execute_shell" and set(args) == {
                        "command"
                    }:
                        result = tools.execute_shell(args["command"])
                    else:
                        raise ValueError("Unknown tool/arguments")
                    payload = json.dumps(
                        {"ok": True, "result": result}, ensure_ascii=False, default=str
                    )
                    ok = True
                except Exception as exc:
                    payload = json.dumps(
                        {"ok": False, "error": str(exc)[:500]}, ensure_ascii=False
                    )
                    ok = False
                trace.append(
                    {
                        "event": "tool_call",
                        "name": call.function.name,
                        "ok": ok,
                        "tool_call_id": call.id,
                    }
                )
                if api_type == "responses":
                    messages.append(
                        {
                            "type": "function_call_output",
                            "call_id": call.id,
                            "output": payload,
                        }
                    )
                else:
                    messages.append(
                        {"role": "tool", "tool_call_id": call.id, "content": payload}
                    )
            if state == "max_tool_calls":
                break
            if budget is not None:
                if not cost_complete:
                    state = "unknown_cost_budget"
                    break
                if spent >= budget:
                    state = "budget_exceeded"
                    break

        if mode == "python_shell":
            tools.publish()
        from .grade import grade

        scored = grade(root)
        result = {
            "run_id": run_id,
            "model_alias": model_alias,
            "provider": provider,
            "model": model,
            "mode": mode,
            "requests": requests,
            "tool_calls": num_tools,
            "state": state,
            "estimated_cost": spent if cost_complete else None,
            "currency": (prices or {}).get("currency"),
            "score": scored,
            "usage_db": str(db_path),
            "events": trace,
            "calls": tools.calls,
        }
        dest = root / "runs"
        dest.mkdir(exist_ok=True)
        (dest / f"{run_id}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {k: v for k, v in result.items() if k not in ("events", "calls")}
    finally:
        if mode == "python_shell":
            tools.close()
