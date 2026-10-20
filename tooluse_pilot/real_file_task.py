"""Real XLSX editing challenge. Tools operate on actual files under one case folder."""
import json
import hashlib
import random
from pathlib import Path
from openpyxl import Workbook, load_workbook

def specs():
    def f(name,desc,props=None,required=None):
        return {"type":"function","function":{"name":name,"description":desc,
           "parameters":{"type":"object","properties":props or {},"required":required or [],"additionalProperties":False}}}
    s={"type":"string"};i={"type":"integer"}
    return [
      f("inspect_sheet","Inspect a sheet's rows and values",{"sheet":s},["sheet"]),
      f("write_cell","Write a cell in the deliverable XLSX",{"sheet":s,"cell":s,"value":{"type":"string"}},["sheet","cell","value"]),
      f("save_workbook","Save modified workbook to disk"),
      f("write_report","Save the final recommendation to a UTF-8 file",{"text":s},["text"]),
      f("finish","Declare the work finished")]

def generate(seed,root):
    root=Path(root);root.mkdir(parents=True,exist_ok=False)
    rng=random.Random(seed)
    vendors=[("Alpha",125000,1,1),("Beta",112000,1,0),("Gamma",147000,1,1),
             ("Delta",138000,1,1),("Epsilon",101000,0,1)]
    rng.shuffle(vendors)
    wb=Workbook();w=wb.active;w.title="Vendors"
    w.append(["Vendor","Quote","Beijing","Shenzhen"])
    for row in vendors:w.append(row)
    s=wb.create_sheet("Decision")
    s.append(["Item","Value"]);s.append(["Budget","150000"]);s.append(["Required cities","Beijing,Shenzhen"])
    s.append(["Recommended",""]);s.append(["Price",""]);s.append(["Eligible count",""])
    wb.save(root/"procurement.xlsx");wb.close()
    case={"id":f"file-procurement-{seed}","family":"real_file_procurement",
      "task":"Use the XLSX workbook in the workspace. Only vendors serving both Beijing and Shenzhen, costing no more than 150000, qualify. Recommend the lowest-priced qualifying vendor (alphabetical tie-break). Write the vendor, price and eligible count to Decision!B4:B6, save the workbook, and write report.txt stating the recommended vendor and price. Call finish when complete.",
      "input":{"workbook":"procurement.xlsx"}}
    (root/"candidate.json").write_text(json.dumps(case,ensure_ascii=False,indent=2),encoding="utf-8")
    return case

class Environment:
    def __init__(self,case,folder):
        self.folder=Path(folder);self.path=self.folder/case["input"]["workbook"]
        if not self.path.is_file():raise FileNotFoundError(self.path)
        self.workbook=load_workbook(self.path)
        self.calls=[];self.saved=False;self.reported=False;self.finished=False
        self.invalid_actions=0
        self.initial_digest=hashlib.sha256(self.path.read_bytes()).hexdigest()
    def call(self,name,args):
        if not isinstance(args,dict):raise ValueError("arguments required")
        if self.finished:raise ValueError("already finished")
        if name=="inspect_sheet" and set(args)=={"sheet"}:
            if args["sheet"] not in self.workbook.sheetnames:raise ValueError("unknown sheet")
            ws=self.workbook[args["sheet"]]
            out={"sheet":args["sheet"],"rows":[[c.value for c in row] for row in ws.iter_rows()]}
        elif name=="write_cell" and set(args)=={"sheet","cell","value"}:
            if args["sheet"]!="Decision" or args["cell"] not in ("B4","B5","B6") or not isinstance(args["value"],str):
                raise ValueError("only output Decision cells may be modified")
            self.workbook["Decision"][args["cell"]]=args["value"];out={"ok":True}
            self.saved=False
        elif name=="save_workbook" and args=={}:
            self.workbook.save(self.path);self.saved=True;out={"saved":True}
        elif name=="write_report" and set(args)=={"text"} and isinstance(args["text"],str):
            (self.folder/"report.txt").write_text(args["text"],encoding="utf-8")
            self.reported=True;out={"saved":True}
        elif name=="finish" and args=={}:
            self.finished=True;out={"ok":True}
        else:raise ValueError("invalid tool")
        self.calls.append({"tool":name,"args":dict(args),"response":out})
        return out
    def score(self):
        # Reopen disk artifacts, never trust in-memory cells or claimed actions.
        wb=load_workbook(self.path,read_only=True,data_only=True)
        try:
            vendors=list(wb["Vendors"].values)[1:]
            eligible=sorted([(int(r[1]),str(r[0])) for r in vendors
                if int(r[1])<=150000 and int(r[2])==1 and int(r[3])==1])
            price,vendor=eligible[0]
            actual=[str(wb["Decision"][c].value or "") for c in ("B4","B5","B6")]
        finally:wb.close()
        report=(self.folder/"report.txt").read_text(encoding="utf-8") if (self.folder/"report.txt").is_file() else ""
        checks={"workbook_changed_on_disk":hashlib.sha256(self.path.read_bytes()).hexdigest()!=self.initial_digest,
                "vendor":actual[0]==vendor,"price":actual[1]==str(price),
                "eligible_count":actual[2]==str(len(eligible)),
                "report_vendor":vendor in report,"report_price":str(price) in report,
                "finished":self.finished}
        return {"success":all(checks.values()) and self.invalid_actions==0,
                "checks":checks,"tool_calls":len(self.calls),
                "invalid_actions":self.invalid_actions}
    def close(self):
        self.workbook.close()

def reference(case,folder):
    env=Environment(case,folder)
    try:
        rows=env.call("inspect_sheet",{"sheet":"Vendors"})["rows"][1:]
        eligible=sorted((int(r[1]),str(r[0])) for r in rows if int(r[1])<=150000 and int(r[2]) and int(r[3]))
        amount,vendor=eligible[0]
        for cell,value in zip(("B4","B5","B6"),(vendor,str(amount),str(len(eligible)))):
            env.call("write_cell",{"sheet":"Decision","cell":cell,"value":value})
        env.call("save_workbook",{})
        env.call("write_report",{"text":f"Recommended: {vendor}; price: {amount} CNY."})
        env.call("finish",{})
        return env.score()
    finally:env.close()
