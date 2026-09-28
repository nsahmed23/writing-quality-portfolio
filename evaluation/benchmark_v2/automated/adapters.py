"""Local JSON subprocess protocol and lossless per-call artifacts."""
from __future__ import annotations

import hashlib
import json
import os
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
    if not isinstance(value, dict) or set(value) - {'schema_version','judges','writer','optimizer','timeout_seconds','max_calls'} or value.get('schema_version') != 1:
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
            resolved=[]
            for idx,arg in enumerate(command):
                candidate=path.parent/arg
                if not Path(arg).is_absolute() and not arg.startswith('-') and candidate.exists() and (idx == 0 or '/' in arg or arg.endswith('.py')):
                    resolved.append(str(candidate.resolve()))
                else:
                    resolved.append(arg)
            entry['command']=resolved
    timeout=value.get('timeout_seconds',120)
    max_calls=value.get('max_calls',200)
    if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not (0 < timeout <= 600):
        raise ValueError('timeout_seconds must be >0 and <=600')
    if isinstance(max_calls,bool) or not isinstance(max_calls,int) or max_calls<=0:
        raise ValueError('max_calls must be positive')
    value['timeout_seconds']=timeout
    value['max_calls']=max_calls
    return value


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
    start=time.monotonic()
    response=b''; stderr=b''; returncode=None; error=None
    try:
        with tempfile.TemporaryDirectory(prefix='wq-call-') as work:
            try:
                proc=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=work,shell=False,
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
        elapsed=time.monotonic()-start
        (directory/'response.bin').write_bytes(response)
        (directory/'stderr.bin').write_bytes(stderr)
        meta={'request_sha256':digest(raw),'response_sha256':digest(response),'stderr_sha256':digest(stderr),
              'returncode':returncode,'elapsed_seconds':elapsed,'error':error}
        (directory/'metadata.json').write_bytes(canonical_bytes(meta)+b'\n')
    return {'ok':error is None and returncode==0,'response':response,'stderr':stderr,**meta}
