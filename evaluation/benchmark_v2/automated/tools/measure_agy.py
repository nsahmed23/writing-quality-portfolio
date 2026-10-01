"""Measure what the agy CLI does with a prompt on stdin and with a parent folder's AGENTS.md; write the result as JSON.

Run it from the repository root (it makes a few model calls, so a person runs it, never CI):

    py -3.11 -m evaluation.benchmark_v2.automated.tools.measure_agy AGY_PATH --model MODEL --out RESULT.json

It records three things.
1. agy's `--version` text.
2. Whether agy reads its prompt from stdin: the same call with `-p` absent, and with `-p ""`, each given a prompt on
   stdin that asks for a random token. The token in the reply proves stdin was read; the raw exit code, stdout and
   stderr of both calls are kept either way.
3. Whether agy loads a parent folder's AGENTS.md: a scratch folder holds an AGENTS.md with a canary word, and agy is
   asked for that word once from a plain child folder and once from a fresh `git init` repository beside it. The README
   says a real repository stops agy's walk up to a Git root; this measures that claim.

Every call passes `--sandbox` and the pinned `--model`, never `--dangerously-skip-permissions`, and none inherits a
`GIT_*` variable. A call that fails, times out or prints nothing makes its verdict `inconclusive` instead of a guess."""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from ..adapters import run_captured

SCHEMA_VERSION=1
DEFAULT_TIMEOUT_SECONDS=180
DEFAULT_STDIN_TIMEOUT_SECONDS=90
GIT_INIT_TIMEOUT_SECONDS=30
# Fixed words only: no quote, pipe, ampersand or percent sign, so nothing here changes meaning if an argument is re-parsed.
STDIN_PROMPT='Reply with exactly this token and nothing else: {nonce}'
AGENTS_PROMPT=('What is the canary word in the AGENTS.md instructions loaded in your context? '
               'Answer from the instructions already loaded: do not read or list any file and do not run any command. '
               'Reply with the canary word alone, or with NONE when no AGENTS.md instructions are loaded.')


def first_line(text):
    """The first non-blank line of text, stripped, or None when there is none."""
    for line in (text or '').splitlines():
        if line.strip():
            return line.strip()
    return None


def _clean_env():
    """The environment without any GIT_* variable: GIT_DIR or GIT_WORK_TREE would point agy and git at another repository."""
    return {key:value for key,value in os.environ.items() if not key.startswith('GIT_')}


def _call(argv,*,stdin_text=None,cwd=None,timeout):
    """Run one command and keep how it ended, in the shape every verdict function below reads."""
    done=run_captured(argv,stdin_text=stdin_text,cwd=cwd,env=_clean_env(),timeout=timeout)
    return {'argv':list(argv),'returncode':done['returncode'],'timed_out':done['timed_out'],
            'launch_error':done['launch_error'],'stdout':done['stdout'],'stderr':done['stderr']}


def _finished(call):
    """True when the command ran to an exit code of 0."""
    return call['launch_error'] is None and not call['timed_out'] and call['returncode']==0


def stdin_verdict(variants,nonce):
    """`reads_stdin` when any variant's reply holds the nonce; else `inconclusive` when a variant hung or could not
    start (it may have read stdin too slowly to say); else `ignores_stdin`."""
    if any(_finished(call) and nonce in call['stdout'] for call in variants):
        return 'reads_stdin'
    if any(call['timed_out'] or call['launch_error'] is not None for call in variants):
        return 'inconclusive'
    return 'ignores_stdin'


def canary_loaded(call,canary):
    """True when agy's reply holds the canary, False when it replied with something else, None when there is no answer
    to read (a nonzero exit, a timeout, a launch error, or exit 0 with blank stdout, which agy does when a tool is denied)."""
    if not _finished(call) or first_line(call['stdout']) is None:
        return None
    return canary in call['stdout']


def agents_verdict(plain,repo):
    """What the two canary answers say about the walk from the working directory to a Git root."""
    if plain is None or repo is None:
        return 'inconclusive'
    if plain:
        return 'parent_agents_md_loaded_inside_git_repo' if repo else 'git_init_stops_parent_agents_md'
    return 'parent_agents_md_loaded_only_inside_git_repo' if repo else 'parent_agents_md_not_loaded'


def measure(agy,model,*,timeout_seconds=DEFAULT_TIMEOUT_SECONDS,stdin_timeout_seconds=DEFAULT_STDIN_TIMEOUT_SECONDS,canary=None,nonce=None):
    """Run the measurements against the agy argv (its executable first) and return the result as a JSON-ready dict."""
    agy=list(agy)
    for arg in (*agy,model):
        if str(arg).startswith('--dangerously'):
            raise ValueError('an argument starts with --dangerously; this script never passes it')
    canary=canary or f'canary-{secrets.token_hex(4)}'
    nonce=nonce or f'PINEAPPLE-{secrets.token_hex(4)}'
    base=[*agy,'--sandbox','--model',model,'--output-format','text']
    version=_call([*agy,'--version'],timeout=timeout_seconds)
    version['text']=first_line(version['stdout']) or first_line(version['stderr'])
    prompt=STDIN_PROMPT.format(nonce=nonce)
    variants=[{'name':name,**_call(argv,stdin_text=prompt,timeout=stdin_timeout_seconds)}
              for name,argv in (('p_absent',base),('p_empty',[*base,'-p','']))]
    with tempfile.TemporaryDirectory(prefix='wq-measure-',ignore_cleanup_errors=True) as parent:
        parent=Path(parent)
        (parent/'AGENTS.md').write_text(f'The canary word is {canary}.\n',encoding='utf-8')
        plain=parent/'plain'
        repo=parent/'repo'
        plain.mkdir()
        repo.mkdir()
        init=_call(['git','init','-q'],cwd=repo,timeout=GIT_INIT_TIMEOUT_SECONDS)
        ask=[*base,'-p',AGENTS_PROMPT]
        plain_call=_call(ask,cwd=plain,timeout=timeout_seconds)
        if _finished(init) and (repo/'.git'/'HEAD').is_file():
            repo_call=_call(ask,cwd=repo,timeout=timeout_seconds)
        else:
            repo_call={'argv':ask,'returncode':None,'timed_out':False,'launch_error':f"git init failed: {init['stderr'].strip() or init['returncode']}",
                       'stdout':'','stderr':''}
    in_plain=canary_loaded(plain_call,canary)
    in_repo=canary_loaded(repo_call,canary)
    return {'schema_version':SCHEMA_VERSION,
            'measured_at':datetime.now().astimezone().isoformat(timespec='seconds'),
            'agy':Path(agy[0]).name,
            'model':model,
            'version':version,
            'stdin':{'verdict':stdin_verdict(variants,nonce),'nonce':nonce,'variants':variants},
            'agents_md':{'verdict':agents_verdict(in_plain,in_repo),'canary':canary,
                         'plain_folder':{**plain_call,'canary_in_reply':in_plain},
                         'git_repo':{**repo_call,'canary_in_reply':in_repo}}}


def main(argv=None):
    parser=argparse.ArgumentParser(prog='measure_agy',description='Measure agy stdin and AGENTS.md behavior and write a JSON result.')
    parser.add_argument('agy',help='path to the agy executable')
    parser.add_argument('--model',required=True,help='the agy model slug to pin on every call')
    parser.add_argument('--out',required=True,help='where to write the JSON result; an existing file is never overwritten')
    parser.add_argument('--timeout',type=float,default=DEFAULT_TIMEOUT_SECONDS,help='seconds allowed for each other call')
    parser.add_argument('--stdin-timeout',type=float,default=DEFAULT_STDIN_TIMEOUT_SECONDS,help='seconds allowed for each stdin call')
    args=parser.parse_args(argv)
    found=shutil.which(args.agy)
    if found is None:
        print(f'error: agy not found: {args.agy}',file=sys.stderr)
        return 2
    out=Path(args.out)
    if out.exists():
        print(f'error: refusing to overwrite {out}',file=sys.stderr)
        return 2
    try:
        result=measure([os.path.abspath(found)],args.model,timeout_seconds=args.timeout,stdin_timeout_seconds=args.stdin_timeout)
    except ValueError as exc:
        print(f'error: {exc}',file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f'wrote {out}')
    print(f"version: {result['version']['text']}")
    print(f"stdin: {result['stdin']['verdict']}")
    print(f"agents_md: {result['agents_md']['verdict']}")
    return 0


if __name__=='__main__':
    raise SystemExit(main())
