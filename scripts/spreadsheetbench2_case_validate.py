"""Standalone, private strict Golden XLSX verifier (stdlib only).

Usage: python private/validate.py --submission output/input.xlsx
Never expose this file, oracle.json or answer.xlsx to the tested model.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

NS={"x":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
SHEET_XML=re.compile(r"xl/worksheets/sheet\d+\.xml$")

def digest(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as fp:
        for chunk in iter(lambda:fp.read(1<<20),b""):h.update(chunk)
    return h.hexdigest()

def xml_signature(node):
    return (node.tag,tuple(sorted(node.attrib.items())),
            (node.text or "").strip(),tuple(xml_signature(c) for c in node))

def extract(path):
    with zipfile.ZipFile(path) as z:
        parts=z.namelist()
        if len(set(parts))!=len(parts):raise ValueError("Duplicate ZIP part names")
        if z.testzip() is not None:raise ValueError("Corrupt XLSX ZIP member")
        if "xl/workbook.xml" not in parts:raise ValueError("Missing workbook.xml")
        cells_by_sheet,structure={},{}
        for part in parts:
            data=z.read(part)
            if SHEET_XML.fullmatch(part):
                root=ET.fromstring(data)
                cells={}
                for c in root.findall(".//x:sheetData/x:row/x:c",NS):
                    f=c.find("x:f",NS)
                    v=c.find("x:v",NS)
                    inline=c.find("x:is",NS)
                    cells[c.attrib["r"]]={
                        "formula":(f.text or "") if f is not None else None,
                        "formula_attributes":dict(sorted(f.attrib.items())) if f is not None else None,
                        "value":v.text if v is not None else None,
                        "inline_string":"".join(inline.itertext()) if inline is not None else None,
                        "type":c.attrib.get("t"),"style_id":c.attrib.get("s","0")}
                cells_by_sheet[part]=cells
                block=root.find("x:sheetData",NS)
                if block is not None:root.remove(block)
                structure[part]=xml_signature(root)
            elif part.endswith(".xml") or part.endswith(".rels"):
                structure[part]=xml_signature(ET.fromstring(data))
            else:
                structure[part]=hashlib.sha256(data).hexdigest()
        return {"parts":sorted(parts),"sheets":cells_by_sheet,"structure":structure}

def validate(case,submission):
    case=Path(case).resolve()
    private=case/"private"
    oracle=json.loads((private/"oracle.json").read_text(encoding="utf-8"))
    answer=private/"answer.xlsx"
    input_file=case/"input.xlsx"
    for file,expected in ((answer,oracle["answer_sha256"]),
                          (input_file,oracle["input_sha256"])):
        if digest(file)!=expected:
            raise ValueError("Trusted case file changed: "+file.name)
    expected=extract(answer)
    output=extract(Path(submission).resolve())
    issues=[]
    if expected["parts"]!=output["parts"]:issues.append("package_part_names_changed")
    if expected["structure"]!=output["structure"]:
        issues.append("non_cell_structure_or_style_table_changed")
    injected={(e["sheet_part"],e["cell"]) for e in oracle["injections"]}
    wrong,unexpected=[],[]
    for part in sorted(set(expected["sheets"])|set(output["sheets"])):
        left=expected["sheets"].get(part,{})
        right=output["sheets"].get(part,{})
        for addr in sorted(set(left)|set(right)):
            if left.get(addr)==right.get(addr):continue
            label=f"{part}!{addr}"
            if (part,addr) in injected:wrong.append(label)
            else:unexpected.append(label)
    return {"pass":not wrong and not unexpected and not issues,
            "target_count":len(injected),
            "correct_targets":len(injected)-len(wrong),
            "wrong_targets":wrong,
            "unexpected_count":len(unexpected),
            "unexpected_edits":unexpected[:60],
            "integrity_issues":issues,
            "note":"Strict Golden contents/structure comparison, not Excel recalculation or formula equivalence."}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case",type=Path,default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--submission",type=Path,required=True)
    args=parser.parse_args()
    try:result=validate(args.case,args.submission)
    except (OSError,ValueError,zipfile.BadZipFile,ET.ParseError,KeyError) as exc:
        result={"pass":False,"error":str(exc)[:500]}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if not result["pass"]:raise SystemExit(1)

if __name__=="__main__":
    main()
