# Local Qwen SpreadsheetBench 2 baseline

Run from the existing repository root, Windows **CMD**:

```bat
git fetch origin feature/dynamic-w6-pilot
git merge FETCH_HEAD
python -m py_compile scripts/spreadsheetbench2_local_qwen.py
docker build -t tooluse-pilot-sandbox:py311-openpyxl -f sandbox/Dockerfile .
python scripts/spreadsheetbench2_local_qwen.py probe
```

The probe must report `"tool_calls_supported": true` before proceeding.
This probes actual Chat Completions `tool_calls`; conversational health alone is
not enough.

List the five case subdirectories:

```bat
dir /b /ad runs\ssb2-debugging-baseline
```

Run the first task, substituting an actual directory name from that output:

```bat
python scripts/spreadsheetbench2_local_qwen.py run --case "runs/ssb2-debugging-baseline/ACTUAL_CASE_DIRECTORY" --max-requests 25 --max-tools 80
```

The script calls `http://10.10.23.7:5610/v1/chat/completions` with
`Qwen3.8-Flash-Next-AWQ-INT4` and
`extra_body={"chat_template_kwargs":{"enable_thinking":false}}`.
It uses the existing Docker sandbox to execute untrusted model tool calls,
publishes XLSX files only, and stores tool traces under `runs/`.

The existing procurement `run-model` must **not** be used for these tasks.
This script does not score the workbook or claim success merely because a file
was generated. Official SpreadsheetBench evaluation and workbook recalculation
remain to be integrated. `openpyxl` may not preserve every Excel extension.

Requirements: `python -m pip install -e .` and Docker Desktop running.
Each run requires a freshly staged case (the command refuses non-empty output).
No public internet connection is required from the model sandbox. Never expose
`private/` or `golden_response_path` to the model.
