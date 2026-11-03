# W6 offline acceptance matrix

The dynamic procurement task has two mandatory file deliveries separated by a user revision. Its baseline is computed from the input workbook, not from a hard-coded winning supplier.

Run `python -m tooluse_pilot.cli verify-w6-mutations <case-folder> [<case-folder> ...]` to evaluate a reference and nine deterministic incorrect executions **without contacting a model**. Each mutation must be rejected by at least one explicit scored check; a mere failed overall score is insufficient.

Mutation categories: stale recommendation in both outputs; stale workbook; stale report; wrong eligible count; wrong price; report not updated after the revision; wrong vendor with revised price; obsolete budget restored in the workbook; and a report that correctly recommends the new vendor but separately endorses the old one.

This is an Oracle regression suite, **not nine independent observed LLM failures**. It confirms only the failure detection properties covered by these mutations. The previously observed Qwen W6 trace remains a separate empirical sample, and the successful multi-sheet run remains a separate control sample.

Do not use these mutation results to estimate model pass rates.
