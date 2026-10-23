"""Multi-sheet, two-stage W6 XLSX reconciliation benchmark."""
import json,random,re
from pathlib import Path
from openpyxl import Workbook,load_workbook

def generate(seed,folder):
    root=Path(folder);root.mkdir(parents=True,exist_ok=False)
    wb=Workbook();orders=wb.active;orders.title="Orders"
    orders.append(["ID","Price","Qty","Beijing","Shenzhen","Status"])
    rows=[("Alpha",1000,8,1,0,"active"),("Beta",1800,3,1,1,"active"),("Gamma",2200,2,1,1,"active"),("Delta",2600,2,1,1,"active"),("Dormant",9000,10,1,1,"inactive")]
    random.Random(seed).shuffle(rows)
    for row in rows:orders.append(row)
    corr=wb.create_sheet("Corrections");corr.append(["ID","Quantity"])
    for name,qty in (("Beta",3),("Gamma",2),("Delta",2)):corr.append([name,qty])
    pol=wb.create_sheet("Policy")
    for row in (("Key","Value"),("Max per order",10000),("Cities","Beijing")):pol.append(row)
    summ=wb.create_sheet("Summary")
    for row in (("Metric","Value"),("Total",None),("Count",None),("Winner",None),("Winner amount",None)):summ.append(row)
    wb.save(root/"reconciliation.xlsx");wb.close()
    case={"id":f"w6-reconcile-{seed}","family":"real_w6_reconciliation","scenario":seed%3,
          "input":{"workbook":"reconciliation.xlsx"},
          "task":"Read Orders, Corrections, Policy. Active orders only; correction quantity replaces original. Filter by all required cities and per-order maximum. Save Summary B2:B5 as sum of eligible values, count, highest-value order ID, highest order amount (ties alphabetical). Write report.txt explicitly containing total, count, winner, amount. Then call receive_update; Policy and Corrections change. Re-read them and revise ALL outputs, save again, finish."}
    (root/"candidate.json").write_text(json.dumps(case,indent=2),encoding="utf-8")
    return case

def oracle(wb):
    corr={str(n):int(q) for n,q in list(wb["Corrections"].values)[1:]}
    maximum=int(wb["Policy"]["B2"].value)
    cities=str(wb["Policy"]["B3"].value).split(",")
    eligible={}
    for name,price,qty,bj,sz,status in list(wb["Orders"].values)[1:]:
        if status!="active" or ("Beijing" in cities and not bj) or ("Shenzhen" in cities and not sz):continue
        total=int(price)*corr.get(str(name),int(qty))
        if total<=maximum:eligible[str(name)]=total
    if not eligible:raise ValueError("no eligible orders")
    winner=min(eligible,key=lambda name:(-eligible[name],name))
    return tuple(map(str,(sum(eligible.values()),len(eligible),winner,eligible[winner])))

def report(answer):
    return f"Total: {answer[0]}; Count: {answer[1]}; Winner: {answer[2]}; Amount: {answer[3]}."

def report_valid(text,answer):
    for label,value in zip(("Total","Count","Winner","Amount"),answer):
        mentions=re.findall(r"(?i)\\b"+label+r"\\s*:\\s*([A-Za-z0-9-]+)",text)
        if not mentions or any(m!=value for m in mentions):return False
    return True

def specs():
    s={"type":"string"}
    def tool(name,props=None):
        return {"type":"function","function":{"name":name,"description":name.replace("_"," "),"parameters":{"type":"object","properties":props or {},"required":list((props or {}).keys()),"additionalProperties":False}}}
    return [tool("list_sheets"),tool("read_sheet",{"sheet":s}),tool("write_summary",{"cell":s,"value":s}),tool("save_workbook"),tool("write_report",{"text":s}),tool("receive_update"),tool("finish")]
