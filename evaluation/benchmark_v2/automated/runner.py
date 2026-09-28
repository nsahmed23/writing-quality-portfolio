"""Unattended, evidence-preserving calibration and comparison."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from .adapters import Budget, canonical_bytes, digest, load_config, run_call
from .contracts import load_rubric, load_suite
from .scoring import build_report, parse_judgment


def _judge_signature(config):
    return digest(canonical_bytes([{'id':j['id'],'family':j['family'],'command':j['command']} for j in config['judges']]))


def _provenance(suite_path,rubric_path,config_path,config,skill_bytes=None):
    return {'candidate_skill_sha256': digest(skill_bytes) if skill_bytes is not None else None,
            'suite_sha256':digest(Path(suite_path).read_bytes()),
            'rubric_sha256':digest(Path(rubric_path).read_bytes()),
            'config_sha256':digest(Path(config_path).read_bytes()),
            'judge_signature':_judge_signature(config)}


def _prepare(out):
    out=Path(out)
    out.mkdir(parents=True,exist_ok=False)
    (out/'calls').mkdir()
    return out


def _save(out,report,records):
    (out/'records.json').write_bytes(canonical_bytes(records)+b'\n')
    (out/'report.json').write_bytes(canonical_bytes(report)+b'\n')
    return report


def _request_id(*parts):
    return digest(canonical_bytes(list(parts)))


def _judge_cases(cases,rubric,config,out,budget):
    records=[]
    for case in cases:
        for judge in config['judges']:
            for order in (1,2):
                a,b=(case['a'],case['b']) if order==1 else (case['b'],case['a'])
                request={'role':'judge','request_id':_request_id(case['id'],judge['id'],order),
                         'prompt':case['prompt'],'context':case['context'],'rubric':rubric['criteria'],'A':a,'B':b}
                budget.charge()
                artifact=out/'calls'/f'{budget.used:05d}'
                result=run_call(judge['command'],request,artifact,timeout_seconds=config['timeout_seconds'])
                record={'case_id':case['id'],'document_id':case['document_id'],'lane':case['lane'],
                        'split':case['split'],'judge_id':judge['id'],'family':judge['family'],
                        'order':order,'valid':False,'winner':None}
                if not result['ok']:
                    record['error']=result['error'] or f"process_exit_{result['returncode']}"
                else:
                    parsed=parse_judgment(result['response'],a,b)
                    record['valid']=parsed['valid']
                    if parsed['valid']:
                        winner=parsed['winner']
                        record['winner']=({'A':'a','B':'b'} if order==1 else {'A':'b','B':'a'}).get(winner,winner)
                    else:
                        record['error']=parsed['error']
                records.append(record)
    return records


def calibrate(suite_path,rubric_path,config_path,out):
    suite=load_suite(suite_path); rubric=load_rubric(rubric_path); config=load_config(config_path)
    cases=[case for case in suite['cases'] if case['split']=='calibration' and case['expected'] is not None]
    if not cases: raise ValueError('calibration requires labeled calibration controls')
    budget=Budget(config['max_calls']); budget.preflight(len(cases)*len(config['judges'])*2)
    out=_prepare(out)
    selected={**suite,'cases':cases}
    records=_judge_cases(cases,rubric,config,out,budget)
    report=build_report(selected,records,config['judges'],mode='calibrate',execution='live')
    report['provenance']=_provenance(suite_path,rubric_path,config_path,config)
    report['artifacts']={'records':'records.json','calls':'calls'}
    return _save(out,report,records)


def _skill_bytes(path):
    path=Path(path)
    if path.is_dir(): path=path/'SKILL.md'
    value=path.read_bytes()
    return value,value.decode('utf-8')


def _write_text(adapter,case,instructions,out,budget,tag,timeout):
    request={'role':'writer','request_id':_request_id(case['id'],tag),
             'prompt':case['prompt'],'context':case['context'],'instructions':instructions}
    budget.charge()
    result=run_call(adapter['command'],request,out/'calls'/f'{budget.used:05d}',timeout_seconds=timeout)
    if not result['ok']:
        return None,result['error'] or f"process_exit_{result['returncode']}"
    try:
        from .contracts import strict_json
        response=strict_json(result['response'])
        if not isinstance(response,dict) or set(response)!={'text'} or not isinstance(response['text'],str) or not response['text'].strip():
            raise ValueError('writer response requires only nonblank text')
        return response['text'],None
    except (ValueError,UnicodeError) as exc:
        return None,f'invalid_writer_response: {exc}'


def compare(suite_path,rubric_path,config_path,calibration,candidate_skill,out,*,baseline_skill=None,repetitions=1):
    suite=load_suite(suite_path); rubric=load_rubric(rubric_path); config=load_config(config_path)
    candidate_raw,candidate_instructions=_skill_bytes(candidate_skill)
    baseline_raw,baseline_instructions=_skill_bytes(baseline_skill) if baseline_skill is not None else (None,'')
    provenance=_provenance(suite_path,rubric_path,config_path,config,candidate_raw)
    certificate=json.loads((Path(calibration)/'report.json').read_bytes())
    cert_provenance=certificate.get('provenance',{})
    if (certificate.get('schema_version')!=1 or certificate.get('evaluation_type')!='automated_proxy' or
        certificate.get('execution')!='live' or certificate.get('mode')!='calibrate' or
        not certificate.get('complete') or not certificate.get('eligible') or cert_provenance.get('rubric_sha256')!=provenance['rubric_sha256'] or
        cert_provenance.get('judge_signature')!=provenance['judge_signature']):
        raise ValueError('matching eligible live calibration required')
    if isinstance(repetitions,bool) or not isinstance(repetitions,int) or repetitions<1 or repetitions>20:
        raise ValueError('repetitions must be 1..20')
    cases=[case for case in suite['cases'] if case['split']=='test']
    if not cases: raise ValueError('compare requires test cases')
    if 'writer' not in config: raise ValueError('writer adapter required for compare')
    budget=Budget(config['max_calls'])
    budget.preflight(len(cases)*repetitions*(2+len(config['judges'])*2))
    out=_prepare(out)
    (out/'candidate-SKILL.md').write_bytes(candidate_raw)
    if baseline_raw is not None: (out/'baseline-SKILL.md').write_bytes(baseline_raw)
    generated=[]; scoring_cases=[]; failures=[]
    for case in cases:
        for repetition in range(repetitions):
            current=copy.deepcopy(case)
            current['id']=f"{case['id']}--repeat-{repetition+1}"
            current['expected']=None
            a,a_error=_write_text(config['writer'],current,baseline_instructions,out,budget,'baseline',config['timeout_seconds'])
            b,b_error=_write_text(config['writer'],current,candidate_instructions,out,budget,'candidate',config['timeout_seconds'])
            current['a']=a if a is not None else ''
            current['b']=b if b is not None else ''
            generated.append(current)
            scoring_case=copy.deepcopy(current)
            # Schema-valid source placeholders make missing model outputs count as
            # missing records. They are never submitted to judges or used as wins.
            if a_error: scoring_case['a']=case['a']
            if b_error: scoring_case['b']=case['b']
            scoring_cases.append(scoring_case)
            if a_error or b_error: failures.append({'case_id':current['id'],'baseline':a_error,'candidate':b_error})
    (out/'generated.json').write_bytes(canonical_bytes({'cases':generated,'failures':failures})+b'\n')
    valid_cases=[c for c in generated if c['a'] and c['b']]
    records=_judge_cases(valid_cases,rubric,config,out,budget)
    # Missing writer outputs have no judge calls; the engine sees absent records, hence incomplete coverage.
    report=build_report({**suite,'cases':scoring_cases},records,config['judges'],mode='compare',calibration=certificate,execution='live')
    if failures:
        report['complete']=False; report['eligible']=False; report['recommendation']='inconclusive'
        report['checks'].append({'id':'writer_outputs','passed':False,'message':f'{len(failures)} writer output failures'})
    report['provenance']=provenance
    report['artifacts']={'records':'records.json','calls':'calls','generated':'generated.json','candidate_skill':'candidate-SKILL.md'}
    return _save(out,report,records)


def demo(out):
    """Static software smoke exercise including a deliberately malformed judgment."""
    from .scoring import parse_judgment
    case={'id':'demo-1','document_id':'demo-doc','split':'calibration','lane':'editing',
          'prompt':'Demonstrate parsing','context':'','a':'alpha','b':'beta','expected':'a',
          'checks':{},'provenance':{'kind':'synthetic_control','source':'static demo','license':'CC0'}}
    suite={'schema_version':1,'name':'static demo','cases':[case]}
    rubric={'schema_version':1,'id':'demo','criteria':[{'id':'meaning','description':'Preserve the intended meaning.'}]}
    judges=[{'id':'synthetic','family':'static-demo','command':[]}]
    valid=canonical_bytes({'winner':'A','reason':'literal demo','evidence':[{'candidate':'A','quote':'alpha'},{'candidate':'B','quote':'beta'}]})
    invalid=b'{"winner":"B","reason":"unsupported","evidence":[{"candidate":"B","quote":"not present"}]}'
    out=_prepare(out)
    (out/'synthetic-response-valid.bin').write_bytes(valid)
    (out/'synthetic-response-invalid.bin').write_bytes(invalid)
    first=parse_judgment(valid,'alpha','beta'); second=parse_judgment(invalid,'beta','alpha')
    records=[{'case_id':'demo-1','document_id':'demo-doc','lane':'editing','split':'calibration','judge_id':'synthetic',
              'family':'static-demo','order':order,'valid':parsed['valid'],
              'winner':('a' if parsed['winner']=='A' else parsed['winner']) if parsed['valid'] else None,
              **({'error':parsed['error']} if not parsed['valid'] else {})}
             for order,parsed in ((1,first),(2,second))]
    report=build_report(suite,records,judges,mode='calibrate',execution='demo')
    report['mode']='calibrate';report['execution']='demo';report['eligible']=False;report['recommendation']='not_applicable'
    report['provenance']={'candidate_skill_sha256':None,'suite_sha256':digest(canonical_bytes(suite)),
                          'rubric_sha256':digest(canonical_bytes(rubric)),'config_sha256':digest(canonical_bytes({'judges':judges})),
                          'judge_signature':digest(canonical_bytes(judges))}
    report['artifacts']={'records':'records.json','synthetic_responses':['synthetic-response-valid.bin','synthetic-response-invalid.bin']}
    return _save(out,report,records)
