"""Create an unhinted audit candidate from the existing derived repair fixture.

No workbook mutation. Gold/Oracle remain private and unavailable to the agent.
This targeted Oracle checks a known defect set, not exhaustive workbook audit.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

INSTRUCTION = (
    "Audit the supplied financial workbook for demonstrably incorrect calculation "
    "formulas. Identify and repair errors you can substantiate from the surrounding "
    "model structure. Preserve formulas and cell contents that you cannot justify "
    "changing. Submit an edited XLSX to output/ using the original filename. "
    "Do not merely describe the errors; deliver the corrected workbook."
)

def filehash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def create(source, destination):
    source=Path(source).resolve()
    destination=Path(destination).resolve()
    if destination.exists():
        raise FileExistsError(destination)
    input_files=list((source/"input").glob("*.xlsx"))
    oracle_file=source/"private"/"oracle.json"
    if len(input_files)!=1 or not oracle_file.is_file():
        raise ValueError("Expected one existing input workbook and private oracle")
    oracle=json.loads(oracle_file.read_text(encoding="utf-8"))
    if oracle["kind"]!="minimal_repair" or len(oracle["expected_formulas"])!=16:
        raise ValueError("Expected vetted 16-target minimal repair fixture")
    if filehash(input_files[0])!=oracle["source_sha256"]:
        raise ValueError("Source workbook hash mismatch")
    destination.mkdir(parents=True)
    shutil.copytree(source/"input", destination/"input")
    shutil.copytree(source/"private", destination/"private")
    (destination/"output").mkdir()
    (destination/"instruction.md").write_text(INSTRUCTION,encoding="utf-8")
    metadata={
        "parent_case":str(source),
        "condition":"blind_audit_candidate",
        "source_sha256":filehash(input_files[0]),
        "oracle_scope":"16_known_MA_subtotal_repairs_only",
        "qualification":"Not exhaustive accuracy of all workbook errors; candidate only"
    }
    (destination/"private"/"study_metadata.json").write_text(
        json.dumps(metadata,ensure_ascii=False,indent=2),encoding="utf-8")
    return {"workspace":str(destination),"input_sha256":metadata["source_sha256"],
            "instruction":INSTRUCTION,"oracle_scope":metadata["oracle_scope"],
            "status":"candidate_requires_review"}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",type=Path,default=Path("runs/ssb2-derived-01/repair"))
    parser.add_argument("--out",type=Path,default=Path("runs/ssb2-derived-blind-01"))
    args=parser.parse_args()
    print(json.dumps(create(args.source,args.out),ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
