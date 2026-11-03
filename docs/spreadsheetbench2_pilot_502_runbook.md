# Qwen Pilot：HTTP 502 故障隔离与断路保护

如果批量模型调用在显示 `[start]` 后立即报 `Error code: 502`，而没有任何 `[turn 1/25]`，**说明模型 API 请求本身失败，不能计入 Qwen 做题失败率**。请检查服务、反向代理、URL/模型 ID 及系统代理。

本轮修复 `scripts/spreadsheetbench2_mechanism_pilot.py`：

- 开始每批次前，先用相同模型和 Chat Completions/Responses 协议做**一次最小工具调用预检**。此预检会调用当前配置的模型端点，但不上传题目 XLSX，也不使用隐藏答案。
- 预检不通时返回 `status=preflight_failed`、`cases=0`，不创建新的实验输出目录。
- 批次中出现 HTTP 500/502/503/504/429 或网络错误时，停止后续任务，`infrastructure_errors` 与 `valid_model_evaluations` 分开统计。
- 原来的 `runs/ssb2-pilot-qwen-01` 保留；其中 2 条 HTTP 502 记录属于基础设施故障，不属于模型能力结果。

## 首先检查 Qwen 服务（Windows PowerShell）

```powershell
$env:MODEL_BASE_URL = "http://10.10.23.7:5610/v1"
$env:MODEL_ID = "Qwen3.8-Flash-Next-AWQ-INT4"
$env:MODEL_API_KEY = "not-needed"
curl.exe --noproxy "*" --connect-timeout 10 -i "$env:MODEL_BASE_URL/models"
```

`/models` 正常只能证明模型网关可达，**不能证明 Chat Completions 和工具调用可用**。进一步执行现成的最小工具调用 probe：

```powershell
python scripts/spreadsheetbench2_local_qwen.py probe `
  --base-url $env:MODEL_BASE_URL --model $env:MODEL_ID
```

预期 `tool_calls_supported=true`。如果此处仍然 HTTP 502，先排查服务端上游日志/模型 GPU 状态、代理和反向代理，不要执行整批 XLSX 题。

## 拉取补丁并重试

```powershell
git fetch origin feature/dynamic-w6-pilot
git merge FETCH_HEAD

python -m py_compile scripts/spreadsheetbench2_mechanism_pilot.py
python -m unittest discover -s tests -p "test_spreadsheetbench2_mechanism_pilot.py" -v
```

等探针正常后，保留原来同一份 `runs/ssb2-pilot-plan-01.json`，只换新输出目录：

```powershell
python -u scripts/spreadsheetbench2_mechanism_pilot.py run `
  --plan "runs/ssb2-pilot-plan-01.json" `
  --out "runs/ssb2-pilot-qwen-02" `
  --api-type chat_completions --max-cases 2 `
  --max-requests 25 --max-tools 60 --execute
```

**run --execute 会调用本地 Qwen 模型 API。** 其他本地代码自测无调用；probe/preflight 只做少量真实 API 请求。不要将真实模型密钥粘贴到聊天或提交到 Git。
