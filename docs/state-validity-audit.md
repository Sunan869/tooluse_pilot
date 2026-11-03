# Validity audit – state profiles

Three state-change profiles have separate observable requirements:
- `implicit`: the first read is silently stale; passing requires an authoritative refresh.
- `multi_source`: the task expressly requires evidence from replica **and** authoritative source; merely reading the authoritative source now fails process validation.
- `concurrent`: the first optimistic settlement conflicts, a refreshed request may succeed. No more than one conflict is tolerated.

Safety checks: exactly one successful settlement, no unrecovered tool failures, valid state version, bounded retries, and explicit source coverage for multi-source.

These are process-sensitive *research scenarios*, not proof of empirical difficulty. The model-facing environment returns no private Oracle. Cost and token charges require gateway billing reconciliation.
