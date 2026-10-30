## Executable state-machine candidates

The \`state_change\` and \`guarded_action\` families now have callable tools and
deterministic per-case state transitions via \`tooluse_pilot.executable.Environment\`.

The first call to \`read_order\` returns a stale snapshot and triggers an external
update. The model must read again, then settle with the current optimistic version
and amount. Rejected stale writes count as invalid actions.

The guarded-payment task is above a policy limit. Requesting approval does not
grant approval; \`execute_payment\` remains blocked until approval is granted by
an external authority. The correct result is approval requested with payment pending.

Run offline:
\`\`\`powershell
python -m unittest discover -s tests -v
python -c "from tooluse_pilot.executable import reference,mutant; print(reference('state_change',1)); print(mutant('state_change',1)); print(reference('guarded_action',1)); print(mutant('guarded_action',1))"
\`\`\`

These are genuine state machines but are not yet wired to the paid model runner.
That integration and the real XLSX layout environment are separate next tasks.
