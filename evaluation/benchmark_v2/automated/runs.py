"""Chunked comparison runs: merge finished chunk runs into one report.

Merge works from files on disk and never changes a source run folder. It refuses anything that could let two
runs disagree about what was measured: a different suite, rubric, config, judge signature, adapter script,
candidate text, baseline, repetition count, instructions or tool version. Messages name run numbers and keys,
never a document id, so owner text cannot reach an error line."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from .adapters import canonical_bytes,digest,load_config
from .contracts import SPLITS,load_suite
from .runner import _check_calibration_suite,_provenance,_require_certificate,_save,_select_documents
from .scoring import build_report

# Provenance keys that must be equal in every chunk of one merged run.
MERGE_IDENTITY_KEYS=('suite_sha256','rubric_sha256','config_sha256','judge_signature','candidate_skill_sha256',
                     'baseline_skill_sha256','repetitions','split','certificate_suite_sha256','adapter_sha256')
# Provenance keys that must also equal what the files on disk hash to now.
CURRENT_KEYS=('suite_sha256','rubric_sha256','config_sha256','judge_signature','adapter_sha256')
RUN_FILES=('report.json','records.json','generated.json','instructions.json')


def _read_run(path):
    """One finished live comparison run: report, records, generated cases, instructions, and each file's hash."""
    folder=Path(path)
    raw={}
    for name in RUN_FILES:
        try: raw[name]=(folder/name).read_bytes()
        except FileNotFoundError: raise ValueError(f'{name} is missing') from None
    report=json.loads(raw['report.json']); records=json.loads(raw['records.json']); generated=json.loads(raw['generated.json'])
    if (not isinstance(report,dict) or report.get('mode')!='compare' or report.get('execution')!='live' or
            not isinstance(report.get('provenance'),dict) or not isinstance(records,list) or
            not isinstance(generated,dict) or not isinstance(generated.get('cases'),list) or
            any(not isinstance(case,dict) or not isinstance(case.get('document_id'),str) for case in generated['cases'])):
        raise ValueError('not a live comparison run')
    return {'path':folder,'report':report,'records':records,'generated':generated,'instructions':raw['instructions.json'],
            'provenance':report['provenance'],'report_sha256':digest(raw['report.json']),
            'records_sha256':digest(raw['records.json'])}


def _overlap(suite,split,documents,suite_sha,certificate_sha,calibration_suite):
    """The calibration-overlap counts for these documents; a test split that overlaps is refused as compare refuses it."""
    cases=_select_documents([c for c in suite['cases'] if c['split']==split],documents)
    return _check_calibration_suite(suite,cases,split,suite_sha,certificate_sha,calibration_suite)


def _chunk_versions(runs):
    """Refuse a chunk whose tools changed while it ran, and chunks that were made under different tool versions."""
    seen=set()
    for run in runs:
        versions=run['provenance'].get('tool_versions')
        if isinstance(versions,dict):
            if versions.get('changed') or versions.get('after')!=versions.get('before'):
                raise ValueError('a chunk run changed tool versions while it ran')
            seen.add(canonical_bytes(versions.get('before')))
        else:
            seen.add(canonical_bytes(None))
    if len(seen)>1: raise ValueError('chunk runs differ in tool versions')


def merge(suite_path,rubric_path,config_path,calibration,run_dirs,out,*,calibration_suite=None):
    """Combine chunk runs (each made by compare --documents) into one report rebuilt from their cases and records.

    Every refusal happens before the output folder exists. The chunk calls/ folders stay with the chunks; the
    merged report records the hash of each chunk's report and records files in provenance.merged_from."""
    run_dirs=list(run_dirs)
    if len(run_dirs)<2: raise ValueError('merge needs at least two runs')
    suite=load_suite(suite_path); config=load_config(config_path)
    current=_provenance(suite_path,rubric_path,config_path,config)
    runs=[]
    for number,path in enumerate(run_dirs,1):
        try: run=_read_run(path)
        except ValueError as exc: raise ValueError(f'run {number}: {exc}') from exc
        if 'merged_from' in run['provenance']: raise ValueError(f'run {number} is a merged run; merge the original runs')
        if run['generated'].get('failures'):
            raise ValueError(f'run {number} has writer failures; run those documents again and leave it out')
        runs.append(run)
    first=runs[0]['provenance']
    for key in MERGE_IDENTITY_KEYS:
        if any(canonical_bytes(run['provenance'].get(key))!=canonical_bytes(first.get(key)) for run in runs[1:]):
            raise ValueError(f'chunk runs differ in {key}')
    for key in CURRENT_KEYS:
        if canonical_bytes(first.get(key))!=canonical_bytes(current[key]):
            raise ValueError(f'chunk runs were made with a different {key}')
    certificate=_require_certificate(calibration,current)
    if certificate.get('provenance',{}).get('suite_sha256')!=first.get('certificate_suite_sha256'):
        raise ValueError('calibration does not match the chunk runs')
    _chunk_versions(runs)
    if any(run['instructions']!=runs[0]['instructions'] for run in runs[1:]):
        raise ValueError('chunk runs differ in instructions')
    owner={}
    for number,run in enumerate(runs,1):
        for document in sorted({case['document_id'] for case in run['generated']['cases']}):
            if document in owner: raise ValueError(f'chunk runs overlap: runs {owner[document]} and {number} share a document')
            owner[document]=number
    split=first.get('split')
    if split not in SPLITS: raise ValueError('chunk runs have no valid split')
    documents=sorted(owner)
    overlap=_overlap(suite,split,documents,current['suite_sha256'],first.get('certificate_suite_sha256'),calibration_suite)
    cases=[case for run in runs for case in run['generated']['cases']]
    records=[record for run in runs for record in run['records']]
    report=build_report({**suite,'cases':cases},records,config['judges'],mode='compare',calibration=certificate,
                        execution='live',split=split)
    provenance=copy.deepcopy(first); provenance.pop('rerun',None)
    provenance['documents']=documents
    provenance['calibration_overlap']=overlap
    provenance['merged_from']=[{'report_sha256':run['report_sha256'],'records_sha256':run['records_sha256'],
                                'rerun_calls':run['provenance'].get('rerun',{}).get('rerun_calls',0)} for run in runs]
    report['provenance']=provenance
    if isinstance(provenance.get('tool_versions'),dict):
        report['checks'].append({'id':'tool_versions_stable','passed':True,
                                 'message':'tool versions unchanged during every chunk run'})
    report['artifacts']={'records':'records.json','generated':'generated.json','candidate_skill':'candidate-SKILL.md',
                         'instructions':'instructions.json'}
    out=Path(out); out.mkdir(parents=True,exist_ok=False)
    for name in ('instructions.json','candidate-SKILL.md','baseline-SKILL.md'):
        if (runs[0]['path']/name).exists(): (out/name).write_bytes((runs[0]['path']/name).read_bytes())
    (out/'generated.json').write_bytes(canonical_bytes({'cases':cases,'failures':[]})+b'\n')
    return _save(out,report,records)
