"""Independent numeric witness checks for a restricted set of financial invariants.

This is NOT a full Excel formula evaluator or a workbook recalculation engine.
For each curated business rule, evaluate candidate formulas against multiple
synthetic, explicitly stated precedent-value scenarios. Only formulas in the
strict supported grammar receive a determinate pass/fail.
"""
from __future__ import annotations

import ast
import collections
import math
import re
from pathlib import Path

from spreadsheetbench2_fault_factory import SHEETS, specs, workbook, sha

REF = re.compile(r"(?<![A-Za-z0-9_])(?:(?:'(?P<quoted>[^']+)'|(?P<bare>[A-Za-z_][A-Za-z0-9_ .-]*))!)?(?P<a>\$?[A-Z]{1,3}\$?[0-9]+)(?::(?P<b>\$?[A-Z]{1,3}\$?[0-9]+))?")
ADDRESS = re.compile(r"([A-Z]{1,3})([0-9]+)$")


class UnsupportedExpression(Exception):
    pass


def cellkey(sheet, address):
    return sheet, address.replace('$', '').upper()


def normalize_excel(formula, active_sheet):
    if not isinstance(formula, str) or not formula.startswith('='):
        raise UnsupportedExpression('not_a_formula')
    expression = formula.lstrip('=+')

    def replace(match):
        sheet = match.group('quoted') or match.group('bare') or active_sheet
        first = match.group('a').replace('$', '')
        last = match.group('b')
        if last:
            return f'RANGE({sheet!r},{first!r},{last.replace("$", "")!r})'
        return f'CELL({sheet!r},{first!r})'

    expression = REF.sub(replace, expression)
    if '!' in expression or ';' in expression or '[' in expression:
        raise UnsupportedExpression('unsupported_reference_or_syntax')
    try:
        return ast.parse(expression, mode='eval')
    except SyntaxError as e:
        raise UnsupportedExpression(f'unsupported_excel_syntax:{e.msg}') from e


def colnumber(s):
    value = 0
    for char in s:
        value = value * 26 + ord(char) - 64
    return value


def colletters(number):
    chars = []
    while number:
        number, rem = divmod(number-1, 26)
        chars.append(chr(65+rem))
    return ''.join(reversed(chars))


def expand_range(sheet, start, end, mapping):
    a, b = ADDRESS.fullmatch(start), ADDRESS.fullmatch(end)
    if not a or not b:
        raise UnsupportedExpression('invalid_range')
    c0, c1 = colnumber(a.group(1)), colnumber(b.group(1))
    r0, r1 = int(a.group(2)), int(b.group(2))
    if c0>c1 or r0>r1 or (c1-c0+1)*(r1-r0+1)>40:
        raise UnsupportedExpression('reversed_or_oversized_range')
    values = []
    for col in range(c0,c1+1):
        for row in range(r0,r1+1):
            key = sheet, f'{colletters(col)}{row}'
            if key not in mapping:
                raise UnsupportedExpression(f'unknown_input:{key[0]}!{key[1]}')
            values.append(mapping[key])
    return values


def eval_excel(formula, sheet, inputs):
    """Evaluate only numeric +/-/*//, SUM and CHOOSE over supplied numeric probes."""
    tree = normalize_excel(formula, sheet)

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int,float,str)):
            return node.value
        if isinstance(node, ast.BinOp):
            a,b = walk(node.left), walk(node.right)
            if not isinstance(a,(int,float)) or not isinstance(b,(int,float)):
                raise UnsupportedExpression('non_numeric_arithmetic')
            if isinstance(node.op, ast.Add): return a+b
            if isinstance(node.op, ast.Sub): return a-b
            if isinstance(node.op, ast.Mult): return a*b
            if isinstance(node.op, ast.Div):
                if b==0: raise UnsupportedExpression('division_by_zero')
                return a/b
            raise UnsupportedExpression('binary_operator')
        if isinstance(node, ast.UnaryOp):
            val=walk(node.operand)
            if not isinstance(val,(int,float)):
                raise UnsupportedExpression('non_numeric_unary')
            if isinstance(node.op,ast.UAdd):return val
            if isinstance(node.op,ast.USub):return -val
            raise UnsupportedExpression('unary_operator')
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and not node.keywords:
            fn=node.func.id.upper()
            args=[walk(v) for v in node.args]
            if fn=='CELL' and len(args)==2:
                if not all(isinstance(a,str) for a in args):
                    raise UnsupportedExpression('invalid_cell_arguments')
                key=cellkey(*args)
                if key not in inputs: raise UnsupportedExpression(f'unknown_input:{key[0]}!{key[1]}')
                return inputs[key]
            if fn=='RANGE' and len(args)==3:
                return expand_range(args[0],args[1],args[2],inputs)
            if fn=='SUM':
                flattened=[]
                for value in args:
                    if isinstance(value,list):flattened.extend(value)
                    else:flattened.append(value)
                if not all(isinstance(v,(int,float)) for v in flattened):
                    raise UnsupportedExpression('non_numeric_sum')
                return sum(flattened)
            if fn=='CHOOSE' and len(args)>=2:
                choice=args[0]
                if not isinstance(choice,(int,float)) or int(choice)!=choice or not 1<=choice<len(args):
                    raise UnsupportedExpression('invalid_choice')
                return args[int(choice)]
            raise UnsupportedExpression(f'unsupported_function:{fn}')
        raise UnsupportedExpression(f'unsupported_ast:{type(node).__name__}')
    return walk(tree)


def probe_values(rule, index):
    """Generate independently curated business witnesses, including distractors."""
    mechanism, sheet, addr = rule['mechanism'], rule['sheet'],rule['cell']
    n=index+1
    ref=lambda s,a:cellkey(s,a)
    inputs={}
    if mechanism=='scenario_selector':
        col=addr[0]
        choices={"D":("K13","R13","Y13"),"E":("L13","S13","Z13"),
                 "F":("M13","T13","AA13"),"G":("N13","U13","AB13")}[col]
        selected=index%3+1
        inputs[ref(sheet,'C4')]=selected
        inputs[ref(sheet,'C3')]=(selected%3)+1
        for i,cell in enumerate(choices):inputs[ref(sheet,cell)]=(i+1)*110+n*3
        expected=inputs[ref(sheet,choices[selected-1])]
    elif mechanism=='cohort_vintage_shift':
        row=int(addr[1:]);metric={37:13,47:16,57:19,67:25}[row]
        units=2+n; first_metric=18+5*n;first_factor=0.35+0.05*n
        inputs.update({ref(sheet,'K33'):units,ref(sheet,f'J{metric}'):first_metric,
                       ref(sheet,'J28'):first_factor,
                       ref(sheet,f'K{metric}'):first_metric+24,
                       ref(sheet,'K28'):1})
        expected=units*first_metric*first_factor
    elif mechanism=='synergy_definition':
        col=addr[0]; synergy=12+3*n; ebitda=65+8*n
        inputs.update({ref(sheet,f'{col}22'):synergy,ref(sheet,f'{col}19'):ebitda,
                       ref(sheet,f'{col}16'):ebitda-18})
        expected=synergy+ebitda
    elif mechanism=='debt_equity_allocation':
        col=addr[0]; consideration=200+50*n;debt=0.6+0.04*n
        inputs.update({ref(sheet,f'{col}79'):consideration,
                       ref(sheet,'J76'):debt,ref(sheet,'J77'):1-debt})
        expected=consideration*debt
    elif mechanism=='organic_revenue_composition':
        col=addr[0];software=200+20*n;services=350+30*n
        inputs.update({ref(sheet,f'{col}16'):software,ref(sheet,f'{col}17'):services})
        expected=software+services
    elif mechanism=='organic_ebitda_bridge':
        col=addr[0];gp=500+25*n;rnd=90+7*n;sga=130+11*n
        inputs.update({ref(sheet,f'{col}28'):gp,ref(sheet,f'{col}31'):rnd,
                       ref(sheet,f'{col}32'):sga,ref(sheet,f'{col}33'):rnd+sga})
        expected=gp-rnd-sga
    elif mechanism in ('pf_revenue_source','pf_synergy_source'):
        col=addr[0];ma=SHEETS['ma'];switch=0 if index==0 else 1
        inputs[ref(sheet,'C5')]=switch
        inputs.update({ref(ma,f'{col}42'):380+17*n,ref(ma,f'{col}52'):240+13*n,
                       ref(ma,f'{col}72'):140+19*n,ref(ma,f'{col}62'):95+11*n})
        expected=switch*(inputs[ref(ma,f'{col}42')] if mechanism=='pf_revenue_source'
                         else inputs[ref(ma,f'{col}72')])
    else:
        raise ValueError(f'Unknown business rule: {mechanism}')
    return inputs,expected


def verify_formula(formula, rule, trials=5):
    """Return pass/fail only for all evaluable numeric witnesses; otherwise unknown."""
    evidence=[]
    for index in range(trials):
        inputs,expected=probe_values(rule,index)
        try:
            actual=eval_excel(formula,rule['sheet'],inputs)
            valid=isinstance(actual,(int,float)) and math.isclose(actual,expected,rel_tol=1e-10,abs_tol=1e-9)
            evidence.append({'scenario':index,'actual':actual,'expected':expected,'pass':valid})
        except (UnsupportedExpression,OverflowError,TypeError) as e:
            return {'status':'unverified','reason':str(e),'scenarios':len(evidence)}
    return {'status':'pass' if all(x['pass'] for x in evidence) else 'fail',
            'scenarios':trials,'counterexamples':[x for x in evidence if not x['pass']][:3]}


def known_rules(book):
    return {(e['sheet'],e['cell']):e for e in specs(book)}


def evaluate_business_constraints(out,task,submission,full=False):
    root=Path(out)
    baseline=root/'private'/'normalized_baseline.xlsx'
    input_path=root/task['input_path']
    if sha(input_path)!=task['input_sha256'] or sha(baseline)!=task['baseline_sha256']:
        raise ValueError('Input or baseline SHA mismatch')
    reference=workbook(baseline)
    broken=workbook(input_path)
    submitted=workbook(submission)
    rules=known_rules(reference)
    if full:
        selected=rules
    else:
        selected={(e['sheet'],e['cell']):rules[(e['sheet'],e['cell'])] for e in task['faults']}
    results=[]
    fault_set={(e['sheet'],e['cell']) for e in task['faults']}
    for (sheet,addr),rule in sorted(selected.items()):
        correct=reference['cells'][sheet][addr]['formula']
        injected=broken['cells'][sheet][addr]['formula']
        actual=submitted['cells'].get(sheet,{}).get(addr,{}).get('formula')
        baseline_result=verify_formula(correct,rule)
        injected_result=verify_formula(injected,rule)
        model_result=verify_formula(actual,rule)
        if baseline_result['status']!='pass':
            raise AssertionError(f'Baseline rule is not satisfied: {sheet}!{addr}')
        if (sheet,addr) in fault_set and injected_result['status']!='fail':
            raise AssertionError(f'Fault does not violate numeric witness: {sheet}!{addr}')
        results.append({'cell':f'{sheet}!{addr}', 'mechanism':rule['mechanism'],
                        'status':model_result['status'],
                        'counterexamples':model_result.get('counterexamples',[]),
                        'unverified_reason':model_result.get('reason')})
    count=collections.Counter(x['status'] for x in results)
    return {'scope':'all_32_curated_rules' if full else 'injected_rules_only',
            'rule_count':len(results),'pass':count['pass'],'fail':count['fail'],
            'unverified':count['unverified'],'rules':results,
            'method':'5 synthetic precedent-value witnesses per known business rule',
            'limitations':['Not workbook recalculation','Not proof of financial correctness in every scenario',
                           'Does not validate non-curated LBO formulas or business assumptions']}


def supplemental_lbo_rules():
    """Business-dimensional witnesses for a few non-injected valuation links.

    These rules must not be misinterpreted as a complete debt/cash policy audit.
    """
    targets={}
    lbo='Ex 1 - LBO'
    bridge='Ex 2 - Valuation Bridge'
    cell='C7'
    targets[(bridge,cell)]={
        'mechanism':'valuation_bridge_multiple_expansion',
        'sheet':bridge,'cell':cell,
        'rule':'Incremental enterprise value from multiple expansion uses exit EBITDA'
    }
    for exit_col,fin_col in zip(('Y','Z','AA','AB','AC'),('Q','R','S','T','U')):
        targets[(lbo,f'{exit_col}20')]={
            'mechanism':'exit_gross_debt',
            'sheet':lbo,'cell':f'{exit_col}20',
            'fin_col':fin_col,
            'rule':'Exit equity bridge subtracts gross debt and separately adds cash'
        }
    return targets


def probe_supplemental(rule,index):
    n=index+1
    lbo='Ex 1 - LBO'
    ref=lambda address:cellkey(lbo,address)
    if rule['mechanism']=='valuation_bridge_multiple_expansion':
        entry_multiple=10+n
        exit_multiple=14+2*n
        exit_ebitda=90+33*n
        inputs={ref('AC18'):exit_multiple,ref('X18'):entry_multiple,
                ref('AC17'):exit_ebitda}
        return inputs,(exit_multiple-entry_multiple)*exit_ebitda
    if rule['mechanism']=='exit_gross_debt':
        col=rule['fin_col']
        revolving=3*n;term_debt=145+21*n;pik=15+4*n;cash=60+11*n
        gross=revolving+term_debt+pik
        inputs={ref(f'{col}65'):revolving,ref(f'{col}76'):term_debt,
                ref(f'{col}85'):pik,ref(f'{col}91'):gross-cash}
        return inputs,gross
    raise ValueError(rule['mechanism'])


def verify_supplemental(formula,rule,trials=5):
    counterexamples=[]
    for index in range(trials):
        inputs,expected=probe_supplemental(rule,index)
        try:
            actual=eval_excel(formula,rule['sheet'],inputs)
        except (UnsupportedExpression,OverflowError,TypeError) as e:
            return {'status':'unverified','reason':str(e),'scenarios':index}
        if not isinstance(actual,(int,float)) or not math.isclose(actual,expected,abs_tol=1e-9,rel_tol=1e-10):
            counterexamples.append({'scenario':index,'actual':actual,'expected':expected})
    return {'status':'pass' if not counterexamples else 'fail','scenarios':trials,
            'counterexamples':counterexamples[:3]}


def classify_extra_business_rule(sheet,address,original,submitted):
    rule=supplemental_lbo_rules().get((sheet,address))
    if rule is None:
        return None
    before=verify_supplemental(original,rule)
    after=verify_supplemental(submitted,rule)
    return {'mechanism':rule['mechanism'],'baseline_status':before['status'],
            'submission_status':after['status'],
            'synthetic_business_witness_improved':before['status']=='fail' and after['status']=='pass',
            'warning':'Synthetic numerical constraint, not full Excel calculation or financial policy approval'}
