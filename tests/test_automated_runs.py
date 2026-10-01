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
                "--candidate-skill", str(self.candidate), "--out", str(out),
                "--documents", "doc-3", "doc-1", "doc-5", "doc-2", "doc-4"]
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(main(argv), 0)
        printed = json.loads(buffer.getvalue())
        self.assertEqual(printed["provenance"]["documents"], ["doc-1", "doc-2", "doc-3", "doc-4", "doc-5"])
        # Five documents, so the lane gate (five per lane) is met: the printed report is the eligible one on disk.
        self.assertEqual(json.loads((out / "report.json").read_bytes()), printed)
        self.assertTrue(printed["eligible"])


class ProvenanceTests(Fixture):
    def test_instructions_json_records_what_the_writer_was_given(self):
        self.compare("one", documents=["doc-1"])
        data = self.read("one", "instructions.json")
        self.assertEqual(data["candidate"]["text"], self.candidate.read_bytes().decode("utf-8"))
        self.assertEqual(data["candidate"]["sha256"], digest(self.candidate.read_bytes()))
        self.assertEqual(data["baseline"]["text"], "No additional instructions.")
        self.assertEqual(data["baseline"]["sha256"], digest(b"No additional instructions."))

    def test_with_no_baseline_skill_the_writer_is_told_there_are_no_additional_instructions(self):
        self.compare("plain", documents=["doc-1"])
        request = json.loads((self.root / "plain" / "calls" / "00001" / "request.json").read_bytes())
        self.assertEqual((request["role"], request["instructions"]), ("writer", "No additional instructions."))

    def test_provenance_records_the_baseline_skill_and_the_repetitions(self):
        plain = self.compare("plain", documents=["doc-1"])
        self.assertIsNone(plain["provenance"]["baseline_skill_sha256"])
        self.assertEqual(plain["provenance"]["repetitions"], 1)
        based = self.compare("based", documents=["doc-1"], baseline_skill=self.baseline, repetitions=2)
        self.assertEqual(based["provenance"]["baseline_skill_sha256"], digest(self.baseline.read_bytes()))
        self.assertEqual(based["provenance"]["repetitions"], 2)
        self.assertEqual(len(self.read("based", "generated.json")["cases"]), 2)

    def test_provenance_records_the_snapshot_hashes_and_keeps_the_skill_md_hash(self):
        plain = self.compare("plain", documents=["doc-1"])["provenance"]
        self.assertEqual(plain["candidate_skill_sha256"], digest(self.candidate.read_bytes()))
        self.assertEqual(plain["candidate_snapshot_sha256"], digest(self.candidate.read_bytes()))
        self.assertIn("baseline_snapshot_sha256", plain)
        self.assertIsNone(plain["baseline_snapshot_sha256"])
        based = self.compare("based", documents=["doc-1"], baseline_skill=self.baseline)["provenance"]
        self.assertEqual(based["baseline_skill_sha256"], digest(self.baseline.read_bytes()))
        self.assertEqual(based["baseline_snapshot_sha256"], digest(self.baseline.read_bytes()))

    def test_the_snapshot_hash_covers_references_while_the_skill_md_hash_does_not(self):
        folder = self.root / "skill"
        (folder / "references").mkdir(parents=True)
        (folder / "SKILL.md").write_bytes(self.candidate.read_bytes())
        (folder / "references" / "a.md").write_bytes(b"Reference A.\n")
        self.candidate = folder
        provenance = self.compare("folder", documents=["doc-1"])["provenance"]
        snapshot = self.read("folder", "instructions.json")["candidate"]["text"]
        self.assertEqual(snapshot, self.candidate.joinpath("SKILL.md").read_bytes().decode("utf-8")
                         + "\n=== references/a.md ===\nReference A.\n")
        self.assertEqual(provenance["candidate_skill_sha256"], digest((folder / "SKILL.md").read_bytes()))
        self.assertEqual(provenance["candidate_snapshot_sha256"], digest(snapshot.encode("utf-8")))
        self.assertNotEqual(provenance["candidate_snapshot_sha256"], provenance["candidate_skill_sha256"])

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


class VersionedFixture(Fixture):
    """The fixture with a configured tool version that a test can change between chunk runs."""

    def setUp(self):
        super().setUp()
        self.version_file = self.root / "tool-version.txt"
        self.set_version("tool 1.0")
        config = json.loads(self.config_path.read_bytes())
        config["version_commands"] = {
            "tool": [PY, "-c", f"print(open({str(self.version_file)!r}).read().strip())"]}
        self.config_path.write_bytes(canonical_bytes(config))

    def set_version(self, text):
        self.version_file.write_text(text, encoding="utf-8")


class MergeTests(VersionedFixture):
    def chunk(self, name, documents, **options):
        return self.compare(name, documents=documents, **options)

    def merge(self, out, *names, **options):
        from evaluation.benchmark_v2.automated import runs
        return runs.merge(self.suite_path, RUBRIC, self.config_path, self.certificate,
                          [self.root / name for name in names], self.root / out, **options)

    def test_merging_two_chunks_equals_one_whole_run(self):
        whole = self.compare("whole")
        self.chunk("first", ["doc-1", "doc-2", "doc-3"])
        self.chunk("second", ["doc-4", "doc-5"])
        merged = self.merge("merged", "first", "second")
        for key in ("by_lane", "counts", "complete", "eligible", "recommendation"):
            self.assertEqual(merged[key], whole[key], key)
        self.assertTrue(merged["complete"])
        self.assertEqual(merged["provenance"]["documents"], ["doc-1", "doc-2", "doc-3", "doc-4", "doc-5"])
        self.assertEqual(len(merged["provenance"]["merged_from"]), 2)
        for entry in merged["provenance"]["merged_from"]:
            self.assertEqual(sorted(entry), ["records_sha256", "report_sha256", "rerun_calls"])
        self.assertEqual((self.root / "merged" / "instructions.json").read_bytes(),
                         (self.root / "first" / "instructions.json").read_bytes())
        self.assertTrue((self.root / "merged" / "candidate-SKILL.md").exists())
        self.assertFalse((self.root / "merged" / "calls").exists())
        self.assertEqual(len(self.read("merged", "records.json")), 20)

    def test_chunks_that_share_a_document_are_refused(self):
        self.chunk("first", ["doc-1", "doc-2"])
        self.chunk("second", ["doc-2", "doc-3"])
        with self.assertRaises(ValueError) as caught:
            self.merge("merged", "first", "second")
        self.assertIn("overlap", str(caught.exception))
        self.assertNotIn("doc-2", str(caught.exception))
        self.assertFalse((self.root / "merged").exists())

    def test_chunks_made_with_different_candidate_text_are_refused(self):
        self.chunk("first", ["doc-1"])
        self.candidate.write_bytes(self.candidate.read_bytes() + b"Keep headings.\n")
        self.chunk("second", ["doc-2"])
        with self.assertRaises(ValueError) as caught:
            self.merge("merged", "first", "second")
        self.assertIn("candidate_skill_sha256", str(caught.exception))
        self.assertFalse((self.root / "merged").exists())

    def skill_folder(self, name, source):
        """A skill folder whose SKILL.md is the given file; returns the folder and its one reference file."""
        folder = self.root / name
        (folder / "references").mkdir(parents=True)
        (folder / "SKILL.md").write_bytes(source.read_bytes())
        reference = folder / "references" / "a.md"
        reference.write_bytes(b"Reference one.\n")
        return folder, reference

    def test_chunks_made_from_different_candidate_references_are_refused(self):
        self.candidate, reference = self.skill_folder("skill", self.candidate)
        self.chunk("first", ["doc-1"])
        reference.write_bytes(b"Reference two.\n")
        self.chunk("second", ["doc-2"])
        with self.assertRaises(ValueError) as caught:
            self.merge("merged", "first", "second")
        self.assertEqual(str(caught.exception), "chunk runs differ in candidate_snapshot_sha256")
        self.assertFalse((self.root / "merged").exists())

    def test_chunks_made_from_different_baseline_references_are_refused(self):
        baseline, reference = self.skill_folder("base", self.baseline)
        self.chunk("first", ["doc-1"], baseline_skill=baseline)
        reference.write_bytes(b"Reference two.\n")
        self.chunk("second", ["doc-2"], baseline_skill=baseline)
        with self.assertRaises(ValueError) as caught:
            self.merge("merged", "first", "second")
        self.assertEqual(str(caught.exception), "chunk runs differ in baseline_snapshot_sha256")
        self.assertFalse((self.root / "merged").exists())

    def test_chunks_with_the_same_snapshot_merge_and_the_report_keeps_its_hashes(self):
        self.candidate, _ = self.skill_folder("skill", self.candidate)
        first = self.chunk("first", ["doc-1"])
        self.chunk("second", ["doc-2"])
        merged = self.merge("merged", "first", "second")
        for key in ("candidate_snapshot_sha256", "baseline_snapshot_sha256", "candidate_skill_sha256"):
            self.assertIn(key, merged["provenance"])
            self.assertEqual(merged["provenance"][key], first["provenance"][key], key)
        self.assertIsNotNone(merged["provenance"]["candidate_snapshot_sha256"])

    def test_chunks_with_different_repetitions_are_refused(self):
        self.chunk("first", ["doc-1"])
        self.chunk("second", ["doc-2"], repetitions=2)
        with self.assertRaises(ValueError) as caught:
            self.merge("merged", "first", "second")
        self.assertIn("repetitions", str(caught.exception))

    def test_a_chunk_with_a_writer_failure_is_refused(self):
        self.chunk("first", ["doc-1"])
        (self.flags / "writer.flag").write_text("x")
        self.chunk("second", ["doc-2"])
        with self.assertRaises(ValueError) as caught:
            self.merge("merged", "first", "second")
        self.assertIn("run 2", str(caught.exception))
        self.assertIn("writer failures", str(caught.exception))

    def test_chunks_made_under_different_tool_versions_are_refused(self):
        self.chunk("first", ["doc-1"])
        self.set_version("tool 2.0")
        self.chunk("second", ["doc-2"])
        with self.assertRaises(ValueError) as caught:
            self.merge("merged", "first", "second")
        self.assertIn("tool versions", str(caught.exception))

    def test_a_chunk_that_recorded_a_tool_change_is_refused(self):
        self.chunk("first", ["doc-1"])
        self.chunk("second", ["doc-2"])
        path = self.root / "second" / "report.json"
        report = json.loads(path.read_bytes())
        report["provenance"]["tool_versions"]["changed"] = ["tool"]
        path.write_bytes(canonical_bytes(report) + b"\n")
        with self.assertRaises(ValueError) as caught:
            self.merge("merged", "first", "second")
        self.assertIn("changed tool versions", str(caught.exception))

    def test_merge_needs_two_runs_and_refuses_a_merged_run(self):
        self.chunk("first", ["doc-1", "doc-2"])
        self.chunk("second", ["doc-3"])
        with self.assertRaises(ValueError) as caught:
            self.merge("one", "first")
        self.assertEqual(str(caught.exception), "merge needs at least two runs")
        self.merge("merged", "first", "second")
        self.chunk("third", ["doc-4", "doc-5"])
        with self.assertRaises(ValueError) as caught:
            self.merge("again", "merged", "third")
        self.assertIn("is a merged run", str(caught.exception))
        self.assertFalse((self.root / "again").exists())

    def test_chunks_made_under_another_config_are_refused(self):
        self.chunk("first", ["doc-1"])
        self.chunk("second", ["doc-2"])
        config = json.loads(self.config_path.read_bytes())
        config["max_calls"] = 500
        self.config_path.write_bytes(canonical_bytes(config))
        with self.assertRaises(ValueError) as caught:
            self.merge("merged", "first", "second")
        self.assertIn("config_sha256", str(caught.exception))

    def test_merge_command_prints_the_merged_report(self):
        self.chunk("first", ["doc-1", "doc-2", "doc-3"])
        self.chunk("second", ["doc-4", "doc-5"])
        argv = ["merge", "--suite", str(self.suite_path), "--rubric", str(RUBRIC),
                "--config", str(self.config_path), "--calibration", str(self.certificate),
                "--out", str(self.root / "cli-merged"),
                "--runs", str(self.root / "first"), str(self.root / "second")]
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(main(argv), 0)
        report = json.loads(buffer.getvalue())
        self.assertEqual(len(report["provenance"]["merged_from"]), 2)
        self.assertTrue(report["complete"])


class RerunFailedTests(VersionedFixture):
    def rerun(self, source, out, **options):
        from evaluation.benchmark_v2.automated import runs
        return runs.rerun_failed(self.suite_path, RUBRIC, self.config_path, self.certificate,
                                 self.root / source, self.root / out, **options)

    def failing_run(self, name="source", documents=("doc-1", "doc-2", "doc-3")):
        """A comparison in which every judge call for doc-2 fails (exit 3); the flag is gone when it returns."""
        (self.flags / "judge.flag").write_text("x")
        report = self.compare(name, documents=list(documents))
        (self.flags / "judge.flag").unlink()
        return report

    def test_a_rerun_replaces_plumbing_failures_and_leaves_the_source_alone(self):
        source = self.failing_run()
        self.assertEqual(source["counts"]["plumbing_failures"], 4)
        self.assertFalse(source["complete"])
        source_bytes = (self.root / "source" / "report.json").read_bytes()
        report = self.rerun("source", "again")
        self.assertTrue(report["complete"])
        self.assertEqual(report["counts"]["plumbing_failures"], 0)
        records = self.read("again", "records.json")
        self.assertEqual(len(records), 12)
        self.assertEqual(sorted(r["case_id"] for r in records if r.get("attempt") == 2), ["case-2--repeat-1"] * 4)
        rerun = report["provenance"]["rerun"]
        self.assertEqual(rerun["rerun_calls"], 4)
        self.assertEqual(rerun["source_report_sha256"], digest(source_bytes))
        self.assertEqual(report["provenance"]["tool_versions"]["changed"], [])
        # The re-run's folder stands alone: the 18 copied source calls (6 writer, 12 judge) plus its own 4 (next test).
        self.assertEqual(len(list((self.root / "again" / "calls").iterdir())), 22)
        self.assertEqual((self.root / "source" / "report.json").read_bytes(), source_bytes)
        for name in ("generated.json", "instructions.json", "candidate-SKILL.md"):
            self.assertEqual((self.root / "again" / name).read_bytes(), (self.root / "source" / name).read_bytes())

    def test_a_rerun_folder_holds_its_own_copy_of_every_call_it_refers_to(self):
        self.failing_run()
        source_calls = self.root / "source" / "calls"
        source_names = sorted(entry.name for entry in source_calls.iterdir())
        # Writer calls and judge calls share one numbering: 6 writer calls, then 12 judge calls.
        self.assertEqual(source_names, [f"{n:05d}" for n in range(1, 19)])
        self.rerun("source", "again")
        again_calls = self.root / "again" / "calls"
        # Every source call is copied unchanged under its own number, so deleting the source loses nothing.
        for name in source_names:
            for part in ("request.json", "response.bin", "stderr.bin", "metadata.json"):
                self.assertEqual((again_calls / name / part).read_bytes(), (source_calls / name / part).read_bytes(), (name, part))
        # The four re-run calls follow them under new numbers and all succeeded (the failure flag was lifted).
        new_names = sorted(entry.name for entry in again_calls.iterdir() if entry.name not in source_names)
        self.assertEqual(new_names, [f"{n:05d}" for n in range(19, 23)])
        for name in new_names:
            self.assertEqual(json.loads((again_calls / name / "metadata.json").read_bytes())["returncode"], 0)
        # The source folder is not touched by the copy.
        self.assertEqual(sorted(entry.name for entry in source_calls.iterdir()), source_names)

    def test_a_rerun_that_fails_again_stays_plumbing_and_cannot_be_run_a_third_time(self):
        self.failing_run()
        (self.flags / "judge.flag").write_text("x")
        report = self.rerun("source", "again")
        self.assertFalse(report["complete"])
        self.assertEqual(report["counts"]["plumbing_failures"], 4)
        self.assertEqual(report["provenance"]["rerun"]["rerun_calls"], 4)
        (self.flags / "judge.flag").unlink()
        with self.assertRaises(ValueError) as caught:
            self.rerun("again", "third")
        self.assertIn("cannot be re-run", str(caught.exception))
        self.assertFalse((self.root / "third").exists())

    def test_a_judgment_failure_is_never_rerun(self):
        (self.flags / "bad.flag").write_text("x")
        source = self.compare("source", documents=["doc-1", "doc-2"])
        (self.flags / "bad.flag").unlink()
        self.assertEqual(source["counts"]["judgment_failures"], 4)
        self.assertEqual(source["counts"]["plumbing_failures"], 0)
        with self.assertRaises(ValueError) as caught:
            self.rerun("source", "again")
        self.assertIn("no plumbing failures", str(caught.exception))
        self.assertFalse((self.root / "again").exists())

    def strip_failure_kinds(self, name):
        """Rewrite a run's records as an older version wrote them: no failure_kind on any record."""
        path = self.root / name / "records.json"
        records = json.loads(path.read_bytes())
        for record in records:
            record.pop("failure_kind", None)
        path.write_bytes(canonical_bytes(records) + b"\n")

    def test_a_run_written_before_failure_kinds_is_rerun_from_its_error_text(self):
        self.failing_run()
        self.strip_failure_kinds("source")
        report = self.rerun("source", "again")
        self.assertTrue(report["complete"])
        self.assertEqual(report["counts"]["plumbing_failures"], 0)
        self.assertEqual(report["provenance"]["rerun"]["rerun_calls"], 4)
        records = self.read("again", "records.json")
        self.assertEqual(sorted(r["case_id"] for r in records if r.get("attempt") == 2), ["case-2--repeat-1"] * 4)

    def test_a_legacy_judgment_failure_is_never_rerun(self):
        (self.flags / "bad.flag").write_text("x")
        self.compare("source", documents=["doc-1", "doc-2"])
        (self.flags / "bad.flag").unlink()
        self.strip_failure_kinds("source")
        with self.assertRaises(ValueError) as caught:
            self.rerun("source", "again")
        self.assertIn("no plumbing failures", str(caught.exception))
        self.assertFalse((self.root / "again").exists())

    def test_a_source_with_writer_failures_is_refused(self):
        (self.flags / "writer.flag").write_text("x")
        self.compare("source", documents=["doc-1", "doc-2"])
        (self.flags / "writer.flag").unlink()
        with self.assertRaises(ValueError) as caught:
            self.rerun("source", "again")
        self.assertIn("writer failures", str(caught.exception))
        self.assertFalse((self.root / "again").exists())

    def test_changed_tool_versions_since_the_run_are_refused(self):
        self.failing_run()
        self.set_version("tool 2.0")
        with self.assertRaises(ValueError) as caught:
            self.rerun("source", "again")
        self.assertIn("tool versions changed", str(caught.exception))
        self.assertFalse((self.root / "again").exists())

    def test_a_rerun_output_merges_with_another_chunk_but_not_with_its_source(self):
        from evaluation.benchmark_v2.automated import runs
        self.failing_run()
        self.rerun("source", "again")
        self.compare("other", documents=["doc-4", "doc-5"])
        merged = runs.merge(self.suite_path, RUBRIC, self.config_path, self.certificate,
                            [self.root / "again", self.root / "other"], self.root / "merged")
        self.assertTrue(merged["complete"])
        self.assertEqual(merged["provenance"]["documents"], ["doc-1", "doc-2", "doc-3", "doc-4", "doc-5"])
        self.assertEqual([entry["rerun_calls"] for entry in merged["provenance"]["merged_from"]], [4, 0])
        with self.assertRaises(ValueError) as caught:
            runs.merge(self.suite_path, RUBRIC, self.config_path, self.certificate,
                       [self.root / "source", self.root / "again"], self.root / "refused")
        self.assertIn("overlap", str(caught.exception))
        self.assertFalse((self.root / "refused").exists())

    def test_rerun_failed_command_prints_the_report(self):
        self.failing_run()
        argv = ["rerun-failed", "--suite", str(self.suite_path), "--rubric", str(RUBRIC),
                "--config", str(self.config_path), "--calibration", str(self.certificate),
                "--from", str(self.root / "source"), "--out", str(self.root / "cli-again")]
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(main(argv), 0)
        report = json.loads(buffer.getvalue())
        self.assertEqual(report["provenance"]["rerun"]["rerun_calls"], 4)
        self.assertTrue(report["complete"])
