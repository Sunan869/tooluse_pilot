# SpreadsheetBench 2: next phase (real task mapping)

The previous shortlist selects XLSX files by formula structure only. It is NOT
yet an evaluation sample: use the official `dataset.json` to associate
workbooks with `id`, `instruction`, `spreadsheet_path`,
`golden_response_path`.

Run these commands from the **existing** repository root:

```powershell
git pull origin feature/dynamic-w6-pilot
python scripts/spreadsheetbench2_cases.py match
Get-Content datasets\spreadsheetbench2\matched_cases.json -TotalCount 100
```

If `matched` is 0 or any inputs/golden files are null, do **not** use a
fuzzy filename match or invent a ground truth. The official metadata may
refer to directories rather than files. Inspect a local category's
`dataset.json` and report its first record for precise schema alignment.

Once a task has a verified input and golden mapping, stage it:

```powershell
python scripts/spreadsheetbench2_cases.py stage --category Debugging --id ACTUAL_ID --out runs/ssb2/debug-001
```

`ACTUAL_ID` must come from `matched_cases.json`. The command refuses to
overwrite an existing workspace. The agent may access only `input/`,
`output/` and `instruction.md`. The `private/` folder contains golden
answers and metadata; it is for trusted-side scoring only.

This stage tool **does not run the model**, **does not recalculate workbooks**,
and **does not provide official SpreadsheetBench 2 scoring**. The upstream
README requires both input and gold workbooks to be recalculated before
evaluation; use its `evaluation/open_spreadsheet.py` on copies and keep the
original files immutable.

Next engineering step after local schema validation: integrate the selected
task with the existing Docker Python/Shell mode, preserving per-run model
traces, and use the upstream evaluator as the baseline scorer.
