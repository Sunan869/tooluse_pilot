"""Counterfactual variants that change the correct settlement path, not just random values."""
import copy
import json
from pathlib import Path
from .enterprise_v2 import reference, mutant

def variants(base):
    if base["family"]!="enterprise_settlement_v2":
        raise ValueError("enterprise_settlement_v2 required")
    unapproved=[o["id"] for o in base["environment"]["orders"] if not o["approved"]]
    if len(unapproved)<2:raise ValueError("need at least two initially blocked orders")
    for ordinal,(target,delay) in enumerate([(unapproved[0],2),(unapproved[1],3)]):
        case=copy.deepcopy(base)
        case["id"]=base["id"]+"-cf-"+str(ordinal)
        case["environment"]["approval_callbacks"]={target:delay}
        case["mutation"]={"kind":"approval_callback_switch","target":target,"poll_threshold":delay}
        yield case

def evaluate(base):
    original=reference(base)
    if not original["success"]:raise ValueError("base reference must pass")
    signature=lambda score:tuple(sorted(k for k,v in score["order_states"].items() if v=="settled"))
    observed={signature(original)}
    summaries=[]
    for case in variants(base):
        good=reference(case)
        bad=mutant(case)
        sig=signature(good)
        if not good["success"] or bad["success"]:
            raise ValueError("reference/mutant validation failed: "+case["id"])
        if sig in observed:raise ValueError("mutation did not alter the expected settlement path")
        observed.add(sig)
        summaries.append((case,{"id":case["id"],"mutation":case["mutation"],
                                "settled_ids":list(sig),"reference_success":True,
                                "mutant_rejected":True}))
    return summaries

def create(source,outdir):
    base=json.loads(Path(source).read_text(encoding="utf-8"))
    checked=evaluate(base)
    root=Path(outdir)
    root.mkdir(parents=True,exist_ok=False)
    entries=[]
    for case,item in checked:
        folder=root/case["id"]
        folder.mkdir()
        (folder/"candidate.json").write_text(json.dumps(case,ensure_ascii=False,indent=2),encoding="utf-8")
        entries.append(item)
    report={"source":str(source),"generated":len(entries),"paid_requests":0,"variants":entries}
    (root/"manifest.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    return report

def verify(outdir):
    root=Path(outdir)
    manifest=json.loads((root/"manifest.json").read_text(encoding="utf-8"))
    candidates=[]
    for entry in manifest["variants"]:
        case=json.loads((root/entry["id"]/"candidate.json").read_text(encoding="utf-8"))
        good=reference(case)
        if not good["success"] or mutant(case)["success"]:
            raise ValueError("failed offline oracle validation")
        actual=sorted(k for k,v in good["order_states"].items() if v=="settled")
        if actual!=entry["settled_ids"]:raise ValueError("expected path mismatch")
        candidates.append(tuple(actual))
    if len(candidates)!=len(set(candidates)):raise ValueError("duplicate correct paths")
    return {"verified":True,"count":len(candidates),"paid_requests":0}
