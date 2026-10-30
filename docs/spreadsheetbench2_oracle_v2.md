# Derived XLSX Oracle v2 and controlled GPT test

Original source and six candidate cases remain unchanged under
`runs/ssb2-derived-01/`. Generated fixtures and hidden oracles never enter
the model's Docker sandbox.

## Offline validation (PowerShell)

```powershell
git fetch origin feature/dynamic-w6-pilot
git merge FETCH_HEAD
python -m py_compile scripts/spreadsheetbench2_derive.py scripts/spreadsheetbench2_oracle_mutations.py scripts/spreadsheetbench2_run_derived.py
python scripts/spreadsheetbench2_derive.py selftest --out runs/ssb2-derived-01
python scripts/spreadsheetbench2_oracle_mutations.py --root runs/ssb2-derived-01
```

Mutation tests check that six positive/reference cases pass and missing,
wrong-reference, unauthorized-edit and sheet-removal negative cases fail.
The original workbook should not be overwritten.

The revised validator checks unchanged non-target cell contents, sheet order,
merged cells, defined-name keys and sheet visibility. It accepts canonical
`SUM(A1:A6)` or a restricted explicit ascending/descending addition of the
same contiguous cells, but does **not** claim general formula equivalence.
It does not execute formulas, validate all OOXML parts or provide the official
SpreadsheetBench 2 score. A candidate Oracle pass is not official correctness.

## One real GPT trial, after all offline tests succeed

Confirm `MODEL_BASE_URL`, `MODEL_API_KEY`, `MODEL_ID` are populated in the
current PowerShell window. Never paste the key into source or logs.

```powershell
python -u scripts/spreadsheetbench2_run_derived.py --case runs/ssb2-derived-01/repair --out runs/derived-repair-gpt-01 --max-requests 25 --max-tools 60
```

The output directory must not already exist. The trusted score is written
to `runs/derived-repair-gpt-01/trusted_result.json`. The model sees only the
prompt and input XLSX. Do not run the JSON location task through this
XLSX-only runner.

**Research validity:** all six cases are candidate derivatives of one parent
workbook and are not statistically independent. Before publication or broad
scaling: adjudicate the 16 formula fixes independently, implement controlled
Excel-compatible recalculation and OOXML integrity checks, and separate
workbooks between train and test sets.
