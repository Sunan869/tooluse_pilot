"""Five-year LBO debt/cash/exit subgraph replay with explicit assumptions.

Not an Excel recalculation. Inputs to P&L, M&A, SOFR and financing are synthetic;
only narrowly selected formulas from the actual workbook are evaluated.
Original cyclic revolver-unused-fee equations are solved to a fixed point.
Cash retention and capital structure assumptions are explicit; policy-dependent
outcomes are diagnostic, not an automatic economic correctness verdict.
"""
from __future__ import annotations

import ast
import math
import re
from dataclasses import asdict, dataclass, replace

from spreadsheetbench2_financial_constraints import (
    normalize_excel, UnsupportedExpression, colnumber, colletters)
from spreadsheetbench2_fault_factory import workbook

LBO = "Ex 1 - LBO"
MA = "Ex 5 - M&A"
COLS = "QRSTU"
MA_COLS = "CDEFG"
EXIT_COLUMNS = ("Y", "Z", "AA", "AB", "AC")
REPORT_ROWS = (54, 55, 56, 57, 58, 59, 60, 63, 64, 65, 67, 68,
               70, 73, 74, 75, 76, 78, 80, 83, 84, 85, 87, 89, 91, 92)


def key(sheet, address):
    return (sheet, address.upper().replace('$', ''))


class FormulaEngine:
    """Read-only numeric evaluator for the few verified schedule formulas."""

    def __init__(self, book, constants):
        self.book, self.constants = book, constants
        self.cache, self.pending = {}, set()

    def get(self, sheet, address):
        target = key(sheet, address)
        if target in self.constants:
            return self.constants[target]
        if target in self.cache:
            return self.cache[target]
        if target in self.pending:
            raise UnsupportedExpression(f"circular_without_guess:{sheet}!{address}")
        c = self.book['cells'].get(sheet, {}).get(target[1])
        if c is None:
            raise UnsupportedExpression(f"missing_cell:{sheet}!{address}")
        self.pending.add(target)
        try:
            if c.get('formula'):
                val = self.evaluate(c['formula'], sheet)
            elif c.get('type') in (None, 'n') and c.get('value') is not None:
                val = float(c['value'])
            else:
                raise UnsupportedExpression(f"not_numeric:{sheet}!{address}")
            if not isinstance(val, (int, float)) or not math.isfinite(val):
                raise UnsupportedExpression(f"nonfinite:{sheet}!{address}")
            self.cache[target] = val
            return val
        finally:
            self.pending.remove(target)

    def evaluate(self, formula, sheet):
        tree = _expression_ast(formula, sheet)

        def walk(n):
            if isinstance(n, ast.Expression):
                return walk(n.body)
            if isinstance(n, ast.Constant) and type(n.value) in (int, float, str, bool):
                return n.value
            if isinstance(n, ast.UnaryOp):
                v = walk(n.operand)
                if isinstance(n.op, ast.USub):
                    return -v
                if isinstance(n.op, ast.UAdd):
                    return v
                raise UnsupportedExpression('unary_operator')
            if isinstance(n, ast.BinOp):
                a, b = walk(n.left), walk(n.right)
                if isinstance(n.op, ast.Add):
                    return a+b
                if isinstance(n.op, ast.Sub):
                    return a-b
                if isinstance(n.op, ast.Mult):
                    return a*b
                if isinstance(n.op, ast.Div):
                    return a/b
                if isinstance(n.op, ast.Pow):
                    if abs(b)>10 or abs(a)>1e9:
                        raise UnsupportedExpression('exponent_limits')
                    return a**b
                raise UnsupportedExpression('binary_operator')
            if isinstance(n, ast.Compare) and len(n.comparators)==1:
                a, b = walk(n.left), walk(n.comparators[0])
                op = n.ops[0]
                if isinstance(op, ast.Eq):
                    return a==b
                if isinstance(op, ast.NotEq):
                    return a!=b
                if isinstance(op, ast.Gt):
                    return a>b
                if isinstance(op, ast.Lt):
                    return a<b
                if isinstance(op, ast.GtE):
                    return a>=b
                if isinstance(op, ast.LtE):
                    return a<=b
                raise UnsupportedExpression('comparison_operator')
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and not n.keywords:
                fn = n.func.id.upper()
                if fn=='CELL' and len(n.args)==2:
                    return self.get(walk(n.args[0]), walk(n.args[1]))
                if fn=='RANGE' and len(n.args)==3:
                    target_sheet, begin, end = (walk(x) for x in n.args)
                    a = re.fullmatch(r'([A-Z]{1,3})(\d+)', begin)
                    b = re.fullmatch(r'([A-Z]{1,3})(\d+)', end)
                    if a is None or b is None:
                        raise UnsupportedExpression('invalid_range')
                    lc, rc = colnumber(a[1]), colnumber(b[1])
                    lr, rr = int(a[2]), int(b[2])
                    if lc>rc or lr>rr or (rc-lc+1)*(rr-lr+1)>100:
                        raise UnsupportedExpression('unsupported_range')
                    return [self.get(target_sheet, f'{colletters(c)}{r}')
                            for c in range(lc,rc+1) for r in range(lr,rr+1)]
                if fn=='IF' and len(n.args)==3:
                    return walk(n.args[1] if walk(n.args[0]) else n.args[2])
                args = [walk(x) for x in n.args]
                if fn=='SUM':
                    return sum(v for arg in args for v in (arg if isinstance(arg,list) else [arg]))
                if fn=='MIN':
                    return min(args)
                if fn=='MAX':
                    return max(args)
                raise UnsupportedExpression(f'unsupported_function:{fn}')
            raise UnsupportedExpression(f'unsupported_ast:{type(n).__name__}')
        return walk(tree)


def _expression_ast(formula, sheet):
    """Convert the supported Excel syntax into a safe, non-executable AST."""
    expression = re.sub(r'(?<![<>=!])=(?!=)', '==',
                        formula.lstrip('=+').replace('^','**'))
    return normalize_excel('='+expression, sheet)


@dataclass(frozen=True)
class Case:
    name: str
    fcf: tuple[float, ...]
    ebitda: tuple[float, ...]
    acq_debt: tuple[float, ...]
    acq_equity: tuple[float, ...]
    sofr: tuple[float, ...]
    tax: float = .22
    senior_initial: float = 400.
    revolver_initial: float = 0.
    pik_initial: float = 0.
    revolver_limit: float = 120.
    revolver_rate: float = .04
    unused_fee_rate: float = .005
    senior_rate: float = .04
    pik_rate: float = .0625
    mandatory_rate: float = 0.
    ma_switch: int = 1
    rollover: float = 20.
    total_uses: float = 650.
    exit_multiple: float = 12.
    opening_cash: float = 0.

    def __post_init__(self):
        for field in ('fcf','ebitda','acq_debt','acq_equity','sofr'):
            if len(getattr(self,field)) != 5:
                raise ValueError(f'5 annual values required: {field}')
        if self.revolver_limit < 0 or self.mandatory_rate < 0:
            raise ValueError('invalid_financing_control')
        if self.ma_switch not in (0,1):
            raise ValueError('ma_switch must be 0 or 1')


def cases():
    default = Case('base', (220,260,300,340,370), (260,285,310,335,365),
                   (25,25,25,25,25), (10,10,10,10,10), (.04,.045,.04,.035,.035))
    return (
        default,
        replace(default,name='mandatory_amort',mandatory_rate=.15,fcf=(90,130,180,220,260)),
        replace(default,name='ma_off',ma_switch=0,fcf=(130,160,190,220,260)),
        replace(default,name='low_cash',fcf=(5,15,20,50,75),revolver_limit=85.),
        replace(default,name='negative_cash',fcf=(-60,-35,10,25,75),revolver_limit=55.),
        replace(default,name='zero_revolver',fcf=(130,160,200,230,270),revolver_limit=0.),
        replace(default,name='high_fee',fcf=(30,45,70,115,150),unused_fee_rate=.035),
        replace(default,name='positive_sweep',fcf=(560,600,650,700,750)),
        replace(default,name='entry_revolver_funded',revolver_initial=35.,revolver_limit=140.),
    )


def _values(book, controls, year_col, guess, previous):
    external = dict(controls)
    external.update(previous)
    external[key(LBO, year_col+'68')] = guess
    return FormulaEngine(book,external)


def replay_formula(book, case):
    """Evaluate selected LBO schedule rows through five years with cyclic fee solver."""
    controlled={
        key(LBO,'C10'):case.ma_switch, key(LBO,'C41'):case.revolver_limit,
        key(LBO,'C42'):case.revolver_rate,key(LBO,'C43'):case.unused_fee_rate,
        key(LBO,'C47'):case.senior_rate,key(LBO,'C49'):case.mandatory_rate,
        key(LBO,'C52'):case.pik_rate,key(LBO,'C20'):case.exit_multiple,
        key(LBO,'F17'):case.revolver_initial,key(LBO,'F18'):case.senior_initial,
        key(LBO,'F19'):case.pik_initial,key(LBO,'F20'):case.rollover,
        key(LBO,'F28'):case.total_uses,key(LBO,'P89'):case.opening_cash,
        key(LBO,'P91'):case.revolver_initial+case.senior_initial+case.pik_initial-case.opening_cash,
    }
    prev={}
    years=[]
    for i,(col,macol,retcol) in enumerate(zip(COLS,MA_COLS,EXIT_COLUMNS)):
        ext=dict(controlled)
        ext.update({key(LBO,col+'38'):case.fcf[i],
                    key(LBO,col+'52'):case.sofr[i],
                    key(LBO,col+'45'):case.tax,
                    key(LBO,col+'23'):case.ebitda[i],
                    key(LBO,col+'29'):case.ebitda[i]*.8,
                    key(MA,macol+'80'):case.acq_debt[i],
                    key(MA,macol+'81'):case.acq_equity[i]})
        guess=max(0.,case.revolver_limit-case.revolver_initial)*case.unused_fee_rate
        converged=False
        for it in range(1,101):
            engine=_values(book,ext,col,guess,prev)
            ending_revolver=engine.get(LBO,col+'65')
            actual_fee=FormulaEngine(book,{**ext,**prev,key(LBO,col+'65'):ending_revolver}).get(LBO,col+'68')
            if abs(actual_fee-guess) < 1e-10:
                converged=True
                guess=actual_fee
                break
            guess=actual_fee
        engine=_values(book,ext,col,guess,prev)
        fields={r:engine.get(LBO,f'{col}{r}') for r in REPORT_ROWS}
        fields[68]=actual_fee
        for row,value in fields.items():
            prev[key(LBO,f'{col}{row}')]=value
        prev.update(ext)
        years.append({'year':2026+i,'column':col,'return_column':retcol,
                      'fee_iterations':it,'fee_converged':converged,
                      'fee_residual':abs(actual_fee-guess),
                      'rows':{str(k):v for k,v in fields.items()}})
    src=FormulaEngine(book,{**controlled,**prev})
    sources={'sponsor_equity':src.get(LBO,'F21'),'reported_total_sources':src.get(LBO,'F22')}
    returns=[]
    for i,(col,ret) in enumerate(zip(COLS,EXIT_COLUMNS)):
        e=FormulaEngine(book,{**controlled,**prev})
        returns.append({'year':2026+i,'equity_value':e.get(LBO,ret+'22'),
                        'exit_gross_debt_row20':e.get(LBO,ret+'20'),
                        'exit_cash_row21':e.get(LBO,ret+'21'),
                        'ma_equity_addon':e.get(LBO,ret+'25'),
                        'invested_equity':e.get(LBO,ret+'26'),
                        'moic':e.get(LBO,ret+'28'),
                        'irr':e.get(LBO,ret+'29')})
    return {'case':case.name,'case_input':asdict(case),'years':years,
            'sources':sources,'returns':returns,
            'limits':{'excel_equivalent_calculation':False,
                      'assumptions_are_synthetic':True,
                      'cash_policy_not_determined':True}}


def validate_replay(result):
    """Check low-assumption accounting identities and separately policy risks."""
    case=result['case_input']
    violations=[];alerts=[]
    def check(name,year,error,tol=1e-7):
        if abs(error)>tol:
            violations.append({'year':year,'rule':name,'difference':round(error,8)})
    prev_rev=case['revolver_initial'];prev_sen=case['senior_initial']
    prev_pik=case['pik_initial']
    running_cash=case['opening_cash']
    for i,year in enumerate(result['years']):
        row={int(k):v for k,v in year['rows'].items()}
        yr=year['year']
        check('revolver_begin_rollforward',yr,row[63]-prev_rev)
        check('revolver_ending_balance',yr,row[65]-(row[63]+row[64]))
        check('senior_begin_rollforward',yr,row[73]-prev_sen)
        check('senior_ending_balance',yr,row[76]-(row[73]+row[74]+row[75]))
        check('pik_begin_rollforward',yr,row[83]-prev_pik)
        check('pik_ending_balance',yr,row[85]-(row[83]+row[84]))
        check('revolver_fee_fixed_point',yr,row[68]-(case['revolver_limit']-row[65])*case['unused_fee_rate'])
        check('cash_available_after_revolver',yr,row[70]-(row[60]+row[64]))
        check('cash_after_all_debt_repayments',yr,row[80]-(row[70]+row[74]+row[75]))
        check('cash_after_pik',yr,row[89]-(row[80]+row[84]))
        check('cash_before_debt',yr,row[60]-(row[54]-row[55]+row[56]-row[57]-row[58]-row[59]))
        check('revolver_interest',yr,row[67]-(case['sofr'][i]+case['revolver_rate'])*row[63])
        check('senior_interest',yr,row[78]-row[73]*(case['sofr'][i]+case['senior_rate']))
        check('pik_interest',yr,row[87]-row[83]*(case['sofr'][i]+case['pik_rate']))
        check('total_interest',yr,row[92]-(row[67]+row[78]+row[87]))
        if row[65]>case['revolver_limit']+1e-6:
            alerts.append({'year':yr,'risk':'revolver_capacity_exceeded','balance':row[65]})
        if row[65]<-1e-6 or row[76]<-1e-6 or row[85]<-1e-6:
            alerts.append({'year':yr,'risk':'negative_debt_balance'})
        if row[75]>1e-6:
            alerts.append({'year':yr,'risk':'accelerated_repayment_is_a_draw'})
        if row[89]<-1e-6:
            alerts.append({'year':yr,'risk':'unfunded_cash_shortfall','cash':row[89]})
        if case['ma_switch']==0 and abs(row[59])>1e-8:
            alerts.append({'year':yr,'risk':'ma_switch_debt_funding_not_disabled','debt_spend':row[59]})
        if case['ma_switch']==0 and abs(result['returns'][i]['ma_equity_addon'])>1e-8:
            alerts.append({'year':yr,'risk':'ma_switch_equity_funding_not_disabled',
                           'equity_spend':result['returns'][i]['ma_equity_addon']})
        running_cash += row[89]
        gross=row[65]+row[76]+row[85]
        check('exit_debt_must_be_gross_when_cash_added_separately',yr,
              result['returns'][i]['exit_gross_debt_row20']-gross)
        if abs(result['returns'][i]['exit_cash_row21']-running_cash)>1e-6:
            alerts.append({'year':yr,'risk':'exit_cash_not_cumulative_under_retention_assumption',
                           'expected_if_retained':round(running_cash,6),
                           'observed':round(result['returns'][i]['exit_cash_row21'],6)})
        prev_rev,prev_sen,prev_pik=row[65],row[76],row[85]
    src=result['sources']
    check('sources_balance',2025,sum([case['revolver_initial'],case['senior_initial'],
          case['pik_initial'],case['rollover'],src['sponsor_equity']])-case['total_uses'])
    check('reported_total_sources',2025,src['reported_total_sources']-case['total_uses'])
    return {'case':case['name'],'hard_invariant_failures':violations,
            'policy_or_liquidity_alerts':alerts,
            'hard_failure_count':len(violations),'policy_alert_count':len(alerts),
            'converged_all_years':all(y['fee_converged'] for y in result['years'])}


def independent_ledger(case):
    """Reference financing policy, calculated without reading any XLSX formulas.

    Hypotheses: unused revolver fee based on ending unused commitment;
    debt interest paid in cash, no PIK capitalization, repay revolver before
    senior debt, mandatory senior amortization before discretionary paydown,
    all positive annual residuals are retained as cash rather than dividends.
    """
    rev=case.revolver_initial;sen=case.senior_initial;pik=case.pik_initial
    retained=case.opening_cash;years=[]
    for i in range(5):
        rate=case.sofr[i]
        interest=rev*(rate+case.revolver_rate)+sen*(rate+case.senior_rate)+pik*(rate+case.pik_rate)
        debt_spend=case.acq_debt[i]*case.ma_switch
        fee_guess=max(case.revolver_limit-rev,0)*case.unused_fee_rate
        for step in range(1,101):
            cash=case.fcf[i]-interest*(1-case.tax)-fee_guess-debt_spend
            if case.revolver_limit==0:
                delta=0.
            elif cash<0:
                delta=min(-cash,max(0,case.revolver_limit-rev))
            else:
                delta=-min(cash,rev)
            end_rev=rev+delta
            fee_new=max(case.revolver_limit-end_rev,0)*case.unused_fee_rate
            if abs(fee_new-fee_guess)<1e-10:
                fee_guess=fee_new
                break
            fee_guess=fee_new
        available=cash+delta
        mand=-min(case.mandatory_rate*sen,sen)
        surplus_after_mand=available+mand
        extra=-min(max(0,surplus_after_mand),max(0,sen+mand))
        end_sen=sen+mand+extra
        residual=surplus_after_mand+extra
        if residual>=0:
            retained+=residual
        years.append({'year':2026+i,'revolver_end':end_rev,
                      'senior_end':end_sen,'pik_end':pik,
                      'fee':fee_guess,'debt_spend':debt_spend,
                      'mandatory':mand,'extra':extra,'cash_residual':residual,
                      'retained_cash_if_no_distribution':retained,
                      'gross_debt':end_rev+end_sen+pik,
                      'equity_if_cash_retained':case.ebitda[i]*case.exit_multiple-(end_rev+end_sen+pik)+retained,
                      'liquidity_gap':max(0,-residual),
                      'solved_fee':step<=100})
        rev,sen=end_rev,end_sen
    sponsor=case.total_uses-sum((case.revolver_initial,case.senior_initial,
                                 case.pik_initial,case.rollover))
    return {'source_of_funds_sponsor_equity':sponsor,'years':years,
            'policy':'full_cash_retention_and_debt_priority_no_dividends',
            'cash_policy_is_hypothetical':True}


def reference_differences(model_result,case):
    reference=independent_ledger(case)
    details=[]
    for actual,expected in zip(model_result['years'],reference['years']):
        f={int(r):v for r,v in actual['rows'].items()}
        diffs={}
        for name,observed,goal in (
            ('revolver_end',f[65],expected['revolver_end']),
            ('senior_end',f[76],expected['senior_end']),
            ('fee',f[68],expected['fee']),
            ('cash_residual',f[89],expected['cash_residual']),
            ('gross_debt',f[65]+f[76]+f[85],expected['gross_debt'])):
            if abs(observed-goal)>1e-6:
                diffs[name]={'model':round(observed,6),
                             'independent_policy':round(goal,6)}
        details.append({'year':expected['year'],'differences':diffs,
                        'independent_liquidity_gap':expected['liquidity_gap']})
    return {'reference_policy':reference['policy'],
            'model_sponsor_equity':model_result['sources']['sponsor_equity'],
            'policy_sponsor_equity':reference['source_of_funds_sponsor_equity'],
            'years_with_differences':sum(bool(y['differences']) for y in details),
            'detail':details,
            'status':'diagnostic_not_proof_of_actual_workbook_cash_policy'}


def compare_books(source,submission,with_details=False):
    reference=workbook(source)
    proposed=workbook(submission)
    cases_summary=[]
    for case in cases():
        try:
            a=replay_formula(reference,case)
            b=replay_formula(proposed,case)
            reference_summary=validate_replay(a)
            proposal_summary=validate_replay(b)
            item={'case':case.name,'reference':reference_summary,
                  'submission':proposal_summary,
                  'baseline_vs_independent_policy':reference_differences(a,case),
                  'submission_vs_independent_policy':reference_differences(b,case)}
            if with_details:
                item['reference_rows']=a['years']
                item['submission_rows']=b['years']
                item['reference_returns']=a['returns']
                item['submission_returns']=b['returns']
            cases_summary.append(item)
        except (UnsupportedExpression,ZeroDivisionError,OverflowError,ValueError) as e:
            cases_summary.append({'case':case.name,'unverified_reason':str(e)})
    return {'scope':'five_year_LBO_debt_cash_exit_subgraph_under_synthetic_drivers',
            'cases':cases_summary,
            'limitations':['No full Excel recalculation',
                           'External P&L, M&A and interest-rate inputs are synthetic',
                           'Cyclic revolver fees solved by fixed-point iteration',
                           'Cash retention is a hypothetical policy, not an established workbook assumption',
                           'Policy alerts are not automatic scoring penalties']}


def summary(report):
    rows=[]
    for item in report['cases']:
        if 'unverified_reason' in item:
            rows.append({'scenario':item['case'],
                         'unverified_reason':item['unverified_reason']})
            continue
        a,b=item['reference'],item['submission']
        rows.append({
            'scenario':item['case'],
            'baseline_hard_failures':a['hard_failure_count'],
            'submission_hard_failures':b['hard_failure_count'],
            'baseline_policy_alerts':a['policy_alert_count'],
            'submission_policy_alerts':b['policy_alert_count'],
            'baseline_policy_ledger_mismatch_years':item['baseline_vs_independent_policy']['years_with_differences'],
            'submission_policy_ledger_mismatch_years':item['submission_vs_independent_policy']['years_with_differences'],
            'fixed_point_converged':a['converged_all_years'] and b['converged_all_years'],
        })
    completed=[r for r in rows if 'unverified_reason' not in r]
    return {
        'scenario_count':len(rows),'evaluated_count':len(completed),
        'unverified_count':len(rows)-len(completed),
        'baseline_total_hard_failures':sum(r['baseline_hard_failures'] for r in completed),
        'submission_total_hard_failures':sum(r['submission_hard_failures'] for r in completed),
        'baseline_total_policy_alerts':sum(r['baseline_policy_alerts'] for r in completed),
        'submission_total_policy_alerts':sum(r['submission_policy_alerts'] for r in completed),
        'fee_solver_all_cases_converged':all(r['fixed_point_converged'] for r in completed),
        'scenarios':rows,
        'policy_condition':'model_executed_with_synthetic_drivers_and_hypothetical_full_cash_retention',
        'status':'supplemental_numeric_evidence_not_authoritative_excel_grading'
    }


def main(argv=None):
    import argparse
    import hashlib
    import json
    from pathlib import Path
    parser=argparse.ArgumentParser(
        description='Independent five-year LBO debt/cash/exit subgraph replay')
    parser.add_argument('--dataset',type=Path,default=Path('runs/ssb2-injected-01'))
    parser.add_argument('--baseline',type=Path,
                        help='Explicit reference workbook; defaults to generated normalized baseline')
    parser.add_argument('--submission',type=Path,required=True)
    parser.add_argument('--report',type=Path,required=True,help='JSON report destination')
    args=parser.parse_args(argv)
    baseline=args.baseline or (args.dataset/'private'/'normalized_baseline.xlsx')
    if not baseline.is_file() or not args.submission.is_file():
        parser.error('Baseline or submission XLSX is missing')
    manifest=args.dataset/'manifest.json'
    if args.baseline is None and manifest.is_file():
        metadata=json.loads(manifest.read_text(encoding='utf-8'))
        digest=hashlib.sha256(baseline.read_bytes()).hexdigest()
        if digest!=metadata.get('baseline_sha256'):
            parser.error('Baseline SHA-256 differs from dataset manifest')
    data=compare_books(baseline,args.submission,with_details=False)
    data['summary']=summary(data)
    data['reference_workbook']=str(baseline)
    data['submission_workbook']=str(args.submission)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(data,ensure_ascii=False,indent=2),
                           encoding='utf-8')
    print(json.dumps(data['summary'],ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
