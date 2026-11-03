"""Traceable partial numeric driver extraction from a real financial workbook.

Extract selected Organic, M&A, PF P&L, SOFR and LBO inputs by following actual
spreadsheet formula dependencies. No Python eval; unsupported syntax fails
closed. This does not recalculate the entire Excel workbook.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import re
from dataclasses import asdict
from pathlib import Path

from spreadsheetbench2_financial_constraints import normalize_excel, UnsupportedExpression, colnumber, colletters
from spreadsheetbench2_lbo_replay import Case, LBO, MA, key, replay_formula, validate_replay
from spreadsheetbench2_fault_factory import workbook

ORG = 'Ex 4 - Organic Operating Model'
PF = 'Ex 3 - PF P&L'
SOFR = 'Ex 7 - SOFR'
BS = 'Ex 10 - Balance Sheet'
CFS = 'Ex 12 - Cash Flow Statement'
COLS = 'QRSTU'
M_COLS = 'CDEFG'
P_COLS = 'CDEFG'
BLANK = object()


class RealDriverEvaluator:
    """Resolve a restricted numeric formula dependency graph with provenance."""

    def __init__(self, book, operating_case=1, ma_case=3, ma_switch=1):
        if operating_case not in (1, 2, 3) or ma_case not in (1, 2, 3) or ma_switch not in (0, 1):
            raise ValueError('invalid_case_selector')
        self.book = book
        self.overrides = {
            key(LBO, 'C9'): operating_case,
            key(LBO, 'C10'): ma_switch,
            key(MA, 'C4'): ma_case,
        }
        self.cache = {}
        self.active = []
        self.visited = {}
        self.notes = []
        self.cell_count_limit = 3500

    def get(self, sheet, addr):
        ref = key(sheet, addr)
        if ref in self.overrides:
            self.visited[ref] = {'mode': 'scenario_override', 'value': self.overrides[ref]}
            return self.overrides[ref]
        if ref in self.cache:
            return self.cache[ref]
        if ref in self.active:
            chain = ' -> '.join(f'{s}!{a}' for s, a in self.active[-8:])
            raise UnsupportedExpression('cycle_in_driver_graph:' + chain)
        if len(self.visited) > self.cell_count_limit:
            raise UnsupportedExpression('driver_dependency_graph_limit')
        row = self.book['cells'].get(sheet, {}).get(ref[1])
        if row is None:
            self.cache[ref] = BLANK
            return BLANK
        self.active.append(ref)
        try:
            formula = row.get('formula')
            if formula is not None:
                if ref == key(LBO, 'C36') and formula == "='Ex 10 - Balance Sheet'!D8:D8/C7":
                    value = self._numeric(self.get(BS, 'D8')) / self._numeric(self.get(LBO, 'C7'))
                    self.notes.append('Scalarized LBO C36 singleton legacy Excel array reference; not a generic array calculation')
                else:
                    value = self.evaluate(formula, sheet)
                mode = 'formula'
            elif row.get('value') is None:
                value = BLANK
                mode = 'empty'
            elif row.get('type') in (None, 'n'):
                try:
                    value = float(row['value'])
                except (ValueError, TypeError):
                    raise UnsupportedExpression(f'nonnumeric_input:{sheet}!{ref[1]}')
                mode = 'hardcoded_numeric'
            else:
                raise UnsupportedExpression(f'unsupported_cell_type:{sheet}!{ref[1]}:{row.get("type")}')
            if value is not BLANK and (not isinstance(value, (float, int)) or not math.isfinite(value)):
                raise UnsupportedExpression(f'nonfinite_or_nonnumeric:{sheet}!{ref[1]}')
            self.cache[ref] = value
            self.visited[ref] = {'mode': mode, 'formula': formula,
                                 'value': None if value is BLANK else value}
            return value
        finally:
            self.active.pop()

    @staticmethod
    def _numeric(value):
        if value is BLANK:
            return 0.
        if not isinstance(value, (int, float, bool)):
            raise UnsupportedExpression('non_numeric_arithmetic')
        return float(value)

    def evaluate(self, formula, sheet):
        if not isinstance(formula, str) or not formula.startswith('='):
            raise UnsupportedExpression('not_a_formula')
        expr = formula.lstrip('=+').replace('^', '**')
        expr = re.sub(r'(?<![A-Za-z0-9_.])((?:\d+\.\d+|\d+))%', r'(\1/100)', expr)
        expr = re.sub(r'(?<![<>=!])=(?!=)', '==', expr)
        try:
            tree = normalize_excel('=' + expr, sheet)
        except (SyntaxError, ValueError) as e:
            raise UnsupportedExpression('formula_parse_error:' + str(e)) from e

        def numeric(v):
            return self._numeric(v)

        def walk(node):
            if isinstance(node, ast.Expression):
                return walk(node.body)
            if isinstance(node, ast.Constant) and type(node.value) in (int, float, str, bool):
                return node.value
            if isinstance(node, ast.UnaryOp):
                v = numeric(walk(node.operand))
                if isinstance(node.op, ast.UAdd):
                    return v
                if isinstance(node.op, ast.USub):
                    return -v
            if isinstance(node, ast.BinOp):
                a, b = numeric(walk(node.left)), numeric(walk(node.right))
                if isinstance(node.op, ast.Add):
                    return a + b
                if isinstance(node.op, ast.Sub):
                    return a - b
                if isinstance(node.op, ast.Mult):
                    return a * b
                if isinstance(node.op, ast.Div):
                    return a / b
                if isinstance(node.op, ast.Pow) and abs(b) < 20:
                    return a ** b
            if isinstance(node, ast.Compare) and len(node.comparators) == 1:
                a, b = walk(node.left), walk(node.comparators[0])
                op = node.ops[0]
                if isinstance(op, ast.Eq):
                    return a == b
                if isinstance(op, ast.NotEq):
                    return a != b
                if isinstance(op, ast.Gt):
                    return a > b
                if isinstance(op, ast.Lt):
                    return a < b
                if isinstance(op, ast.LtE):
                    return a <= b
                if isinstance(op, ast.GtE):
                    return a >= b
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
                name = node.func.id.upper()
                if name == 'CELL' and len(node.args) == 2:
                    target, addr = (walk(x) for x in node.args)
                    return self.get(target, addr)
                if name == 'RANGE' and len(node.args) == 3:
                    target, start, end = (walk(x) for x in node.args)
                    a = re.fullmatch(r'([A-Z]{1,3})(\d+)', start)
                    b = re.fullmatch(r'([A-Z]{1,3})(\d+)', end)
                    if not a or not b:
                        raise UnsupportedExpression('invalid_range')
                    c0, c1 = colnumber(a[1]), colnumber(b[1])
                    r0, r1 = int(a[2]), int(b[2])
                    if c0 > c1 or r0 > r1 or (c1 - c0 + 1) * (r1 - r0 + 1) > 90:
                        raise UnsupportedExpression('invalid_or_large_range')
                    return [self.get(target, f'{colletters(c)}{r}')
                            for c in range(c0, c1 + 1) for r in range(r0, r1 + 1)]
                if name == 'IF' and len(node.args) == 3:
                    return walk(node.args[1] if walk(node.args[0]) else node.args[2])
                if name == 'CHOOSE' and len(node.args) >= 2:
                    idx = numeric(walk(node.args[0]))
                    if idx != int(idx) or not 1 <= idx < len(node.args):
                        raise UnsupportedExpression('choose_selector_not_1_to_N')
                    return walk(node.args[int(idx)])
                if name == 'INDEX' and len(node.args) == 2:
                    values = walk(node.args[0])
                    position = numeric(walk(node.args[1]))
                    if not isinstance(values, list) or int(position) != position or not 1 <= position <= len(values):
                        raise UnsupportedExpression('index_out_of_range')
                    return values[int(position) - 1]
                if name == 'MATCH' and len(node.args) == 3:
                    sought = numeric(walk(node.args[0]))
                    values = walk(node.args[1])
                    mode = numeric(walk(node.args[2]))
                    if not isinstance(values, list) or mode != 0:
                        raise UnsupportedExpression('match_only_exact')
                    for pos, val in enumerate(values, 1):
                        if val is not BLANK and math.isclose(numeric(val), sought, rel_tol=0, abs_tol=1e-10):
                            return pos
                    raise UnsupportedExpression('match_not_found')
                if name in ('SUM', 'AVERAGE', 'MIN', 'MAX'):
                    args = [walk(x) for x in node.args]
                    values = [numeric(x) for value in args
                              for x in (value if isinstance(value, list) else [value]) if x is not BLANK]
                    if name == 'SUM':
                        return sum(values)
                    if not values:
                        raise UnsupportedExpression('empty_aggregate')
                    if name == 'AVERAGE':
                        return sum(values) / len(values)
                    if name == 'MIN':
                        return min(values)
                    if name == 'MAX':
                        return max(values)
            raise UnsupportedExpression('unsupported_formula_node:' + type(node).__name__)

        return walk(tree)

    def number(self, sheet, addr):
        v = self.get(sheet, addr)
        if v is BLANK:
            raise UnsupportedExpression('driver_value_is_blank:' + sheet + '!' + addr)
        return self._numeric(v)


def derive_case(path, *, operating_case=1, ma_case=3, ma_switch=1):
    """Extract one five-year Case and a cell-linked driver provenance report."""
    path = Path(path)
    book = workbook(path)
    e = RealDriverEvaluator(book, operating_case, ma_case, ma_switch)
    fcf = tuple(e.number(LBO, col + '38') for col in COLS)
    ebitda = tuple(e.number(LBO, col + '23') for col in COLS)
    debt = tuple(e.number(MA, col + '80') for col in M_COLS)
    equity = tuple(e.number(MA, col + '81') for col in M_COLS)
    sofr = tuple(e.number(LBO, col + '52') for col in COLS)
    tax = tuple(e.number(LBO, col + '45') for col in COLS)
    if max(tax) - min(tax) > 1e-10:
        raise UnsupportedExpression('varying_tax_rates_replay_requires_per_year_rates')
    expected_ebitda = tuple(e.number(PF, col + '27') for col in P_COLS)
    for i, (a, b) in enumerate(zip(ebitda, expected_ebitda)):
        if not math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-7):
            raise ValueError('PF EBITDA and LBO EBITDA disagreed, year ' + str(2026 + i))
    scenario = Case(name=f'actual_drivers_op{operating_case}_ma{ma_case}_switch{ma_switch}',
        fcf=fcf, ebitda=ebitda, acq_debt=debt, acq_equity=equity, sofr=sofr,
        tax=tax[0],
        senior_initial=e.number(LBO, 'F18'), revolver_initial=e.number(LBO, 'F17'),
        pik_initial=e.number(LBO, 'F19'), revolver_limit=e.number(LBO, 'C41'),
        revolver_rate=e.number(LBO, 'C42'), unused_fee_rate=e.number(LBO, 'C43'),
        senior_rate=e.number(LBO, 'C47'), pik_rate=e.number(LBO, 'C52'),
        mandatory_rate=e.number(LBO, 'C49'), ma_switch=ma_switch,
        rollover=e.number(LBO, 'F20'), total_uses=e.number(LBO, 'F28'),
        exit_multiple=e.number(LBO, 'C20'), opening_cash=0.)
    trace = []
    for sheet, addr in ((LBO, 'Q38'), (LBO, 'Q23'), (MA, 'C80'), (MA, 'C81'), (LBO, 'Q52'),
                        (LBO, 'C41'), (LBO, 'C20'), (LBO, 'F18')):
        val = e.number(sheet, addr)
        trace.append({'cell':f'{sheet}!{addr}', 'value':val,
                      'origin':e.visited.get(key(sheet, addr), {}).get('mode')})
    report = {
        'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'workbook_driver_source':'computed_from_real_workbook_formula_graph',
        'not_full_workbook_recalculation':True,
        'selectors':{'operating_case':operating_case, 'ma_case':ma_case, 'ma_switch':ma_switch},
        'provenance_cells_visited':len(e.visited),
        'input_dependencies':trace,
        'warnings':sorted(set(e.notes)) + [
            'Opening_cash_is_assumed_zero: LBO P89 is empty in source workbook; not an observed balance',
            'LBO P91 initial net debt initialized from actual entry financing only for replay',
            'Scenario selectors are explicit overrides, not edits to the XLSX file'
        ],
        'case':asdict(scenario),
    }
    return scenario, report


def compare_actual_drivers(baseline, submission, operating_case=1, ma_case=3, ma_switch=1):
    before, trace_before = derive_case(baseline, operating_case=operating_case,
                                       ma_case=ma_case, ma_switch=ma_switch)
    after, trace_after = derive_case(submission, operating_case=operating_case,
                                     ma_case=ma_case, ma_switch=ma_switch)
    fields = ['fcf', 'ebitda', 'acq_debt', 'acq_equity', 'sofr']
    difference = {}
    for attr in fields:
        a, b = getattr(before, attr), getattr(after, attr)
        changed = [{'year':2026+i, 'reference':x, 'submitted':y}
                   for i, (x, y) in enumerate(zip(a, b))
                   if not math.isclose(x, y, abs_tol=1e-7, rel_tol=1e-10)]
        if changed:
            difference[attr] = changed
    return {
        'baseline_driver_trace':trace_before,
        'submission_driver_trace':trace_after,
        'driver_differences':difference,
        'common_driver_replay':{'baseline':before.name,'same_inputs':True},
        'warning':'Common-driver comparison deliberately isolates debt schedule formulas and does not prove unchanged upstream calculations',
    }


def replay_real_driver_matrix(baseline, submission):
    """18 control combinations: common-driver and per-workbook-driver comparisons."""
    baseline = Path(baseline)
    submission = Path(submission)
    base_book = workbook(baseline)
    sub_book = workbook(submission)
    outcomes = []
    for op_case in (1, 2, 3):
        for ma_case in (1, 2, 3):
            for switch in (0, 1):
                choices = {'operating_case':op_case, 'ma_case':ma_case, 'ma_switch':switch}
                label = f'op{op_case}_ma{ma_case}_switch{switch}'
                try:
                    base_input, base_trace = derive_case(baseline, **choices)
                    sub_input, sub_trace = derive_case(submission, **choices)
                    base_output = replay_formula(base_book, base_input)
                    common_output = replay_formula(sub_book, base_input)
                    endogenous_output = replay_formula(sub_book, sub_input)

                    def metrics(series):
                        check = validate_replay(series)
                        return {'hard_invariant_failures':check['hard_failure_count'],
                                'policy_or_liquidity_alerts':check['policy_alert_count'],
                                'fee_solver_converged':check['converged_all_years'],
                                'hard_failure_details':check['hard_invariant_failures'],
                                'policy_alert_details':check['policy_or_liquidity_alerts']}
                    different = {}
                    for field in ('fcf','ebitda','acq_debt','acq_equity','sofr'):
                        left = getattr(base_input, field)
                        right = getattr(sub_input, field)
                        changes = [{'year':2026+i,'reference':a,'submission':b}
                                   for i,(a,b) in enumerate(zip(left,right))
                                   if not math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-7)]
                        if changes:
                            different[field] = changes
                    outcomes.append({
                        'scenario':label,'selectors':choices,
                        'reference':metrics(base_output),
                        'submission_common_drivers':metrics(common_output),
                        'submission_own_drivers':metrics(endogenous_output),
                        'driver_differences':different,
                        'reference_case_values':asdict(base_input),
                        'submission_case_values':asdict(sub_input),
                        'dependency_cells_visited':{
                            'reference':base_trace['provenance_cells_visited'],
                            'submission':sub_trace['provenance_cells_visited']},
                        'warnings':base_trace['warnings']
                    })
                except (UnsupportedExpression,ValueError,ZeroDivisionError,OverflowError) as exc:
                    outcomes.append({'scenario':label,'selectors':choices,
                                     'status':'unverified','reason':str(exc)[:500]})
    evaluated = [v for v in outcomes if v.get('status') != 'unverified']
    return {
        'scope':'real_2026_2030_driver_formulas_plus_LBO_debt_subgraph',
        'workbook_hashes':{
            'reference':hashlib.sha256(baseline.read_bytes()).hexdigest(),
            'submission':hashlib.sha256(submission.read_bytes()).hexdigest()},
        'status':'supplemental_partial_workbook_replay',
        'scenario_count':len(outcomes),
        'evaluated_count':len(evaluated),
        'unverified_count':len(outcomes)-len(evaluated),
        'baseline_total_hard_failures':sum(v['reference']['hard_invariant_failures'] for v in evaluated),
        'submission_common_drivers_total_hard_failures':sum(
            v['submission_common_drivers']['hard_invariant_failures'] for v in evaluated),
        'submission_own_drivers_total_hard_failures':sum(
            v['submission_own_drivers']['hard_invariant_failures'] for v in evaluated),
        'scenario_count_with_changed_upstream_drivers':sum(bool(v['driver_differences']) for v in evaluated),
        'all_converged':all(v[which]['fee_solver_converged'] for v in evaluated
                             for which in ('reference','submission_common_drivers','submission_own_drivers')),
        'scenarios':outcomes,
        'limitations':[
            'No full Excel calculation, Excel Data Table, chart or shared formula validation',
            'Model control selectors are explicit overrides, not file mutations',
            'Opening cash is assumed zero; previous year cash policy remains unverified',
            'Subgraph replay still uses explicit simplifications and must not score all workbook errors',
            'M&A revenue from source baseline must have its known 16 duplicate-counting formulas normalized']
    }


def main():
    import argparse
    p = argparse.ArgumentParser(
        description='Trace workbook-derived LBO inputs and audit 18 real-driver control combinations, no API')
    p.add_argument('--baseline',type=Path,required=True,
                   help='Normalized baseline from the existing fault-injection dataset')
    p.add_argument('--submission',type=Path,required=True)
    p.add_argument('--mode',choices=['matrix','one'],default='matrix')
    p.add_argument('--operating-case',type=int,choices=[1,2,3],default=1)
    p.add_argument('--ma-case',type=int,choices=[1,2,3],default=3)
    p.add_argument('--ma-switch',type=int,choices=[0,1],default=1)
    p.add_argument('--out',type=Path,required=True)
    args = p.parse_args()
    if args.mode == 'matrix':
        result = replay_real_driver_matrix(args.baseline,args.submission)
        compact = {
            'scenario_count':result['scenario_count'],
            'evaluated_count':result['evaluated_count'],
            'unverified_count':result['unverified_count'],
            'baseline_total_hard_failures':result['baseline_total_hard_failures'],
            'submission_common_drivers_total_hard_failures':result['submission_common_drivers_total_hard_failures'],
            'submission_own_drivers_total_hard_failures':result['submission_own_drivers_total_hard_failures'],
            'scenario_count_with_changed_upstream_drivers':result['scenario_count_with_changed_upstream_drivers'],
            'all_converged':result['all_converged'],
            'status':result['status']
        }
    else:
        case, trace = derive_case(args.baseline,operating_case=args.operating_case,
                                  ma_case=args.ma_case,ma_switch=args.ma_switch)
        result = {'reference':trace,
                  'comparison':compare_actual_drivers(args.baseline,args.submission,
                      operating_case=args.operating_case,ma_case=args.ma_case,
                      ma_switch=args.ma_switch)}
        compact = {
            'selectors':trace['selectors'],'fcf':case.fcf,'ebitda':case.ebitda,
            'sofr':case.sofr,'acq_debt':case.acq_debt,
            'provenance_cells_visited':trace['provenance_cells_visited'],
            'driver_diff_categories':list(result['comparison']['driver_differences']),
            'warnings':trace['warnings']
        }
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(compact,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
