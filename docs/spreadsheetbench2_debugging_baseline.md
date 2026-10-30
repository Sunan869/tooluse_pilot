# SpreadsheetBench 2 Debugging baseline: staged workspaces

The dataset contains 100 eligible Debugging tasks according to the user's local
selection report. Balanced selection has selected five **distinct** workbooks.

Run from Windows CMD in the existing repository:

```bat
git fetch origin feature/dynamic-w6-pilot
git merge FETCH_HEAD
python -m py_compile scripts/spreadsheetbench2_cases.py
python scripts/spreadsheetbench2_cases.py stage-selected --category Debugging --out runs/ssb2-debugging-baseline
```

The command creates five independent case directories plus `index.json`.
Each case contains:
- `instruction.md`: actual task description
- `input/`: only the official input XLSX
- `output/`: empty target directory
- `private/`: official golden XLSX and checksums; NEVER expose to an agent

**DO NOT use `python -m tooluse_pilot.cli run-model` on these staged cases yet.**
The current runner requires `task.json`, expects procurement input and only
publishes `output/anomalies.csv`, and calls the procurement grader. It does not
test XLSX editing or SpreadsheetBench's official scoring.

Next step: implement an XLSX-specific Docker runner with per-workspace
input/output mounts, update file publishing to retain edited XLSX, integrate
upstream official recomputation/scoring and test against five staged cases.
Run baseline (no Skill) first, then compare with Skill at matched budgets.

Local data and runs are gitignored. Do not commit third-party golden files
or private grader artifacts.
