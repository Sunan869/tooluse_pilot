# SpreadsheetBench 2 01_01 derived task pilot

**Original workbook stays immutable.** Source:
`runs/ssb2-debugging-baseline/01_Debugging_01_01/input/Double Counting_input.xlsx`
(SHA-256: `e6d8eb78c3c91d352c054a5c043493861954ffa1cf75f80076a1b2d062709c10`).

This pilot derives **six candidate prompts** using independently verified formula
differences seen in the official `01_golden.xlsx`, focusing on 16 M&A
subtotal cells in rows 42, 52, 62, 72 and columns D:G. They are candidates,
NOT six independently validated difficulty samples. The four row-specific
tasks overlap the full repair task. Golden differences alone do not prove
semantic correctness; a domain review is required.

PowerShell (from original project directory):

```powershell
git fetch origin feature/dynamic-w6-pilot
git merge FETCH_HEAD
python -m py_compile scripts/spreadsheetbench2_derive.py
python scripts/spreadsheetbench2_derive.py generate --out runs/ssb2-derived-01
python scripts/spreadsheetbench2_derive.py selftest --out runs/ssb2-derived-01
```

The six directories are `locate`, `repair`, `row42`, `row52`,
`row62`, `row72`. Each has `input/`, `output/`, `instruction.md`
and hidden `private/oracle.json`. The self-test produces trusted-side
positive/negative fixtures in `private/`. NEVER mount private or the
generator in the agent sandbox.

For a model-edited XLSX, use:
```powershell
python scripts/spreadsheetbench2_derive.py grade --case runs/ssb2-derived-01/repair --submission path/to/edited.xlsx
```

For the `locate` task, the submission must be a JSON file containing
`{"cells":["D42",...]}` (cell addresses only).

**Important limits:** The current deterministic grader accepts only exact
canonical formulas and checks non-target cell *values/formulas* remain
unchanged. It does not yet prove formula semantic equivalence, recalculated
values, preservation of all OOXML constructs, formatting, named ranges or
external links; it is NOT the official SpreadsheetBench evaluator. A model
could produce a valid formula with different syntax and be rejected. A file
with broken non-cell OOXML could pass. Accordingly, treat these tasks as
`candidate_requires_review` until verified with an Excel-compatible
recalculation engine and independent invariants.

Do not claim six fully independent problems or a benchmark success rate from
this output. For a larger dataset, split train/test by parent workbook hash.
