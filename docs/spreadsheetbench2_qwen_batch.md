# Qwen SpreadsheetBench 2 five-case baseline

The first single case (Double Counting) reached 25 requests / 29 tool calls
with no XLSX output. Treat it as an incomplete run, not an official wrong
answer. The task asks for a broad workbook audit and fixes.

From the existing Windows CMD project directory:

```bat
git fetch origin feature/dynamic-w6-pilot
git merge FETCH_HEAD
python -m py_compile scripts/spreadsheetbench2_batch_qwen.py scripts/spreadsheetbench2_local_qwen.py scripts/spreadsheetbench2_xlsx_diff.py
python scripts/spreadsheetbench2_batch_qwen.py --out runs/ssb2-qwen-batch-01 --limit 5 --max-requests 25 --max-tools 60
```

For a smaller environment smoke test use a different output directory,
`--limit 1 --max-requests 8 --max-tools 20`. Each run writes into a new
workspace and preserves source staged workspaces. A missing XLSX is reported,
not silently treated as a valid benchmark score. Results live in
`runs/ssb2-qwen-batch-01/summary.json`; detailed traces are saved under each
case's `runs/` subdirectory.

Audit an edited workbook without opening the private golden answer:

```bat
python scripts/spreadsheetbench2_xlsx_diff.py runs/ssb2-qwen-batch-01/01_Debugging_01_01
```

This audit checks cell values/formulas and style changes but deliberately
does not claim official correctness. It does not recalculate formulas and
may not detect all OOXML-level changes or drawing/relationship corruption.
The source input is preserved.

The batch uses only the local model
`Qwen3.8-Flash-Next-AWQ-INT4` served at
`http://10.10.23.7:5610/v1`; requests include
`chat_template_kwargs.enable_thinking=false`. No GPT/TokenOPS.

**Remaining implementation:** official evaluation/recalculation,
repeatable skill-on/off conditions, source artifact preservation checks.
