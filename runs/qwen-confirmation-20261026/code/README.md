# ToolUse Pilot v0.1 — 双模式工具使用评测

第一期交付：单个可复现的 Excel 采购核验基准题（W7 长表格覆盖 + W12 跨源核验 + W4 多要求覆盖）。这是一套 **可运行基座和参考执行器**，不是已经接通真实模型 API 的成品基准。

## 架构

- `generate.py`: 确定性生成 XLSX 输入、任务说明、隐藏 Oracle、元数据
- `xlsx.py`: 基于 Python 标准库 OOXML 的 XLSX 表格读取器
- `tools.py`: 结构化工具 `list_sheets/read_rows/write_csv`，含分页和记录
- `reference.py`: 两种参考执行模式（结构化工具链及 Python 程序处理）
- `core.py`: 独立业务计算逻辑，仅供题目生产和参考验证
- `grade.py`: 读取**私有** Oracle，按业务结果和可选工具轨迹评分
- `tests`: 端到端、污染输出检测、确定性测试

## 安装运行

```bash
python -m pip install -e .
python -m tooluse_pilot.cli generate examples/case-001 --seed 20261019 --count 80
python -m tooluse_pilot.cli reference examples/case-001 --mode structured
python -m tooluse_pilot.cli grade examples/case-001 --trace examples/case-001/trace.json
python -m tooluse_pilot.cli reference examples/case-001 --mode python_shell
python -m tooluse_pilot.cli grade examples/case-001
python -m unittest discover -s tests -v
```

## 面向被测模型

**务必隔离**：模型只能看到 `instruction.md`、`input/` 及可写 `output/`。严禁挂载 `private/`、`reference.py`、`core.py`、`grade.py` 等；这些只在评测器容器中存在。参考执行器仅用于验证样题和评分器是否自洽，不能作为模型可用工具。

- 结构化模式：Runner 接收模型返回的 JSON 工具调用，将其分发到 `StructuredTools`，循环直至完成/达到预算，并将调用记录保存为 `trace.json`。本项目提供工具和参考轨迹，**尚未提供模型 API Runner**。
- Python/Shell 模式：给 Agent 一个隔离工作区及有限工具，允许通过 Python 处理 `input/procurement.xlsx`，产出 `output/anomalies.csv`。评测器从可信侧评估输出；参考方案演示 Python 执行，但**不是实际隔离沙箱**。

## 评分与限制

- 结果 85 分：逐行订单 ID、应付金额、净支付金额、异常标签、排序和额外错误条目。
- 过程 15 分：结构化模式要求有列举表和读取 4 个 Sheet 及写出文件的可验证调用轨迹。
- Python/Shell 模式未接入命令级 Trace，因而只会按结果部分打最高 85 分；对比两模式时应优先比较 `result_score`，**不能把总分当作同口径比较**。
- 本版本不含浏览器、LLM 裁判、模型自动运行、故障注入、异步工具或 PPT；这些是下一迭代。
- Excel 生成采用 `artifact_tool`；解析采用 OOXML 标准库；不执行宏或 Excel 公式。
- 生产题库时必须拆开 generator/oracle 与被测运行镜像，并针对不同随机种子做泛化检查和错例回归。

## v0.2 统一模型网关与逐请求账本（新增）

新增 OpenAI-compatible Chat Completions 网关 Runner，**当前真实模型执行仅支持 structured 模式**。旧版 `python_shell` 为参考执行器；真实模型 Python/Shell 必须等待隔离容器执行器上线，不能在本机直接执行模型生成的命令。

复制 `gateway.models.example.json` 为 `gateway.models.json`，修改网关返回的**真实模型 ID**、provider 标签和计费价格。示例价格纯属占位，不代表网关真实价格。模型报价若未核实，建议删除 `pricing`，这时请求会被记录，但费用保持未知。

PowerShell 示例：

```powershell
$env:MODEL_BASE_URL = 'https://YOUR-GATEWAY/v1'
$env:MODEL_API_KEY = 'YOUR_KEY'
Copy-Item gateway.models.example.json gateway.models.json
# 先编辑 gateway.models.json：替换模型 ID，核实单价或移除 pricing
python -m tooluse_pilot.cli run-model examples/case-001 --config gateway.models.json --model model_a --max-requests 25 --max-tools 100
python -m tooluse_pilot.cli grade examples/case-001
python -m tooluse_pilot.cli usage-summary
python -m tooluse_pilot.cli export-usage --out runs/api_usage.csv
```

同一批多模型实验必须**复制独立 case 工作区**再分别运行，避免互相覆盖输出文件。禁止把 `private/` 挂载给模型的执行容器或将 Oracle 文本注入提示词。structured 模式下只暴露受限工具读写接口，但仓库运行环境仍保留 Oracle 供可信评分器使用。

网关 API 地址和 Key **仅通过环境变量读取**，不写入日志。每个 HTTP 尝试记录到 `runs/usage.sqlite`，失败尝试也记录，包含 run_id、模型、provider、请求 ID、Token、耗时、估算费用和价格别名；`runs/api_usage.csv` 可用于内部用量对账。多模型只需在 `gateway.models.json` 中增加模型别名与网关模型 ID，无需多份 API Key（除非你的网关配置要求）。

**费用注意**：在不知道真实价格和缓存明细时 `estimated_cost` 留空；如果超时，网关可能已计费，账本记为未知。费用估算不等于正式账单、充值记录或发票；需要和网关后台按时间区间、模型、项目/子 Key 对账。统一网关可能不透传原始厂商 request ID 与细粒度 Token 字段；需对照网关的实际响应验证。不同模型可能拒绝 `temperature` 等参数，按网关文档调整 `request_options`。

**当前限制**：暂不支持 Responses API、Anthropic 原生消息协议、流式 API、真实 Python/Shell Agent、自动多模型批次/费用硬预算。`--budget` 仅基于已知逐次估算费用停止**后续**请求，不能保证单次请求事前不超额；用量/价格不完整时自动停止预算受控运行。运行前请设置网关账户侧额度和调用限额。`run-model` 不做自动重试，防止超时后重复计费。

## v0.3 (2026-10-19) · TokenOPS 多模型网关与双执行模式

### 依赖修复

`artifact-tool` 已从强制依赖及生成器代码删除；改用 `openpyxl` 生成 XLSX。在 Windows PowerShell 中：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m unittest discover -s tests -v
```

### 网关配置

官方文档确认 `https://api.tokenops.ai/v1/chat/completions` 支持 OpenAI 兼容请求，模型广场标注下列四个模型有 Function Call 能力。但**没有你的 API Key，未能核实账号权限、四个模型逐一实际工具调用行为、精细 Token 字段或账单单价**。建议从低价模型小样本开始探测。

```powershell
Copy-Item gateway.models.example.json gateway.models.json
$env:MODEL_BASE_URL = 'https://api.tokenops.ai/v1'
$env:MODEL_API_KEY = '在自己电脑设置，不要提交到 Git 或分享给他人'
python -m tooluse_pilot.cli diagnose --config gateway.models.json
python -m tooluse_pilot.cli generate examples/new-001 --seed 20261019 --count 30
python -m tooluse_pilot.cli run-model examples/new-001 --config gateway.models.json --model deepseek --mode structured --max-requests 8 --max-tools 25
python -m tooluse_pilot.cli grade examples/new-001
```

配置模型别名：`claude -> claude-opus-5`、`gpt -> gpt-6-astra`、`gemini -> gemini-3.7-flash`、`deepseek -> deepseek-v4-flash-0731`，ID 必须与网关模型广场完全一致。`request_options` 默认空字典，避免各厂商对 temperature 等参数的差异。所有模型使用 Chat Completions 的工具调用回合（`message.tool_calls`, `role=tool`, `tool_call_id`）。**这不等于证明所有模型在该入口上的实际兼容性**。若个别模型要求 Responses 或 Anthropic 原生格式，需要专门新增协议适配器。

### Python/Shell 模式：Docker 隔离（无宿主机直接执行回退）

需要 Docker Desktop 运行 Linux containers。在首次运行 Python/Shell 模式前先准备镜像：

```powershell
docker build -t tooluse-pilot-sandbox:py311-openpyxl -f sandbox/Dockerfile .
python -m tooluse_pilot.cli run-model examples/new-001 --config gateway.models.json --model deepseek --mode python_shell --max-requests 10 --max-tools 20
```

Agent 的脚本只允许在隔离的 `/work` 目录中运行。挂载单独的 `input/`、`output/`、任务说明，**不挂载 oracle/private、代码库、用户目录或 API 密钥**。容器设置网络隔离、低权限、资源限制。不要把此实验容器视为已通过对抗性安全审计的强沙箱：生产环境请使用独立虚拟机 / 专用计算节点与额外的隔离策略。Docker 镜像中的 Python 安装 `openpyxl`。Shell 使用容器内 `sh`，不是 Windows PowerShell。

### 多模型多模式批量执行

```powershell
python -m tooluse_pilot.cli batch examples/new-001 --config gateway.models.json --models deepseek gemini claude gpt --modes structured python_shell --outdir runs/batch-001 --max-requests 12 --max-tools 30
python -m tooluse_pilot.cli usage-summary
python -m tooluse_pilot.cli export-usage --out runs/api_usage.csv
```

每个模型/模式复制独立工作区，评分前清除目标输出；批次每次使用**新的** `--outdir`。逐请求 API 尝试写入 `runs/usage.sqlite`，用量原始 JSON 也保留。空用量或价格未知时，成本列为空，不能当作零。失败/超时请求仍会计数，费用可能后续才在网关账单出现；没有自动重试。请先设置平台账户配额。

### 统一口径与计费边界

- 使用 `prompt_tokens` / `completion_tokens` / `total_tokens` 及 `prompt_tokens_details.cached_tokens`、`completion_tokens_details.reasoning_tokens`；兼容 `input_tokens` / `output_tokens` 结构，但 Runner 本身当前仅请求 Chat Completions。
- 价格必须经过**网关实时价格与实际账单**核实，再手动放入 `gateway.models.json` 的 `pricing`；未验证时不要填写。模型广场美元标价不等于实际账单计费币种和最终成本。
- 当前记录总耗时、错误状态和 tool_calls 数量；`run_id` 挂接题目、模型与执行模式。导出的 CSV 仅为内部使用证据，不代替平台发票及付款流水。
- v0.3 的 Python/Shell 和结构化模式**结果评分可比** (`score.result_score`)，但过程分尚未统一，严禁将 `score.total` 当成跨模式能力排名。
- 批量执行顺序运行；如其中模型报错会继续返回 `api_error` 结果；配置或环境错误（如缺 Docker）会直接中断批次。
- 如果用户要评测“是否能自主选择执行工具”，两种模式都提供 `tool_choice=auto`，只提供各自可用工具，不提供参考执行源码。

### 已知问题 / 下一阶段

- 尚未通过真实 TokenOPS 密钥进行四模型实测，不保证兼容性或适用的推理参数。
- 目前仅 Chat Completions；后续增加 Responses 和 Anthropic 原生协议。
- Docker 操作和执行超时尚需进一步做极端恶意命令、磁盘占用、并发执行压力测试。
- 更严格的实验记录应加入请求响应体哈希、账单导入核销、执行环境镜像摘要、限制输出大小及模型版本固定。


### v0.3.1 Windows 兼容性修复

修复 SQLite 数据库连接未显式关闭导致 Windows unittest TemporaryDirectory 清理时报 WinError 32 的问题；无需 API Key 即可运行离线测试。

## v0.4 high-difficulty scenario (W12 / W7 / W4 / W11)

The first high-complexity *candidate* adds effective-dated supplier versions, aliased IDs, effective-dated approval rules, approved historical amendments, refunds, reversals, pending holds, and snapshot-date constraints. It generates 8 worksheets in one workbook, with a private deterministic Oracle and a hidden verifier. It is **not calibrated high difficulty** until an actual model run.

Generate and verify offline (no API key or charges):

```powershell
python -m tooluse_pilot.cli generate-hard examples/hard-001 --seed 20261019 --count 180
python -m tooluse_pilot.cli reference-hard examples/hard-001
python -m tooluse_pilot.cli grade examples/hard-001 --trace examples/hard-001/trace.json
python -m unittest discover -s tests -v
```

Model run: `reference-hard` creates output/anomalies.csv: the model runner deletes this before trial, but for a cleaner audit use **a newly generated case**. In particular, do not expose `private/`, reference source, or oracle to the model.

```powershell
python -m tooluse_pilot.cli generate-hard examples/hard-deepseek-001 --seed 20261020 --count 180
$env:MODEL_BASE_URL = 'https://api.tokenops.ai/v1'
$env:MODEL_API_KEY = 'YOUR_KEY' # Set locally only. Never paste or commit the key.
Copy-Item gateway.models.example.json gateway.models.json
python -m tooluse_pilot.cli run-model examples/hard-deepseek-001 --config gateway.models.json --model deepseek --mode structured --max-requests 35 --max-tools 100
python -m tooluse_pilot.cli usage-summary
python -m tooluse_pilot.cli export-usage --out runs/deepseek-hard-usage.csv
```

IMPORTANT: `--max-requests` and `--max-tools` are hard execution limits, but without configured pricing a monetary budget cannot be enforced. Inspect the TokenOPS invoice; estimated cost is not a receipt. For a low-spend pilot try `--count 60` first. The structured tool returns row data and `write_csv` takes the entire output as JSON; it will not scale to arbitrary-size workbooks. This is intentional for the first pilot, not an enterprise spreadsheet engine. Python/Shell mode uses a Docker sandbox and is not exercised by this first single-mode trial.


## W6 dynamic follow-up experiment

Use `python -m tooluse_pilot.cli generate-hard examples/dynamic-w6 --seed 20261019 --count 100 --dynamic` to generate the case. After the model has read every sheet, the Runner injects a *new user message* moving the snapshot to 2026-09-11. The private oracle changes only when the update is injected. Run `python -m unittest discover -s tests -v` before using the paid API, then `python -m tooluse_pilot.cli run-model examples/dynamic-w6 --config gateway.models.json --model gpt --mode structured --max-requests 20 --max-tools 60`. Inspect `events` for `user_revision` and `score.revision_injected`. The existing static case remains supported.


### Two-stage W6 protocol

The dynamic Runner now waits for the first complete model submission (final assistant turn with `output/anomalies.csv` on disk), stores a private snapshot and first-stage grade, **then** injects the changed user cutoff. A second `write_csv` call is mandatory for the updated submission. Outputs include `initial_result_score`, `revised_result_score`, `artifact_updated`, and `delta` with the exact changed-order accuracy. The revision is never inserted merely because all sheets were read. A single-write run cannot earn full marks. Use a fresh case directory for each run to avoid overwriting experiment outputs.
