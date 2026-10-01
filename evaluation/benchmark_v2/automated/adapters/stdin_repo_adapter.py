#!/usr/bin/env python3
"""Bridge JSON requests to a model CLI that reads its prompt from stdin (agy with no -p).

Usage: python stdin_repo_adapter.py -- MODEL_CLI ARG ...
The prompt is the one generic_json_adapter.py writes to a stdin CLI. It goes to MODEL_CLI as UTF-8 bytes on stdin, followed
by end of file, and never as an argument. So the command line has no length cap, and the text being judged stays out of the
process list. ARG ... must not include a prompt option (-p, --prompt, --prompt=...): agy ignores stdin when it is given
one. MODEL_CLI must write only the JSON object on stdout.

MODEL_CLI runs in the same isolation as under prompt_arg_adapter.py, and fresh_repo.py holds the code for both: a new empty
directory that is a Git repository of its own (so no AGENTS.md or GEMINI.md above the temp folder is loaded), no GIT_*
variable for git or MODEL_CLI, and stdout passed on as it arrives so a timeout keeps what was written. The prompt is written
from a second thread while this one reads stdout, so a prompt larger than a pipe buffer cannot stall against a CLI that
echoes as it reads.

The call exits 2 before MODEL_CLI starts when git is missing, git init runs past 30 seconds, git leaves no repository (no
.git/HEAD after git init), MODEL_CLI is a .cmd or .bat file or is cmd, powershell or pwsh, an argument starts with
--dangerously or is a prompt option, the request has no valid role, or the prompt is not valid UTF-8. MODEL_CLI exiting 0
with blank stdout also becomes exit 2, because agy does that when it is denied a tool call; so does MODEL_CLI exiting 0
when its stdin did not take the whole prompt, because that answer rests on text the model never saw. Any other exit code is
passed through, except that on POSIX a MODEL_CLI that a signal killed exits 128 plus the signal number (137 for SIGKILL), as
a shell reports it; a raw -9 would wrap to 247.

Editing this file, fresh_repo.py or any other script in this folder changes the judge signature, so calibrations must rerun.
"""
import argparse
import sys
from pathlib import Path

# The two bridges share their prompt and their isolation; this script is not in a package, so put its own folder on the import path.
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fresh_repo import GIT_INIT_TIMEOUT_SECONDS,refuse_unsafe_program,run_in_fresh_repository
from generic_json_adapter import build_prompt,load_request

PROMPT_OPTIONS=('-p','--prompt')  # agy reads the prompt from stdin only when none of these is given


def refuse_unsafe(command):
    """Raise ValueError for a call that must not start."""
    refuse_unsafe_program(command)
    for arg in command:
        if arg in PROMPT_OPTIONS or arg.startswith('--prompt='):
            raise ValueError(f'{arg} is a prompt option, and this adapter sends the prompt on stdin; leave it out of the command')


def main(argv=None):
    parser=argparse.ArgumentParser(description='model CLI bridge for a CLI that reads its prompt from stdin')
    parser.add_argument('command',nargs=argparse.REMAINDER)
    args=parser.parse_args(argv)
    command=args.command[1:] if args.command and args.command[0]=='--' else args.command
    if not command: parser.error('model CLI argv is required after --')
    try:
        prompt=build_prompt(load_request()).encode('utf-8')  # raises for a lone surrogate, which would otherwise reach the CLI as a mangled prompt
        refuse_unsafe(command)
        code,answered,write_error=run_in_fresh_repository(command,prefix='wq-stdin-repo-',git_init_timeout=GIT_INIT_TIMEOUT_SECONDS,
                                                          stdin_bytes=prompt)
    except (OSError,ValueError,UnicodeError) as exc:
        print(f'stdin repo adapter error: {exc}',file=sys.stderr)
        return 2
    if code==0 and write_error is not None:
        print(f'stdin repo adapter error: the model CLI exited 0 but its stdin did not take the whole prompt ({write_error!r})',file=sys.stderr)
        return 2
    if code==0 and not answered:
        print('stdin repo adapter error: the model CLI exited 0 with no output',file=sys.stderr)
        return 2
    return 128-code if code<0 else code  # POSIX reports death by signal N as -N; sys.exit(-N) would wrap to 256-N

if __name__=='__main__': sys.exit(main())
