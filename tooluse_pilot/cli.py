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
