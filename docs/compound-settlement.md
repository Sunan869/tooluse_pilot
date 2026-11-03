# Compound settlement candidate

Combines a stale reporting replica, an authoritative primary, a concurrent
version update during the first settlement attempt, and idempotency-key
semantics. Failed optimistic-lock attempts do not create a charge. The first
successful settlement registers a key; repeated identical requests with the
same key are deduplicated and cannot charge twice. Different keys cannot cause
a second settlement.

Offline generation and regression tests:

```powershell
python -m unittest discover -s tests -v
python -m tooluse_pilot.cli generate-compound runs/compound-001 --seeds 10
python -m tooluse_pilot.cli verify-compound runs/compound-001
```

Once verified, optionally run ONE paid model experiment:

```powershell
python -m tooluse_pilot.cli run-candidate runs/compound-001/compound_settlement-0/candidate.json --config gateway.models.json --model gpt --max-requests 12 --max-tools 30
```

Offline validity does not guarantee model difficulty. No API calls are made
unless run-candidate is explicitly invoked.
