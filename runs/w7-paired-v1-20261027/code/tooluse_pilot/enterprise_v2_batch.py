"""Offline generation and verification of enterprise settlement v2 candidates."""
import json
from pathlib import Path
from .enterprise_v2 import generate,reference,mutant

def make_batch(root,seeds=5,orders=8):
    root=Path(root)
    root.mkdir(parents=True,exist_ok=True)
    items=[]
    for seed in range(seeds):
        c=generate(seed,orders)
        good=reference(c)
        bad=mutant(c)
        if not good["success"] or bad["success"]:
            raise ValueError("invalid case: "+c["id"])
        folder=root/c["id"]
        folder.mkdir(exist_ok=False)
        (folder/"candidate.json").write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding="utf-8")
        items.append({"id":c["id"],"reference_success":True,"mutant_rejected":True})
    manifest={"count":len(items),"results":items,"paid_api_requests":0}
    (root/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    return manifest

def verify(root):
    root=Path(root)
    manifest=json.loads((root/"manifest.json").read_text(encoding="utf-8"))
    for row in manifest["results"]:
        c=json.loads((root/row["id"]/"candidate.json").read_text(encoding="utf-8"))
        if c["id"]!=row["id"] or not reference(c)["success"] or mutant(c)["success"]:
            raise ValueError("invalid candidate "+row["id"])
    return {"count":len(manifest["results"]),"verified":True}
