"""Certificate, split and provenance tests. Fresh local subprocesses; no model calls or mock responses."""

import contextlib
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from evaluation.benchmark_v2.automated import runner
from evaluation.benchmark_v2.automated.__main__ import main
from evaluation.benchmark_v2.automated.adapters import _resolved, canonical_bytes, digest, load_config, tool_versions
from evaluation.benchmark_v2.automated.runner import calibrate, compare

ADAPTER = '''import json, sys
r = json.load(sys.stdin)
if r.get('role') == 'writer':
    print(json.dumps({'text': 'A short revision.'}))
    sys.exit()
print(json.dumps({'winner': 'A' if r['A'] == 'alpha' else 'B', 'reason': 'literal',
                  'evidence': [{'candidate': 'A', 'quote': r['A']}, {'candidate': 'B', 'quote': r['B']}]}))
'''


def case(case_id, doc, split, *, cluster=None, expected=None, text=None):
    key = text or doc
    value = {
        "id": case_id, "document_id": doc, "split": split, "lane": "editing",
        "prompt": f"Revise the notice for {key}.", "context": f"Context for {key}.",
        "a": "alpha", "b": "beta", "expected": expected, "checks": {},
        "provenance": {"kind": "synthetic_control", "source": "unit test", "license": "CC0-1.0"},
    }
    if cluster is not None:
        value["cluster_id"] = cluster
    return value


def suite_of(cases):
    return {"schema_version": 1, "name": "unit", "cases": cases}


def certificate_cases():
    cases = [case(f"cal{i}", f"dcal{i}", "calibration", expected="a",
                  cluster="shared-thread" if i == 1 else None) for i in range(8)]
    return cases + [case(f"tst{i}", f"dtst{i}", "test") for i in range(5)]


def comparison_cases():
    return ([case(f"dev{i}", f"ddev{i}", "development") for i in range(2)] +
            [case(f"cmp{i}", f"dcmp{i}", "test") for i in range(5)])


def config_of(command, **extra):
    return {"schema_version": 1,
            "judges": [{"id": "first", "family": "one", "command": command},
                       {"id": "second", "family": "two", "command": command}],
            "writer": {"id": "writer", "family": "three", "command": command},
            "timeout_seconds": 10, "max_calls": 500, **extra}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class CertificateCase(unittest.TestCase):
    """Class-level fixture: one eligible calibration certificate shared by every test."""

    @classmethod
    def setUpClass(cls):
        tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmp.cleanup)
        # Resolve once: a Windows TEMP can be an 8.3 short path while load_config reports the long one.
        cls.root = Path(tmp.name).resolve()
        script = cls.root / "adapter.py"
        script.write_text(ADAPTER, encoding="utf-8")
        cls.command = [sys.executable, str(script)]
        cls.rubric = cls.write_json("rubric.json", {
            "schema_version": 1, "id": "r", "criteria": [{"id": "meaning", "description": "Preserve meaning."}]})
        cls.cal_suite = cls.write_json("cal-suite.json", suite_of(certificate_cases()))
        cls.cmp_suite = cls.write_json("cmp-suite.json", suite_of(comparison_cases()))
        cls.config = cls.write_json("config.json", config_of(cls.command))
        cls.skill = cls.root / "skill"
        cls.skill.mkdir()
        (cls.skill / "SKILL.md").write_text("Keep it short.\n", encoding="utf-8")
        cls.certificate_dir = cls.root / "certificate"
        cls.certificate = calibrate(cls.cal_suite, cls.rubric, cls.config, cls.certificate_dir)
        if not cls.certificate["eligible"]:
            raise AssertionError(f"fixture certificate is not eligible: {cls.certificate['checks']}")

    @classmethod
    def write_json(cls, name, value):
        path = cls.root / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def run_compare(self, name, **kwargs):
        options = {"suite": self.cmp_suite, "calibration_suite": self.cal_suite}
        options.update(kwargs)
        suite = options.pop("suite")
        return compare(suite, self.rubric, self.config, self.certificate_dir, self.skill, self.root / name, **options)

    def overlap_suite(self, name, *extra_cases):
        return self.write_json(f"overlap-{name}.json", suite_of(comparison_cases() + list(extra_cases)))

    def line_ending_pair(self, name, value):
        """Write the same pretty-printed JSON twice, with LF and with CRLF line endings; return both paths."""
        lf = json.dumps(value, indent=2).encode("utf-8")
        paths = []
        for suffix, data in (("lf", lf), ("crlf", lf.replace(b"\n", b"\r\n"))):
            path = self.root / f"{name}-{suffix}.json"
            path.write_bytes(data)
            paths.append(path)
        return paths

    def certificate_copy(self, name, **provenance):
        """A copy of the shared certificate with provenance fields replaced; a value of None removes the field."""
        copy = self.root / name
        shutil.copytree(self.certificate_dir, copy)
        path = copy / "report.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        for key, value in provenance.items():
            if value is None:
                report["provenance"].pop(key, None)
            else:
                report["provenance"][key] = value
        path.write_text(json.dumps(report), encoding="utf-8")
        return copy


class SplitAndGuardTests(CertificateCase):
    def test_compare_refuses_a_split_with_no_cases(self):
        with self.assertRaisesRegex(ValueError, "compare requires development cases"):
            self.run_compare("out-no-cases", suite=self.cal_suite, split="development")
        self.assertFalse((self.root / "out-no-cases").exists())

    def test_compare_refuses_an_unknown_split(self):
        with self.assertRaisesRegex(ValueError, "invalid split"):
            self.run_compare("out-holdout", split="holdout")
        self.assertFalse((self.root / "out-holdout").exists())

    def test_compare_records_split_and_certificate_suite_hash(self):
        report = self.run_compare("out-development", split="development")
        self.assertEqual(report["provenance"]["split"], "development")
        self.assertEqual(report["provenance"]["certificate_suite_sha256"], sha256(self.cal_suite))
        self.assertEqual(report["provenance"]["suite_sha256"], sha256(self.cmp_suite))
        self.assertEqual(report["provenance"]["calibration_overlap"], {"documents": 0, "clusters": 0, "pairs": 0})
        # Two development cases, two judges, two presentation orders; no test case was judged.
        self.assertEqual(report["counts"]["expected_records"], 8)
        self.assertEqual(report["counts"]["received_records"], 8)
        self.assertEqual(report["by_lane"]["editing"]["documents"], 2)
        self.assertFalse(report["eligible"])

    def test_compare_on_the_default_test_split_is_eligible(self):
        report = self.run_compare("out-default-split")
        self.assertEqual(report["provenance"]["split"], "test")
        # Five test cases, two judges, two presentation orders; the two development cases were not judged.
        self.assertEqual(report["counts"]["expected_records"], 20)
        self.assertEqual(report["counts"]["received_records"], 20)
        self.assertEqual(report["by_lane"]["editing"]["documents"], 5)
        self.assertTrue(report["eligible"], report["checks"])

    def test_a_certificate_from_another_suite_needs_the_calibration_suite_option(self):
        with self.assertRaisesRegex(ValueError, "issued on another suite"):
            self.run_compare("out-no-option", calibration_suite=None)
        self.assertFalse((self.root / "out-no-option").exists())

    def test_a_calibration_suite_that_does_not_match_the_certificate_is_refused(self):
        with self.assertRaisesRegex(ValueError, "does not match the certificate"):
            self.run_compare("out-wrong-suite", calibration_suite=self.cmp_suite)
        self.assertFalse((self.root / "out-wrong-suite").exists())

    def test_provenance_file_digests_ignore_line_endings(self):
        config = load_config(self.config)
        rubric = json.loads(self.rubric.read_text(encoding="utf-8"))
        files = {"suite": suite_of(certificate_cases()), "rubric": rubric, "config": config_of(self.command)}
        lf = {name: self.line_ending_pair(f"endings-{name}", value)[0] for name, value in files.items()}
        crlf = {name: self.line_ending_pair(f"endings-{name}", value)[1] for name, value in files.items()}
        from_lf = runner._provenance(lf["suite"], lf["rubric"], lf["config"], config)
        from_crlf = runner._provenance(crlf["suite"], crlf["rubric"], crlf["config"], config)
        for key in ("suite_sha256", "rubric_sha256", "config_sha256"):
            self.assertEqual(from_lf[key], from_crlf[key], key)
        # Only the line ending is ignored: a changed value still changes the digest.
        edited = self.line_ending_pair("endings-edited", suite_of(comparison_cases()))[1]
        self.assertNotEqual(runner._provenance(edited, lf["rubric"], lf["config"], config)["suite_sha256"],
                            from_crlf["suite_sha256"])

    def test_a_calibration_suite_with_other_line_endings_still_matches_the_certificate(self):
        lf, crlf = self.line_ending_pair("cal-suite-endings", suite_of(certificate_cases()))
        recorded = hashlib.sha256(lf.read_bytes()).hexdigest()
        certificate = self.certificate_copy("certificate-endings", suite_sha256=recorded)
        for path in (lf, crlf):
            with self.subTest(path.name):
                report = compare(self.cmp_suite, self.rubric, self.config, certificate, self.skill,
                                 self.root / f"out-{path.stem}", split="development", calibration_suite=path)
                self.assertEqual(report["provenance"]["certificate_suite_sha256"], recorded)

    def test_a_certificate_without_a_suite_hash_is_refused_up_front(self):
        certificate = self.certificate_copy("certificate-no-suite-hash", suite_sha256=None)
        for option in (self.cal_suite, None):
            with self.subTest(calibration_suite=option):
                with self.assertRaisesRegex(ValueError, "matching eligible live calibration required"):
                    compare(self.cmp_suite, self.rubric, self.config, certificate, self.skill,
                            self.root / "out-no-suite-hash", calibration_suite=option)
        self.assertFalse((self.root / "out-no-suite-hash").exists())

    def test_a_certificate_with_a_malformed_suite_hash_is_refused_up_front(self):
        # Empty, whitespace-only and non-string values; the whitespace ones used to get past the check.
        for index, value in enumerate(("", "   ", "\t\n", 123, ["abc"], True, {"sha256": "abc"})):
            certificate = self.certificate_copy(f"certificate-bad-hash-{index}", suite_sha256=value)
            for option in (self.cal_suite, None):
                with self.subTest(suite_sha256=value, calibration_suite=option):
                    with self.assertRaisesRegex(ValueError, "matching eligible live calibration required"):
                        compare(self.cmp_suite, self.rubric, self.config, certificate, self.skill,
                                self.root / "out-bad-suite-hash", calibration_suite=option)
        self.assertFalse((self.root / "out-bad-suite-hash").exists())

    def assert_overlap_refused(self, extra_case, kind, forbidden):
        suite = self.overlap_suite(extra_case["id"], extra_case)
        name = f"out-{extra_case['id']}"
        with self.assertRaises(ValueError) as caught:
            self.run_compare(name, suite=suite)
        message = str(caught.exception)
        self.assertIn(f"{extra_case['id']} overlaps a calibration control ({kind})", message)
        self.assertNotIn(forbidden, message)
        self.assertFalse((self.root / name).exists())

    def test_document_overlap_is_refused_without_echoing_ids(self):
        self.assert_overlap_refused(case("cmp-doc", "dcal0", "test", text="unrelated wording"), "document", "dcal0")

    def test_cluster_overlap_is_refused_without_echoing_ids(self):
        self.assert_overlap_refused(
            case("cmp-cluster", "dother", "test", cluster="shared-thread", text="another wording"),
            "cluster", "shared-thread")

    def test_copied_pair_overlap_is_refused_without_echoing_text(self):
        self.assert_overlap_refused(case("cmp-copy", "dother2", "test", text="dcal3"), "copied pair", "dcal3")

    def test_development_split_may_share_identities_with_the_calibration_suite(self):
        # Real-anchored controls are derived from development documents, so sharing is expected there.
        # The overlap is disclosed in provenance; only the test split refuses it.
        suite = self.overlap_suite(
            "development",
            case("dev-doc", "dcal0", "development", text="unrelated wording"),
            case("dev-cluster", "dother", "development", cluster="shared-thread", text="another wording"),
            case("dev-copy", "dother2", "development", text="dcal3"))
        report = self.run_compare("out-development-overlap", suite=suite, split="development")
        self.assertEqual(report["provenance"]["calibration_overlap"], {"documents": 1, "clusters": 1, "pairs": 1})
        # Five development cases, two judges, two presentation orders.
        self.assertEqual(report["counts"]["expected_records"], 20)
        self.assertEqual(report["counts"]["received_records"], 20)

    def cli_error(self, suite, *extra):
        argv = ["compare", "--suite", str(suite), "--rubric", str(self.rubric), "--config", str(self.config),
                "--out", str(self.root / "out-cli"), "--calibration", str(self.certificate_dir),
                "--candidate-skill", str(self.skill), *extra]
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr), self.assertRaises(SystemExit) as caught:
            main(argv)
        self.assertEqual(caught.exception.code, 2)
        return stderr.getvalue()

    def test_cli_passes_split_and_calibration_suite_to_compare(self):
        self.assertIn("compare requires development cases", self.cli_error(self.cal_suite, "--split", "development"))
        self.assertIn("does not match the certificate",
                      self.cli_error(self.cmp_suite, "--calibration-suite", str(self.cmp_suite)))
        self.assertIn("invalid choice", self.cli_error(self.cal_suite, "--split", "holdout"))
        self.assertFalse((self.root / "out-cli").exists())

    def test_cli_compare_succeeds_with_exit_zero_and_prints_the_report(self):
        out = self.root / "out-cli-ok"
        argv = ["compare", "--suite", str(self.cmp_suite), "--rubric", str(self.rubric), "--config", str(self.config),
                "--out", str(out), "--calibration", str(self.certificate_dir),
                "--candidate-skill", str(self.skill), "--calibration-suite", str(self.cal_suite)]
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(argv)
        self.assertEqual(code, 0)
        printed = json.loads(stdout.getvalue())
        self.assertEqual(printed["provenance"]["split"], "test")
        self.assertEqual(printed["counts"]["received_records"], 20)
        self.assertTrue((out / "report.json").is_file())


class AdapterSignatureTests(CertificateCase):
    def adapter_copy(self, name):
        """A private copy of the three shipped adapter scripts, so a test can edit bytes without touching the repository."""
        copy = self.root / name
        copy.mkdir()
        for script in runner.ADAPTER_SCRIPTS:
            shutil.copyfile(runner.ADAPTER_DIR / script, copy / script)
        return copy

    def test_changing_an_adapter_script_changes_the_judge_signature(self):
        config = load_config(self.config)
        original = runner._judge_signature(config)
        with mock.patch.object(runner, "ADAPTER_DIR", self.adapter_copy("adapters-identical")):
            self.assertEqual(runner._judge_signature(config), original)
        for script in runner.ADAPTER_SCRIPTS:
            edited = self.adapter_copy(f"adapters-edited-{script}")
            with (edited / script).open("ab") as handle:
                handle.write(b"\n# one more byte\n")
            with mock.patch.object(runner, "ADAPTER_DIR", edited):
                self.assertNotEqual(runner._judge_signature(config), original, script)

    def test_a_certificate_is_refused_after_an_adapter_script_changes(self):
        edited = self.adapter_copy("adapters-refused")
        with (edited / "codex_adapter.py").open("ab") as handle:
            handle.write(b"\n# edited after calibration\n")
        with mock.patch.object(runner, "ADAPTER_DIR", edited):
            with self.assertRaisesRegex(ValueError, "matching eligible live calibration required"):
                self.run_compare("out-edited-adapter")
        self.assertFalse((self.root / "out-edited-adapter").exists())

    def test_provenance_records_each_adapter_script_hash(self):
        recorded = self.certificate["provenance"]["adapter_sha256"]
        self.assertEqual(sorted(recorded), sorted(runner.ADAPTER_SCRIPTS))
        for script in runner.ADAPTER_SCRIPTS:
            # CRLF is read as LF (see the next test), so a CRLF checkout of the script records the same digest.
            raw = (runner.ADAPTER_DIR / script).read_bytes()
            self.assertEqual(recorded[script], hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest())

    def test_the_adapter_hashes_and_judge_signature_ignore_crlf_line_endings(self):
        config = load_config(self.config)
        original_hashes = runner._adapter_hashes()
        original_signature = runner._judge_signature(config)
        converted = self.adapter_copy("adapters-crlf")
        for script in runner.ADAPTER_SCRIPTS:
            lf_bytes = (converted / script).read_bytes().replace(b"\r\n", b"\n")
            (converted / script).write_bytes(lf_bytes.replace(b"\n", b"\r\n"))
            self.assertIn(b"\r\n", (converted / script).read_bytes(), script)
        with mock.patch.object(runner, "ADAPTER_DIR", converted):
            self.assertEqual(runner._adapter_hashes(), original_hashes)
            self.assertEqual(runner._judge_signature(config), original_signature)
        # A real edit still changes the digest: only the line ending is ignored.
        with (converted / runner.ADAPTER_SCRIPTS[0]).open("ab") as handle:
            handle.write(b"# edited\r\n")
        with mock.patch.object(runner, "ADAPTER_DIR", converted):
            self.assertNotEqual(runner._judge_signature(config), original_signature)

    def fixture_adapters(self, name, newline):
        """Three adapter scripts whose bytes this test writes itself, so the result does not depend on how the checkout stores the real ones."""
        folder = self.root / name
        folder.mkdir()
        for index, script in enumerate(runner.ADAPTER_SCRIPTS):
            lines = [f"# fixture adapter {index}", "import sys", "print(sys.argv)", ""]
            (folder / script).write_bytes(newline.join(lines).encode("utf-8"))
        return folder

    def test_adapter_hashes_agree_between_explicit_lf_and_crlf_fixture_folders(self):
        config = load_config(self.config)
        lf = self.fixture_adapters("fixture-lf", "\n")
        crlf = self.fixture_adapters("fixture-crlf", "\r\n")
        for script in runner.ADAPTER_SCRIPTS:
            self.assertNotIn(b"\r", (lf / script).read_bytes(), script)
            self.assertIn(b"\r\n", (crlf / script).read_bytes(), script)
            self.assertNotEqual((lf / script).read_bytes(), (crlf / script).read_bytes(), script)
        with mock.patch.object(runner, "ADAPTER_DIR", lf):
            lf_hashes, lf_signature = runner._adapter_hashes(), runner._judge_signature(config)
        with mock.patch.object(runner, "ADAPTER_DIR", crlf):
            crlf_hashes, crlf_signature = runner._adapter_hashes(), runner._judge_signature(config)
        self.assertEqual(crlf_hashes, lf_hashes)
        self.assertEqual(crlf_signature, lf_signature)
        for script in runner.ADAPTER_SCRIPTS:
            self.assertEqual(lf_hashes[script], hashlib.sha256((lf / script).read_bytes()).hexdigest(), script)
        # Different content still gives a different signature, so the equality above is not a constant.
        different = self.fixture_adapters("fixture-different", "\n")
        with (different / runner.ADAPTER_SCRIPTS[0]).open("ab") as handle:
            handle.write(b"print('extra')\n")
        with mock.patch.object(runner, "ADAPTER_DIR", different):
            self.assertNotEqual(runner._judge_signature(config), lf_signature)

    def test_a_certificate_signed_before_adapter_hashing_is_refused(self):
        old = self.root / "certificate-old-signature"
        shutil.copytree(self.certificate_dir, old)
        path = old / "report.json"
        report = json.loads(path.read_text(encoding="utf-8"))
        config = load_config(self.config)
        report["provenance"]["judge_signature"] = digest(canonical_bytes(
            [{"id": j["id"], "family": j["family"], "command": j["command"]} for j in config["judges"]]))
        path.write_text(json.dumps(report), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "matching eligible live calibration required"):
            compare(self.cmp_suite, self.rubric, self.config, old, self.skill, self.root / "out-old-signature",
                    calibration_suite=self.cal_suite)
        self.assertFalse((self.root / "out-old-signature").exists())


VERSION_PROBE = '''import os, sys, time
mode = sys.argv[1]
if mode == "noisy":
    sys.stdout.write("\\n\\n   tool 1.0   \\nsecond line\\n")
elif mode == "stderr-only":
    sys.stderr.write("\\n  tool 3.2.1  \\n")
elif mode == "both":
    sys.stdout.write("tool out\\n")
    sys.stderr.write("tool err\\n")
elif mode == "fail":
    sys.stdout.write("tool 9.9\\n")
    sys.exit(3)
elif mode == "hang":
    time.sleep(60)
elif mode == "cwd":
    print(os.getcwd())
elif mode == "stdin":
    print("stdin=" + repr(sys.stdin.read()))
'''

# Prints "tool <contents of the file>"; fails (nonzero exit) when the file is missing.
FILE_PROBE = '''import sys
from pathlib import Path
print("tool " + Path(sys.argv[1]).read_text(encoding="utf-8").strip())
'''

# Behaves like ADAPTER, except that on every call it first rewrites a version file once:
# when the file holds BEFORE it is replaced by AFTER, or deleted when AFTER is DELETE.
# As a writer it returns "alpha" for candidate instructions (the ones containing "Keep it short") and "beta" otherwise.
MUTATING_ADAPTER = '''import json, sys
from pathlib import Path
path, before, after = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
if path.exists() and path.read_text(encoding="utf-8").strip() == before:
    if after == "DELETE":
        path.unlink()
    else:
        path.write_text(after + "\\n", encoding="utf-8")
r = json.load(sys.stdin)
if r.get("role") == "writer":
    print(json.dumps({"text": "alpha" if "Keep it short" in r["instructions"] else "beta"}))
    sys.exit()
print(json.dumps({"winner": "A" if r["A"] == "alpha" else "B", "reason": "literal",
                  "evidence": [{"candidate": "A", "quote": r["A"]}, {"candidate": "B", "quote": r["B"]}]}))
'''


class ToolVersionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.probe_script = self.root / "probe.py"
        self.probe_script.write_text(VERSION_PROBE, encoding="utf-8")

    def version(self, mode, timeout=30):
        config = {"version_commands": {"probe": [sys.executable, str(self.probe_script), mode]}}
        return tool_versions(config, timeout=timeout)["probe"]

    def write_config(self, **extra):
        value = {"schema_version": 1, "judges": [{"id": "j", "family": "f", "command": [sys.executable]}], **extra}
        path = self.root / "config.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def test_first_nonblank_stdout_line_is_the_version(self):
        self.assertEqual(self.version("noisy"), "tool 1.0")

    def test_stderr_is_the_fallback_when_stdout_is_empty(self):
        self.assertEqual(self.version("stderr-only"), "tool 3.2.1")

    def test_stdout_wins_when_both_streams_have_text(self):
        self.assertEqual(self.version("both"), "tool out")

    def fake_tool(self, name, version):
        """Put an executable called name in a private folder and return the folder.

        On Windows it is name.cmd, the shape of an npm shim such as codex.cmd. CreateProcess does not
        search PATHEXT, so the bare name is not found by subprocess unless it is resolved first."""
        folder = self.root / "bin"
        folder.mkdir(exist_ok=True)
        if os.name == "nt":
            (folder / f"{name}.cmd").write_bytes(f"@echo off\r\necho {name} {version}\r\n".encode("utf-8"))
        else:
            tool = folder / name
            tool.write_text(f"#!/bin/sh\necho '{name} {version}'\n", encoding="utf-8")
            tool.chmod(0o755)
        return folder

    def test_a_bare_command_name_is_resolved_through_path_like_an_npm_shim(self):
        folder = self.fake_tool("shimtool", "4.5.6")
        config = {"version_commands": {"shim": ["shimtool", "--version"]}}
        with mock.patch.dict(os.environ, {"PATH": os.pathsep.join([str(folder), os.environ.get("PATH", "")])}):
            self.assertEqual(tool_versions(config)["shim"], "shimtool 4.5.6")
        self.assertIsNone(tool_versions({"version_commands": {"gone": ["no-such-tool-anywhere", "--version"]}})["gone"])

    def test_record_versions_tolerates_a_report_without_lanes(self):
        config = {"version_commands": {"probe": [sys.executable, str(self.probe_script), "noisy"]}}
        report = {"provenance": {}, "checks": [], "eligible": True, "recommendation": "candidate"}
        runner._record_versions(report, config, {"probe": "tool 0.9"}, "compare")
        self.assertEqual(report["provenance"]["tool_versions"]["changed"], ["probe"])
        self.assertFalse(report["eligible"])
        self.assertEqual(report["recommendation"], "inconclusive")

    def test_a_command_found_through_a_relative_path_entry_runs_from_its_absolute_path(self):
        # The version command runs in a scratch folder, so a relative result from shutil.which would point nowhere.
        folder = self.fake_tool("relshim", "7.8.9")
        original = Path.cwd()
        os.chdir(self.root)
        try:
            with mock.patch.dict(os.environ, {"PATH": folder.name}):
                argv = _resolved(["relshim", "--version"])
                self.assertTrue(os.path.isabs(argv[0]), argv[0])
                self.assertEqual(argv[1:], ["--version"])
                config = {"version_commands": {"rel": ["relshim", "--version"]}}
                self.assertEqual(tool_versions(config)["rel"], "relshim 7.8.9")
        finally:
            os.chdir(original)

    def test_a_command_that_is_not_found_is_left_as_written(self):
        self.assertEqual(_resolved(["no-such-tool-anywhere", "--version"]), ["no-such-tool-anywhere", "--version"])

    def test_record_versions_tolerates_a_report_whose_lanes_are_explicitly_none(self):
        config = {"version_commands": {"probe": [sys.executable, str(self.probe_script), "noisy"]}}
        report = {"provenance": {}, "checks": [], "eligible": True, "recommendation": "candidate", "by_lane": None}
        runner._record_versions(report, config, {"probe": "tool 0.9"}, "compare")
        self.assertEqual(report["provenance"]["tool_versions"]["changed"], ["probe"])
        self.assertFalse(report["eligible"])
        self.assertEqual(report["recommendation"], "inconclusive")

    def test_nonzero_exit_silence_and_missing_executable_are_unreadable(self):
        self.assertIsNone(self.version("fail"))
        self.assertIsNone(self.version("silent"))
        gone = {"version_commands": {"gone": [str(self.root / "no-such-tool")]}}
        self.assertIsNone(tool_versions(gone)["gone"])

    def test_a_hung_version_command_times_out_as_unreadable(self):
        started = time.monotonic()
        self.assertIsNone(self.version("hang", timeout=1))
        self.assertLess(time.monotonic() - started, 30)

    def test_probe_has_no_stdin_and_runs_outside_the_working_directory(self):
        self.assertEqual(self.version("stdin"), "stdin=''")
        probe_directory = Path(self.version("cwd")).resolve()
        self.assertNotEqual(probe_directory, Path.cwd().resolve())

    def test_tool_versions_maps_each_configured_name_in_sorted_order(self):
        config = {"version_commands": {
            "b-tool": [sys.executable, str(self.probe_script), "noisy"],
            "a-tool": [sys.executable, str(self.probe_script), "fail"]}}
        result = tool_versions(config)
        self.assertEqual(list(result), ["a-tool", "b-tool"])
        self.assertEqual(result, {"a-tool": None, "b-tool": "tool 1.0"})
        self.assertEqual(tool_versions({}), {})
        self.assertEqual(tool_versions({"version_commands": {}}), {})

    def test_load_config_keeps_valid_version_commands_and_defaults_to_none(self):
        self.assertEqual(load_config(self.write_config())["version_commands"], {})
        (self.root / "local-tool").write_text("x", encoding="utf-8")
        commands = {"agy": ["agy", "--version"], "codex.cli_2": ["local-tool", "--version"]}
        value = load_config(self.write_config(version_commands=commands))
        # The argv stays as written: unlike adapter commands it is not resolved against the config folder.
        self.assertEqual(value["version_commands"], commands)

    def test_load_config_rejects_invalid_version_commands(self):
        bad = [
            ("not an object", ["agy", "--version"]),
            ("name with a space", {"has space": ["agy", "--version"]}),
            ("empty name", {"": ["agy", "--version"]}),
            ("argv not a list", {"agy": "agy --version"}),
            ("empty argv", {"agy": []}),
            ("blank part", {"agy": ["agy", "  "]}),
            ("non-string part", {"agy": ["agy", 1]}),
        ]
        for label, commands in bad:
            with self.subTest(label):
                with self.assertRaisesRegex(ValueError, "version[ _]command"):
                    load_config(self.write_config(version_commands=commands))


class RunVersionTests(CertificateCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mutator = cls.root / "mutator.py"
        cls.mutator.write_text(MUTATING_ADAPTER, encoding="utf-8")
        cls.reader = cls.root / "reader.py"
        cls.reader.write_text(FILE_PROBE, encoding="utf-8")

    def version_file(self, name, content=None):
        path = self.root / f"{name}.version"
        if content is not None:
            path.write_text(content, encoding="utf-8")
        return path

    def mutator_command(self, version_file, before, after):
        return [sys.executable, str(self.mutator), str(version_file), before, after]

    def probe_config(self, name, version_file, *, judges=None, writer=None):
        """A config with one version command, named probe, that reads the version file."""
        extra = {"version_commands": {"probe": [sys.executable, str(self.reader), str(version_file)]}}
        if writer is not None:
            extra["writer"] = {"id": "writer", "family": "three", "command": writer}
        return self.write_json(f"{name}-config.json", config_of(judges or self.command, **extra))

    def versioned_compare(self, name, config):
        # The judges keep the certificate's commands, so the class-level certificate still matches.
        return compare(self.cmp_suite, self.rubric, config, self.certificate_dir, self.skill, self.root / name,
                       calibration_suite=self.cal_suite)

    def check_of(self, report):
        return next(c for c in report["checks"] if c["id"] == "tool_versions_stable")

    def test_calibrate_records_versions_before_and_after(self):
        version = self.version_file("cal-stable", "2.0.0")
        config = self.probe_config("cal-stable", version, judges=self.mutator_command(version, "1.0.0", "2.0.0"))
        report = calibrate(self.cal_suite, self.rubric, config, self.root / "out-cal-stable")
        self.assertEqual(report["provenance"]["tool_versions"],
                         {"before": {"probe": "tool 2.0.0"}, "after": {"probe": "tool 2.0.0"}, "changed": []})
        self.assertTrue(self.check_of(report)["passed"])
        self.assertTrue(report["eligible"])

    def test_calibrate_with_a_version_that_changes_is_not_eligible(self):
        version = self.version_file("cal-changing", "1.0.0")
        config = self.probe_config("cal-changing", version, judges=self.mutator_command(version, "1.0.0", "2.0.0"))
        report = calibrate(self.cal_suite, self.rubric, config, self.root / "out-cal-changing")
        self.assertEqual(report["provenance"]["tool_versions"],
                         {"before": {"probe": "tool 1.0.0"}, "after": {"probe": "tool 2.0.0"}, "changed": ["probe"]})
        self.assertFalse(self.check_of(report)["passed"])
        self.assertIn("probe", self.check_of(report)["message"])
        self.assertFalse(report["eligible"])
        self.assertTrue(report["complete"])

    def test_compare_records_stable_versions_and_keeps_the_recommendation(self):
        version = self.version_file("cmp-stable", "2.0.0")
        config = self.probe_config("cmp-stable", version, writer=self.mutator_command(version, "1.0.0", "2.0.0"))
        report = self.versioned_compare("out-cmp-stable", config)
        self.assertEqual(report["provenance"]["tool_versions"]["changed"], [])
        self.assertTrue(self.check_of(report)["passed"])
        self.assertTrue(report["eligible"])
        self.assertEqual(report["recommendation"], "candidate")

    def test_compare_with_a_version_change_voids_the_run(self):
        version = self.version_file("cmp-changing", "1.0.0")
        config = self.probe_config("cmp-changing", version, writer=self.mutator_command(version, "1.0.0", "2.0.0"))
        report = self.versioned_compare("out-cmp-changing", config)
        self.assertEqual(report["provenance"]["tool_versions"],
                         {"before": {"probe": "tool 1.0.0"}, "after": {"probe": "tool 2.0.0"}, "changed": ["probe"]})
        self.assertFalse(self.check_of(report)["passed"])
        self.assertFalse(report["eligible"])
        self.assertEqual(report["recommendation"], "inconclusive")
        self.assertEqual({lane["recommendation"] for lane in report["by_lane"].values()}, {"inconclusive"})
        self.assertTrue(report["complete"])

    def test_an_unreadable_version_after_the_run_voids_the_run(self):
        version = self.version_file("cmp-deleted", "1.0.0")
        config = self.probe_config("cmp-deleted", version, writer=self.mutator_command(version, "1.0.0", "DELETE"))
        report = self.versioned_compare("out-cmp-deleted", config)
        tools = report["provenance"]["tool_versions"]
        self.assertEqual((tools["before"], tools["after"], tools["changed"]),
                         ({"probe": "tool 1.0.0"}, {"probe": None}, ["probe"]))
        self.assertFalse(report["eligible"])
        self.assertEqual(report["recommendation"], "inconclusive")

    def test_a_version_command_that_fails_before_the_run_aborts_with_no_output(self):
        config = self.probe_config("abort", self.root / "never-created.version")
        with self.assertRaisesRegex(ValueError, "version command failed before the run: probe"):
            self.versioned_compare("out-abort-compare", config)
        with self.assertRaisesRegex(ValueError, "version command failed before the run: probe"):
            calibrate(self.cal_suite, self.rubric, config, self.root / "out-abort-calibrate")
        self.assertFalse((self.root / "out-abort-compare").exists())
        self.assertFalse((self.root / "out-abort-calibrate").exists())

    def test_without_version_commands_nothing_is_recorded(self):
        report = self.run_compare("out-no-versions")
        for value in (report, self.certificate):
            self.assertNotIn("tool_versions", value["provenance"])
            self.assertNotIn("tool_versions_stable", [c["id"] for c in value["checks"]])
