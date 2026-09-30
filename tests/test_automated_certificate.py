"""Certificate, split and provenance tests. Fresh local subprocesses; no model calls or mock responses."""

import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

from evaluation.benchmark_v2.automated.__main__ import main
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

    def test_a_certificate_from_another_suite_needs_the_calibration_suite_option(self):
        with self.assertRaisesRegex(ValueError, "issued on another suite"):
            self.run_compare("out-no-option", calibration_suite=None)
        self.assertFalse((self.root / "out-no-option").exists())

    def test_a_calibration_suite_that_does_not_match_the_certificate_is_refused(self):
        with self.assertRaisesRegex(ValueError, "does not match the certificate"):
            self.run_compare("out-wrong-suite", calibration_suite=self.cmp_suite)
        self.assertFalse((self.root / "out-wrong-suite").exists())

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
