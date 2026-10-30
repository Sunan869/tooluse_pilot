# Repository contents

Source, tests, documentation, curated example inputs/oracles, and environment-variable based gateway examples are versioned. Copy a gateway example to a local configuration file and provide credentials through environment variables; do not commit real credentials.

Historical `runs/` output, raw requests/responses, workbooks, usage databases, logs, downloaded archives and local gateway configurations are local evidence, not distributable source. Ignoring or removing these paths from the Git index does not delete their local files. This change does not remove anything from earlier Git history.

Reusable Python/PowerShell/shell scripts, patches, code snapshots and text test fixtures inside `runs/` remain tracked at their existing paths. They are historical experiment utilities: some require the original local evidence/configuration and are not a self-contained public reproduction bundle. Review required inputs and output paths before running them; committing them does not authorize model/API calls.

Do not use blanket `git add -f runs` or force-add local configurations. To share a reproducible experiment, explicitly curate and sanitize its inputs and instructions outside the raw evidence directory first.
