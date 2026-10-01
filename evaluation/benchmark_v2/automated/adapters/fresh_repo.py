"""Isolation that the two model CLI bridges share: prompt_arg_adapter.py and stdin_repo_adapter.py.

This is a module, not a script to run. Each bridge puts its own folder on sys.path and imports it, as it does with
generic_json_adapter.py. It is listed in the runner's ADAPTER_SCRIPTS like the other files here, so an edit to it
changes the judge signature and needs a new calibration.

A model CLI that loads AGENTS.md or GEMINI.md by walking up from its working directory would otherwise find the ones
above the temp folder, and a Git root ends that walk. So the CLI runs in a new empty directory that is a Git repository
of its own. The repository must be a real one: an empty .git folder did not stop agy 1.2.12. Neither git nor the CLI
inherits a GIT_* variable, because GIT_DIR or GIT_WORK_TREE would send both to some other repository. The directory is
removed afterwards; a call that the runner kills on a timeout can leave a small folder behind in the temp directory.

The CLI's stdout is passed on as it arrives, so a timeout keeps what was written. When the caller gives the prompt as
bytes, a second thread writes it to the CLI's stdin while this one reads stdout. Writing it all first would stall on a
prompt larger than a pipe buffer: a CLI that echoes while it reads fills its stdout pipe, stops reading, and the write
then never finishes.
"""
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

SHIM_SUFFIXES=('.cmd','.bat')
SHELL_NAMES=('cmd','powershell','pwsh')  # a shell that names a .cmd shim as its argument would slip past the suffix check
GIT_INIT_TIMEOUT_SECONDS=30  # git init takes milliseconds; a hung one would otherwise hold the call until the runner's own timeout
FEEDER_JOIN_SECONDS=5  # how long to wait for the stdin writer once the CLI has exited; a writer still stuck then did not deliver the prompt


def refuse_unsafe_program(command):
    """Raise ValueError for a CLI that must not start: a .cmd or .bat shim, a command shell, or a --dangerously* argument."""
    program=Path(command[0])
    suffix=program.suffix.lower()
    if suffix in SHIM_SUFFIXES:
        raise ValueError(f'{command[0]} is a {suffix} script, and cmd.exe would re-parse the prompt; name the native executable')
    if program.stem.lower() in SHELL_NAMES:
        raise ValueError(f'{command[0]} is a command shell, and it would re-parse the prompt; name the native executable')
    for arg in command:
        if arg.startswith('--dangerously'):
            raise ValueError(f'{arg} bypasses the CLI permission checks, and this adapter never passes it')


def git_free_environment():
    """This process's environment without any GIT_* variable; GIT_DIR and GIT_WORK_TREE make git ignore the directory it is in."""
    return {name:value for name,value in os.environ.items() if not name.upper().startswith('GIT_')}


def init_repository(directory,env,timeout):
    try:
        done=subprocess.run(['git','init','-q',directory],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,env=env,timeout=timeout,check=False)
    except FileNotFoundError as exc:
        raise OSError('git was not found, and the model CLI needs a repository of its own to keep it from loading parent instructions') from exc
    except subprocess.TimeoutExpired as exc:
        raise OSError(f'git init timed out after {timeout} seconds') from exc
    if done.returncode!=0:
        raise OSError('git init failed: '+done.stderr.decode('utf-8','replace').strip())
    if not (Path(directory)/'.git'/'HEAD').is_file():
        raise OSError(f'git init succeeded but made no repository in {directory}, and the model CLI needs one of its own')


def copy_stdout(proc):
    """Pass the CLI's stdout on as it arrives, so a timeout keeps what was written. True if any non-blank byte came."""
    answered=False
    while True:
        chunk=proc.stdout.read1(65536)
        if not chunk: return answered
        sys.stdout.buffer.write(chunk)
        sys.stdout.buffer.flush()
        answered=answered or bool(chunk.strip())


def feed_stdin(stream,data,failures):
    """Write `data` to the CLI's stdin and close it; append what went wrong to `failures`.
    A CLI that closed its stdin early breaks the pipe: BrokenPipeError on POSIX, and an OSError (EINVAL) on Windows."""
    try:
        try:
            stream.write(data)
        finally:
            stream.close()
    except Exception as exc:  # recorded for the caller, so a failed write is never mistaken for a delivered prompt
        failures.append(exc)


def run_in_fresh_repository(command,*,prefix,git_init_timeout,stdin_bytes=None):
    """Run `command` in a new Git repository and return (exit code, whether stdout held any text, stdin write error or None).
    With stdin_bytes=None the CLI's stdin is empty from the start; otherwise those bytes are its stdin, followed by end of file."""
    env=git_free_environment()
    with tempfile.TemporaryDirectory(prefix=prefix,ignore_cleanup_errors=True) as work:
        init_repository(work,env,git_init_timeout)
        feeding=stdin_bytes is not None
        with subprocess.Popen(command,cwd=work,env=env,stdin=subprocess.PIPE if feeding else subprocess.DEVNULL,
                              stdout=subprocess.PIPE,stderr=sys.stderr.buffer) as proc:
            failures=[]
            feeder=None
            try:
                if feeding:
                    # The writer thread owns the stdin pipe from here: Popen's own cleanup must not close it under a blocked write.
                    stream,proc.stdin=proc.stdin,None
                    feeder=threading.Thread(target=feed_stdin,args=(stream,stdin_bytes,failures),daemon=True)
                    feeder.start()
                answered=copy_stdout(proc)
            except BaseException:
                proc.kill()
                raise
            code=proc.wait()
            if feeder is not None:
                feeder.join(timeout=FEEDER_JOIN_SECONDS)
                if feeder.is_alive():
                    failures.append(OSError('the writer was still blocked on the pipe after the model CLI exited'))
            return code,answered,(failures[0] if failures else None)
