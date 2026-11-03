# Blind audit candidate for the unchanged SpreadsheetBench 2 01_01 workbook

This is a **research diagnostic**, separate from the official SpreadsheetBench
task and from the guided `repair` case. The model prompt contains no sheet
name, error class, cell addresses, or reference formulas. The same original
workbook bytes are copied, with SHA-256 checked first.

The hidden Oracle is deliberately **only the 16 previously inspected M&A
subtotal formulas**. It is NOT a complete authoritative oracle for the
open-ended instruction to audit an entire workbook. Consequently, an otherwise
valid edit outside these 16 cells may be rejected by this narrow diagnostic
Oracle. Never call that an official benchmark failure.

## Offline preparation (PowerShell)

```powershell
git fetch origin feature/dynamic-w6-pilot
git merge FETCH_HEAD
python -m py_compile scripts/spreadsheetbench2_blind_case.py scripts/spreadsheetbench2_run_derived.py
python -m unittest tests.test_spreadsheetbench2_blind_case -v
python scripts/spreadsheetbench2_blind_case.py --source runs/ssb2-derived-01/repair --out runs/ssb2-derived-blind-01
Get-Content runs/ssb2-derived-blind-01/instruction.md -Encoding UTF8
```

Test the new case with existing trusted positive and negative files (zero model
calls, each should respectively pass and fail):

```powershell
python scripts/spreadsheetbench2_derive.py grade --case runs/ssb2-derived-blind-01 --submission runs/ssb2-derived-01/repair/private/correct.xlsx
python scripts/spreadsheetbench2_derive.py grade --case runs/ssb2-derived-blind-01 --submission runs/ssb2-derived-01/repair/input/Double Counting_input.xlsx
```

## Optional model trial AFTER offline validation

PowerShell must have MODEL_BASE_URL, MODEL_API_KEY, MODEL_ID. For GPT Responses:

```powershell
python -u scripts/spreadsheetbench2_run_derived.py --case runs/ssb2-derived-blind-01 --out runs/ssb2-blind-gpt-01 --api-type responses --max-requests 25 --max-tools 60
```

A fresh output directory is required. The model cannot access private/
through DockerTools. Inspect `trusted_result.json` and full run trace.
A score of 0 under this narrow Oracle can mean excessive edits or missed
target formulas, not necessarily that the model failed all workbook auditing.
For a formally defensible benchmark, independently adjudicate all possible
errors, add calculation-based validation with an Excel-compatible engine,
and test multiple distinct workbooks before drawing broad conclusions.
