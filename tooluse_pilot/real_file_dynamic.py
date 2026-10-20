"""Two-stage XLSX editing benchmark. The second-stage user request is revealed by a tool."""
import json,random,re
from pathlib import Path
from openpyxl import Workbook,load_workbook
from .real_file_task import Environment as Base,specs as basic_specs

def specs():
    items=basic_specs()
    items.insert(-1,{"type":"function","function":{"name":"receive_update","description":"Get the next user revision after the initial files are saved","parameters":{"type":"object","properties":{},"required":[],"additionalProperties":False}}})
    return items

def generate(seed,folder):
    p=Path(folder);p.mkdir(parents=True,exist_ok=False)
    rng=random.Random(seed)
    data=[("Alpha",99000+rng.randrange(2000),1,0),
          ("Beta",116000+rng.randrange(2000),1,1),
          ("Gamma",139000+rng.randrange(2000),1,1),
          ("Delta",149000+rng.randrange(2000),1,1)]
    rng.shuffle(data)
    wb=Workbook();v=wb.active;v.title="Vendors"
    v.append(["Vendor","Quote","Beijing","Shenzhen"])
    for row in data:v.append(row)
    d=wb.create_sheet("Decision")
    for row in (("Item","Value"),("Budget","160000"),("Required cities","Beijing"),("Recommended",""),("Price",""),("Eligible count","")):d.append(row)
    wb.save(p/"procurement.xlsx");wb.close()
    c={"id":f"file-dynamic-{seed}","family":"real_file_dynamic","input":{"workbook":"procurement.xlsx"},
       "task":"Using the workbook, recommend the lowest-priced Beijing supplier within the initial budget. Save Decision B4:B6 and report.txt first. Call receive_update for the later user requirements. Then revise all affected workbook and report values, save, and finish. Do not guess the revised requirements."}
    (p/"candidate.json").write_text(json.dumps(c,indent=2),encoding="utf-8")
    return c

def expected(wb,budget,cities):
    rows=list(wb["Vendors"].values)[1:]
    good=sorted((int(r[1]),str(r[0])) for r in rows if int(r[1])<=budget and
        all(int(r[2] if c=="Beijing" else r[3])==1 for c in cities))
    return (good[0][1],str(good[0][0]),str(len(good)))

def report_matches(text, vendor, amount):
    # Accept 100729 and 100,729, but not 1007290 or a substring of another amount.
    number=re.escape(str(int(amount)))
    grouped=re.escape(format(int(amount),','))
    return (re.search(r'(?<![A-Za-z0-9])'+re.escape(vendor)+r'(?![A-Za-z0-9])',text) is not None
            and re.search(r'(?<![0-9])(?:'+number+'|'+grouped+r')(?![0-9])',text) is not None)

class Environment(Base):
    def __init__(self,case,folder):
        super().__init__(case,folder);self.transitioned=False;self.initial_ok=False;self.old_report=None
    def call(self,name,args):
        if name=="receive_update":
            if self.finished or self.transitioned or args!={}:raise ValueError("update not available")
            e=expected(self.workbook,160000,["Beijing"])
            disk=load_workbook(self.path,read_only=True,data_only=True)
            try:actual=tuple(str(disk["Decision"][c].value or "") for c in ("B4","B5","B6"))
            finally:disk.close()
            rp=self.folder/"report.txt"
            text=rp.read_text(encoding="utf-8") if rp.exists() else ""
            self.initial_ok=self.saved and actual==e and report_matches(text,e[0],e[1])
            if not self.initial_ok:raise ValueError("initial deliverables are missing or incorrect")
            self.old_report=text
            self.transitioned=True
            d=self.workbook["Decision"];d["B2"]="130000";d["B3"]="Beijing,Shenzhen"
            self.workbook.save(self.path);self.saved=False
            out={"budget":130000,"cities":["Beijing","Shenzhen"]}
            self.calls.append({"tool":name,"args":{},"response":out})
            return out
        if name=="finish" and not self.transitioned:raise ValueError("update not received")
        return super().call(name,args)
    def score(self):
        wb=load_workbook(self.path,read_only=True,data_only=True)
        try:
            e=expected(wb,130000,["Beijing","Shenzhen"])
            d=wb["Decision"];actual=tuple(str(d[c].value or "") for c in ("B4","B5","B6"))
            correct_requirements=str(d["B2"].value)=="130000" and str(d["B3"].value)=="Beijing,Shenzhen"
        finally:wb.close()
        rp=self.folder/"report.txt";text=rp.read_text(encoding="utf-8") if rp.exists() else ""
        checks={"initial_delivered":self.initial_ok,"update_received":self.transitioned,
                "requirements":correct_requirements,"result":actual==e,
                "report":e[0] in text and e[1] in text and text!=self.old_report,
                "finished":self.finished}
        return {"success":all(checks.values()) and not self.invalid_actions,
                "checks":checks,"tool_calls":len(self.calls),"invalid_actions":self.invalid_actions}

def reference(case,folder):
    env=Environment(case,folder)
    try:
        for budget,cities in [(160000,["Beijing"]),(130000,["Beijing","Shenzhen"])]:
            x=expected(env.workbook,budget,cities)
            for cell,val in zip(("B4","B5","B6"),x):
                env.call("write_cell",{"sheet":"Decision","cell":cell,"value":val})
            env.call("save_workbook",{})
            env.call("write_report",{"text":f"Recommended {x[0]} for {x[1]} CNY; {x[2]} eligible."})
            if not env.transitioned:env.call("receive_update",{})
        env.call("finish",{})
        return env.score()
    finally:env.close()
