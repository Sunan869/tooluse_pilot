"""Minimal XLSX tabular reader, built on stdlib OOXML. No Excel execution/macros."""
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile
from pathlib import PurePosixPath

S = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
P = '{http://schemas.openxmlformats.org/package/2006/relationships}'

def read_sheets(path):
    with ZipFile(path) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist():
            root=ET.fromstring(z.read('xl/sharedStrings.xml'))
            strings=[''.join(t.text or '' for t in si.iter(S+'t')) for si in root.findall(S+'si')]
        book=ET.fromstring(z.read('xl/workbook.xml'))
        relroot=ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        rels={r.get('Id'):r.get('Target') for r in relroot.findall(P+'Relationship')}
        result={}
        for sheet in book.find(S+'sheets'):
            name=sheet.get('name'); target=rels[sheet.get(R+'id')]
            member=target.lstrip('/') if target.startswith('/') else str(PurePosixPath('xl') / target)
            root=ET.fromstring(z.read(member))
            cells={}; maxr=maxc=0
            for c in root.iter(S+'c'):
                ref=c.get('r',''); match=re.match(r'([A-Z]+)(\d+)',ref)
                if not match: continue
                col=0
                for char in match.group(1): col=col*26+ord(char)-64
                row=int(match.group(2)); maxr=max(maxr,row); maxc=max(maxc,col)
                typ=c.get('t'); val=c.find(S+'v')
                if typ=='inlineStr':
                    value=''.join(t.text or '' for t in c.iter(S+'t'))
                elif val is None: value=None
                elif typ=='s': value=strings[int(val.text)]
                elif typ=='b': value=(val.text=='1')
                elif typ in ('str','e'): value=val.text
                else:
                    try: value=float(val.text); value=int(value) if value.is_integer() else value
                    except (ValueError,TypeError): value=val.text
                cells[(row,col)]=value
            data=[[cells.get((row,col)) for col in range(1,maxc+1)] for row in range(1,maxr+1)]
            if not data: result[name]=[]; continue
            cols=[str(x) if x is not None else '' for x in data[0]]
            result[name]=[dict(zip(cols,r)) for r in data[1:] if any(v is not None for v in r)]
        return result
