"""Structured tools bound to a single sandboxed case directory."""
import csv
from pathlib import Path
from .xlsx import read_sheets

class StructuredTools:
    def __init__(self,case_dir):
        self.root=Path(case_dir).resolve(); self.calls=[]
        self.sheets=read_sheets(self.root/'input'/'procurement.xlsx')
    def _record(self,name,args,output):
        self.calls.append({'tool':name,'args':args,'result_size':len(output) if isinstance(output,list) else None})
        return output
    def list_sheets(self):
        return self._record('list_sheets',{},list(self.sheets))
    def read_rows(self,sheet,offset=0,limit=100):
        if sheet not in self.sheets: raise ValueError('unknown sheet')
        if not isinstance(offset,int) or not isinstance(limit,int) or offset<0 or limit<1 or limit>500: raise ValueError('invalid page')
        return self._record('read_rows',{'sheet':sheet,'offset':offset,'limit':limit},self.sheets[sheet][offset:offset+limit])
    def write_csv(self,rows):
        cols=['order_id','expected_cents','net_paid_cents','issues']
        if not isinstance(rows,list) or any(set(r)!=set(cols) for r in rows): raise ValueError('invalid schema')
        output=self.root/'output'/'anomalies.csv'; output.parent.mkdir(parents=True,exist_ok=True)
        with output.open('w',newline='',encoding='utf-8') as f:
            writer=csv.DictWriter(f,fieldnames=cols); writer.writeheader();writer.writerows(rows)
        return self._record('write_csv',{'row_count':len(rows)},str(output.relative_to(self.root)))
