import sys,unittest
from pathlib import Path
from openpyxl import Workbook
sys.path.insert(0,str(Path(__file__).parent/'code'))
from tooluse_pilot.reservation_task import calculate

def fixture():
    w=Workbook();w.remove(w.active)
    data={'Orders':[['ID','Price','Qty','Beijing','Shenzhen','Status','Group'],['A',10,9,1,1,'active','X'],['B',10,4,1,1,'active','X'],['C',10,3,1,1,'active','X']],
    'Corrections':[['ID','Quantity']], 'Priority':[['ID','Rank'],['A',1],['B',3],['C',2]],'Dependencies':[['ID','Requires']],
    'Policy':[['Key','Value'],['Max per order',100],['Cities','Beijing'],['Budget',70]],'Limits':[['Group','Capacity'],['X',70]],
    'Commitments':[['ID','Amount'],['A',30]],'Withdrawn':[['ID']], 'Stage':[['Key','Value'],['Current',1]]}
    for s,rows in data.items():
        sh=w.create_sheet(s)
        for row in rows:sh.append(row)
    return w

class Semantics(unittest.TestCase):
    def test_locked_amount_and_reserved_before_rank(self):
        w=fixture();summary,rows=calculate(w)
        self.assertEqual(summary,['70','2','B','40'])
        self.assertEqual(rows,[['B',40,1,'selected'],['C',30,0,'group_cap'],['A',30,1,'retained']])
    def test_recursive_release_and_cancelled_precedence(self):
        w=fixture();w['Commitments'].append(['B',20]);w['Commitments'].append(['C',10]);w['Dependencies'].append(['B','A']);w['Dependencies'].append(['C','B']);w['Withdrawn'].append(['A'])
        summary,rows=calculate(w);self.assertEqual(summary,['0','0','NONE','0']);self.assertEqual([r[3] for r in rows],['dependency','dependency','cancelled'])
    def test_equal_budget_is_allowed(self):
        w=fixture();w['Limits']['B2']=100;w['Policy']['B4']=70
        self.assertEqual(calculate(w)[1][1][3],'budget');self.assertEqual(calculate(w)[0][0],'70')
    def test_retained_exempt_new_city_and_price(self):
        w=fixture();w['Orders']['D2']=0;w['Orders']['B2']=1000
        self.assertEqual(calculate(w)[1][-1],['A',30,1,'retained'])

if __name__=='__main__':unittest.main()
