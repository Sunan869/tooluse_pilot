"""Write authoritative runner JSON directly; never transport it via console encoding."""
import argparse
import json
from pathlib import Path
import sys

def write_result(result, destination):
    # Exclusive creation preserves previous results, including partial failures.
    with Path(destination).open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2)
        stream.write('\n')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--candidate',required=True)
    parser.add_argument('--config',required=True)
    parser.add_argument('--out',required=True)
    parser.add_argument('--model',required=True)
    parser.add_argument('--db',required=True)
    parser.add_argument('--max-requests',type=int,default=25)
    parser.add_argument('--max-tools',type=int,default=80)
    args=parser.parse_args()
    destination=Path(args.out)
    if destination.exists():raise FileExistsError('Result already exists; no model request was made.')
    sys.path.insert(0,str(Path(__file__).resolve().parent/'code'))
    from tooluse_pilot.executable_runner import run_candidate
    result=run_candidate(args.candidate,args.config,args.model,args.db,args.max_requests,args.max_tools)
    write_result(result,destination)
    print('Result file saved.')  # ASCII-only diagnostic; JSON is never stdout.

if __name__=='__main__':main()
