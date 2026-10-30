"""Generate paired evidence-decision candidates for zero-cost offline validation."""
import json
from pathlib import Path
from .evidence_decision import SCENARIOS,generate,reference,mutants
def make_batch(root,seeds=2):
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    entries=[]
    for seed in range(seeds):
        for scenario in SCENARIOS:
            c=generate(seed,scenario)
            good=reference(c);bad=mutants(c)
            if not good["success"] or any(x["success"] for x in bad):raise ValueError(c["id"])
            folder=root/c["id"];folder.mkdir()
            (folder/"candidate.json").write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding="utf-8")
            entries.append({"candidate_id":c["id"],"scenario":scenario,"expected_outcome":good["expected_outcome"]})
    manifest={"count":len(entries),"paid_requests":0,"candidates":entries}
    (root/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    return manifest
def verify(root):
    root=Path(root);m=json.loads((root/"manifest.json").read_text(encoding="utf-8"))
    for entry in m["candidates"]:
        c=json.loads((root/entry["candidate_id"]/"candidate.json").read_text(encoding="utf-8"))
        good=reference(c)
        if not good["success"] or any(r["success"] for r in mutants(c)) or good["expected_outcome"]!=entry["expected_outcome"]:
            raise ValueError(entry["candidate_id"])
    return {"verified":True,"count":len(m["candidates"]),"paid_requests":0}
