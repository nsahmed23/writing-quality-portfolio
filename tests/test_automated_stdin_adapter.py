"""stdin_repo_adapter.py bridges JSON requests to a model CLI that reads its prompt from stdin (agy with no -p).

Every call is a local subprocess against a stand-in CLI; no model is called. The adapter keeps every protection that
prompt_arg_adapter.py has (a Git repository of its own, no GIT_* variable, no shell or .cmd shim, no --dangerously flag,
blank output is an error) and must not stall on a prompt larger than a pipe buffer, which a CLI that echoes while it reads
would otherwise fill in both directions."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from evaluation.benchmark_v2.automated import runner
from evaluation.benchmark_v2.automated.adapters import Budget, canonical_bytes, run_call

AUTOMATED = Path(__file__).resolve().parents[1] / "evaluation" / "benchmark_v2" / "automated"
ADAPTERS = AUTOMATED / "adapters"
REQUEST = {"role": "judge", "request_id": "r1", "prompt": "inspect", "context": "", "A": "alpha", "B": "beta",
           "rubric": [{"id": "meaning", "description": "Preserve meaning."}]}
# Text that Windows argument parsing, shells and locale decoding each get wrong somewhere; built with chr() to keep this file ASCII.
AWKWARD = ('quote " backslash \\ percent %PATH% amp & pipe | caret ^ angle <> combining ' + chr(0x301) + ' accent ' + chr(0xe9)
           + ' dash ' + chr(0x2014) + ' cjk ' + chr(0x65e5) + chr(0x672c) + ' emoji ' + chr(0x1F600))
ONE_AND_A_TENTH_MEGABYTES = 1_100_000

# Records what the adapter gave it, then behaves as `mode` says. `echo` writes every chunk back as it arrives; `early` and
# `early_fail` never read stdin, as a CLI that gave up on its input would.
FAKE_CLI = r'''import json,os,signal,subprocess,sys,time
from pathlib import Path
argv=sys.argv[1:]
mode=argv[0]
here=Path(__file__).parent
def git(*args):
    return subprocess.run(['git',*args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False).stdout.decode('utf-8').strip()
def same(a,b):
    return bool(a) and os.path.exists(a) and os.path.exists(b) and os.path.samefile(a,b)
(here/'seen.json').write_text(json.dumps({'argv':argv,'cwd':os.getcwd(),
    'has_head':os.path.isfile(os.path.join(os.getcwd(),'.git','HEAD')),
    'git_top_is_cwd':same(git('rev-parse','--show-toplevel'),os.getcwd()),
    'git_dir_is_own':same(git('rev-parse','--absolute-git-dir'),os.path.join(os.getcwd(),'.git')),
    'git_env':{k:v for k,v in os.environ.items() if k.upper().startswith('GIT')}}),encoding='utf-8')
if mode=='early': sys.stdout.buffer.write(b'{"winner":"tie"}\n'); sys.exit(0)
if mode=='early_fail': sys.stderr.write('gave up on stdin'); sys.exit(3)
if mode=='echo':
    while True:
        chunk=sys.stdin.buffer.read1(65536)
        if not chunk: sys.exit(0)
        sys.stdout.buffer.write(chunk); sys.stdout.buffer.flush()
(here/'stdin.bin').write_bytes(sys.stdin.buffer.read())
if mode=='answer': sys.stdout.buffer.write(b'{"winner":"tie"}\n')
elif mode=='blank': sys.stdout.buffer.write(b'\n'); sys.stderr.write('nothing to say')
elif mode=='fail': sys.stdout.buffer.write(b'partial'); sys.stderr.write('refused'); sys.exit(7)
elif mode=='killed': os.kill(os.getpid(),signal.SIGKILL)
elif mode=='slow':
    sys.stdout.buffer.write(b'partial-json'); sys.stdout.buffer.flush()
    sys.stderr.write('partial-log'); sys.stderr.flush()
    time.sleep(60)
'''
# Starts the adapter with `git` replaced by another script. A stand-in on PATH cannot do this on Windows, which starts only .exe files by bare name.
LAUNCHER = r'''import json,subprocess,sys
spec=json.loads(sys.argv[1])
sys.path.insert(0,spec['adapters'])
import stdin_repo_adapter
run=subprocess.run
def run_with_stand_in_git(args,**kwargs):
    if args[0]=='git': args=[sys.executable,spec['git'],*args[1:]]
    return run(args,**kwargs)
subprocess.run=run_with_stand_in_git
if 'git_init_timeout' in spec: stdin_repo_adapter.GIT_INIT_TIMEOUT_SECONDS=spec['git_init_timeout']
sys.exit(stdin_repo_adapter.main(['--',*spec['command']]))
'''
# A judge CLI that reads the whole prompt from stdin, takes the request from the prompt's last line, and answers as the stand-in judges do.
JUDGE_CLI = r'''import json,sys
prompt=sys.stdin.buffer.read().decode('utf-8')
request=json.loads(prompt.rstrip('\n').rsplit('\n',1)[-1])
a,b=request['A'],request['B']
print(json.dumps({'winner':'A' if a.startswith('beta') else 'B','reason':'because',
                  'evidence':[{'candidate':'A','quote':a[:5]},{'candidate':'B','quote':b[:5]}]}))
'''


@unittest.skipUnless(shutil.which("git"), "the adapter prepares its working directory with git")
class StdinRepoAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        # The adapter makes a work directory in the temp folder; keep it (and any left by a killed call) inside this test.
        scratch = self.root / "scratch"
        scratch.mkdir()
        patcher = mock.patch.dict(os.environ, {"TMPDIR": str(scratch), "TEMP": str(scratch), "TMP": str(scratch)})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.adapter = ADAPTERS / "stdin_repo_adapter.py"
        self.bridge = ADAPTERS / "generic_json_adapter.py"
        fake = self.root / "fake_cli.py"
        fake.write_text(FAKE_CLI, encoding="utf-8")
        self.cli = [sys.executable, str(fake)]

    def adapter_run(self, request, command, *, env=None, raw=None):
        """Start the adapter as a config does: request bytes as the runner writes them on stdin, CLI argv after `--`."""
        (self.root / "seen.json").unlink(missing_ok=True)
        (self.root / "stdin.bin").unlink(missing_ok=True)
        return subprocess.run([sys.executable, str(self.adapter), "--", *command],
                              input=canonical_bytes(request) if raw is None else raw,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=60, check=False)

    def stand_in_git_run(self, git_source, *, git_init_timeout=None):
        """Run the adapter against the fake CLI with `git` replaced by a Python script holding `git_source`."""
        (self.root / "seen.json").unlink(missing_ok=True)
        git = self.root / "stand_in_git.py"
        git.write_text(git_source, encoding="utf-8")
        launcher = self.root / "launcher.py"
        launcher.write_text(LAUNCHER, encoding="utf-8")
        spec = {"adapters": str(ADAPTERS), "git": str(git), "command": [*self.cli, "answer"]}
        if git_init_timeout is not None:
            spec["git_init_timeout"] = git_init_timeout
        return subprocess.run([sys.executable, str(launcher), json.dumps(spec)], input=canonical_bytes(REQUEST),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=False)

    def seen(self):
        return json.loads((self.root / "seen.json").read_text(encoding="utf-8"))

    def stdin_bytes(self):
        """What the CLI read from its stdin."""
        return (self.root / "stdin.bin").read_bytes()

    def bridge_prompt(self, request, env=None):
        """The prompt generic_json_adapter.py writes to a stdin CLI for the same request, as bytes."""
        recorder = self.root / "record_stdin.py"
        recorder.write_text('import sys\nfrom pathlib import Path\nPath(__file__).with_name("bridge-stdin.bin").write_bytes(sys.stdin.buffer.read())\nprint("{}")\n', encoding="utf-8")
        done = subprocess.run([sys.executable, str(self.bridge), "--", sys.executable, str(recorder)], input=canonical_bytes(request),
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=60, check=False)
        self.assertEqual(done.returncode, 0, done.stderr)
        return (self.root / "bridge-stdin.bin").read_bytes()

    def request_in(self, prompt_bytes):
        """The request object embedded on the last line of a bridge prompt."""
        return json.loads(prompt_bytes.decode("utf-8").rstrip("\n").rsplit("\n", 1)[-1])

    def test_prompt_goes_to_stdin_whole_with_no_prompt_option_and_matches_the_other_bridge(self):
        request = dict(REQUEST, context=AWKWARD)
        result = run_call([sys.executable, str(self.adapter), "--", *self.cli, "answer", "--flag", "value"], request,
                          self.root / "call", timeout_seconds=30)
        self.assertTrue(result["ok"], result["stderr"])
        self.assertEqual(result["response"], b'{"winner":"tie"}\n')
        self.assertEqual(self.seen()["argv"], ["answer", "--flag", "value"], "the prompt must not reach the process list")
        self.assertEqual(self.stdin_bytes(), self.bridge_prompt(request), "both bridges must send one prompt")
        self.assertEqual(self.request_in(self.stdin_bytes()), request)

    def test_request_is_decoded_as_utf8_whatever_the_locale(self):
        # UTF-8 mode off: Windows then decodes a piped stdin with the ANSI code page, which mangles UTF-8 request text.
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONIOENCODING", "PYTHONUTF8", "PYTHONCOERCECLOCALE", "LC_ALL", "LC_CTYPE", "LANG")}
        env["PYTHONUTF8"] = "0"
        request = dict(REQUEST, context=AWKWARD)
        done = self.adapter_run(request, [*self.cli, "answer"], env=env)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.request_in(self.stdin_bytes()), request)
        self.assertEqual(self.stdin_bytes(), self.bridge_prompt(request, env=dict(env, PYTHONCOERCECLOCALE="0")))

    def test_cli_starts_in_its_own_git_repository_and_the_directory_is_removed(self):
        done = self.adapter_run(REQUEST, [*self.cli, "answer"])
        self.assertEqual(done.returncode, 0, done.stderr)
        seen = self.seen()
        self.assertTrue(seen["has_head"], "no .git/HEAD in the CLI working directory")
        self.assertTrue(seen["git_top_is_cwd"], "git does not treat the CLI working directory as a repository root")
        self.assertNotEqual(os.path.realpath(seen["cwd"]), os.path.realpath(os.getcwd()))
        self.assertFalse(os.path.exists(seen["cwd"]), "the work directory outlived the call")

    def test_missing_git_fails_closed_before_the_cli_starts(self):
        (self.root / "no-git-here").mkdir()
        done = self.adapter_run(REQUEST, [*self.cli, "answer"], env=dict(os.environ, PATH=str(self.root / "no-git-here")))
        self.assertEqual(done.returncode, 2)
        self.assertIn(b"git", done.stderr)
        self.assertFalse((self.root / "seen.json").exists(), "the CLI ran without the isolation it depends on")

    def test_inherited_git_variables_cannot_redirect_the_repository(self):
        # Git honors GIT_DIR over the working directory, so an inherited one sends `git init` and the CLI's own repository lookup elsewhere.
        base = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT")}
        decoy = self.root / "decoy"
        subprocess.run(["git", "init", "-q", str(decoy)], env=base, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        # Running `git init` again in a repository recreates whatever is missing, so a deleted folder shows that it ran there.
        (decoy / ".git" / "refs" / "tags").rmdir()

        def paths():
            return {p.relative_to(decoy).as_posix() for p in decoy.rglob("*")}
        before = paths()
        env = dict(base, GIT_DIR=(decoy / ".git").as_posix(), GIT_WORK_TREE=decoy.as_posix(), GITHUB_WQ_MARKER="kept")
        done = self.adapter_run(REQUEST, [*self.cli, "answer"], env=env)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(sorted(paths() - before), [], "the adapter ran git init in the repository named by GIT_DIR")
        seen = self.seen()
        self.assertTrue(seen["has_head"], "no .git/HEAD in the CLI working directory")
        self.assertTrue(seen["git_dir_is_own"], "git resolves the CLI working directory to some other repository")
        self.assertEqual(seen["git_env"], {"GITHUB_WQ_MARKER": "kept"}, "the CLI inherited a GIT_ variable, or lost an unrelated one")

    def test_a_git_that_reports_success_without_a_repository_fails_closed(self):
        done = self.stand_in_git_run("import sys\nsys.exit(0)\n")
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertIn(b"no repository", done.stderr)
        self.assertFalse((self.root / "seen.json").exists(), "the CLI started without a repository")

    def test_a_git_init_that_hangs_is_stopped_at_the_timeout_and_fails_closed(self):
        # The stand-in sleeps for 10 s; the limit is patched down to half a second so the test stays fast.
        done = self.stand_in_git_run("import time\ntime.sleep(10)\n", git_init_timeout=0.5)
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertIn(b"timed out", done.stderr)
        self.assertFalse((self.root / "seen.json").exists(), "the CLI started after a git init that never finished")

    def test_blank_output_is_an_error_and_a_failing_exit_code_passes_through(self):
        blank = self.adapter_run(REQUEST, [*self.cli, "blank"])
        self.assertEqual(blank.returncode, 2, "exit 0 with nothing to parse must not pass as an answer")
        self.assertIn(b"no output", blank.stderr)
        self.assertIn(b"nothing to say", blank.stderr, "the CLI's own diagnosis is kept")
        failed = self.adapter_run(REQUEST, [*self.cli, "fail"])
        self.assertEqual(failed.returncode, 7)
        self.assertEqual(failed.stdout, b"partial")
        self.assertIn(b"refused", failed.stderr)

    @unittest.skipIf(os.name == "nt", "only POSIX reports a death by signal, as a negative exit code")
    def test_a_cli_killed_by_a_signal_exits_with_the_code_a_shell_reports(self):
        # A raw -9 would leave the adapter as 247 (256-9), which no shell or log reader connects to SIGKILL; 137 is 128+9.
        done = self.adapter_run(REQUEST, [*self.cli, "killed"])
        self.assertEqual(done.returncode, 137, done.stderr)

    def test_timeout_keeps_partial_output(self):
        result = run_call([sys.executable, str(self.adapter), "--", *self.cli, "slow"], REQUEST, self.root / "slow", timeout_seconds=6)
        self.assertEqual(result["error"], "timeout")
        self.assertIn(b"partial-json", result["response"])
        self.assertIn(b"partial-log", result["stderr"])

    def test_unsafe_calls_are_refused_before_the_cli_starts(self):
        lone_surrogate = b'{"role":"judge","context":"\\ud800"}'  # a JSON escape, so the request bytes stay valid ASCII
        answer = [*self.cli, "answer"]
        cases = (("a .cmd shim", dict(command=["agy.CMD", "--model", "x"]), b".cmd"),
                 ("a .bat shim", dict(command=["run.bat"]), b".bat"),
                 ("cmd.exe running a .cmd shim", dict(command=["CMD.EXE", "/c", "agy.cmd", "--model", "x"]), b"command shell"),
                 ("a PowerShell wrapper", dict(command=["powershell", "-NoProfile", "-File", "agy.ps1"]), b"command shell"),
                 ("pwsh named by its path", dict(command=["C:/Program Files/PowerShell/7/pwsh.exe", "-File", "agy.ps1"]), b"command shell"),
                 ("a permission-bypass flag", dict(command=[*answer, "--dangerously-skip-permissions"]), b"dangerously"),
                 ("-p, which would put the prompt on the command line", dict(command=[*answer, "-p", "text"]), b"prompt option"),
                 ("-p with an empty prompt", dict(command=[*answer, "-p", ""]), b"prompt option"),
                 ("--prompt", dict(command=[*answer, "--prompt", "text"]), b"prompt option"),
                 ("--prompt=TEXT", dict(command=[*answer, "--prompt=text"]), b"prompt option"),
                 ("an unknown role", dict(command=answer, request=dict(REQUEST, role="admin")), b"role"),
                 ("a lone surrogate", dict(command=answer, raw=lone_surrogate), b"surrogate"))
        for name, spec, message in cases:
            with self.subTest(name):
                done = self.adapter_run(spec.get("request", REQUEST), spec["command"], raw=spec.get("raw"))
                self.assertEqual(done.returncode, 2, done.stderr)
                self.assertIn(message, done.stderr)
                self.assertFalse((self.root / "seen.json").exists(), "the CLI started")

    def test_a_prompt_far_over_the_command_line_limit_is_delivered_whole(self):
        # prompt_arg_adapter.py refuses 32,000 UTF-16 units; stdin has no such limit, so 100,000 characters must arrive intact.
        request = dict(REQUEST, context="x" * 100_000)
        done = self.adapter_run(request, [*self.cli, "answer"])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertGreater(len(self.stdin_bytes()), 100_000)
        self.assertEqual(self.request_in(self.stdin_bytes()), request)

    def test_a_prompt_over_a_megabyte_does_not_stall_a_cli_that_echoes_while_it_reads(self):
        # Writing the whole prompt before reading any output fills the CLI's stdout pipe, then the CLI stops reading, then the write
        # blocks: neither side moves. The adapter must feed stdin from one thread and stream stdout from another.
        request = dict(REQUEST, context="x" * ONE_AND_A_TENTH_MEGABYTES)
        expected = self.bridge_prompt(request)
        self.assertGreater(len(expected), 1_000_000)
        done = self.adapter_run(request, [*self.cli, "echo"])
        self.assertEqual(done.returncode, 0, done.stderr[:300])
        self.assertEqual(len(done.stdout), len(expected))
        self.assertEqual(done.stdout, expected, "the CLI did not get the whole prompt, or the adapter lost some of its output")

    def test_a_cli_that_answers_without_reading_the_whole_prompt_fails_closed(self):
        # The answer came from a prompt the model never fully saw, so exit 0 here would pass a judgment that rests on part of it.
        done = self.adapter_run(dict(REQUEST, context="x" * ONE_AND_A_TENTH_MEGABYTES), [*self.cli, "early"])
        self.assertEqual(done.returncode, 2, done.stderr[:300])
        self.assertIn(b"stdin", done.stderr)

    def test_a_cli_that_fails_without_reading_the_prompt_keeps_its_own_exit_code(self):
        done = self.adapter_run(dict(REQUEST, context="x" * ONE_AND_A_TENTH_MEGABYTES), [*self.cli, "early_fail"])
        self.assertEqual(done.returncode, 3, done.stderr[:300])
        self.assertIn(b"gave up on stdin", done.stderr)

    def test_command_after_double_dash_is_required(self):
        done = subprocess.run([sys.executable, str(self.adapter), "--"], input=b"", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=60, check=False)
        self.assertEqual(done.returncode, 2)
        self.assertIn(b"model CLI", done.stderr)


class AdapterSignatureCoverageTests(unittest.TestCase):
    def test_every_adapter_script_in_the_folder_is_hashed_into_the_judge_signature(self):
        # A script that builds or isolates a judge call but is missing from ADAPTER_SCRIPTS could change without invalidating a calibration.
        on_disk = {path.name for path in runner.ADAPTER_DIR.glob("*.py")}
        self.assertTrue(on_disk, "no adapter scripts found, so this check would pass for nothing")
        self.assertTrue(runner.ADAPTER_SCRIPTS)
        self.assertEqual(len(runner.ADAPTER_SCRIPTS), len(set(runner.ADAPTER_SCRIPTS)), "a script is listed twice")
        self.assertEqual(set(runner.ADAPTER_SCRIPTS), on_disk)
        self.assertEqual(set(runner._adapter_hashes()), on_disk)

    def test_the_new_bridge_and_its_shared_module_are_in_the_signature(self):
        self.assertIn("stdin_repo_adapter.py", runner.ADAPTER_SCRIPTS)
        self.assertIn("fresh_repo.py", runner.ADAPTER_SCRIPTS)

    def test_the_readme_and_the_contract_name_every_adapter_script(self):
        for document in ("README.md", "CONTRACT.md"):
            text = (AUTOMATED / document).read_text(encoding="utf-8")
            for script in runner.ADAPTER_SCRIPTS:
                with self.subTest(document=document, script=script):
                    self.assertIn(script, text)


@unittest.skipUnless(shutil.which("git"), "the adapter prepares its working directory with git")
class StdinJudgeIsNeverSkippedTests(unittest.TestCase):
    """The pre-judge size check measures a command line, and only prompt_arg_adapter.py puts the prompt on one."""

    RUBRIC = {"schema_version": 1, "id": "r", "criteria": [{"id": "meaning", "description": "Preserve the meaning."}]}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        scratch = self.root / "scratch"
        scratch.mkdir()
        patcher = mock.patch.dict(os.environ, {"TMPDIR": str(scratch), "TEMP": str(scratch), "TMP": str(scratch)})
        patcher.start()
        self.addCleanup(patcher.stop)
        (self.root / "judge_cli.py").write_text(JUDGE_CLI, encoding="utf-8")
        self.out = self.root / "out"
        (self.out / "calls").mkdir(parents=True)

    def long_case(self, characters):
        return {"id": "c1", "document_id": "d1", "split": "test", "lane": "editing", "prompt": "inspect", "context": "case 1",
                "a": "alpha " + "x" * characters, "b": "beta", "expected": None, "checks": {},
                "provenance": {"kind": "synthetic_control", "source": "test fixture", "license": "CC0"}}

    def judge(self):
        command = [sys.executable, str(ADAPTERS / "stdin_repo_adapter.py"), "--", sys.executable, str(self.root / "judge_cli.py")]
        return {"id": "agy", "family": "f1", "command": command}

    def test_the_size_check_has_nothing_to_measure_for_the_stdin_adapter(self):
        request = dict(REQUEST, context="x" * 100_000)
        self.assertIsNone(runner._command_units(self.judge()["command"], request))

    def test_a_100000_character_case_is_judged_through_the_real_adapter_not_skipped(self):
        config = {"judges": [self.judge()], "timeout_seconds": 120}
        budget = Budget(10)
        records = runner._judge_cases([self.long_case(100_000)], self.RUBRIC, config, self.out, budget)
        self.assertEqual(budget.used, 2)
        self.assertEqual(len(records), 2)
        for entry in records:
            self.assertTrue(entry["valid"], entry)
            self.assertNotIn("failure_kind", entry)
            self.assertFalse(str(entry.get("error", "")).startswith("oversized_prompt"), entry)


if __name__ == "__main__":
    unittest.main()
