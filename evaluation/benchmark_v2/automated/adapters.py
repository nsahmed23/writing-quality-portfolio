"""Local JSON subprocess protocol and lossless per-call artifacts."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
from pathlib import Path
import subprocess
import tempfile
import time


def canonical_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_config(path):
    from .contracts import strict_json
    path = Path(path).resolve()
    value = strict_json(path.read_bytes())
    if not isinstance(value, dict) or set(value) - {'schema_version','judges','writer','optimizer','timeout_seconds','max_calls','version_commands','isolation_probe'} or value.get('schema_version') != 1:
        raise ValueError('invalid config schema')
    judges = value.get('judges')
    if not isinstance(judges,list) or not judges:
        raise ValueError('config needs judges')
    if len({j.get('id') for j in judges if isinstance(j,dict)}) != len(judges):
        raise ValueError('duplicate judge id')
    for key in ('judges','writer','optimizer'):
        entries = value[key] if key == 'judges' else ([value[key]] if key in value else [])
        for entry in entries:
            if not isinstance(entry,dict) or set(entry) != {'id','family','command'}:
                raise ValueError(f'invalid {key} adapter')
            if any(not isinstance(entry[k],str) or not entry[k].strip() for k in ('id','family')):
                raise ValueError(f'invalid {key} id/family')
            command=entry['command']
            if not isinstance(command,list) or not command or any(not isinstance(arg,str) or not arg for arg in command):
                raise ValueError(f'invalid {key} command')
            entry['command']=_resolve_command(command,path.parent)
    timeout=value.get('timeout_seconds',300)
    max_calls=value.get('max_calls',2000)
    if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not (0 < timeout <= 600):
        raise ValueError('timeout_seconds must be >0 and <=600')
    if isinstance(max_calls,bool) or not isinstance(max_calls,int) or max_calls<=0:
        raise ValueError('max_calls must be positive')
    value['timeout_seconds']=timeout
    value['max_calls']=max_calls
    value['version_commands']=_version_commands(value.get('version_commands',{}))
    if 'isolation_probe' in value:
        value['isolation_probe']=_isolation_probe(value['isolation_probe'],path.parent)
    return value


def _resolve_command(command,base):
    """Replace each argument that names a file beside the config (the executable, a script, or a path with a slash) by its absolute path."""
    resolved=[]
    for idx,arg in enumerate(command):
        candidate=base/arg
        if not Path(arg).is_absolute() and not arg.startswith('-') and candidate.exists() and (idx == 0 or '/' in arg or arg.endswith('.py')):
            resolved.append(str(candidate.resolve()))
        else:
            resolved.append(arg)
    return resolved


def _isolation_probe(probe,base):
    """Validate the optional isolation_probe object: the argv that asks the writer one question, and the prompt-token limit."""
    if not isinstance(probe,dict) or set(probe)!={'command','max_prompt_tokens'}:
        raise ValueError('isolation_probe must be an object with exactly command and max_prompt_tokens')
    command=probe['command']
    if not isinstance(command,list) or not command or any(not isinstance(arg,str) or not arg.strip() for arg in command):
        raise ValueError('isolation_probe command must be a nonempty list of nonblank strings')
    limit=probe['max_prompt_tokens']
    if isinstance(limit,bool) or not isinstance(limit,int) or limit<=0:
        raise ValueError('isolation_probe max_prompt_tokens must be a positive integer')
    return {'command':_resolve_command(command,base),'max_prompt_tokens':limit}


def _version_commands(commands):
    """Validate the optional version_commands object: a tool name, then the argv that prints its version."""
    if not isinstance(commands,dict):
        raise ValueError('version_commands must be an object')
    for name,argv in commands.items():
        if not re.fullmatch(r'[A-Za-z0-9_.-]+',name):
            raise ValueError(f'invalid version command name: {name!r}')
        if not isinstance(argv,list) or not argv or any(not isinstance(part,str) or not part.strip() for part in argv):
            raise ValueError(f'version command {name} must be a nonempty list of nonblank strings')
    return commands


def _resolved(argv):
    """argv with its first element replaced by the executable `shutil.which` finds, or argv itself when none is found.

    On Windows an npm shim such as `codex` is `codex.cmd`, and CreateProcess does not search PATHEXT,
    so the bare name would never start. Only version commands go through here: they carry no prompt,
    so running a .cmd target through cmd.exe is safe, unlike for an adapter command. The found path is made
    absolute because the command runs in a scratch folder, where a relative PATH entry would point nowhere."""
    found=shutil.which(argv[0])
    return [os.path.abspath(found),*argv[1:]] if found else list(argv)


def _version_of(argv,timeout=30):
    """First non-blank line of one version command's standard output, or of its standard error when
    standard output has no non-blank line; None when the command fails, times out or prints nothing.

    The command gets no stdin and runs in a temporary scratch folder, not the caller's working
    directory. Its output goes to files rather than pipes: a child that leaves a grandchild holding
    a pipe open would block the read after a timeout on Windows."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as scratch:
        scratch=Path(scratch)
        try:
            with open(scratch/'out.txt','wb') as out, open(scratch/'err.txt','wb') as err:
                done=subprocess.run(_resolved(argv),stdin=subprocess.DEVNULL,stdout=out,stderr=err,cwd=scratch,timeout=timeout)
            if done.returncode!=0:
                return None
            for name in ('out.txt','err.txt'):
                for line in (scratch/name).read_text(encoding='utf-8',errors='replace').splitlines():
                    if line.strip():
                        return line.strip()
        except (OSError,ValueError,subprocess.TimeoutExpired):
            return None
    return None


def _kill_tree(proc):
    """Stop a timed-out child and what it started: killpg on POSIX, taskkill /T on Windows (fixed argv, no shell)."""
    if os.name=='posix':
        try:
            os.killpg(proc.pid,signal.SIGKILL)
        except OSError:
            proc.kill()
    else:
        subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
        if proc.poll() is None: proc.kill()


def run_captured(argv,*,stdin_text=None,cwd=None,env=None,timeout=120):
    """Run argv once, without a shell, and report how it ended: returncode (None when it never finished), timed_out,
    launch_error (None unless it could not start), and stdout and stderr decoded as UTF-8 with bad bytes replaced.

    stdin_text None gives the child no stdin; a string (even empty) is its whole stdin. The child runs in cwd, or in a
    scratch folder. Output goes to files rather than pipes, as in _version_of, so a grandchild that outlives a timeout
    cannot hold the read open. The executable goes through _resolved, so keep prompts off argv when argv[0] may be a
    .cmd shim; the callers here pass fixed words only."""
    result={'returncode':None,'timed_out':False,'launch_error':None,'stdout':'','stderr':''}
    with tempfile.TemporaryDirectory(prefix='wq-run-',ignore_cleanup_errors=True) as scratch:
        scratch=Path(scratch)
        (scratch/'in.txt').write_bytes((stdin_text or '').encode('utf-8'))
        try:
            with open(scratch/'in.txt','rb') as stdin, open(scratch/'out.txt','wb') as out, open(scratch/'err.txt','wb') as err:
                proc=subprocess.Popen(_resolved(argv),stdin=stdin if stdin_text is not None else subprocess.DEVNULL,
                                      stdout=out,stderr=err,cwd=cwd if cwd is not None else scratch,env=env,shell=False,
                                      start_new_session=(os.name=='posix'),
                                      creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0))
                try:
                    proc.wait(timeout=timeout)
                    result['returncode']=proc.returncode
                except subprocess.TimeoutExpired:
                    result['timed_out']=True
                    _kill_tree(proc)
                    try:
                        proc.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        pass
        except (OSError,ValueError) as exc:
            result['launch_error']=str(exc)
        for key,name in (('stdout','out.txt'),('stderr','err.txt')):
            if (scratch/name).exists():
                result[key]=(scratch/name).read_text(encoding='utf-8',errors='replace')
    return result


def tool_versions(config,timeout=30):
    """Map each configured version command name to its version text, or None when it cannot be read."""
    return {name:_version_of(argv,timeout) for name,argv in sorted(config.get('version_commands',{}).items())}


class Budget:
    def __init__(self,max_calls):
        self.limit=max_calls
        self.used=0

    def preflight(self,needed):
        if self.used + needed > self.limit:
            raise ValueError(f'call budget exceeded: need {self.used+needed}, max_calls={self.limit}')

    def charge(self):
        self.preflight(1)
        self.used+=1


def run_call(command, request, directory, *, timeout_seconds=120):
    """Run once without a shell; retain first raw response, stderr and metadata on every exit."""
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=False)
    raw=canonical_bytes(request)
    (directory/'request.json').write_bytes(raw)
    response_file=(directory/'provider-response.bin').resolve()
    start=time.monotonic()
    response=b''; stderr=b''; returncode=None; error=None
    try:
        with tempfile.TemporaryDirectory(prefix='wq-call-') as work:
            try:
                proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=work,shell=False,
                                      env={**os.environ,'WQ_EVAL_FINAL_RESPONSE_FILE':str(response_file)},
                                      start_new_session=(os.name=='posix'),
                                      creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name=='nt' else 0))
                try:
                    response,stderr=proc.communicate(raw,timeout=timeout_seconds)
                except subprocess.TimeoutExpired as exc:
                    if os.name=='posix':
                        os.killpg(proc.pid,signal.SIGKILL)
                    else:
                        # Windows taskkill /T terminates child processes as well as the adapter.
                        # Fixed argv, no shell or model-generated command execution.
                        subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],
                                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=False)
                        if proc.poll() is None: proc.kill()
                    rest_out,rest_err=proc.communicate()
                    # communicate() after timeout may return the entire buffered prefix; use it when present.
                    response=rest_out if rest_out.startswith(exc.stdout or b'') else (exc.stdout or b'')+rest_out
                    stderr=rest_err if rest_err.startswith(exc.stderr or b'') else (exc.stderr or b'')+rest_err
                    error='timeout'
                returncode=proc.returncode
            except OSError as exc:
                error=f'launch_error: {exc}'
    finally:
        # A file emitted by an adapter survives termination of its process group.
        # When present it is the provider response; stdout remains the fallback
        # for generic adapters and for failures before the provider wrote a file.
        if response_file.is_file():
            # Keep the original stdout distinct when the sidecar takes priority.
            (directory/'adapter-stdout.bin').write_bytes(response)
            adapter_stdout_sha256=digest(response)
            response=response_file.read_bytes()
            response_file.unlink()
        else:
            adapter_stdout_sha256=None
        elapsed=time.monotonic()-start
        (directory/'response.bin').write_bytes(response)
        (directory/'stderr.bin').write_bytes(stderr)
        meta={'request_sha256':digest(raw),'response_sha256':digest(response),'stderr_sha256':digest(stderr),
              'returncode':returncode,'elapsed_seconds':elapsed,'error':error}
        if adapter_stdout_sha256 is not None:
            meta['adapter_stdout_sha256']=adapter_stdout_sha256
        (directory/'metadata.json').write_bytes(canonical_bytes(meta)+b'\n')
    return {'ok':error is None and returncode==0,'response':response,'stderr':stderr,**meta}
