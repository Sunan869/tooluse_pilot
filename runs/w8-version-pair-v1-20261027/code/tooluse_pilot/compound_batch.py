"""Generate and validate multi-source + concurrent + idempotent candidates offline."""
import json
from pathlib import Path
from .compound import generate,reference,mutant

def batch(root,n=10):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    items=[]
    for seed in range(n):
        case=generate(seed)
        ok=reference(case);bad=mutant(case)
        if not ok["success"] or bad["success"]:raise ValueError(f"invalid case {seed}")
        folder=root/case["id"];folder.mkdir(exist_ok=False)
        (folder/"candidate.json").write_text(json.dumps(case,ensure_ascii=False,indent=2),encoding="utf-8")
        items.append({"id":case["id"],"reference_success":True,"mutant_rejected":True})
    result={"count":n,"results":items,"paid_api_requests":0}
    (root/"manifest.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    return result

def verify(root):
    root=Path(root);items=json.loads((root/"manifest.json").read_text(encoding="utf-8"))["results"]
    for item in items:
        case=json.loads((root/item["id"]/"candidate.json").read_text(encoding="utf-8"))
        if case["id"]!=item["id"] or not reference(case)["success"] or mutant(case)["success"]:
            raise ValueError(item["id"])
    return {"verified":True,"count":len(items)}
