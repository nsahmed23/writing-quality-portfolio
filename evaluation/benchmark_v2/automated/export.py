"""Export: an allowlisted aggregate of a finished report, safe to publish.

The export is built by copying named fields into a new object, never by deleting fields from a copy of the report,
so a field the report grows later stays out until it is named here. It carries counts, per-lane document and
decisive counts, proportions, means, Wilson bounds and sign-test p-values, the recommendation, each check's name and
passed flag, provenance SHA-256 values and tool
versions. It never carries a case, document or cluster id, a prompt, context, candidate text, a quote, a reason or
a file path. A value that is not the shape the export names is refused, naming the field path and never the value,
so a refusal cannot echo owner text. The export is public by design, so it is not held to the private root."""
from __future__ import annotations

import math
import re
from pathlib import Path

from .adapters import canonical_bytes
from .contracts import strict_json
from .runner import ADAPTER_SCRIPTS

EXPORT_VERSION=1
MODES=('calibrate','compare','score')
EXECUTIONS=('live','demo')
RECOMMENDATIONS=('candidate','baseline','inconclusive','not_applicable')
LANES=('editing','communication')
# The count names scoring.build_report writes; a name not listed here is left behind.
COUNT_KEYS=('expected_records','received_records','missing_records','duplicate_records','invalid_records',
            'unexpected_records','plumbing_failures','judgment_failures','skipped_records','skipped_cases',
            'order_disagreements','abstentions','ties','both_bad','candidate_check_failures',
            'baseline_check_failures','candidate_check_diagnostics','baseline_check_diagnostics')
LANE_COUNT_KEYS=('cases','documents','decisive','wins','losses')
LANE_NUMBER_KEYS=('proportion','wilson_lower','wilson_upper','mean','sign_test_p')
HASH_KEYS=('candidate_skill_sha256','suite_sha256','rubric_sha256','config_sha256','judge_signature',
           'baseline_skill_sha256','certificate_suite_sha256','candidate_snapshot_sha256','baseline_snapshot_sha256')
CHUNK_HASH_KEYS=('report_sha256','records_sha256')
RERUN_HASH_KEYS=('source_report_sha256','source_records_sha256')
HASH=re.compile(r'[0-9a-f]{64}')
CHECK_NAME=re.compile(r'[a-z][a-z0-9_]{0,159}')
TOOL_NAME=re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}')
# Version text has no slash, backslash or colon, so a path cannot ride in it.
TOOL_VERSION=re.compile(r'[A-Za-z0-9][A-Za-z0-9 ._+()-]{0,99}')


def _refuse(path):
    raise ValueError(f'report field {path} has an unexpected value')


def _is_bool(value): return type(value) is bool
def _is_count(value): return type(value) is int and value>=0
def _is_number(value): return value is None or (type(value) in (int,float) and math.isfinite(value))
def _is_hash(value): return value is None or (isinstance(value,str) and HASH.fullmatch(value) is not None)
def _is_text(pattern,value): return isinstance(value,str) and pattern.fullmatch(value) is not None


def _copy(source,keys,path,valid):
    """The named keys that source has, each checked; every other key of source is left behind."""
    copied={}
    for key in keys:
        if key in source:
            if not valid(source[key]): _refuse(f'{path}.{key}' if path else key)
            copied[key]=source[key]
    return copied


def _section(report,key,kind):
    value=report.get(key)
    if not isinstance(value,kind): _refuse(key)
    return value


def _envelope(report):
    checks=(('mode',lambda v:v in MODES),('execution',lambda v:v in EXECUTIONS),('complete',_is_bool),
            ('eligible',_is_bool),('recommendation',lambda v:v in RECOMMENDATIONS))
    envelope={}
    for key,valid in checks:
        if key not in report: _refuse(key)
        envelope.update(_copy(report,(key,),'',valid))
    return envelope


def _lanes(report):
    by_lane=_section(report,'by_lane',dict)
    lanes={}
    for lane in LANES:
        if lane not in by_lane: continue
        entry=by_lane[lane]; path=f'by_lane.{lane}'
        if not isinstance(entry,dict): _refuse(path)
        lanes[lane]={**_copy(entry,LANE_COUNT_KEYS,path,_is_count),**_copy(entry,LANE_NUMBER_KEYS,path,_is_number),
                     **_copy(entry,('recommendation',),path,lambda v:v in RECOMMENDATIONS)}
    return lanes


def _checks(report):
    checks=_section(report,'checks',list)
    names=[]
    for index,check in enumerate(checks):
        path=f'checks[{index}]'
        if not isinstance(check,dict) or not _is_text(CHECK_NAME,check.get('id')): _refuse(path)
        if not _is_bool(check.get('passed')): _refuse(f'{path}.passed')
        names.append({'name':check['id'],'passed':check['passed']})
    return names


def _versions(value):
    return isinstance(value,dict) and all(_is_text(TOOL_NAME,name) and (version is None or _is_text(TOOL_VERSION,version))
                                          for name,version in value.items())


def _tool_versions(value):
    """before, after and changed as the runner records them; any other shape is refused whole."""
    if not (isinstance(value,dict) and _versions(value.get('before')) and _versions(value.get('after')) and
            isinstance(value.get('changed'),list) and all(_is_text(TOOL_NAME,name) for name in value['changed'])):
        _refuse('provenance.tool_versions')
    return {'before':dict(value['before']),'after':dict(value['after']),'changed':list(value['changed'])}


def _chunks(value):
    if not isinstance(value,list): _refuse('provenance.merged_from')
    chunks=[]
    for index,chunk in enumerate(value):
        path=f'provenance.merged_from[{index}]'
        if not isinstance(chunk,dict): _refuse(path)
        chunks.append({**_copy(chunk,CHUNK_HASH_KEYS,path,_is_hash),**_copy(chunk,('rerun_calls',),path,_is_count)})
    return chunks


def _rerun(value):
    if not isinstance(value,dict): _refuse('provenance.rerun')
    return {**_copy(value,RERUN_HASH_KEYS,'provenance.rerun',_is_hash),
            **_copy(value,('rerun_calls',),'provenance.rerun',_is_count)}


def _provenance(report):
    source=_section(report,'provenance',dict)
    provenance=_copy(source,HASH_KEYS,'provenance',_is_hash)
    if 'adapter_sha256' in source:
        adapters=source['adapter_sha256']
        if not isinstance(adapters,dict): _refuse('provenance.adapter_sha256')
        provenance['adapter_sha256']=_copy(adapters,ADAPTER_SCRIPTS,'provenance.adapter_sha256',_is_hash)
    if 'tool_versions' in source: provenance['tool_versions']=_tool_versions(source['tool_versions'])
    if 'merged_from' in source: provenance['merged_from']=_chunks(source['merged_from'])
    if 'rerun' in source: provenance['rerun']=_rerun(source['rerun'])
    return provenance


def build_export(report):
    """The allowlisted aggregate of one report; raises ValueError naming the field of anything it cannot trust."""
    if not isinstance(report,dict): raise ValueError('report is not a JSON object')
    if type(report.get('schema_version')) is not int or report['schema_version']!=1 or report.get('evaluation_type')!='automated_proxy':
        raise ValueError('report is not an automated proxy report')
    return {'export_version':EXPORT_VERSION,**_envelope(report),'counts':_copy(_section(report,'counts',dict),COUNT_KEYS,'counts',_is_count),
            'by_lane':_lanes(report),'checks':_checks(report),'provenance':_provenance(report)}


def export_report(report_path,out):
    """Read a finished report, write its export with exclusive create, and return the export.

    A report that is refused leaves no output file, because the export is built before the file is opened."""
    try: report=strict_json(Path(report_path).read_bytes())
    except ValueError: raise ValueError('report is not valid JSON') from None
    export=build_export(report)
    with Path(out).open('xb') as handle: handle.write(canonical_bytes(export)+b'\n')
    return export
