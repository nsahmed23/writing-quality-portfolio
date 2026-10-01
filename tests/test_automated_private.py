"""Private outputs: a suite with owner_session cases writes a run only inside WQ_EVAL_PRIVATE_ROOT.

No model is called. The writer and the judges are stand-in scripts that the real runner starts, as in
test_automated_runs; the calibration certificate is written by hand. Each refusal test also checks that the
output path was never created, because the refusal must come before any output exists. The refusal messages
are pinned here and in CONTRACT.md."""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from evaluation.benchmark_v2.automated import runner, runs
from evaluation.benchmark_v2.automated.__main__ import main
from evaluation.benchmark_v2.automated.adapters import canonical_bytes, load_config
from evaluation.benchmark_v2.automated.contracts import load_suite
from evaluation.benchmark_v2.automated.optimize import optimize

AUTOMATED = Path(__file__).resolve().parents[1] / "evaluation" / "benchmark_v2" / "automated"
RUBRIC = AUTOMATED / "data" / "rubric.json"
PY = sys.executable
ENV = "WQ_EVAL_PRIVATE_ROOT"
MARK = "OWNERMARK-7Q2X"

UNSET = "suite has owner_session cases; set WQ_EVAL_PRIVATE_ROOT to a private folder and write the run inside it"
OUTSIDE = "suite has owner_session cases; the output path must be inside WQ_EVAL_PRIVATE_ROOT"
NOT_A_FOLDER = "WQ_EVAL_PRIVATE_ROOT must name an existing folder"

WRITER = '''import json, sys
request = json.load(sys.stdin)
lead = "Brief take on " if "CANDIDATE-MARK" in request["instructions"] else "A rather wordy take on "
print(json.dumps({"text": lead + request["prompt"]}))
'''

JUDGE = '''import json, sys
request = json.load(sys.stdin)
a, b = request["A"], request["B"]
winner = "A" if a.startswith("Brief") else "B"
print(json.dumps({"winner": winner, "reason": "briefer",
                  "evidence": [{"candidate": "A", "quote": a[:5]}, {"candidate": "B", "quote": b[:5]}]}))
'''


def guard():
    """The guard module, loaded inside each test so a missing module fails that test and not the whole file."""
    from evaluation.benchmark_v2.automated import private
    return private


def suite_dict(owner=()):
    """Four documents; the numbers in owner are owner_session cases and carry the planted marker."""
    cases = []
    for n in range(1, 5):
        planted = n in owner
        cases.append({"id": f"case-{n}", "document_id": f"doc-{n}", "split": "test" if n < 3 else "development",
                      "lane": "editing", "prompt": f"Revise item {n}.", "context": f"Context {n}" + (f" {MARK}" if planted else ""),
                      "a": f"alpha {n}", "b": f"beta {n}", "expected": None, "checks": {},
                      "provenance": {"kind": "owner_session" if planted else "synthetic_control",
                                     "source": "test fixture", "license": "CC0"}})
    return {"schema_version": 1, "name": "private-fixture", "cases": cases}


@contextlib.contextmanager
def private_root(value):
    """Set WQ_EVAL_PRIVATE_ROOT for the block (None removes it) and put the old environment back after."""
    with mock.patch.dict(os.environ):
        if value is None:
            os.environ.pop(ENV, None)
        else:
            os.environ[ENV] = str(value)
        yield


def remove_link(path):
    """Remove a symlink or junction itself, never what it points to."""
    try:
        os.rmdir(path)
    except OSError:
        try:
            os.unlink(path)
        except OSError:
            pass


class PrivateFixture(unittest.TestCase):
    """A temporary folder holding an owner suite, a public suite, stand-in adapters, a config and certificates."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.private = self.root / "private"
        self.private.mkdir()
        self.public = self.root / "public"
        self.public.mkdir()
        (self.root / "writer.py").write_text(WRITER, encoding="utf-8")
        (self.root / "judge.py").write_text(JUDGE, encoding="utf-8")
        config = {"schema_version": 1,
                  "judges": [{"id": "j1", "family": "f1", "command": [PY, str(self.root / "judge.py")]},
                             {"id": "j2", "family": "f2", "command": [PY, str(self.root / "judge.py")]}],
                  "writer": {"id": "w", "family": "fw", "command": [PY, str(self.root / "writer.py")]}}
        self.config_path = self.root / "config.json"
        self.config_path.write_bytes(canonical_bytes(config))
        self.candidate = self.root / "candidate.md"
        self.candidate.write_bytes(b"# Candidate\nCANDIDATE-MARK\nWrite briefly.\n")
        self.owner_suite = self.write_suite("owner-suite.json", suite_dict(owner=(2, 3)))
        self.public_suite = self.write_suite("public-suite.json", suite_dict())
        self.owner_certificate = self.write_certificate(self.owner_suite, "owner-certificate")
        self.public_certificate = self.write_certificate(self.public_suite, "public-certificate")

    def write_suite(self, name, suite):
        path = self.root / name
        path.write_bytes(canonical_bytes(suite))
        return path

    def write_certificate(self, suite_path, name):
        config = load_config(self.config_path)
        report = {"schema_version": 1, "evaluation_type": "automated_proxy", "execution": "live",
                  "mode": "calibrate", "complete": True, "eligible": True,
                  "provenance": runner._provenance(suite_path, RUBRIC, self.config_path, config)}
        folder = self.root / name
        folder.mkdir()
        (folder / "report.json").write_bytes(canonical_bytes(report))
        return folder

    def writers(self):
        """Every command that writes a run, as a function of the output path, for the owner suite."""
        suite, certificate = self.owner_suite, self.owner_certificate
        chunks = [self.root / "chunk-1", self.root / "chunk-2"]
        return {
            "calibrate": lambda out: runner.calibrate(suite, RUBRIC, self.config_path, out),
            "compare": lambda out: runner.compare(suite, RUBRIC, self.config_path, certificate, self.candidate, out),
            "merge": lambda out: runs.merge(suite, RUBRIC, self.config_path, certificate, chunks, out),
            "rerun-failed": lambda out: runs.rerun_failed(suite, RUBRIC, self.config_path, certificate, chunks[0], out),
            "optimize": lambda out: optimize(suite, RUBRIC, self.config_path, out),
        }

    def refused(self, call, message, out):
        """call(out) must raise ValueError with exactly this message and leave nothing at out."""
        with self.assertRaises(ValueError) as caught:
            call(out)
        self.assertEqual(str(caught.exception), message)
        self.assertFalse(Path(out).exists(), "the output exists after a refusal")

    def run_cli(self, argv):
        """Run main(argv); return (exit code or None, stdout, stderr)."""
        stdout, stderr = io.StringIO(), io.StringIO()
        code = None
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                code = main(argv)
            except SystemExit as exc:
                code = exc.code
        return code, stdout.getvalue(), stderr.getvalue()

    def compare_argv(self, suite, certificate, out):
        return ["compare", "--suite", str(suite), "--rubric", str(RUBRIC), "--config", str(self.config_path),
                "--calibration", str(certificate), "--candidate-skill", str(self.candidate), "--out", str(out)]

    def make_junction(self, link, target):
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], capture_output=True, text=True)
        if result.returncode != 0:
            self.skipTest("this machine cannot create a junction")
        self.addCleanup(remove_link, link)

    def make_symlink(self, link, target):
        try:
            os.symlink(target, link, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("this machine cannot create a symlink")
        self.addCleanup(remove_link, link)


class GuardTests(PrivateFixture):
    """The guard function itself, with a suite loaded by the real loader."""

    def setUp(self):
        super().setUp()
        self.suite = load_suite(self.owner_suite)

    def check(self, out, root=None):
        with private_root(self.private if root is None else root):
            return guard().require_private_output(self.suite, out)

    def assertRefuses(self, out, message=OUTSIDE, root=None):
        with self.assertRaises(ValueError) as caught:
            self.check(out, root)
        self.assertEqual(str(caught.exception), message)

    def test_the_variable_is_named_in_one_place(self):
        self.assertEqual(guard().PRIVATE_ROOT_ENV, ENV)

    def test_a_suite_without_owner_session_cases_is_never_guarded(self):
        suite = load_suite(self.public_suite)
        with private_root(None):
            self.assertIsNone(guard().require_private_output(suite, self.public / "anywhere"))
        with private_root(self.private):
            self.assertIsNone(guard().require_private_output(suite, self.public / "anywhere"))

    def test_one_owner_session_case_guards_the_whole_suite(self):
        suite = load_suite(self.public_suite)
        suite["cases"][3]["provenance"]["kind"] = "owner_session"
        with private_root(None), self.assertRaises(ValueError):
            guard().require_private_output(suite, self.public / "anywhere")

    def test_an_unset_or_blank_variable_refuses(self):
        for value in (None, "", "   "):
            with self.subTest(value=value), private_root(value), self.assertRaises(ValueError) as caught:
                guard().require_private_output(self.suite, self.private / "run")
            self.assertEqual(str(caught.exception), UNSET)

    def test_a_root_that_is_not_an_existing_folder_refuses(self):
        a_file = self.root / "a-file"
        a_file.write_bytes(b"x")
        for value in (self.root / "no-such-folder", a_file):
            with self.subTest(value=value.name):
                self.assertRefuses(self.private / "run", NOT_A_FOLDER, root=value)

    def test_an_output_inside_the_root_is_allowed_even_when_nested_and_new(self):
        self.assertIsNone(self.check(self.private / "run"))
        self.assertIsNone(self.check(self.private / "deep" / "er" / "run"))
        self.assertIsNone(self.check(self.private / "a" / ".." / "b"))

    def test_a_relative_output_is_resolved_against_the_current_folder(self):
        previous = os.getcwd()
        self.addCleanup(os.chdir, previous)
        os.chdir(self.private)
        self.assertIsNone(self.check(Path("relative-run")))
        os.chdir(self.public)
        self.assertRefuses(Path("relative-run"))

    def test_an_output_outside_the_root_refuses(self):
        self.assertRefuses(self.public / "run")
        self.assertRefuses(self.root / "run")

    def test_the_root_itself_is_not_outside_but_a_sibling_with_the_same_prefix_is(self):
        self.assertIsNone(self.check(self.private))
        self.assertRefuses(self.root / "private-copy" / "run")

    def test_dot_dot_cannot_climb_out_of_the_root(self):
        self.assertRefuses(self.private / "inner" / ".." / ".." / "public" / "run")
        (self.private / "inner").mkdir()
        self.assertRefuses(self.private / "inner" / ".." / ".." / "public" / "run")

    def test_a_symlink_inside_the_root_cannot_lead_outside(self):
        link = self.private / "link"
        self.make_symlink(link, self.public)
        self.assertRefuses(link / "run")

    def test_a_junction_inside_the_root_cannot_lead_outside(self):
        if os.name != "nt":
            self.skipTest("junctions exist only on Windows")
        link = self.private / "junction"
        self.make_junction(link, self.public)
        self.assertRefuses(link / "run")

    def test_a_root_given_through_a_symlink_or_junction_is_the_folder_it_points_to(self):
        link = self.root / "root-link"
        if os.name == "nt":
            self.make_junction(link, self.private)
        else:
            self.make_symlink(link, self.private)
        self.assertIsNone(self.check(link / "run", root=link))
        self.assertIsNone(self.check(self.private / "run", root=link))
        self.assertRefuses(self.public / "run", root=link)

    def test_windows_paths_compare_without_regard_to_case(self):
        if os.name != "nt":
            self.skipTest("case is significant outside Windows")
        self.assertIsNone(self.check(str(self.private / "Run").lower(), root=str(self.private).upper()))

    def test_a_path_on_another_drive_is_outside_not_an_error(self):
        with mock.patch("os.path.commonpath", side_effect=ValueError("Paths don't have the same drive")):
            self.assertRefuses(self.private / "run")

    def test_no_message_carries_a_path_or_owner_text(self):
        seen = []
        for root, out in ((None, self.private / "run"), (self.root / "nope", self.private / "run"),
                          (self.private, self.public / "run")):
            with private_root(root), self.assertRaises(ValueError) as caught:
                guard().require_private_output(self.suite, out)
            seen.append(str(caught.exception))
        self.assertEqual(seen, [UNSET, NOT_A_FOLDER, OUTSIDE])
        for message in seen:
            self.assertNotIn(str(self.root), message)
            self.assertNotIn(MARK, message)


class WriterTests(PrivateFixture):
    """Every writer asks the guard before it creates anything."""

    def test_every_writer_refuses_when_the_variable_is_unset(self):
        for name, call in self.writers().items():
            with self.subTest(name), private_root(None):
                self.refused(call, UNSET, self.public / name)

    def test_every_writer_refuses_an_output_outside_the_private_root(self):
        for name, call in self.writers().items():
            with self.subTest(name), private_root(self.private):
                self.refused(call, OUTSIDE, self.public / name)

    def test_every_writer_refuses_an_output_that_escapes_through_dot_dot(self):
        for name, call in self.writers().items():
            with self.subTest(name), private_root(self.private):
                self.refused(call, OUTSIDE, self.private / ".." / "public" / name)

    def test_every_writer_refuses_an_output_that_escapes_through_a_link(self):
        link = self.private / "link"
        if os.name == "nt":
            self.make_junction(link, self.public)
        else:
            self.make_symlink(link, self.public)
        for name, call in self.writers().items():
            with self.subTest(name), private_root(self.private):
                self.refused(call, OUTSIDE, link / name)
                self.assertFalse((self.public / name).exists())

    def test_the_refusal_comes_before_the_writer_reads_anything_else(self):
        # The chunk folders and the calibration do not exist; the guard message still wins over their own refusals.
        with private_root(None):
            self.refused(lambda out: runs.merge(self.owner_suite, RUBRIC, self.config_path, self.root / "no-certificate",
                                                [self.root / "gone-1", self.root / "gone-2"], out), UNSET, self.public / "m")
            self.refused(lambda out: runs.rerun_failed(self.owner_suite, RUBRIC, self.config_path, self.root / "no-certificate",
                                                       self.root / "gone", out), UNSET, self.public / "r")

    def test_a_writer_inside_the_private_root_passes_the_guard_and_meets_its_own_checks(self):
        calls = self.writers()
        with private_root(self.private):
            with self.assertRaisesRegex(ValueError, "run 1: report.json is missing"):
                calls["merge"](self.private / "m")
            with self.assertRaisesRegex(ValueError, "source run: report.json is missing"):
                calls["rerun-failed"](self.private / "r")
            with self.assertRaisesRegex(ValueError, "calibration requires labeled calibration controls"):
                calls["calibrate"](self.private / "c")

    def test_compare_writes_a_complete_run_inside_the_private_root(self):
        with private_root(self.private):
            report = self.writers()["compare"](self.private / "run")
        self.assertTrue(report["complete"])
        self.assertTrue((self.private / "run" / "report.json").is_file())

    def test_a_suite_without_owner_session_cases_writes_anywhere_with_the_variable_unset(self):
        with private_root(None):
            report = runner.compare(self.public_suite, RUBRIC, self.config_path, self.public_certificate,
                                    self.candidate, self.public / "run")
        self.assertTrue(report["complete"])
        self.assertTrue((self.public / "run" / "report.json").is_file())

    def test_the_demo_writes_anywhere_with_the_variable_unset(self):
        with private_root(None):
            code, _, _ = self.run_cli(["demo", "--out", str(self.public / "demo")])
        self.assertEqual(code, 0)
        self.assertTrue((self.public / "demo" / "report.json").is_file())


class CommandLineTests(PrivateFixture):
    def test_compare_refuses_with_exit_code_2_and_an_error_line_free_of_owner_text(self):
        out = self.public / "cli"
        with private_root(None):
            code, stdout, stderr = self.run_cli(self.compare_argv(self.owner_suite, self.owner_certificate, out))
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, f"error: {UNSET}\n")
        self.assertFalse(out.exists())

    def test_compare_outside_the_private_root_refuses_the_same_way(self):
        out = self.public / "cli"
        with private_root(self.private):
            code, _, stderr = self.run_cli(self.compare_argv(self.owner_suite, self.owner_certificate, out))
        self.assertEqual((code, stderr), (2, f"error: {OUTSIDE}\n"))
        self.assertFalse(out.exists())

    def test_compare_inside_the_private_root_runs(self):
        with private_root(self.private):
            code, stdout, _ = self.run_cli(self.compare_argv(self.owner_suite, self.owner_certificate, self.private / "cli"))
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(stdout)["complete"])

    def test_calibrate_merge_rerun_failed_and_optimize_refuse_through_the_command_line(self):
        base = ["--suite", str(self.owner_suite), "--rubric", str(RUBRIC), "--config", str(self.config_path)]
        commands = {
            "calibrate": ["calibrate", *base],
            "optimize": ["optimize", *base],
            "merge": ["merge", *base, "--calibration", str(self.owner_certificate),
                      "--runs", str(self.root / "gone-1"), str(self.root / "gone-2")],
            "rerun-failed": ["rerun-failed", *base, "--calibration", str(self.owner_certificate),
                             "--from", str(self.root / "gone")],
        }
        for name, argv in commands.items():
            out = self.public / name
            with self.subTest(name), private_root(None):
                code, _, stderr = self.run_cli([*argv, "--out", str(out)])
                self.assertEqual((code, stderr), (2, f"error: {UNSET}\n"))
                self.assertFalse(out.exists())

    def test_prepare_optimize_is_guarded_because_its_subset_can_hold_owner_cases(self):
        out = self.public / "subset.json"
        with private_root(None):
            code, _, stderr = self.run_cli(["prepare-optimize", "--suite", str(self.owner_suite), "--out", str(out)])
        self.assertEqual((code, stderr), (2, f"error: {UNSET}\n"))
        self.assertFalse(out.exists())
        with private_root(self.private):
            code, _, stderr = self.run_cli(["prepare-optimize", "--suite", str(self.owner_suite), "--out", str(out)])
        self.assertEqual((code, stderr), (2, f"error: {OUTSIDE}\n"))
        self.assertFalse(out.exists())
        inside = self.private / "subset.json"
        with private_root(self.private):
            code, stdout, _ = self.run_cli(["prepare-optimize", "--suite", str(self.owner_suite), "--out", str(inside)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout)["cases"], 2)
        self.assertTrue(inside.is_file())

    def test_prepare_optimize_for_a_public_suite_is_unchanged(self):
        out = self.public / "subset.json"
        with private_root(None):
            code, stdout, _ = self.run_cli(["prepare-optimize", "--suite", str(self.public_suite), "--out", str(out)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout)["cases"], 2)
        self.assertTrue(out.is_file())

    def test_validate_never_writes_and_is_never_guarded(self):
        with private_root(None):
            code, stdout, _ = self.run_cli(["validate", "--suite", str(self.owner_suite), "--rubric", str(RUBRIC)])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(stdout)["valid"])


if __name__ == "__main__":
    unittest.main()
