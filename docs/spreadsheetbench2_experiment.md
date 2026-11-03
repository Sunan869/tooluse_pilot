# SpreadsheetBench 2 — real XLSX reliability experiment

This experiment is **separate from existing W6 / allocation / reservation cases**.
Source: https://github.com/RUCKBReasoning/SpreadsheetBench-2
Data: https://huggingface.co/datasets/KAKA22/SpreadsheetBench-v2

## Windows PowerShell

Run from the existing `tooluse_pilot` repository root, on
`feature/dynamic-w6-pilot`:

```powershell
python -m pip install "huggingface_hub>=0.25" "openpyxl>=3.1,<4"
python scripts/spreadsheetbench2_data.py download
python scripts/spreadsheetbench2_data.py catalog
python scripts/spreadsheetbench2_data.py shortlist --count 20
```

Downloads one official dataset archive (not the full HF repo), extracts to
`datasets/spreadsheetbench2/raw/`, and writes `manifest.json` and
`shortlist.json` locally. 442 MB is the *entire HF repository* size, not
necessarily the size of the selected archive. These files are gitignored.

If Hugging Face cannot be accessed, download
`spreadsheetbench-v2-09-10.zip` from the link above, put it at
`datasets/spreadsheetbench2/downloads/`, then extract it under
`datasets/spreadsheetbench2/raw/` with the archive's directory structure
intact (or use the script's safe extraction routine).

For a quick smoke test use `catalog --limit 5`; full cataloging may take
time for large workbooks. This inspection is **read-only**; it does not
recalculate formulas or edit workbooks. The shortlist is structural
preselection, *not* a set of scored cases. Verify task IDs, instructions and
golden workbook paths against each category's `dataset.json` before trials.

## Controlled benchmark protocol

1. Prefer `Debugging`, then `Financial_Model`; retain a small fixed
   representative sample alongside failure-targeted diagnostic cases.
2. Record source repository, archive filename/hash, task ID, original
   instruction, input workbook, gold workbook, scoring rules and environment.
3. Recalculate **input and golden workbooks in copies**, according to the
   official repository's `evaluation/open_spreadsheet.py`. Do not overwrite
   original files; LibreOffice and Excel may differ on some formulas.
4. Stage each run in a distinct isolated workspace. Give the agent only the
   original task instruction and its permitted input workbook; NEVER expose
   golden, metadata containing answers, reference files or private grader.
5. Run baseline (no Skill), Skill instructions only, script/tool additions only,
   then combined Skill+tools with the same model, prompt budget and environment.
   At least three independent repeats per condition.
6. Score with the unmodified official evaluation pipeline first. For
   reproducibility add checks for unauthorized workbook modifications,
   retained formulas, and recalculation under controlled input perturbations.
   These supplemental metrics must be labeled separately from official score.
7. Preserve model/tool traces, hashes of initial/final workbooks, failures,
   costs and all attempted tasks. Avoid measuring only known failures.

## Scope / current status

This commit only implements **download + formula-structure screening**.
It does *not* claim that the existing ToolUse Pilot structured runner can
edit arbitrary workbook cells: its current tool contract is oriented toward
reading rows and writing CSV. Real XLSX mutation should use the existing
Docker Python/Shell mode or a purpose-built workbook tool, with separate
agent workspaces and trusted grading. No model has been run, and no benchmark
success rate is claimed yet.

Upstream notes: SpreadsheetBench 2 describes `Debugging`,
`Financial_Model`, `Template`, `Visualization` and warns that both
input and gold files need recalculation. The official evaluation is the
source of truth, particularly for formula correctness and workbook behavior.
