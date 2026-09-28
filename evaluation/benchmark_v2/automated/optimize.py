"""Bounded rubric description proposals; never edits skills or reads test cases."""
from __future__ import annotations

import copy
from pathlib import Path

from .adapters import Budget, canonical_bytes, load_config, run_call
from .contracts import load_rubric, load_suite, strict_json, validate_rubric
from .runner import _judge_cases, _prepare, _provenance


def _accuracy(cases, records, judges):
    by_key={(r['case_id'],r['judge_id'],r['order']):r for r in records}
    wins=0; total=0
    for case in cases:
        for judge in judges:
            first=by_key.get((case['id'],judge['id'],1))
            second=by_key.get((case['id'],judge['id'],2))
            total+=1
            if first and second and first['valid'] and second['valid'] and first['winner']==second['winner']==case['expected']:
                wins+=1
    return {'stable_correct':wins,'judgments':total,'accuracy':wins/total if total else None}


def optimize(suite_path,rubric_path,config_path,out,*,rounds=1):
    suite=load_suite(suite_path); start=load_rubric(rubric_path); config=load_config(config_path)
    if any(c['split']=='test' for c in suite['cases']):
        raise ValueError('optimize refuses suites containing test cases')
    if isinstance(rounds,bool) or not isinstance(rounds,int) or not 1<=rounds<=3:
        raise ValueError('rounds must be 1..3')
    if 'optimizer' not in config:
        raise ValueError('optimizer adapter required')
    controls=[c for c in suite['cases'] if c['expected'] is not None and c['split'] in ('calibration','development')]
    if not controls: raise ValueError('optimize requires labeled controls')
    budget=Budget(config['max_calls'])
    budget.preflight((rounds+1)*len(controls)*len(config['judges'])*2+rounds)
    out=_prepare(out)
    candidates=[]; rubric=start; feedback=[]; state='completed'
    for index in range(rounds+1):
        (out/f'rubric-{index}.json').write_bytes(canonical_bytes(rubric)+b'\n')
        records=_judge_cases(controls,rubric,config,out,budget)
        cal=[c for c in controls if c['split']=='calibration']
        dev=[c for c in controls if c['split']=='development']
        scores={'calibration':_accuracy(cal,records,config['judges']),
                'development':_accuracy(dev,records,config['judges'])}
        candidates.append({'index':index,'rubric_file':f'rubric-{index}.json','scores':scores,
                           'records':records})
        feedback.append({'index':index,'scores':scores})
        if index==rounds: break
        request={'role':'optimizer','request_id':f'rubric-round-{index+1}',
                 'rubric':rubric,'examples':controls,'feedback':feedback}
        budget.charge()
        call=run_call(config['optimizer']['command'],request,out/'calls'/f'{budget.used:05d}',timeout_seconds=config['timeout_seconds'])
        if not call['ok']:
            state=call['error'] or f"optimizer_exit_{call['returncode']}"; break
        try:
            rubric=validate_rubric(strict_json(call['response']))
        except (ValueError,UnicodeError,TypeError) as exc:
            state=f'invalid_optimizer_response: {exc}'; break
    metric='development' if any(c['split']=='development' for c in controls) else 'calibration'
    selected=max(candidates,key=lambda c:(c['scores'][metric]['accuracy'] or 0, -c['index']))
    (out/'selected-rubric.json').write_bytes((out/selected['rubric_file']).read_bytes())
    report={'schema_version':1,'artifact_type':'rubric_optimization',
            'complete':state=='completed',
            'state':state,'selected_index':selected['index'],'selection_split':metric,
            'candidates':[{'index':c['index'],'rubric_file':c['rubric_file'],'scores':c['scores']} for c in candidates],
            'provenance':_provenance(suite_path,rubric_path,config_path,config),
            'calls_used':budget.used,'max_calls':budget.limit,
            'message':'Selected rubric requires fresh live calibration before comparison.'}
    (out/'candidate-records.json').write_bytes(canonical_bytes(candidates)+b'\n')
    (out/'optimization.json').write_bytes(canonical_bytes(report)+b'\n')
    return report
