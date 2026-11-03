# SpreadsheetBench Windows GBK / UTF-8 诊断（2026-11）

## 实验事实

`SSB2-NEW-0068` 和 `SSB2-NEW-0005` 的 Qwen/GPT 对照均达到 25 次请求上限，均未交付 XLSX。两次模型运行都存在工具调用错误，GPT 运行还反复出现 Windows Python 3.12 的 `subprocess._readerthread` 中 `UnicodeDecodeError: 'gbk' codec...`。

**这不是纯模型推理失败证据。** GBK 堆栈来自宿主 Windows Python 的文本管道读取线程；当前 `tooluse_pilot/sandbox.py` 的 `DockerTools._exec` 已使用 `text=False` 和显式 UTF-8 `errors='replace'` 解码。因此**不能无证据断言异常来自这段 `_exec`**，也不能声称改动这段代码已经解决问题。其他宿主子进程路径、Python 解释器编码模式或进程环境仍需排查。

## 本轮改动

- 新增 `scripts/spreadsheetbench2_host_io_probe.py`：通过真实 DockerTools 分别运行 Python/Shell，写出大段中文 UTF-8 和故意不完整的 UTF-8 字节，验证原始字节捕获及 replacement 解码。**此步骤不调用模型 API。**
- `spreadsheetbench2_mechanism_pilot.py run` 启动模型预检前，自动执行同一沙盒编码预检；失败即返回 `preflight_failed`、`cases=0`，避免在明显损坏的工具链上继续消耗 Token。
- 增加 `tests/test_spreadsheetbench2_host_io_probe.py` 回归测试，使用 mock 验证 `text=False` 和错误字节处理。它不等于 Windows 真机的 Docker 测试。

## 推荐 Windows PowerShell 检查（不调用模型 API）

```powershell
git fetch origin feature/dynamic-w6-pilot
git merge FETCH_HEAD

python -m py_compile scripts/spreadsheetbench2_host_io_probe.py scripts/spreadsheetbench2_mechanism_pilot.py

python -m unittest discover -s tests -p "test_spreadsheetbench2_host_io_probe.py" -v
python -m unittest discover -s tests -p "test_spreadsheetbench2_mechanism_pilot.py" -v

python -X utf8 scripts/spreadsheetbench2_host_io_probe.py
```

`python -X utf8` 显式让宿主 Python 使用 UTF-8 模式，避免某些调用 `subprocess.run(text=True)` 时默认选用 GBK。**它不能修复显式指定 `encoding='gbk'` 的其他调用，也不能保证模型代码本身正确。**

如果要做新的模型试验，在新 PowerShell 中设置：

```powershell
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8:replace"
```

并通过 `python -X utf8 -u ...` 运行。**run --execute 会调用模型 API**，在诊断完成前不要为这些已受环境错误干扰的结果反复付费重测。

## 分类建议

- 两次 `max_requests` 都是有效观察到的“在给定预算内无交付”，但有工具异常干扰。
- 不能将 `delivered_xlsx=0` 单独归因为公式推理失败。
- 对严格 Qwen/GPT 难度比较，优先排除或单独标注工具链出错的运行；在 UTF-8 路径和真实 Docker smoke 验证稳定后，采用相同题面、预算做对照。
- 不要因为编码故障就重写整个 `DockerTools` 或放开容器的隔离设置。
