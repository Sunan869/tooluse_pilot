"""Paired clean/conflict candidates with stable reference & mutant checks."""
import json
from pathlib import Path
from .evidence_conflict import generate,reference,mutant

def generate_pair(root,seeds=3):
    if seeds<1:raise ValueError("positive seeds required")
    root=Path(root)
    root.mkdir(parents=True,exist_ok=False)
    out=[]
    for seed in range(seeds):
        for mode in ("clean","conflict"):
            case=generate(seed,mode)
            good=reference(case);bad=mutant(case)
            if not good["success"] or bad["success"]:raise ValueError("invalid oracle")
            folder=root/case["id"];folder.mkdir()
            (folder/"candidate.json").write_text(json.dumps(case,indent=2),encoding="utf-8")
            out.append({"candidate_id":case["id"],"mode":mode,"path":str(folder/"candidate.json")})
    report={"candidate_count":len(out),"paid_requests":0,"candidates":out}
    (root/"manifest.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
    return report

def verify(root):
    root=Path(root)
    manifest=json.loads((root/"manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["candidates"]:
        candidate=root/entry["candidate_id"]/"candidate.json"
        case=json.loads(candidate.read_text(encoding="utf-8"))
        if not reference(case)["success"] or mutant(case)["success"]:raise ValueError(case["id"])
    return {"verified":True,"candidate_count":len(manifest["candidates"]),"paid_requests":0}
