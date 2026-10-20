import argparse,json,shutil
from pathlib import Path
from .generate import make_case
from .reference import run
from .grade import grade

def main():
    p=argparse.ArgumentParser(description='Dual-mode tool-use benchmark pilot')
    sub=p.add_subparsers(dest='cmd',required=True)
    g=sub.add_parser('generate');g.add_argument('case');g.add_argument('--seed',type=int,default=20261019);g.add_argument('--count',type=int,default=40)
    h=sub.add_parser('generate-hard');h.add_argument('case');h.add_argument('--seed',type=int,default=20261019);h.add_argument('--count',type=int,default=180);h.add_argument('--dynamic',action='store_true')
    rh=sub.add_parser('reference-hard');rh.add_argument('case')
    r=sub.add_parser('reference');r.add_argument('case');r.add_argument('--mode',choices=['structured','python_shell'],default='structured')
    s=sub.add_parser('grade');s.add_argument('case');s.add_argument('--trace')
    m=sub.add_parser('run-model');m.add_argument('case');m.add_argument('--config',default='gateway.models.json');m.add_argument('--model',required=True);m.add_argument('--db',default='runs/usage.sqlite');m.add_argument('--max-requests',type=int,default=25);m.add_argument('--max-tools',type=int,default=100);m.add_argument('--budget',type=float);m.add_argument('--mode',choices=['structured','python_shell'],default='structured');m.add_argument('--sandbox-image',default='tooluse-pilot-sandbox:py311-openpyxl')
    b=sub.add_parser('batch');b.add_argument('case');b.add_argument('--config',default='gateway.models.json');b.add_argument('--models',nargs='+',required=True);b.add_argument('--modes',nargs='+',choices=['structured','python_shell'],default=['structured','python_shell']);b.add_argument('--outdir',default='runs/batch');b.add_argument('--db',default='runs/usage.sqlite');b.add_argument('--max-requests',type=int,default=25);b.add_argument('--max-tools',type=int,default=100);b.add_argument('--budget',type=float)
    cnd=sub.add_parser('run-candidate');cnd.add_argument('candidate');cnd.add_argument('--config',default='gateway.models.json');cnd.add_argument('--model',required=True);cnd.add_argument('--db',default='runs/usage.sqlite');cnd.add_argument('--max-requests',type=int,default=12);cnd.add_argument('--max-tools',type=int,default=30)
    pg=sub.add_parser('generate-profiles');pg.add_argument('directory');pg.add_argument('--seeds',type=int,default=10)
    pv=sub.add_parser('verify-profiles');pv.add_argument('directory')
    cg=sub.add_parser('generate-compound');cg.add_argument('directory');cg.add_argument('--seeds',type=int,default=10)
    cv=sub.add_parser('verify-compound');cv.add_argument('directory')
    eg=sub.add_parser('generate-enterprise');eg.add_argument('directory');eg.add_argument('--seeds',type=int,default=5);eg.add_argument('--orders',type=int,default=8)
    ev=sub.add_parser('verify-enterprise');ev.add_argument('directory')
    ev2=sub.add_parser('generate-enterprise-v2');ev2.add_argument('directory');ev2.add_argument('--seeds',type=int,default=5);ev2.add_argument('--orders',type=int,default=8)
    vv2=sub.add_parser('verify-enterprise-v2');vv2.add_argument('directory')
    cal=sub.add_parser('calibrate');cal.add_argument('roots',nargs='+');cal.add_argument('--per-family',type=int,default=2);cal.add_argument('--execute',action='store_true');cal.add_argument('--model');cal.add_argument('--config',default='gateway.models.json');cal.add_argument('--outdir',default='runs/calibration');cal.add_argument('--db',default='runs/usage.sqlite');cal.add_argument('--max-requests',type=int,default=20);cal.add_argument('--max-tools',type=int,default=60)
    ar=sub.add_parser('analyze-candidates');ar.add_argument('results',nargs='+')
    fm=sub.add_parser('mutate-candidate');fm.add_argument('candidate');fm.add_argument('outdir')
    fv=sub.add_parser('verify-mutations');fv.add_argument('outdir')
    egc=sub.add_parser('generate-evidence-pairs');egc.add_argument('directory');egc.add_argument('--seeds',type=int,default=3)
    evc=sub.add_parser('verify-evidence-pairs');evc.add_argument('directory')
    ed=sub.add_parser('generate-decision-batch');ed.add_argument('directory');ed.add_argument('--seeds',type=int,default=2)
    vd=sub.add_parser('verify-decision-batch');vd.add_argument('directory')
    d=sub.add_parser('diagnose');d.add_argument('--config',default='gateway.models.json')
    e=sub.add_parser('export-usage');e.add_argument('--db',default='runs/usage.sqlite');e.add_argument('--out',default='runs/api_usage.csv')
    u=sub.add_parser('usage-summary');u.add_argument('--db',default='runs/usage.sqlite')
    a=p.parse_args()
    if a.cmd=='generate': print(make_case(a.case,a.seed,a.count))
    elif a.cmd=='generate-hard':
        from .hard import make_hard_case
        print(make_hard_case(a.case,a.seed,a.count,dynamic=a.dynamic))
    elif a.cmd=='reference-hard':
        from .hard import reference_hard
        print(reference_hard(a.case))
    elif a.cmd=='reference':print(run(a.case,a.mode))
    elif a.cmd=='grade':print(json.dumps(grade(a.case,a.trace),ensure_ascii=False,indent=2))
    elif a.cmd=='run-model':
        from .gateway import run_gateway
        print(json.dumps(run_gateway(a.case,a.config,a.model,a.db,a.max_requests,a.max_tools,a.budget,a.mode,a.sandbox_image),ensure_ascii=False,indent=2))
    elif a.cmd=='batch':
        from .gateway import run_gateway
        source=Path(a.case); destination=Path(a.outdir);destination.mkdir(parents=True,exist_ok=True)
        reports=[]
        for alias in a.models:
            for mode in a.modes:
                target=destination/(alias+'__'+mode)
                if target.exists():raise RuntimeError(f'Batch destination exists: {target}. Use a new outdir to avoid overwriting runs')
                shutil.copytree(source,target,ignore=shutil.ignore_patterns('private','output','runs','trace.json'))
                # Private oracle is needed by trusted grader but NEVER mounted in code container.
                shutil.copytree(source/'private',target/'private')
                report=run_gateway(target,a.config,alias,a.db,a.max_requests,a.max_tools,a.budget,mode)
                reports.append(report)
                print(json.dumps(report,ensure_ascii=False),flush=True)
        (destination/'summary.json').write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding='utf-8')
    elif a.cmd=='run-candidate':
        from .executable_runner import run_candidate
        print(json.dumps(run_candidate(a.candidate,a.config,a.model,a.db,a.max_requests,a.max_tools),ensure_ascii=False,indent=2))
    elif a.cmd=='generate-profiles':
        from .profile_candidates import make_profiles
        print(json.dumps(make_profiles(a.directory,range(a.seeds)),ensure_ascii=False,indent=2))
    elif a.cmd=='verify-profiles':
        from .profile_candidates import verify_profiles
        print(json.dumps(verify_profiles(a.directory),ensure_ascii=False,indent=2))
    elif a.cmd=='generate-compound':
        from .compound_batch import batch
        print(json.dumps(batch(a.directory,a.seeds),ensure_ascii=False,indent=2))
    elif a.cmd=='verify-compound':
        from .compound_batch import verify
        print(json.dumps(verify(a.directory),ensure_ascii=False,indent=2))
    elif a.cmd=='generate-enterprise':
        from .enterprise_batch import make_batch
        print(json.dumps(make_batch(a.directory,a.seeds,a.orders),ensure_ascii=False,indent=2))
    elif a.cmd=='verify-enterprise':
        from .enterprise_batch import verify
        print(json.dumps(verify(a.directory),ensure_ascii=False,indent=2))
    elif a.cmd=='generate-enterprise-v2':
        from .enterprise_v2_batch import make_batch
        print(json.dumps(make_batch(a.directory,a.seeds,a.orders),ensure_ascii=False,indent=2))
    elif a.cmd=='verify-enterprise-v2':
        from .enterprise_v2_batch import verify
        print(json.dumps(verify(a.directory),ensure_ascii=False,indent=2))
    elif a.cmd=='calibrate':
        from .research_calibration import plan,execute
        if a.per_family<1:raise ValueError('--per-family must be positive')
        if a.execute:
            if not a.model:raise ValueError('--model is required with --execute')
            result=execute(a.roots,a.outdir,a.config,a.model,a.per_family,a.max_requests,a.max_tools,a.db)
        else:
            result=plan(a.roots,a.per_family)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    elif a.cmd=='analyze-candidates':
        from .research_calibration import analyze,read_results
        print(json.dumps(analyze(read_results(a.results)),ensure_ascii=False,indent=2))
    elif a.cmd=='mutate-candidate':
        from .failure_mutations import create
        print(json.dumps(create(a.candidate,a.outdir),ensure_ascii=False,indent=2))
    elif a.cmd=='verify-mutations':
        from .failure_mutations import verify
        print(json.dumps(verify(a.outdir),ensure_ascii=False,indent=2))
    elif a.cmd=='generate-evidence-pairs':
        from .evidence_batch import generate_pair
        print(json.dumps(generate_pair(a.directory,a.seeds),ensure_ascii=False,indent=2))
    elif a.cmd=='verify-evidence-pairs':
        from .evidence_batch import verify
        print(json.dumps(verify(a.directory),ensure_ascii=False,indent=2))
    elif a.cmd=='generate-decision-batch':
        from .evidence_decision_batch import make_batch
        print(json.dumps(make_batch(a.directory,a.seeds),ensure_ascii=False,indent=2))
    elif a.cmd=='verify-decision-batch':
        from .evidence_decision_batch import verify
        print(json.dumps(verify(a.directory),ensure_ascii=False,indent=2))
    elif a.cmd=='diagnose':
        from .gateway import _config
        cfg=_config(a.config)
        from os import getenv
        print(json.dumps({'base_url':getenv(cfg.get('base_url_env','MODEL_BASE_URL')),'key_present':bool(getenv(cfg.get('api_key_env','MODEL_API_KEY'))),'model_ids':{k:v['model'] for k,v in cfg['models'].items()},'docker_available':bool(shutil.which('docker'))},ensure_ascii=False,indent=2))
    elif a.cmd=='usage-summary':
        from .ledger import summary
        print(json.dumps(summary(a.db),ensure_ascii=False,indent=2))
    elif a.cmd=='export-usage':
        from pathlib import Path
        from .ledger import export_csv
        Path(a.out).parent.mkdir(parents=True,exist_ok=True)
        print('exported',export_csv(a.db,a.out),'rows to',a.out)
if __name__=='__main__':main()
