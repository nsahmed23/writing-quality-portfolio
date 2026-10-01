#!/usr/bin/env python3
"""Bridge JSON requests to a model CLI that takes its prompt as an argument and ignores stdin.

Usage: python prompt_arg_adapter.py -- MODEL_CLI ARG ...
Transport: the prompt is the one generic_json_adapter.py writes to a stdin CLI. It is appended as `-p PROMPT`, so ARG ...
must not include a prompt option, and the whole command line, owner text included, is visible in the process list and
capped at 32,000 UTF-16 units. A CLI that reads the prompt from stdin (agy does, when it is not given -p) is better served
by stdin_repo_adapter.py, which has neither limit. MODEL_CLI must write only the JSON object on stdout.

MODEL_CLI runs in a new empty directory that is a Git repository of its own; fresh_repo.py, which this script shares with
stdin_repo_adapter.py, holds that code. A CLI that loads AGENTS.md or GEMINI.md by walking up from its working directory
would otherwise find the ones above the temp folder, and a Git root ends that walk. The repository must be a real one: an
empty .git folder did not stop agy 1.2.12. Neither git nor MODEL_CLI inherits a GIT_* variable, because GIT_DIR or
GIT_WORK_TREE would send both to some other repository. The directory is removed afterwards; a call that the runner kills
on a timeout can leave a small wq-prompt-arg-* folder in the temp directory.

The call exits 2 before MODEL_CLI starts when git is missing, git init runs past 30 seconds, git leaves no repository
(no .git/HEAD after git init), MODEL_CLI is a .cmd or .bat file or is cmd, powershell or pwsh (a shell would re-parse
the prompt), an argument starts with --dangerously, the request has no valid role, the prompt is not valid UTF-8, or
the command line would pass 32,000 UTF-16 units. MODEL_CLI exiting 0 with blank stdout also becomes exit 2, because agy
does that when it is denied a tool call. Any other exit code is passed through, except that on POSIX a MODEL_CLI that a
signal killed exits 128 plus the signal number (137 for SIGKILL), as a shell reports it; a raw -9 would wrap to 247.
"""
import argparse
import subprocess
import sys
from pathlib import Path

# The two bridges share their prompt and their isolation; this script is not in a package, so put its own folder on the import path.
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fresh_repo import GIT_INIT_TIMEOUT_SECONDS,refuse_unsafe_program,run_in_fresh_repository
from generic_json_adapter import build_prompt,load_request

MAX_COMMAND_LINE_UNITS=32000  # CreateProcess accepts 32,767 UTF-16 units; the difference is headroom


def command_line_units(command):
    """The length of the command line Windows would be given, in UTF-16 code units."""
    return len(subprocess.list2cmdline(command).encode('utf-16-le'))//2


def refuse_unsafe(command,full):
    """Raise ValueError for a call that must not start; `full` is `command` plus the prompt argument."""
    refuse_unsafe_program(command)
    units=command_line_units(full)
    if units>MAX_COMMAND_LINE_UNITS:
        raise ValueError(f'the prompt makes a command line of {units} UTF-16 units, over the limit of {MAX_COMMAND_LINE_UNITS}')


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
        code,answered,_=run_in_fresh_repository(full,prefix='wq-prompt-arg-',git_init_timeout=GIT_INIT_TIMEOUT_SECONDS)
    except (OSError,ValueError,UnicodeError) as exc:
        print(f'prompt argument adapter error: {exc}',file=sys.stderr)
        return 2
    if code==0 and not answered:
        print('prompt argument adapter error: the model CLI exited 0 with no output',file=sys.stderr)
        return 2
    return 128-code if code<0 else code  # POSIX reports death by signal N as -N; sys.exit(-N) would wrap to 256-N

if __name__=='__main__': sys.exit(main())
