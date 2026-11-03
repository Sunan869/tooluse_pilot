"""Reference solution for self-testing, not given to evaluated models."""
import json
from pathlib import Path
from .core import compute
from .tools import StructuredTools
from .xlsx import read_sheets

def run(case_dir,mode='structured'):
    root=Path(case_dir)
    if mode=='structured':
        tools=StructuredTools(root)
        pages={}
        for name in tools.list_sheets():
            pages[name]=[]; offset=0
            while True:
                batch=tools.read_rows(name,offset,25)
                pages[name].extend(batch)
                if len(batch)<25:break
                offset+=25
        rows=compute(pages)
        tools.write_csv(rows)
        (root/'trace.json').write_text(json.dumps({'mode':mode,'calls':tools.calls},indent=2),encoding='utf-8')
        return root/'trace.json'
    if mode=='python_shell':
        # Reference programmatic execution; models get only instruction + input files.
        from csv import DictWriter
        sheets=read_sheets(root/'input'/'procurement.xlsx')
        rows=compute(sheets)
        out=root/'output'/'anomalies.csv'; out.parent.mkdir(exist_ok=True)
        with out.open('w',newline='',encoding='utf-8') as f:
            writer=DictWriter(f,fieldnames=['order_id','expected_cents','net_paid_cents','issues']);writer.writeheader();writer.writerows(rows)
        return None
    raise ValueError('unsupported mode')
