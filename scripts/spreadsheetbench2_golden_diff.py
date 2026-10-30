"""Trusted-side diagnostic: compare official SpreadsheetBench input and golden XLSX.

Run ONLY on the host, never mount private/ or this script in the agent.
A golden diff is evidence of changes, not a substitute for official grading.
"""
import argparse
import json
from collections import Counter
from pathlib import Path
from openpyxl import load_workbook

def normalize(value):
    if value is None or isinstance(value,(str,int,float,bool)):
        return value
    return {"kind":type(value).__name__,
            "text":getattr(value,"text",None),
            "ref":getattr(value,"ref",None),
            "dt2D":getattr(value,"dt2D",None)}

def compare(case, max_examples=60):
    case=Path(case)
    inputs=list((case/"input").glob("*.xlsx"))
    golds=list((case/"private").glob("*.xlsx"))
    if len(inputs)!=1 or len(golds)!=1:
        raise ValueError(f"Expected one input and one golden workbook; found {len(inputs)} and {len(golds)}")
    a=load_workbook(inputs[0],read_only=False,data_only=False,keep_links=True)
    b=load_workbook(golds[0],read_only=False,data_only=False,keep_links=True)
    changes=[]
    by_sheet=Counter()
    kinds=Counter()
    try:
        for name in sorted(set(a.sheetnames)|set(b.sheetnames)):
            if name not in a or name not in b:
                by_sheet[name]+=1
                kinds["sheet_added_or_removed"]+=1
                changes.append({"sheet":name,"kind":"sheet_added_or_removed"})
                continue
            old,new=a[name],b[name]
            coords=set(old._cells)|set(new._cells)
            for row,col in sorted(coords):
                x=old._cells.get((row,col));y=new._cells.get((row,col))
                before=normalize(x.value) if x else None
                after=normalize(y.value) if y else None
                style_before=x.style_id if x else None
                style_after=y.style_id if y else None
                value_changed=before!=after
                style_changed=style_before!=style_after
                if not value_changed and not style_changed: continue
                by_sheet[name]+=1
                kind="value_or_formula" if value_changed else "style_only"
                kinds[kind]+=1
                if len(changes)<max_examples:
                    changes.append({"sheet":name,"cell":f"{old.cell(row,col).coordinate}",
                                    "kind":kind,"before":before,"after":after,
                                    "style_changed":style_changed})
        return {"case":str(case),"input":inputs[0].name,"golden":golds[0].name,
                "total_changed_cells":sum(by_sheet.values()),
                "by_sheet":dict(by_sheet),"change_kinds":dict(kinds),
                "examples":changes,"examples_truncated":sum(by_sheet.values())>len(changes),
                "notice":"This is a trusted-side structural diff, not official SpreadsheetBench grading or proof that every difference is required."}
    finally:
        a.close();b.close()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("case",type=Path)
    p.add_argument("--out",type=Path)
    p.add_argument("--max-examples",type=int,default=60)
    a=p.parse_args()
    result=compare(a.case,max(0,a.max_examples))
    if a.out:
        a.out.parent.mkdir(parents=True,exist_ok=True)
        a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False,indent=2,default=str))

if __name__=="__main__":main()
