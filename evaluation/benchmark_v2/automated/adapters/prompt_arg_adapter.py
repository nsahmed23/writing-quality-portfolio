#!/usr/bin/env python3
"""Bridge JSON requests to a model CLI that takes its prompt as an argument and ignores stdin (agy).

Usage: python prompt_arg_adapter.py -- MODEL_CLI ARG ...
The prompt is the one generic_json_adapter.py writes to a stdin CLI. It is appended as `-p PROMPT`, so ARG ... must not
include a prompt option. MODEL_CLI must write only the JSON object on stdout.

MODEL_CLI runs in a new empty directory that is a Git repository of its own. A CLI that loads AGENTS.md or GEMINI.md by
walking up from its working directory would otherwise find the ones above the temp folder, and a Git root ends that walk.
The repository must be a real one: an empty .git folder did not stop agy 1.2.12. Neither git nor MODEL_CLI inherits a
GIT_* variable, because GIT_DIR or GIT_WORK_TREE would send both to some other repository. The directory is removed
afterwards; a call that the runner kills on a timeout can leave a small wq-prompt-arg-* folder in the temp directory.

The call exits 2 before MODEL_CLI starts when git is missing or leaves no repository (no .git/HEAD after git init),
MODEL_CLI is a .cmd or .bat file or is cmd, powershell or pwsh (a shell would re-parse the prompt), an argument starts
with --dangerously, the request has no valid role, the prompt is not valid UTF-8, or the command line would pass 32,000
UTF-16 units. MODEL_CLI exiting 0 with blank stdout also becomes exit 2, because agy does that when it is denied a tool
call. Any other exit code is passed through unchanged.
"""
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# The two bridges share their prompt; this script is not in a package, so put its own folder on the import path.
sys.path.insert(0,str(Path(__file__).resolve().parent))
from generic_json_adapter import build_prompt,load_request

MAX_COMMAND_LINE_UNITS=32000  # CreateProcess accepts 32,767 UTF-16 units; the difference is headroom
SHIM_SUFFIXES=('.cmd','.bat')
SHELL_NAMES=('cmd','powershell','pwsh')  # a shell that names a .cmd shim as its argument would slip past the suffix check


def command_line_units(command):
    """The length of the command line Windows would be given, in UTF-16 code units."""
    return len(subprocess.list2cmdline(command).encode('utf-16-le'))//2


def refuse_unsafe(command,full):
    """Raise ValueError for a call that must not start; `full` is `command` plus the prompt argument."""
    program=Path(command[0])
    suffix=program.suffix.lower()
    if suffix in SHIM_SUFFIXES:
        raise ValueError(f'{command[0]} is a {suffix} script, and cmd.exe would re-parse the prompt; name the native executable')
    if program.stem.lower() in SHELL_NAMES:
        raise ValueError(f'{command[0]} is a command shell, and it would re-parse the prompt; name the native executable')
    for arg in command:
        if arg.startswith('--dangerously'):
            raise ValueError(f'{arg} bypasses the CLI permission checks, and this adapter never passes it')
    units=command_line_units(full)
    if units>MAX_COMMAND_LINE_UNITS:
        raise ValueError(f'the prompt makes a command line of {units} UTF-16 units, over the limit of {MAX_COMMAND_LINE_UNITS}')


def git_free_environment():
    """This process's environment without any GIT_* variable; GIT_DIR and GIT_WORK_TREE make git ignore the directory it is in."""
    return {name:value for name,value in os.environ.items() if not name.upper().startswith('GIT_')}


def init_repository(directory,env):
    try:
        done=subprocess.run(['git','init','-q',directory],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,env=env,check=False)
    except FileNotFoundError as exc:
        raise OSError('git was not found, and the model CLI needs a repository of its own to keep it from loading parent instructions') from exc
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


def run_in_fresh_repository(command):
    """Run `command` in a new Git repository and return (exit code, whether stdout held any text)."""
    env=git_free_environment()
    with tempfile.TemporaryDirectory(prefix='wq-prompt-arg-',ignore_cleanup_errors=True) as work:
        init_repository(work,env)
        with subprocess.Popen(command,cwd=work,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=sys.stderr.buffer) as proc:
            try:
                answered=copy_stdout(proc)
            except BaseException:
                proc.kill()
                raise
            return proc.wait(),answered


def main(argv=None):
    parser=argparse.ArgumentParser(description='model CLI bridge for a CLI that takes its prompt as an argument')
    parser.add_argument('command',nargs=argparse.REMAINDER)
    args=parser.parse_args(argv)
    command=args.command[1:] if args.command and args.command[0]=='--' else args.command
    if not command: parser.error('model CLI argv is required after --')
    try:
        prompt=build_prompt(load_request())
        prompt.encode('utf-8')  # raises for a lone surrogate, which would otherwise reach the CLI as a mangled prompt
        full=[*command,'-p',prompt]
        refuse_unsafe(command,full)
        code,answered=run_in_fresh_repository(full)
    except (OSError,ValueError,UnicodeError) as exc:
        print(f'prompt argument adapter error: {exc}',file=sys.stderr)
        return 2
    if code==0 and not answered:
        print('prompt argument adapter error: the model CLI exited 0 with no output',file=sys.stderr)
        return 2
    return code

if __name__=='__main__': sys.exit(main())
