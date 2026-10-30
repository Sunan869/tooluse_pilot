"""Offline enterprise candidate generation with reference and mutant checks."""
import json
from pathlib import Path
from .enterprise import generate,reference,mutant
def make_batch(root,n=5,orders=8):
    root=Path(root);root.mkdir(parents=True,exist_ok=True);items=[]
    for seed in range(n):
        c=generate(seed,orders)
        good=reference(c);bad=mutant(c)
        if not good["success"] or bad["success"]:raise ValueError(f"invalid seed {seed}")
        folder=root/c["id"];folder.mkdir(exist_ok=False)
        (folder/"candidate.json").write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding="utf-8")
        items.append({"id":c["id"],"reference_success":True,"mutant_rejected":True})
    data={"count":len(items),"results":items,"paid_api_requests":0}
    (root/"manifest.json").write_text(json.dumps(data,indent=2),encoding="utf-8")
    return data
def verify(root):
    root=Path(root);d=json.loads((root/"manifest.json").read_text(encoding="utf-8"))
    for item in d["results"]:
        c=json.loads((root/item["id"]/"candidate.json").read_text(encoding="utf-8"))
        if not reference(c)["success"] or mutant(c)["success"]:raise ValueError(item["id"])
    return {"verified":True,"count":len(d["results"])}
