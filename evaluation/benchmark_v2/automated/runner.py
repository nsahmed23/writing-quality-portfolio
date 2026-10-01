"""Unattended, evidence-preserving calibration and comparison."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

from .adapters import Budget, canonical_bytes, digest, load_config, run_call, tool_versions
from .contracts import SPLITS, case_fingerprint, load_rubric, load_suite
from .private import require_private_output
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


MAX_COMMAND_LINE_UNITS=32000  # adapters/prompt_arg_adapter.py refuses above this; a test keeps the two numbers equal
ARGUMENT_ADAPTER='prompt_arg_adapter.py'
BUILDER_SCRIPT='generic_json_adapter.py'


def _units(command):
    """The length of the command line Windows would be given, in UTF-16 code units (as the argument adapter counts it).

    surrogatepass counts a lone surrogate as one unit. The adapter refuses such a prompt itself (exit 2), so the
    pre-check must not crash the run before that call is made."""
    return len(subprocess.list2cmdline(command).encode('utf-16-le','surrogatepass'))//2


def _prompt_builder(folder):
    """build_prompt from the generic bridge that sits next to the argument adapter, or None when it cannot be loaded."""
    try:
        spec=importlib.util.spec_from_file_location('wq_generic_json_adapter',Path(folder)/BUILDER_SCRIPT)
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.build_prompt
    except (OSError,ImportError,AttributeError,SyntaxError):
        return None


def _command_units(command,request):
    """Units of the command line the argument adapter would measure for this request, or None.

    None means the judge does not pass its prompt as an argument, or the measurement cannot be made (fail open:
    the call then runs and the adapter decides). The adapter measures [*model_command,'-p',prompt]."""
    for index,part in enumerate(command):
        if Path(part).name==ARGUMENT_ADAPTER: break
    else:
        return None
    tail=list(command[index+1:])
    if tail[:1]==['--']: tail=tail[1:]
    if not tail: return None
    build=_prompt_builder(Path(part).resolve().parent)
    if build is None: return None
    return _units([*tail,'-p',build(request)])


def _judge_request(case,judge,order,rubric):
    a,b=(case['a'],case['b']) if order==1 else (case['b'],case['a'])
    return {'role':'judge','request_id':_request_id(case['id'],judge['id'],order),
            'prompt':case['prompt'],'context':case['context'],'rubric':rubric['criteria'],'A':a,'B':b}


def _skipped_record(case,judge,order,units):
    return {'case_id':case['id'],'document_id':case['document_id'],'lane':case['lane'],'split':case['split'],
            'judge_id':judge['id'],'family':judge['family'],'order':order,'valid':False,'winner':None,
            'failure_kind':'skipped',
            'error':f'oversized_prompt: a judge command line of {units} UTF-16 units is over the limit of {MAX_COMMAND_LINE_UNITS}'}


def _oversized_units(case,rubric,config):
    """The largest command line above the limit that any judge would be given for this case, else None."""
    worst=None
    for judge in config['judges']:
        for order in (1,2):
            units=_command_units(judge['command'],_judge_request(case,judge,order,rubric))
            if units is not None and units>MAX_COMMAND_LINE_UNITS and (worst is None or units>worst):
                worst=units
    return worst


def _judge_one(case,judge,order,rubric,out,budget,timeout):
    """One judge call for one case in one presentation order; returns its record. Charges the budget once.
    Part D (rerun-failed) calls this directly, so a re-run builds the same request and the same record."""
    request=_judge_request(case,judge,order,rubric)
    a,b=request['A'],request['B']
    budget.charge()
    artifact=out/'calls'/f'{budget.used:05d}'
    result=run_call(judge['command'],request,artifact,timeout_seconds=timeout)
    record={'case_id':case['id'],'document_id':case['document_id'],'lane':case['lane'],
            'split':case['split'],'judge_id':judge['id'],'family':judge['family'],
            'order':order,'valid':False,'winner':None}
    if not result['ok']:
        record['failure_kind']='plumbing'
        record['error']=result['error'] or f"process_exit_{result['returncode']}"
    else:
        parsed=parse_judgment(result['response'],a,b)
        record['valid']=parsed['valid']
        if parsed['valid']:
            winner=parsed['winner']
            record['winner']=({'A':'a','B':'b'} if order==1 else {'A':'b','B':'a'}).get(winner,winner)
        else:
            record['failure_kind']='judgment'
            record['error']=parsed['error']
    return record


def _judge_cases(cases,rubric,config,out,budget):
    """Judge every case with every judge in both orders. A case that one judge's command line cannot carry is
    skipped for all judges (no call, no charge), so every judge scores the same documents."""
    records=[]
    for case in cases:
        units=_oversized_units(case,rubric,config)
        for judge in config['judges']:
            for order in (1,2):
                if units is not None:
                    records.append(_skipped_record(case,judge,order,units))
                else:
                    records.append(_judge_one(case,judge,order,rubric,out,budget,config['timeout_seconds']))
    return records


def calibrate(suite_path,rubric_path,config_path,out):
    suite=load_suite(suite_path); require_private_output(suite,out)
    rubric=load_rubric(rubric_path); config=load_config(config_path)
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


MAX_SNAPSHOT_CHARACTERS=60000
NO_BASELINE_INSTRUCTIONS='No additional instructions.'


def _snapshot_text(raw,name,label):
    """One skill file as text: UTF-8, with CRLF read as LF so a Windows and a POSIX checkout give the same snapshot."""
    try: return raw.decode('utf-8').replace('\r\n','\n')
    except UnicodeDecodeError as exc: raise ValueError(f'skill {name}: {label} is not valid UTF-8') from exc


def _skill_snapshot(path):
    """What a skill is evaluated as: its SKILL.md, then every file under the references/ folder beside it.

    path is a skill folder or its SKILL.md file. Returns (raw SKILL.md bytes, snapshot text). The raw bytes alone
    feed candidate_skill_sha256 and the saved SKILL.md copy; the text is what the writer is given as instructions.
    References come in sorted forward-slash path order (text order, so it is the same on every platform), each after
    a blank line and a '=== references/<path> ===' line. SKILL.md has no header, so a skill without references is
    its own SKILL.md text. A snapshot over MAX_SNAPSHOT_CHARACTERS characters is refused, naming the skill."""
    path=Path(path)
    folder=path if path.is_dir() else path.parent
    skill=path/'SKILL.md' if path.is_dir() else path
    name=folder.resolve().name
    raw=skill.read_bytes()
    text=_snapshot_text(raw,name,'SKILL.md')
    references=folder/'references'
    if references.is_dir():
        found=sorted(((file.relative_to(references).as_posix(),file) for file in references.rglob('*') if file.is_file()),
                     key=lambda item:item[0])
        for relative,file in found:
            if not text.endswith('\n'): text+='\n'
            text+=f'\n=== references/{relative} ===\n'+_snapshot_text(file.read_bytes(),name,f'references/{relative}')
    if len(text)>MAX_SNAPSHOT_CHARACTERS:
        raise ValueError(f'skill snapshot too large: {name} is {len(text)} characters, over the limit of {MAX_SNAPSHOT_CHARACTERS}')
    return raw,text


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


def _require_certificate(calibration,provenance):
    """The calibration report compare needs: live, complete, eligible, and made for this rubric and judge signature."""
    certificate=json.loads((Path(calibration)/'report.json').read_bytes())
    cert_provenance=certificate.get('provenance',{})
    if (certificate.get('schema_version')!=1 or certificate.get('evaluation_type')!='automated_proxy' or
        certificate.get('execution')!='live' or certificate.get('mode')!='calibrate' or
        not certificate.get('complete') or not certificate.get('eligible') or
        cert_provenance.get('rubric_sha256')!=provenance['rubric_sha256'] or
        cert_provenance.get('judge_signature')!=provenance['judge_signature'] or
        # Leakage cannot be checked without the suite the certificate was issued on.
        not isinstance(cert_provenance.get('suite_sha256'),str) or not cert_provenance['suite_sha256']):
        raise ValueError('matching eligible live calibration required')
    return certificate


def _scoring_case(current,source,a_error,b_error):
    """The case the report scores. A missing writer output keeps the suite's own text as a schema-valid
    placeholder, so the case counts as missing judge records; no judge ever sees the placeholder."""
    scoring=copy.deepcopy(current)
    if a_error: scoring['a']=source['a']
    if b_error: scoring['b']=source['b']
    return scoring


def _apply_writer_failures(report,failures):
    """A run with a failed writer call is incomplete, ineligible and inconclusive, and says how many failed."""
    if not failures: return
    report['complete']=False; report['eligible']=False; report['recommendation']='inconclusive'
    report['checks'].append({'id':'writer_outputs','passed':False,'message':f'{len(failures)} writer output failures'})


def _select_documents(cases,documents):
    """The cases whose document id is in documents, in suite order; None keeps every case.

    An unknown id is refused by its position in the list, never by the id, so the message cannot carry a
    private document name; the caller sees its own command line."""
    if documents is None: return cases
    if (not isinstance(documents,(list,tuple)) or not documents or
            any(not isinstance(d,str) or not d for d in documents) or len(set(documents))!=len(documents)):
        raise ValueError('documents must be a nonempty list of distinct document ids')
    known={c['document_id'] for c in cases}
    for position,document in enumerate(documents,1):
        if document not in known: raise ValueError(f'unknown document in documents (position {position}) for this split')
    wanted=set(documents)
    return [c for c in cases if c['document_id'] in wanted]


def _instructions_bytes(baseline,candidate):
    """What the writer was given, once per run: each side's exact text and its hash."""
    def entry(text): return {'sha256':digest(text.encode('utf-8')),'text':text}
    return canonical_bytes({'baseline':entry(baseline),'candidate':entry(candidate)})+b'\n'


def compare(suite_path,rubric_path,config_path,calibration,candidate_skill,out,*,baseline_skill=None,repetitions=1,split='test',calibration_suite=None,documents=None):
    if split not in SPLITS: raise ValueError('invalid split')
    suite=load_suite(suite_path); require_private_output(suite,out)
    rubric=load_rubric(rubric_path); config=load_config(config_path)
    candidate_raw,candidate_instructions=_skill_snapshot(candidate_skill)
    baseline_raw,baseline_instructions=_skill_snapshot(baseline_skill) if baseline_skill is not None else (None,NO_BASELINE_INSTRUCTIONS)
    provenance=_provenance(suite_path,rubric_path,config_path,config,candidate_raw)
    provenance['split']=split
    provenance['baseline_skill_sha256']=digest(baseline_raw) if baseline_raw is not None else None
    # The skill hashes cover SKILL.md alone (the metric pack checks candidate_skill_sha256); these cover what the writer was given.
    provenance['candidate_snapshot_sha256']=digest(candidate_instructions.encode('utf-8'))
    provenance['baseline_snapshot_sha256']=digest(baseline_instructions.encode('utf-8')) if baseline_raw is not None else None
    provenance['repetitions']=repetitions
    certificate=_require_certificate(calibration,provenance)
    provenance['certificate_suite_sha256']=certificate.get('provenance',{}).get('suite_sha256')
    if isinstance(repetitions,bool) or not isinstance(repetitions,int) or repetitions<1 or repetitions>20:
        raise ValueError('repetitions must be 1..20')
    cases=[case for case in suite['cases'] if case['split']==split]
    if not cases: raise ValueError(f'compare requires {split} cases')
    cases=_select_documents(cases,documents)
    provenance['documents']=sorted(documents) if documents is not None else None
    if 'writer' not in config: raise ValueError('writer adapter required for compare')
    provenance['calibration_overlap']=_check_calibration_suite(suite,cases,split,provenance['suite_sha256'],provenance['certificate_suite_sha256'],calibration_suite)
    budget=Budget(config['max_calls'])
    budget.preflight(len(cases)*repetitions*(2+len(config['judges'])*2))
    before=_versions_before(config)
    out=_prepare(out)
    (out/'candidate-SKILL.md').write_bytes(candidate_raw)
    if baseline_raw is not None: (out/'baseline-SKILL.md').write_bytes(baseline_raw)
    (out/'instructions.json').write_bytes(_instructions_bytes(baseline_instructions,candidate_instructions))
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
            scoring_cases.append(_scoring_case(current,case,a_error,b_error))
            if a_error or b_error: failures.append({'case_id':current['id'],'baseline':a_error,'candidate':b_error})
    (out/'generated.json').write_bytes(canonical_bytes({'cases':generated,'failures':failures})+b'\n')
    valid_cases=[c for c in generated if c['a'] and c['b']]
    records=_judge_cases(valid_cases,rubric,config,out,budget)
    # Missing writer outputs have no judge calls; the engine sees absent records, hence incomplete coverage.
    report=build_report({**suite,'cases':scoring_cases},records,config['judges'],mode='compare',calibration=certificate,execution='live',split=split)
    _apply_writer_failures(report,failures)
    report['provenance']=provenance
    _record_versions(report,config,before,'compare')
    report['artifacts']={'records':'records.json','calls':'calls','generated':'generated.json','candidate_skill':'candidate-SKILL.md','instructions':'instructions.json'}
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
