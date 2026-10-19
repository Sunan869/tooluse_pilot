"""Offline construction of executable advanced state-profile candidates."""
import json
from pathlib import Path
from .research import generate, validate
from .state_profiles import PROFILES, reference, mutant

def make_profiles(root, seeds=range(10)):
    root=Path(root)
    root.mkdir(parents=True,exist_ok=True)
    records=[]
    for profile in PROFILES:
        for seed in seeds:
            case=generate("state_change",seed)
            case["profile"]=profile
            case["id"]=f"state_change-{profile}-{seed}"
            case["task"]="Reconcile the order and settle using the latest authoritative version. A reporting replica may lag; changes may occur concurrently. Handle recoverable version conflicts without duplicate settlement."
            ref=reference(profile,seed)
            bad=mutant(profile,seed)
            if not ref["success"] or bad["success"]:
                raise AssertionError((profile,seed,ref,bad))
            folder=root/case["id"]
            folder.mkdir(exist_ok=False)
            (folder/"candidate.json").write_text(json.dumps(case,ensure_ascii=False,indent=2),encoding="utf-8")
            records.append({"id":case["id"],"profile":profile,"reference_success":True,"mutant_rejected":True})
    manifest={"count":len(records),"results":records,"paid_api_requests":0}
    (root/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return manifest

def verify_profiles(root):
    root=Path(root)
    manifest=json.loads((root/"manifest.json").read_text(encoding="utf-8"))
    for item in manifest["results"]:
        case=json.loads((root/item["id"]/"candidate.json").read_text(encoding="utf-8"))
        profile=case["profile"];seed=int(case["seed"])
        if case["family"]!="state_change" or not reference(profile,seed)["success"] or mutant(profile,seed)["success"]:
            raise AssertionError(item["id"])
    return {"count":len(manifest["results"]),"verified":True}
