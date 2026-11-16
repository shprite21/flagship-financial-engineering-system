"""Run from apps/engine: python -m india ingest|research|doctor|verify."""
import argparse
import json
from pathlib import Path

from .data import ingest, sha
from .research import device_report, run


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['ingest','research','doctor','verify'])
    parser.add_argument('--root',default=str(Path(__file__).resolve().parents[3]/'.data/india'))
    parser.add_argument('--provider',choices=['yahoo','groww'],default='yahoo')
    parser.add_argument('--start',default='2021-01-01')
    parser.add_argument('--end',default='2026-10-17')
    parser.add_argument('--dataset')
    parser.add_argument('--device',choices=['cuda','cpu'],default='cuda')
    parser.add_argument('--run')
    args=parser.parse_args()
    if args.command=='doctor': result=device_report(args.device)
    elif args.command=='ingest': result={'dataset':ingest(args.root,args.provider,args.start,args.end)}
    elif args.command=='research':
        if not args.dataset: parser.error('--dataset is required')
        report=run(args.root,args.dataset,args.device)
        result={k:report[k] for k in ('id','selected_candidate','decision','blockers')}
    else:
        if not args.run: parser.error('--run is required')
        folder=Path(args.root)/'runs'/args.run
        checks=json.loads((folder/'checksums.json').read_text())
        for name,expected in checks.items():
            if Path(name).name!=name or sha((folder/name).read_bytes())!=expected:
                raise ValueError('Checkpoint/artifact checksum mismatch')
        result={'verified':True,'files':len(checks)}
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':
    main()
