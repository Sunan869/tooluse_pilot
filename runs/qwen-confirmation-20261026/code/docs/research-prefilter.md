# Offline research candidate factory

This is a **research prefilter**, not a finished benchmark task. It intentionally
does **not** run a model and does not measure actual difficulty.

Three families generate distinct deterministic witnesses:

- \`state_change\`: an order changes after it was read; the expected
  action must use the latest value and version.
- \`guarded_action\`: an irreversible payment is disallowed until approval.
- \`workbook_layout\`: a current table and nearby archive table have
  confusable structure, but only one is a valid source.

Every candidate contains a task description, environment state, a trigger,
a hidden expected outcome and a known failure pattern. The validator
independently recomputes the expected outcome and checks one representative
incorrect behavior is rejected. These toy environments **do not yet expose**
callable APIs, Excel files, or model-facing tools; that requires the next
integration phase.

Run, without model credentials or API cost:

\`\`\`powershell
python -m tooluse_pilot.research generate runs/research-candidates --seeds 10
python -m tooluse_pilot.research verify runs/research-candidates
python -m unittest discover -s tests -v
\`\`\`

Do not commit private usage logs, keys, or generated candidates with user data.
The offline prefilter tests validity, **not** model failure rate; select
candidate families for later runnable environment implementations and GPT tests.
