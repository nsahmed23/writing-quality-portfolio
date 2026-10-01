"""Unattended, evidence-preserving calibration and comparison."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from .adapters import Budget, canonical_bytes, digest, load_config, run_call, tool_versions
from .contracts import SPLITS, case_fingerprint, load_rubric, load_suite
from .scoring import build_report, parse_judgment


ADAPTER_DIR=Path(__file__).resolve().parent/'adapters'
ADAPTER_SCRIPTS=('codex_adapter.py','generic_json_adapter.py','prompt_arg_adapter.py')


def _text_digest(path):
    """SHA-256 of a text file with CRLF read as LF, so a Windows and a POSIX checkout of the same file agree."""
    return digest(Path(path).read_bytes().replace(b'\r\n',b'\n'))


def _adapter_hashes():
    """Line-ending-independent hash of each shipped adapter script; a missing script raises OSError naming the file."""
    return {name:_text_digest(ADAPTER_DIR/name) for name in ADAPTER_SCRIPTS}


def _judge_signature(config):
    judges=[{'id':j['id'],'family':j['family'],'command':j['command']} for j in config['judges']]
    return digest(canonical_bytes({'judges':judges,'adapters':_adapter_hashes()}))


def _provenance(suite_path,rubric_path,config_path,config,skill_bytes=None):
    return {'candidate_skill_sha256': digest(skill_bytes) if skill_bytes is not None else None,
            'suite_sha256':_text_digest(suite_path),
            'rubric_sha256':_text_digest(rubric_path),
            'config_sha256':_text_digest(config_path),
            'judge_signature':_judge_signature(config),
            'adapter_sha256':_adapter_hashes()}


def _versions_before(config):
    """Read the configured tool versions before a run; a command that fails stops the run before any output exists."""
    before=tool_versions(config)
    broken=sorted(name for name,value in before.items() if value is None)
    if broken: raise ValueError('version command failed before the run: '+', '.join(broken))
    return before


def _record_versions(report,config,before,mode):
    """Read the versions again; record before, after and changed, and void a run whose tools changed or became unreadable."""
    if not before: return
    after=tool_versions(config)
    changed=sorted(name for name in before if after.get(name)!=before[name])
    report['provenance']['tool_versions']={'before':before,'after':after,'changed':changed}
    report['checks'].append({'id':'tool_versions_stable','passed':not changed,
                             'message':'tool versions unchanged during the run' if not changed else 'tool versions changed or unreadable after the run: '+', '.join(changed)})
    if changed:
        report['eligible']=False
        if mode=='compare':
            report['recommendation']='inconclusive'
            for lane in report.get('by_lane',{}).values(): lane['recommendation']='inconclusive'


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
    before=_versions_before(config)
    out=_prepare(out)
    selected={**suite,'cases':cases}
    records=_judge_cases(cases,rubric,config,out,budget)
    report=build_report(selected,records,config['judges'],mode='calibrate',execution='live')
    report['provenance']=_provenance(suite_path,rubric_path,config_path,config)
    _record_versions(report,config,before,'calibrate')
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


def _check_calibration_suite(suite,cases,split,suite_sha,certificate_sha,calibration_suite):
    """Count the selected cases that share an identity with the certificate's labeled controls.

    A test-split comparison that shares a document id, a cluster id or a copied pair with those
    controls is refused. The development and calibration splits may share identities (real-anchored
    controls are derived from development documents), so they only record the counts. Messages
    name the comparison case id and the kind, never a document id, a cluster id or text, so owner
    text cannot reach an error line, a log or a terminal."""
    if calibration_suite is not None:
        if _text_digest(calibration_suite)!=certificate_sha:
            raise ValueError('calibration suite does not match the certificate')
        source=load_suite(calibration_suite)
    elif certificate_sha==suite_sha:
        source=suite
    else:
        raise ValueError('certificate was issued on another suite; pass --calibration-suite so leakage can be checked')
    controls=[c for c in source['cases'] if c['split']=='calibration' and c['expected'] is not None]
    documents={c['document_id'] for c in controls}
    clusters={c['cluster_id'] for c in controls if 'cluster_id' in c}
    fingerprints={case_fingerprint(c) for c in controls}
    found={'documents':[],'clusters':[],'pairs':[]}
    for case in cases:
        if case['document_id'] in documents: found['documents'].append(case['id'])
        if case.get('cluster_id') in clusters: found['clusters'].append(case['id'])
        if case_fingerprint(case) in fingerprints: found['pairs'].append(case['id'])
    if split=='test':
        for key,label in (('documents','document'),('clusters','cluster'),('pairs','copied pair')):
            if found[key]:
                raise ValueError(f"comparison case {found[key][0]} overlaps a calibration control ({label})")
    return {key:len(ids) for key,ids in found.items()}


def compare(suite_path,rubric_path,config_path,calibration,candidate_skill,out,*,baseline_skill=None,repetitions=1,split='test',calibration_suite=None):
    if split not in SPLITS: raise ValueError('invalid split')
    suite=load_suite(suite_path); rubric=load_rubric(rubric_path); config=load_config(config_path)
    candidate_raw,candidate_instructions=_skill_bytes(candidate_skill)
    baseline_raw,baseline_instructions=_skill_bytes(baseline_skill) if baseline_skill is not None else (None,'')
    provenance=_provenance(suite_path,rubric_path,config_path,config,candidate_raw)
    provenance['split']=split
    certificate=json.loads((Path(calibration)/'report.json').read_bytes())
    cert_provenance=certificate.get('provenance',{})
    provenance['certificate_suite_sha256']=cert_provenance.get('suite_sha256')
    if (certificate.get('schema_version')!=1 or certificate.get('evaluation_type')!='automated_proxy' or
        certificate.get('execution')!='live' or certificate.get('mode')!='calibrate' or
        not certificate.get('complete') or not certificate.get('eligible') or cert_provenance.get('rubric_sha256')!=provenance['rubric_sha256'] or
        cert_provenance.get('judge_signature')!=provenance['judge_signature'] or
        # Leakage cannot be checked without the suite the certificate was issued on.
        not isinstance(cert_provenance.get('suite_sha256'),str) or not cert_provenance['suite_sha256']):
        raise ValueError('matching eligible live calibration required')
    if isinstance(repetitions,bool) or not isinstance(repetitions,int) or repetitions<1 or repetitions>20:
        raise ValueError('repetitions must be 1..20')
    cases=[case for case in suite['cases'] if case['split']==split]
    if not cases: raise ValueError(f'compare requires {split} cases')
    if 'writer' not in config: raise ValueError('writer adapter required for compare')
    provenance['calibration_overlap']=_check_calibration_suite(suite,cases,split,provenance['suite_sha256'],provenance['certificate_suite_sha256'],calibration_suite)
    budget=Budget(config['max_calls'])
    budget.preflight(len(cases)*repetitions*(2+len(config['judges'])*2))
    before=_versions_before(config)
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
    report=build_report({**suite,'cases':scoring_cases},records,config['judges'],mode='compare',calibration=certificate,execution='live',split=split)
    if failures:
        report['complete']=False; report['eligible']=False; report['recommendation']='inconclusive'
        report['checks'].append({'id':'writer_outputs','passed':False,'message':f'{len(failures)} writer output failures'})
    report['provenance']=provenance
    _record_versions(report,config,before,'compare')
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
