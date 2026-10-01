"""Tests for tools/measure_agy.py: parsing and decision logic, driven by a stand-in agy. No model call is made."""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from evaluation.benchmark_v2.automated.tools import measure_agy

# A stand-in agy. It answers --version, reads a prompt from -p (or, when allowed, from stdin), echoes a
# PINEAPPLE nonce it finds in the prompt, and otherwise looks for an AGENTS.md the way agy does: from its
# working directory upward, stopping at a Git root when STOPS_AT_GIT_ROOT is set. Every call is logged.
FAKE_AGY = r'''import json, os, re, sys
VERSION = {version!r}
READS_STDIN = {reads_stdin!r}
LOADS_PARENT_AGENTS = {loads_parent!r}
STOPS_AT_GIT_ROOT = {stops_at_git_root!r}
args = sys.argv[1:]
with open({log!r}, "a", encoding="utf-8") as log:
    log.write(json.dumps({{"args": args, "cwd": os.getcwd(),
                          "git_env": [k for k in os.environ if k.startswith("GIT_")]}}) + "\n")
if "--version" in args:
    print(VERSION)
    sys.exit(0)
prompt = args[args.index("-p") + 1] if "-p" in args else None
if not prompt:
    text = sys.stdin.read()
    if not READS_STDIN or not text.strip():
        sys.stderr.write("error: no prompt given\n")
        sys.exit(2)
    prompt = text
match = re.search(r"PINEAPPLE-[0-9a-f]+", prompt)
if match:
    print(match.group(0))
    sys.exit(0)
folder = os.getcwd()
found = None
while LOADS_PARENT_AGENTS:
    candidate = os.path.join(folder, "AGENTS.md")
    if os.path.isfile(candidate):
        found = open(candidate, encoding="utf-8").read()
        break
    if STOPS_AT_GIT_ROOT and os.path.exists(os.path.join(folder, ".git")):
        break
    parent = os.path.dirname(folder)
    if parent == folder:
        break
    folder = parent
word = re.search(r"canary word is (\S+?)\.", found or "")
print(word.group(1) if word else "NONE")
'''


def call(**fields):
    base = {"argv": ["agy"], "returncode": 0, "timed_out": False, "launch_error": None, "stdout": "", "stderr": ""}
    return {**base, **fields}


class DecisionTests(unittest.TestCase):
    def test_first_line_is_the_first_nonblank_line(self):
        self.assertEqual(measure_agy.first_line("\n  \n agy 1.2.12 \nmore"), "agy 1.2.12")
        self.assertIsNone(measure_agy.first_line(""))
        self.assertIsNone(measure_agy.first_line(" \n\t\n"))

    def test_stdin_verdict(self):
        reply = call(stdout="PINEAPPLE-ab12\n")
        refusal = call(returncode=2, stderr="error: no prompt given\n")
        hang = call(returncode=None, timed_out=True)
        launch = call(returncode=None, launch_error="boom")
        other = call(stdout="something else\n")  # exit 0, no nonce
        nonce = "PINEAPPLE-ab12"
        # A variant that finished with the nonce proves stdin is read, whatever the control did.
        self.assertEqual(measure_agy.stdin_verdict([refusal, reply], nonce, refusal), "reads_stdin")
        self.assertEqual(measure_agy.stdin_verdict([hang, reply], nonce, hang), "reads_stdin")
        # Ignoring stdin needs proof that the same prompt works as a -p argument.
        self.assertEqual(measure_agy.stdin_verdict([refusal, refusal], nonce, reply), "ignores_stdin")
        self.assertEqual(measure_agy.stdin_verdict([other, refusal], nonce, reply), "ignores_stdin")
        # Without a control that answered, failing variants prove nothing (this was `ignores_stdin` before the control).
        for control in (refusal, hang, launch, other, None):
            with self.subTest(control=control):
                self.assertEqual(measure_agy.stdin_verdict([refusal, refusal], nonce, control), "inconclusive")
        self.assertEqual(measure_agy.stdin_verdict([refusal, refusal], nonce), "inconclusive")
        # A variant that hung or could not start may only have been slow, so even a good control cannot rule stdin out.
        self.assertEqual(measure_agy.stdin_verdict([refusal, hang], nonce, reply), "inconclusive")
        self.assertEqual(measure_agy.stdin_verdict([launch], nonce, reply), "inconclusive")

    def test_canary_loaded(self):
        self.assertTrue(measure_agy.canary_loaded(call(stdout="canary-1\n"), "canary-1"))
        self.assertFalse(measure_agy.canary_loaded(call(stdout="NONE\n"), "canary-1"))
        self.assertIsNone(measure_agy.canary_loaded(call(returncode=1, stdout="canary-1"), "canary-1"))
        self.assertIsNone(measure_agy.canary_loaded(call(timed_out=True, returncode=None), "canary-1"))
        self.assertIsNone(measure_agy.canary_loaded(call(launch_error="boom", returncode=None), "canary-1"))
        self.assertIsNone(measure_agy.canary_loaded(call(stdout="  \n"), "canary-1"))  # exit 0 with no answer

    def test_agents_verdict(self):
        expected = {
            (True, False): "git_init_stops_parent_agents_md",
            (True, True): "parent_agents_md_loaded_inside_git_repo",
            (False, False): "parent_agents_md_not_loaded",
            (False, True): "parent_agents_md_loaded_only_inside_git_repo",
            (None, True): "inconclusive", (True, None): "inconclusive", (None, None): "inconclusive",
            (None, False): "inconclusive", (False, None): "inconclusive",
        }
        for (plain, repo), verdict in expected.items():
            with self.subTest(plain=plain, repo=repo):
                self.assertEqual(measure_agy.agents_verdict(plain, repo), verdict)

    def test_a_dangerous_flag_is_refused(self):
        with self.assertRaisesRegex(ValueError, "--dangerously"):
            measure_agy.measure([sys.executable, "--dangerously-skip-permissions"], "m")


class MeasureTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.log = self.root / "calls.jsonl"

    def measure(self, **behavior):
        settings = {"version": "agy 9.9.9", "reads_stdin": False, "loads_parent": True, "stops_at_git_root": True}
        settings.update(behavior)
        script = self.root / "fake_agy.py"
        script.write_text(FAKE_AGY.format(log=str(self.log), **settings), encoding="utf-8")
        return measure_agy.measure([sys.executable, str(script)], "model-x", timeout_seconds=60, stdin_timeout_seconds=60,
                                   canary="canary-7f3a", nonce="PINEAPPLE-0123abcd")

    def logged(self):
        return [json.loads(line) for line in self.log.read_text(encoding="utf-8").splitlines()]

    def test_the_version_is_recorded(self):
        result = self.measure()
        self.assertEqual(result["version"]["text"], "agy 9.9.9")
        self.assertEqual(result["version"]["returncode"], 0)
        self.assertEqual(result["model"], "model-x")
        self.assertEqual(result["schema_version"], 1)

    def test_an_agy_that_ignores_stdin_is_recorded_with_what_it_did(self):
        stdin = self.measure(reads_stdin=False)["stdin"]
        self.assertEqual(stdin["verdict"], "ignores_stdin")
        self.assertEqual([v["name"] for v in stdin["variants"]], ["p_absent", "p_empty"])
        for variant in stdin["variants"]:
            self.assertEqual(variant["returncode"], 2)
            self.assertIn("error: no prompt given", variant["stderr"])
        self.assertNotIn("-p", stdin["variants"][0]["argv"])
        self.assertEqual(stdin["variants"][1]["argv"][-2:], ["-p", ""])

    def test_a_p_control_call_with_the_same_prompt_is_recorded(self):
        stdin = self.measure(reads_stdin=False)["stdin"]
        control = stdin["control"]
        self.assertEqual(control["name"], "p_control")
        self.assertEqual(control["argv"][-2:], ["-p", measure_agy.STDIN_PROMPT.format(nonce="PINEAPPLE-0123abcd")])
        self.assertEqual(control["returncode"], 0)
        self.assertIn("PINEAPPLE-0123abcd", control["stdout"])
        self.assertEqual(stdin["nonce"], "PINEAPPLE-0123abcd")

    def test_an_agy_that_reads_stdin_is_recorded(self):
        stdin = self.measure(reads_stdin=True)["stdin"]
        self.assertEqual(stdin["verdict"], "reads_stdin")
        self.assertIn("PINEAPPLE-0123abcd", stdin["variants"][0]["stdout"])

    def test_git_init_stops_the_parent_agents_md_walk(self):
        agents = self.measure(loads_parent=True, stops_at_git_root=True)["agents_md"]
        self.assertEqual(agents["verdict"], "git_init_stops_parent_agents_md")
        self.assertTrue(agents["plain_folder"]["canary_in_reply"])
        self.assertFalse(agents["git_repo"]["canary_in_reply"])

    def test_a_git_repo_that_does_not_stop_the_walk_is_reported(self):
        agents = self.measure(loads_parent=True, stops_at_git_root=False)["agents_md"]
        self.assertEqual(agents["verdict"], "parent_agents_md_loaded_inside_git_repo")

    def test_an_agy_that_never_loads_a_parent_agents_md_is_reported(self):
        agents = self.measure(loads_parent=False)["agents_md"]
        self.assertEqual(agents["verdict"], "parent_agents_md_not_loaded")

    def test_every_model_call_pins_the_model_and_never_skips_permissions(self):
        self.measure()
        calls = self.logged()
        self.assertEqual(calls[0]["args"], ["--version"])
        for entry in calls[1:]:
            self.assertEqual(entry["args"][:5], ["--sandbox", "--model", "model-x", "--output-format", "text"])
        self.assertEqual(len(calls), 1 + 2 + 1 + 2)  # version, two stdin variants, the -p control, two AGENTS.md runs
        for entry in calls:
            self.assertFalse([arg for arg in entry["args"] if arg.startswith("--dangerously")])

    def test_the_agents_md_runs_use_a_plain_folder_and_a_fresh_repo_under_one_parent(self):
        self.measure()
        runs = [entry for entry in self.logged() if "-p" in entry["args"] and entry["args"][-1] != ""
                and "PINEAPPLE" not in entry["args"][-1]]
        self.assertEqual(len(runs), 2)
        plain, repo = (Path(entry["cwd"]) for entry in runs)
        self.assertEqual(plain.name, "plain")
        self.assertEqual(repo.name, "repo")
        self.assertEqual(plain.parent, repo.parent)
        self.assertTrue(plain.parent.name.startswith("wq-measure-"))
        self.assertFalse(plain.parent.exists())  # the scratch tree is removed afterwards

    def test_git_variables_do_not_reach_agy(self):
        with mock.patch.dict(os.environ, {"GIT_DIR": str(self.root / "elsewhere"), "GIT_WORK_TREE": str(self.root)}):
            self.measure()
        self.assertEqual([entry["git_env"] for entry in self.logged()], [[]] * 6)


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()

    def run_main(self, *argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                code = measure_agy.main(list(argv))
            except SystemExit as exit_:
                code = exit_.code
        return code, stdout.getvalue(), stderr.getvalue()

    def test_a_missing_agy_exits_2(self):
        code, _, err = self.run_main(str(self.root / "no-agy.exe"), "--model", "m", "--out", str(self.root / "r.json"))
        self.assertEqual(code, 2)
        self.assertIn("agy not found", err)
        self.assertFalse((self.root / "r.json").exists())

    def test_an_existing_result_file_is_not_overwritten(self):
        out = self.root / "r.json"
        out.write_text("keep", encoding="utf-8")
        code, _, err = self.run_main(sys.executable, "--model", "m", "--out", str(out))
        self.assertEqual(code, 2)
        self.assertIn("refusing to overwrite", err)
        self.assertEqual(out.read_text(encoding="utf-8"), "keep")

    def test_an_unknown_cli_is_recorded_as_inconclusive_not_crashed(self):
        # python.exe rejects --sandbox: every model call fails, which the result must say instead of guessing.
        out = self.root / "nested" / "r.json"
        code, printed, _ = self.run_main(sys.executable, "--model", "m", "--out", str(out),
                                         "--timeout", "60", "--stdin-timeout", "60")
        self.assertEqual(code, 0)
        result = json.loads(out.read_text(encoding="utf-8"))
        self.assertTrue(result["version"]["text"].startswith("Python"))
        self.assertEqual(result["agents_md"]["verdict"], "inconclusive")
        self.assertNotEqual(result["stdin"]["control"]["returncode"], 0)  # no working -p call, so nothing can be ruled out
        self.assertEqual(result["stdin"]["verdict"], "inconclusive")
        self.assertIn(str(out), printed)


if __name__ == "__main__":
    unittest.main()
