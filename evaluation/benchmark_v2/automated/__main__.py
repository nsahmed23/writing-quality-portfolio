"""Command-line entry point for automated proxy evaluation."""
import argparse
import json
import sys
from pathlib import Path

from .contracts import SPLITS, load_rubric, load_suite, validate_suite
from .adapters import canonical_bytes
from .optimize import optimize
from .runner import calibrate, compare, demo


def main(argv=None):
    parser=argparse.ArgumentParser(description='Unattended automated proxy writing evaluations')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('demo').add_argument('--out',required=True)
    subset=sub.add_parser('prepare-optimize',help='write calibration/development-only suite')
    subset.add_argument('--suite',required=True)
    subset.add_argument('--out',required=True)
    for name in ('calibrate','compare','optimize','validate'):
        p=sub.add_parser(name)
        p.add_argument('--suite',required=True)
        p.add_argument('--rubric',required=True)
        if name!='validate':
            p.add_argument('--config',required=True)
            p.add_argument('--out',required=True)
        if name=='compare':
            p.add_argument('--calibration',required=True)
            p.add_argument('--candidate-skill',required=True)
            p.add_argument('--baseline-skill')
            p.add_argument('--repetitions',type=int,default=1)
            p.add_argument('--split',choices=SPLITS,default='test')
            p.add_argument('--calibration-suite')
        if name=='optimize': p.add_argument('--rounds',type=int,default=1)
    args=parser.parse_args(argv)
    try:
        if args.command=='demo': report=demo(args.out)
        elif args.command=='prepare-optimize':
            suite=load_suite(args.suite)
            subset=validate_suite({**suite,'cases':[case for case in suite['cases'] if case['split'] in ('calibration','development')]})
            with Path(args.out).open('xb') as handle: handle.write(canonical_bytes(subset)+b'\n')
            report={'valid':True,'cases':len(subset['cases']),'out':str(args.out)}
        elif args.command=='validate':
            suite=load_suite(args.suite);rubric=load_rubric(args.rubric)
            report={'valid':True,'cases':len(suite['cases']),'criteria':len(rubric['criteria'])}
        elif args.command=='calibrate': report=calibrate(args.suite,args.rubric,args.config,args.out)
        elif args.command=='compare':
            report=compare(args.suite,args.rubric,args.config,args.calibration,args.candidate_skill,args.out,
                           baseline_skill=args.baseline_skill,repetitions=args.repetitions,
                           split=args.split,calibration_suite=args.calibration_suite)
        else: report=optimize(args.suite,args.rubric,args.config,args.out,rounds=args.rounds)
    except (ValueError,OSError,KeyError) as exc:
        parser.exit(2,f'error: {exc}\n')
    print(json.dumps(report,ensure_ascii=False,sort_keys=True))
    return 0

if __name__=='__main__': sys.exit(main())
