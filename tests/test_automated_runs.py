"""Chunked comparison runs: compare --documents, instructions.json, merge and rerun-failed.

No model is called. The writer and the judges are stand-in scripts that the real runner starts; the
calibration certificate is written by hand. A flag file makes a stand-in fail on demand, so a run can have
a plumbing failure and a later re-run can succeed."""

import contextlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from evaluation.benchmark_v2.automated import runner
from evaluation.benchmark_v2.automated.__main__ import main
from evaluation.benchmark_v2.automated.adapters import canonical_bytes, digest, load_config

AUTOMATED = Path(__file__).resolve().parents[1] / "evaluation" / "benchmark_v2" / "automated"
RUBRIC = AUTOMATED / "data" / "rubric.json"
PY = sys.executable

# Stand-in writer. A skill text that holds CANDIDATE-MARK makes it write the brief text; any other
# instructions make it write the wordy text. While the flag file exists it fails (exit 3) on the candidate
# call for the document whose context is "Context 2".
WRITER = '''import json, sys
from pathlib import Path
request = json.load(sys.stdin)
marked = "CANDIDATE-MARK" in request["instructions"]
if marked and Path(__FLAG__).exists() and request["context"] == "Context 2":
    sys.exit(3)
lead = "Brief take on " if marked else "A rather wordy take on "
print(json.dumps({"text": lead + request["prompt"]}))
'''

# Stand-in judge. It prefers the text that starts with "Brief" and quotes the first five characters of both
# texts. While its flag file exists it fails (exit 3) for the document whose context is "Context 2". While the
# bad-flag file exists it answers that document with an empty evidence list, which is an invalid judgment.
JUDGE = '''import json, sys
from pathlib import Path
request = json.load(sys.stdin)
if Path(__FLAG__).exists() and request["context"] == "Context 2":
    sys.exit(3)
if Path(__BAD__).exists() and request["context"] == "Context 2":
    print(json.dumps({"winner": "A", "reason": "x", "evidence": []}))
    sys.exit(0)
a, b = request["A"], request["B"]
winner = "A" if a.startswith("Brief") else "B"
print(json.dumps({"winner": winner, "reason": "briefer",
                  "evidence": [{"candidate": "A", "quote": a[:5]}, {"candidate": "B", "quote": b[:5]}]}))
'''


def suite_dict():
    cases = []
    for n in range(1, 6):
        cases.append({"id": f"case-{n}", "document_id": f"doc-{n}", "split": "test", "lane": "editing",
                      "prompt": f"Revise item {n}.", "context": f"Context {n}",
                      "a": f"alpha {n}", "b": f"beta {n}", "expected": None, "checks": {},
                      "provenance": {"kind": "synthetic_control", "source": "test fixture", "license": "CC0"}})
    return {"schema_version": 1, "name": "runs-fixture", "cases": cases}


class Fixture(unittest.TestCase):
    """A temporary folder holding a five-document test suite, stand-in adapters, a config and a certificate."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.flags = self.root / "flags"
        self.flags.mkdir()
        self.suite_path = self.root / "suite.json"
        self.suite_path.write_bytes(canonical_bytes(suite_dict()))
        (self.root / "writer.py").write_text(WRITER.replace("__FLAG__", repr(str(self.flags / "writer.flag"))), encoding="utf-8")
        (self.root / "judge.py").write_text(
            JUDGE.replace("__FLAG__", repr(str(self.flags / "judge.flag"))).replace("__BAD__", repr(str(self.flags / "bad.flag"))),
            encoding="utf-8")
        config = {"schema_version": 1,
                  "judges": [{"id": "j1", "family": "f1", "command": [PY, str(self.root / "judge.py")]},
                             {"id": "j2", "family": "f2", "command": [PY, str(self.root / "judge.py")]}],
                  "writer": {"id": "w", "family": "fw", "command": [PY, str(self.root / "writer.py")]}}
        self.config_path = self.root / "config.json"
        self.config_path.write_bytes(canonical_bytes(config))
        self.candidate = self.root / "candidate.md"
        self.candidate.write_bytes(b"# Candidate\nCANDIDATE-MARK\nWrite briefly.\n")
        self.baseline = self.root / "baseline.md"
        self.baseline.write_bytes(b"# Baseline\nKeep the draft as it is.\n")
        self.certificate = self.write_certificate()

    def write_certificate(self):
        config = load_config(self.config_path)
        report = {"schema_version": 1, "evaluation_type": "automated_proxy", "execution": "live",
                  "mode": "calibrate", "complete": True, "eligible": True,
                  "provenance": runner._provenance(self.suite_path, RUBRIC, self.config_path, config)}
        folder = self.root / "certificate"
        folder.mkdir()
        (folder / "report.json").write_bytes(canonical_bytes(report))
        return folder

    def compare(self, name, **options):
        return runner.compare(self.suite_path, RUBRIC, self.config_path, self.certificate,
                              self.candidate, self.root / name, **options)

    def read(self, name, filename):
        return json.loads((self.root / name / filename).read_bytes())


class DefaultsTests(unittest.TestCase):
    def config(self, **extra):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, folder, True)
        path = folder / "config.json"
        path.write_bytes(canonical_bytes({"schema_version": 1, **extra,
                                          "judges": [{"id": "j", "family": "f", "command": [PY]}]}))
        return path

    def test_config_defaults_are_300_seconds_and_2000_calls(self):
        config = load_config(self.config())
        self.assertEqual(config["timeout_seconds"], 300)
        self.assertEqual(config["max_calls"], 2000)

    def test_config_still_caps_timeout_at_600_and_keeps_an_explicit_call_limit(self):
        self.assertEqual(load_config(self.config(timeout_seconds=600, max_calls=50))["max_calls"], 50)
        with self.assertRaises(ValueError) as caught:
            load_config(self.config(timeout_seconds=601))
        self.assertEqual(str(caught.exception), "timeout_seconds must be >0 and <=600")


class DocumentsTests(Fixture):
    def test_documents_limits_the_run_to_the_named_documents(self):
        report = self.compare("two", documents=["doc-2", "doc-1"])
        self.assertEqual(report["provenance"]["documents"], ["doc-1", "doc-2"])
        generated = self.read("two", "generated.json")
        self.assertEqual(sorted(c["document_id"] for c in generated["cases"]), ["doc-1", "doc-2"])
        self.assertEqual(len(self.read("two", "records.json")), 8)
        self.assertEqual(len(list((self.root / "two" / "calls").iterdir())), 12)
        self.assertTrue(report["complete"])

    def test_no_documents_option_runs_every_document_and_records_null(self):
        report = self.compare("all")
        self.assertIsNone(report["provenance"]["documents"])
        self.assertEqual(len(self.read("all", "generated.json")["cases"]), 5)

    def test_an_unknown_document_is_refused_before_any_output(self):
        with self.assertRaises(ValueError) as caught:
            self.compare("unknown", documents=["doc-1", "doc-9"])
        self.assertIn("position 2", str(caught.exception))
        self.assertFalse((self.root / "unknown").exists())

    def test_empty_and_duplicate_document_lists_are_refused(self):
        for documents in ([], ["doc-1", "doc-1"], [""], "doc-1"):
            with self.assertRaises(ValueError, msg=repr(documents)):
                self.compare("refused", documents=documents)
            self.assertFalse((self.root / "refused").exists())

    def test_compare_command_accepts_several_documents(self):
        out = self.root / "cli"
        argv = ["compare", "--suite", str(self.suite_path), "--rubric", str(RUBRIC),
                "--config", str(self.config_path), "--calibration", str(self.certificate),
                "--candidate-skill", str(self.candidate), "--out", str(out), "--documents", "doc-2", "doc-1"]
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(main(argv), 0)
        self.assertEqual(json.loads(buffer.getvalue())["provenance"]["documents"], ["doc-1", "doc-2"])


class ProvenanceTests(Fixture):
    def test_instructions_json_records_what_the_writer_was_given(self):
        self.compare("one", documents=["doc-1"])
        data = self.read("one", "instructions.json")
        self.assertEqual(data["candidate"]["text"], self.candidate.read_bytes().decode("utf-8"))
        self.assertEqual(data["candidate"]["sha256"], digest(self.candidate.read_bytes()))
        self.assertEqual(data["baseline"]["text"], "")
        self.assertEqual(data["baseline"]["sha256"], digest(b""))

    def test_provenance_records_the_baseline_skill_and_the_repetitions(self):
        plain = self.compare("plain", documents=["doc-1"])
        self.assertIsNone(plain["provenance"]["baseline_skill_sha256"])
        self.assertEqual(plain["provenance"]["repetitions"], 1)
        based = self.compare("based", documents=["doc-1"], baseline_skill=self.baseline, repetitions=2)
        self.assertEqual(based["provenance"]["baseline_skill_sha256"], digest(self.baseline.read_bytes()))
        self.assertEqual(based["provenance"]["repetitions"], 2)
        self.assertEqual(len(self.read("based", "generated.json")["cases"]), 2)

    def test_a_failed_writer_call_voids_the_run_and_is_named(self):
        (self.flags / "writer.flag").write_text("x")
        report = self.compare("bad", documents=["doc-2"])
        self.assertFalse(report["complete"])
        self.assertFalse(report["eligible"])
        self.assertEqual(report["recommendation"], "inconclusive")
        checks = [c for c in report["checks"] if c["id"] == "writer_outputs"]
        self.assertEqual(len(checks), 1)
        self.assertFalse(checks[0]["passed"])
        failure = self.read("bad", "generated.json")["failures"][0]
        self.assertEqual(failure, {"case_id": "case-2--repeat-1", "baseline": None, "candidate": "process_exit_3"})

    def test_compare_requires_a_certificate_for_this_judge_signature(self):
        path = self.certificate / "report.json"
        report = json.loads(path.read_bytes())
        report["provenance"]["judge_signature"] = "0" * 64
        path.write_bytes(canonical_bytes(report))
        with self.assertRaises(ValueError) as caught:
            self.compare("refused", documents=["doc-1"])
        self.assertEqual(str(caught.exception), "matching eligible live calibration required")
        self.assertFalse((self.root / "refused").exists())
