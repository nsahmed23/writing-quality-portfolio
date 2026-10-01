"""Harvest candidate suite cases from the owner's own Claude Code transcripts.

A candidate is one owner turn that asks for writing (draft, tighten, reply and similar) and carries its source text:
a pasted block, a fenced block, text under the instruction line, or the assistant message right before the turn.
Nothing here calls a model. The harvest runs on the owner's machine and writes three files, all of which hold or
describe owner text, so --out must lie inside WQ_EVAL_PRIVATE_ROOT:

  candidates.json  suite-shaped cases (no split yet; a later step assigns it)
  sidecar.json     per case: the owner's next turn as a correction, and hints for the privacy pass
  exclusions.json  counts only: skips and exclusions by reason, lane, length bucket

Run from the repository root. Transcripts are read only when named, so the run needs --allow NAME (repeatable) or
--allow-all, and only the *.jsonl files directly inside a project folder are read (subfolders hold subagents):

  $env:WQ_EVAL_PRIVATE_ROOT='<an existing folder outside this repository>'
  py -3.11 -m evaluation.benchmark_v2.automated.tools.harvest --allow-all --out "$env:WQ_EVAL_PRIVATE_ROOT/harvest/v1"

Standard output carries aggregates only. An existing output file is never overwritten."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

from ..contracts import case_fingerprint
from ..private import require_private_output

CONTEXT_CAP=2500       # a source longer than this is excluded (over_cap)
CORRECTION_CAP=2500    # the owner's next turn is kept up to this many characters
INLINE_MIN=80          # text under the instruction line must run this long to count as a source
INSTRUCTION_LINE_MAX=300
INSTRUCTION_MAX=600    # a longer instruction is a task brief that happens to name a verb, not a writing request
FOLLOW_UP_MAX=400      # a turn that points back at the assistant's last message stays short
MAX_TURN=200_000       # beyond this an owner turn is not scanned at all
LICENSE='owner_private'
SUITE_NAME='owner-harvest-candidates'
OUT_NAMES=('candidates.json','sidecar.json','exclusions.json')
PROGRAMMATIC_SOURCES=('sdk','system')
COMPACT_PREFIX='This session is being continued from a previous conversation'
COMMAND_PREFIXES=('<command-name>','<command-message>','<command-args>','<local-command-stdout>',
                  '<local-command-stderr>','<local-command-caveat>')
# Turns the harness or another session writes into the transcript as if the owner had typed them.
MACHINE_PREFIXES=('Another Claude session sent','<teammate-message','<task-notification','[Request interrupted')
VERBS=('draft','write','rewrite','reword','tighten','shorten','trim','edit','proofread','polish','simplify',
       'clarify','reply','respond','summarize','summarise','rephrase','condense')
CODE_LANGUAGES=frozenset((
    'python','py','javascript','js','typescript','ts','tsx','jsx','json','jsonc','yaml','yml','toml','bash','sh',
    'shell','zsh','powershell','ps1','pwsh','bat','cmd','go','rust','rs','zig','c','cpp','h','java','kotlin',
    'swift','ruby','rb','php','lua','sql','html','css','scss','xml','diff','ini','dockerfile','makefile',
    'csharp','cs','r','perl','dart','scala'))

_REMINDER_RE=re.compile(r'<system-reminder>.*?</system-reminder>',re.S)
_PASTED_RE=re.compile(r'<pasted_content\b[^>]*>(.*?)</pasted_content>',re.S|re.I)
_FENCE_RE=re.compile(r'^[ \t]*```([^\n`]*)\n(.*?)\n[ \t]*```[ \t]*$',re.S|re.M)
_VERB_RE=re.compile(r'\b('+'|'.join(VERBS)+r')\b|\bmake (?:this|it|that|these|those)(?: \w+)? '
                    r'(?:clearer|shorter|tighter|simpler|better|more concise)\b',re.I)
_COMMUNICATION_RE=re.compile(r'\b(?:e-?mails?|messages?|repl(?:y|ies|ied|ying)|respon(?:d|ds|se|ses)|'
                             r'announce(?:ment|ments)?|slack|dms?|memo|letter|invitation|note to)\b',re.I)
_POINTER_RE=re.compile(r'\b(?:this|that|it|these|those|above|previous|last|earlier|'
                       r'your (?:draft|reply|response|answer|message|version|summary))\b',re.I)


def length_bucket(n):
    """Bucket label for the length of a kept source (it can never exceed the cap)."""
    for top,label in ((299,'0-299'),(999,'300-999'),(1999,'1000-1999'),(CONTEXT_CAP,'2000-2500')):
        if n<=top: return label
    return f'{CONTEXT_CAP+1}+'


def over_cap_bucket(n):
    if n<=5000: return '2501-5000'
    if n<=10000: return '5001-10000'
    return '10001+'


def _clean(text):
    """Make text safe to write as UTF-8: a lone surrogate (a few transcripts carry one) becomes '?'."""
    return text.encode('utf-8','replace').decode('utf-8')


def _collapse(text):
    return re.sub(r'\n{3,}','\n\n',text).strip()


def _digest(*parts):
    return hashlib.sha256('\x1f'.join(parts).encode('utf-8','replace')).hexdigest()[:16]


def user_text(event):
    """Return (text, None) for an owner text turn, or (None, reason) for a user line that is not one."""
    message=event.get('message')
    content=message.get('content') if isinstance(message,dict) else None
    if isinstance(content,list):
        if any(isinstance(b,dict) and b.get('type')=='tool_result' for b in content): return None,'tool_result'
        text='\n'.join(b['text'] for b in content
                       if isinstance(b,dict) and b.get('type')=='text' and isinstance(b.get('text'),str))
    elif isinstance(content,str): text=content
    else: return None,'empty'
    if event.get('isMeta'): return None,'meta'
    if event.get('isSidechain'): return None,'sidechain'
    origin=event.get('origin')
    kind=origin.get('kind') if isinstance(origin,dict) else None
    if kind not in (None,'human'): return None,'machine_origin'
    if kind!='human' and event.get('promptSource') in PROGRAMMATIC_SOURCES: return None,'programmatic'
    if event.get('isCompactSummary'): return None,'compact_summary'
    stripped=_REMINDER_RE.sub('',text).strip()
    if not stripped: return None,('system_reminder_only' if text.strip() else 'empty')
    if stripped.startswith(COMPACT_PREFIX): return None,'compact_summary'
    if stripped.startswith(COMMAND_PREFIXES): return None,'command_wrapper'
    if stripped.startswith(MACHINE_PREFIXES): return None,'machine_text'
    return _clean(stripped),None


def assistant_text(event):
    """The text blocks of one assistant line, or '' when it carries none (tool calls, thinking)."""
    message=event.get('message')
    content=message.get('content') if isinstance(message,dict) else None
    if isinstance(content,str): return content.strip()
    if not isinstance(content,list): return ''
    return '\n'.join(b['text'] for b in content
                     if isinstance(b,dict) and b.get('type')=='text' and isinstance(b.get('text'),str)).strip()


def _is_code(info):
    words=info.strip().lower().split()
    return bool(words) and words[0].rstrip(',;') in CODE_LANGUAGES


def split_turn(text):
    """Split an owner turn into (kind, instruction, source).

    kind is pasted, fenced, code_source (fences hold code only), inline, or None when the turn names no source
    of its own; then instruction is the whole turn."""
    pasted=[b.strip() for b in _PASTED_RE.findall(text)]
    if any(pasted):
        return 'pasted',_collapse(_PASTED_RE.sub('',text)),'\n\n'.join(b for b in pasted if b)
    fences=_FENCE_RE.findall(text)
    if fences:
        prose=[body.strip() for info,body in fences if body.strip() and not _is_code(info)]
        instruction=_collapse(_FENCE_RE.sub('',text))
        return ('fenced',instruction,'\n\n'.join(prose)) if prose else ('code_source',instruction,None)
    lines=text.split('\n')
    start=next((i for i,line in enumerate(lines) if line.strip()),None)
    if start is None: return None,text.strip(),None
    first=lines[start].strip()
    rest='\n'.join(lines[start+1:]).strip()
    if len(first)<=INSTRUCTION_LINE_MAX:
        if len(rest)>=INLINE_MIN: return 'inline',first,rest
        head,colon,tail=first.partition(':')
        body=(tail+'\n'+rest).strip()
        if colon and len(body)>=INLINE_MIN: return 'inline',head.strip()+':',body
    return None,text.strip(),None


def instruction_verb(text):
    """The first writing verb in the instruction, or None. A "make this shorter" phrase counts as make_adjective."""
    match=_VERB_RE.search(text)
    if not match: return None
    return match.group(1).lower() if match.group(1) else 'make_adjective'


def analyse_turn(text,previous):
    """Decide what one owner turn is: ('excluded', reason, length) or ('case', fields, None)."""
    if len(text)>MAX_TURN: return 'excluded','turn_too_long',len(text)
    has_pasted=bool(_PASTED_RE.search(text))
    kind,instruction,source=split_turn(text)
    verb=instruction_verb(instruction)
    if verb is None: return 'excluded','no_instruction',0
    if len(instruction)>INSTRUCTION_MAX: return 'excluded','long_instruction',0
    if kind=='code_source': return 'excluded','code_source',0
    if kind is None:
        # No source in the turn: only a short follow-up that points back may take the assistant's last message.
        if not previous or len(text)>FOLLOW_UP_MAX or not _POINTER_RE.search(text): return 'excluded','no_source',0
        kind,instruction,source='previous_assistant',text.strip(),_clean(previous.strip())
    if len(source)>CONTEXT_CAP: return 'excluded','over_cap',len(source)
    return 'case',{'kind':kind,'verb':verb,'prompt':instruction,'source':source,'has_pasted_content':has_pasted},None


def make_case(session,uuid,project,fields):
    source=fields['source']
    lane='communication' if _COMMUNICATION_RE.search(fields['prompt']) else 'editing'
    return {'id':'case-'+_digest('case',session,uuid),'document_id':'doc-'+_digest('document',session),
            'lane':lane,'prompt':fields['prompt'],'context':source,'a':source,'b':source,'expected':None,
            'checks':{},'provenance':{'kind':'owner_session','source':project,'license':LICENSE}}


class Harvest:
    """Streams transcripts one line at a time and keeps only candidates, hints and counts."""

    def __init__(self):
        self.cases=[]
        self.sidecar={}
        self.fingerprints=set()
        self.skipped=Counter()
        self.excluded=Counter()
        self.over_cap=Counter()
        self.by_lane=Counter()
        self.by_kind=Counter()
        self.by_verb=Counter()
        self.lengths=Counter()
        self.owner_turns=0
        self.files=0
        self.lines=0
        self.bad_lines=0
        self.projects=set()
        self.projects_with_cases=set()

    def read_project(self,folder):
        files=sorted(p for p in folder.glob('*.jsonl') if p.is_file())
        if not files: return
        self.projects.add(folder.name)
        for path in files: self.read_file(folder.name,path)

    def read_file(self,project,path):
        self.files+=1
        previous=None   # text of the latest assistant line; an owner turn reads it, then it is gone
        pending=None    # id of the latest case, until the owner's next turn answers it
        responded=False  # an assistant line has come since that case
        with open(path,'r',encoding='utf-8',errors='replace') as fh:
            for number,raw in enumerate(fh,1):
                if not raw.strip(): continue
                self.lines+=1
                try: event=json.loads(raw)
                except ValueError: event=None
                if not isinstance(event,dict):
                    self.bad_lines+=1
                    continue
                kind=event.get('type')
                if kind=='assistant':
                    if event.get('isSidechain'): continue
                    responded=True
                    text=assistant_text(event)
                    if text: previous=text
                    continue
                if kind!='user': continue
                text,reason=user_text(event)
                if reason:
                    self.skipped[reason]+=1
                    continue
                self.owner_turns+=1
                if pending is not None:
                    if responded: self._attach_correction(pending,text)
                    pending=None
                verdict,detail,length=analyse_turn(text,previous)
                previous=None
                if verdict=='excluded':
                    self._exclude(detail,length)
                    continue
                session=event.get('sessionId') if isinstance(event.get('sessionId'),str) else path.stem
                uuid=event.get('uuid') if isinstance(event.get('uuid'),str) else f'line{number}'
                case=self._add_case(session,uuid,project,detail)
                if case is not None:
                    pending,responded=case['id'],False

    def _exclude(self,reason,length):
        self.excluded[reason]+=1
        if reason=='over_cap': self.over_cap[over_cap_bucket(length)]+=1

    def _attach_correction(self,case_id,text):
        entry=self.sidecar[case_id]
        entry['correction']=text[:CORRECTION_CAP]
        entry['correction_truncated']=len(text)>CORRECTION_CAP

    def _add_case(self,session,uuid,project,fields):
        case=make_case(session,uuid,project,fields)
        fingerprint=case_fingerprint(case)
        if fingerprint in self.fingerprints:
            self._exclude('duplicate_pair',0)
            return None
        self.fingerprints.add(fingerprint)
        self.cases.append(case)
        self.sidecar[case['id']]={'correction':None,'correction_truncated':False,'source_kind':fields['kind'],
                                  'has_pasted_content':fields['has_pasted_content']}
        self.projects_with_cases.add(project)
        self.by_lane[case['lane']]+=1
        self.by_kind[fields['kind']]+=1
        self.by_verb[fields['verb']]+=1
        self.lengths[length_bucket(len(fields['source']))]+=1
        return case

    def report(self):
        """Counts only: nothing here can carry owner text."""
        return {
            'format':1,
            'scanned':{'projects':len(self.projects),'files':self.files,'lines':self.lines,
                       'unparsable_lines':self.bad_lines},
            'owner_turns':self.owner_turns,
            'skipped_turns':dict(self.skipped),
            'exclusions':dict(self.excluded),
            'over_cap_length_buckets':dict(self.over_cap),
            'candidates':{
                'total':len(self.cases),
                'projects':len(self.projects_with_cases),
                'by_lane':dict(self.by_lane),
                'by_source_kind':dict(self.by_kind),
                'by_verb':dict(self.by_verb),
                'length_buckets':dict(self.lengths),
                'with_correction':sum(1 for e in self.sidecar.values() if e['correction'] is not None),
                'with_pasted_content':sum(1 for e in self.sidecar.values() if e['has_pasted_content']),
            },
        }


def _refuse(message):
    print(f'error: {message}',file=sys.stderr)
    return 2


def _dump(payload):
    return json.dumps(payload,indent=2,ensure_ascii=False,sort_keys=True)+'\n'


def main(argv=None):
    parser=argparse.ArgumentParser(prog='harvest',description='Harvest candidate cases from Claude Code transcripts.')
    parser.add_argument('--projects-root',default=str(Path.home()/'.claude'/'projects'),
                        help='folder of project folders (default ~/.claude/projects)')
    parser.add_argument('--allow',action='append',default=[],metavar='NAME',
                        help='project folder to read; repeat for more')
    parser.add_argument('--allow-all',action='store_true',help='read every project folder')
    parser.add_argument('--out',required=True,help='new folder inside WQ_EVAL_PRIVATE_ROOT for the three outputs')
    args=parser.parse_args(argv)
    if args.allow and args.allow_all: return _refuse('use --allow NAME or --allow-all, not both')
    if not args.allow and not args.allow_all:
        return _refuse('refusing to read any transcript; pass --allow NAME (repeatable) or --allow-all')
    root=Path(args.projects_root).expanduser()
    if not root.is_dir(): return _refuse('--projects-root is not a folder')
    folders=sorted((p for p in root.iterdir() if p.is_dir()),key=lambda p:p.name)
    if args.allow:
        names=set(args.allow)
        if not names<={p.name for p in folders}: return _refuse('an --allow name matches no project folder')
        folders=[p for p in folders if p.name in names]
    out=Path(args.out)
    try: require_private_output({'cases':[{'provenance':{'kind':'owner_session'}}]},out)
    except ValueError as exc: return _refuse(str(exc))
    if out.exists() and not out.is_dir(): return _refuse('--out exists and is not a folder')
    if any((out/name).exists() for name in OUT_NAMES): return _refuse('refusing to overwrite an existing harvest output')
    started=time.monotonic()
    harvest=Harvest()
    for folder in folders: harvest.read_project(folder)
    report=harvest.report()
    payloads=(('candidates.json',{'schema_version':1,'name':SUITE_NAME,'cases':harvest.cases}),
              ('sidecar.json',{'schema_version':1,'cases':harvest.sidecar}),
              ('exclusions.json',report))
    out.mkdir(parents=True,exist_ok=True)
    try:
        for name,payload in payloads:
            with open(out/name,'x',encoding='utf-8',newline='\n') as fh: fh.write(_dump(payload))
    except FileExistsError: return _refuse('refusing to overwrite an existing harvest output')
    printed=dict(report,elapsed_seconds=round(time.monotonic()-started,1),out=str(out))
    print(json.dumps(printed,indent=2,sort_keys=True))
    return 0


if __name__=='__main__': raise SystemExit(main())
