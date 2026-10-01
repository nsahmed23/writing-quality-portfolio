"""Export: an allowlisted aggregate of a finished report, safe to publish.

No model is called. One live run is made from an owner_session suite inside a private root, with a planted
string in the case text, in the judge's quotes and in the judge's reasons; the export of its report must not
carry that string, any case, document or cluster id, any prompt or context, or any file path. A second group of
tests feeds hand-built reports that hide private strings in every place the export does not name, and values the
export does name but cannot trust."""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from evaluation.benchmark_v2.automated import runner
from evaluation.benchmark_v2.automated.__main__ import main
from evaluation.benchmark_v2.automated.adapters import canonical_bytes

AUTOMATED = Path(__file__).resolve().parents[1] / "evaluation" / "benchmark_v2" / "automated"
RUBRIC = AUTOMATED / "data" / "rubric.json"
PY = sys.executable
ENV = "WQ_EVAL_PRIVATE_ROOT"
MARK = "OWNERMARK-7Q2X"

# The planted string rides in the prompt, so it is in the writer's text; the judge quotes it and gives it as its reason.
WRITER = '''import json, sys
request = json.load(sys.stdin)
lead = "Brief take on " if "CANDIDATE-MARK" in request["instructions"] else "A rather wordy take on "
print(json.dumps({"text": lead + request["prompt"]}))
'''
JUDGE = '''import json, sys
request = json.load(sys.stdin)
a, b = request["A"], request["B"]
mark = "__MARK__"
winner = "A" if a.startswith("Brief") else "B"
print(json.dumps({"winner": winner, "reason": "preferred because " + mark,
                  "evidence": [{"candidate": "A", "quote": mark}, {"candidate": "B", "quote": mark}]}))
'''


def export():
    """The export module, loaded inside each test so a missing module fails that test and not the whole file."""
    from evaluation.benchmark_v2.automated import export as module
    return module


def suite_dict():
    cases = []
    for n in range(1, 4):
        cases.append({"id": f"case-{n}", "document_id": f"doc-{n}", "split": "test", "lane": "editing",
                      "prompt": f"Revise item {n}. {MARK}", "context": f"Context {n} {MARK}",
                      "a": f"alpha {n} {MARK}", "b": f"beta {n} {MARK}", "expected": None, "checks": {},
                      "cluster_id": f"cluster-{n}",
                      "provenance": {"kind": "owner_session", "source": "owner harvest", "license": "owner"}})
    return {"schema_version": 1, "name": "export-fixture", "cases": cases}


def sha(character):
    return character * 64


LANE_STATISTICS = {"cases": 6, "documents": 5, "decisive": 4, "wins": 3, "losses": 1, "proportion": 0.75,
                   "wilson_lower": 0.3562, "wilson_upper": 0.9421, "mean": 0.5, "sign_test_p": 0.3125,
                   "recommendation": "candidate"}
EMPTY_LANE = {"cases": 0, "documents": 0, "decisive": 0, "wins": 0, "losses": 0, "proportion": None,
              "wilson_lower": 0.0, "wilson_upper": 1.0, "mean": None, "sign_test_p": 1.0,
              "recommendation": "inconclusive"}


def sample_report():
    """A report with every field the export names and, around them, private strings in places it does not name."""
    return {
        "schema_version": 1, "evaluation_type": "automated_proxy", "execution": "live", "mode": "compare",
        "complete": True, "eligible": True, "recommendation": "candidate",
        "metrics": {"calibration_accuracy": 0.95, "note": MARK},
        "checks": [{"id": "coverage", "passed": True, "message": f"all records valid {MARK}"},
                   {"id": "lane_documents_editing", "passed": False, "message": f"case-1 doc-1 {MARK}"},
                   {"id": "calibration_judge_6a31", "passed": True, "message": MARK}],
        "by_judge": {f"judge-{MARK}": {"family": f"family-{MARK}", "controls": 8, "documents": 4,
                                      "complete": True, "eligible": True, "accuracy": 1.0}},
        "by_lane": {"editing": {**LANE_STATISTICS, "quote": MARK, "case_ids": ["case-1"]},
                    "communication": {**EMPTY_LANE},
                    "doc-1": {"cases": 1, "documents": 1, "mean": 1, "recommendation": "candidate"}},
        "counts": {"expected_records": 48, "received_records": 48, "missing_records": 0, "duplicate_records": 0,
                   "invalid_records": 0, "unexpected_records": 0, "plumbing_failures": 1, "judgment_failures": 0,
                   "skipped_records": 0, "skipped_cases": 0, "order_disagreements": 2, "abstentions": 1,
                   "ties": 3, "both_bad": 0, "candidate_check_failures": 0, "baseline_check_failures": 0,
                   "candidate_check_diagnostics": 1, "baseline_check_diagnostics": 0, "case-1": 7, MARK: 9},
        "diagnostics": [{"case_id": "case-1", "document_id": "doc-1", "cluster_id": "cluster-1",
                         "candidate_misses": 1, "baseline_misses": 0, "reason": MARK, "quote": MARK}],
        "provenance": {
            "candidate_skill_sha256": sha("1"), "suite_sha256": sha("2"), "rubric_sha256": sha("3"),
            "config_sha256": sha("4"), "judge_signature": sha("5"),
            "adapter_sha256": {"codex_adapter.py": sha("6"), "generic_json_adapter.py": sha("7"),
                               "prompt_arg_adapter.py": sha("8"), f"{MARK}.py": sha("9")},
            "split": "test", "baseline_skill_sha256": None, "candidate_snapshot_sha256": sha("a"),
            "baseline_snapshot_sha256": None, "certificate_suite_sha256": sha("b"), "repetitions": 1,
            "documents": ["doc-1", f"doc-{MARK}"], "calibration_overlap": {"documents": ["doc-1"]},
            "tool_versions": {"before": {"codex": "codex-cli 0.46.0", "python": "Python 3.11.9"},
                              "after": {"codex": "codex-cli 0.46.0", "python": "Python 3.11.9"}, "changed": []},
            "merged_from": [{"report_sha256": sha("c"), "records_sha256": sha("d"), "rerun_calls": 0,
                             "path": "C:/private/run-1"}],
            "rerun": {"source_report_sha256": sha("e"), "source_records_sha256": sha("f"), "rerun_calls": 2},
            "source_path": "C:/private/suite.json"},
        "artifacts": {"records": "records.json", "calls": "calls"},
    }


EXPECTED = {
    "export_version": 1, "mode": "compare", "execution": "live", "complete": True, "eligible": True,
    "recommendation": "candidate",
    "counts": {"expected_records": 48, "received_records": 48, "missing_records": 0, "duplicate_records": 0,
               "invalid_records": 0, "unexpected_records": 0, "plumbing_failures": 1, "judgment_failures": 0,
               "skipped_records": 0, "skipped_cases": 0, "order_disagreements": 2, "abstentions": 1,
               "ties": 3, "both_bad": 0, "candidate_check_failures": 0, "baseline_check_failures": 0,
               "candidate_check_diagnostics": 1, "baseline_check_diagnostics": 0},
    "by_lane": {"editing": dict(LANE_STATISTICS), "communication": dict(EMPTY_LANE)},
    "checks": [{"name": "coverage", "passed": True}, {"name": "lane_documents_editing", "passed": False},
               {"name": "calibration_judge_6a31", "passed": True}],
    "provenance": {
        "candidate_skill_sha256": sha("1"), "suite_sha256": sha("2"), "rubric_sha256": sha("3"),
        "config_sha256": sha("4"), "judge_signature": sha("5"),
        "baseline_skill_sha256": None, "certificate_suite_sha256": sha("b"),
        "candidate_snapshot_sha256": sha("a"), "baseline_snapshot_sha256": None,
        "adapter_sha256": {"codex_adapter.py": sha("6"), "generic_json_adapter.py": sha("7"),
                           "prompt_arg_adapter.py": sha("8")},
        "tool_versions": {"before": {"codex": "codex-cli 0.46.0", "python": "Python 3.11.9"},
                          "after": {"codex": "codex-cli 0.46.0", "python": "Python 3.11.9"}, "changed": []},
        "merged_from": [{"report_sha256": sha("c"), "records_sha256": sha("d"), "rerun_calls": 0}],
        "rerun": {"source_report_sha256": sha("e"), "source_records_sha256": sha("f"), "rerun_calls": 2}},
}

# Every private string the export must not carry; the end-to-end run adds the temporary folder.
PRIVATE_STRINGS = (MARK, "case-", "doc-", "cluster-", "Revise item", "Context ", "alpha", "beta", "preferred because",
                   "C:/private", "records.json", "artifacts")


def message_of(function, *args):
    with unittest.TestCase().assertRaises(ValueError) as caught:
        function(*args)
    return str(caught.exception)


class AllowlistTests(unittest.TestCase):
    """build_export on hand-built reports."""

    def build(self, report=None):
        return export().build_export(sample_report() if report is None else report)

    def assertRefused(self, path, report):
        with self.assertRaises(ValueError) as caught:
            export().build_export(report)
        self.assertEqual(str(caught.exception), f"report field {path} has an unexpected value")
        self.assertNotIn(MARK, str(caught.exception))

    def test_a_full_report_exports_exactly_the_named_fields_and_nothing_else(self):
        self.assertEqual(self.build(), EXPECTED)

    def test_the_export_carries_no_private_string_in_any_byte(self):
        data = canonical_bytes(self.build())
        for private in PRIVATE_STRINGS:
            self.assertNotIn(private.encode(), data, private)

    def test_the_export_is_built_by_copying_so_a_new_report_field_never_reaches_it(self):
        report = sample_report()
        report["transcript"] = MARK
        report["by_lane"]["editing"]["extra"] = {"text": MARK}
        report["counts"]["extra_count"] = 5
        report["provenance"]["extra"] = MARK
        self.assertEqual(self.build(report), EXPECTED)

    def test_a_calibrate_report_with_no_lanes_or_certificate_exports_what_it_has(self):
        report = {"schema_version": 1, "evaluation_type": "automated_proxy", "execution": "live", "mode": "calibrate",
                  "complete": True, "eligible": False, "recommendation": "not_applicable", "metrics": {}, "checks": [],
                  "by_judge": {}, "by_lane": {}, "counts": {"expected_records": 0}, "diagnostics": [],
                  "provenance": {"candidate_skill_sha256": None, "suite_sha256": sha("2")}}
        self.assertEqual(self.build(report), {
            "export_version": 1, "mode": "calibrate", "execution": "live", "complete": True, "eligible": False,
            "recommendation": "not_applicable", "counts": {"expected_records": 0}, "by_lane": {}, "checks": [],
            "provenance": {"candidate_skill_sha256": None, "suite_sha256": sha("2")}})

    def test_the_export_does_not_change_the_report(self):
        report = sample_report()
        before = canonical_bytes(report)
        self.build(report)
        self.assertEqual(canonical_bytes(report), before)

    def test_a_report_that_is_not_an_automated_proxy_report_is_refused(self):
        for report in ([], "text", None, {"schema_version": 1}, {**sample_report(), "evaluation_type": "other"},
                       {**sample_report(), "schema_version": 2}):
            with self.subTest(report=type(report).__name__):
                self.assertIn(message_of(export().build_export, report),
                              ("report is not a JSON object", "report is not an automated proxy report"))

    def test_a_value_the_export_names_but_cannot_trust_is_refused_by_field_name(self):
        cases = {
            "mode": ("mode", MARK), "execution": ("execution", MARK), "recommendation": ("recommendation", MARK),
            "complete": ("complete", "yes"), "eligible": ("eligible", 1),
        }
        for path, (name, value) in cases.items():
            with self.subTest(path):
                report = sample_report()
                report[name] = value
                self.assertRefused(path, report)

    def test_a_count_must_be_a_nonnegative_integer(self):
        for value in (MARK, -1, 1.5, True, None, [1]):
            with self.subTest(value=repr(value)):
                report = sample_report()
                report["counts"]["ties"] = value
                self.assertRefused("counts.ties", report)
        report = sample_report()
        report["counts"] = [1]
        self.assertRefused("counts", report)

    def test_a_lane_entry_must_be_well_formed(self):
        for name, value in (("documents", MARK), ("cases", -2), ("decisive", 1.5), ("wins", -1), ("losses", True),
                            ("mean", MARK), ("mean", True), ("proportion", "x"), ("wilson_lower", "x"),
                            ("wilson_upper", float("nan")), ("sign_test_p", MARK), ("recommendation", MARK)):
            with self.subTest(name=name, value=repr(value)):
                report = sample_report()
                report["by_lane"]["editing"][name] = value
                self.assertRefused(f"by_lane.editing.{name}", report)
        report = sample_report()
        report["by_lane"]["editing"] = MARK
        self.assertRefused("by_lane.editing", report)
        report = sample_report()
        report["by_lane"] = [MARK]
        self.assertRefused("by_lane", report)

    def test_a_check_must_have_a_plain_name_and_a_boolean_flag(self):
        for position, change in ((0, {"id": MARK}), (1, {"id": "has space"}), (2, {"id": 7}), (0, {"id": ""}),
                                 (1, {"passed": "true"}), (2, {"passed": None})):
            with self.subTest(position=position, change=repr(change)):
                report = sample_report()
                report["checks"][position].update(change)
                path = f"checks[{position}].passed" if "passed" in change else f"checks[{position}]"
                self.assertRefused(path, report)
        report = sample_report()
        report["checks"] = {"coverage": True}
        self.assertRefused("checks", report)
        report = sample_report()
        report["checks"][0] = "coverage"
        self.assertRefused("checks[0]", report)

    def test_a_hash_must_be_64_lowercase_hex_digits_or_null(self):
        for value in (MARK, "A" * 64, "a" * 63, "g" * 64, 5, ["a" * 64]):
            with self.subTest(value=repr(value)):
                report = sample_report()
                report["provenance"]["suite_sha256"] = value
                self.assertRefused("provenance.suite_sha256", report)
        report = sample_report()
        report["provenance"]["adapter_sha256"]["codex_adapter.py"] = MARK
        self.assertRefused("provenance.adapter_sha256.codex_adapter.py", report)
        report = sample_report()
        report["provenance"]["merged_from"][0]["report_sha256"] = MARK
        self.assertRefused("provenance.merged_from[0].report_sha256", report)
        report = sample_report()
        report["provenance"]["rerun"]["source_records_sha256"] = MARK
        self.assertRefused("provenance.rerun.source_records_sha256", report)

    def test_tool_versions_must_be_plain_names_and_plain_version_text(self):
        for before, after, changed in (({"codex": MARK + "/x"}, {}, []), ({"bad name": "1.0"}, {}, []),
                                       ({"codex": "1.0"}, {"codex": 7}, []), ({"codex": "line\nbreak"}, {}, []),
                                       ({"codex": "1.0"}, {}, [MARK + " x"]), ({"codex": "a" * 101}, {}, [])):
            with self.subTest(before=before, after=after, changed=changed):
                report = sample_report()
                report["provenance"]["tool_versions"] = {"before": before, "after": after, "changed": changed}
                self.assertRefused("provenance.tool_versions", report)

    def test_a_tool_that_could_not_be_read_after_the_run_exports_as_null(self):
        report = sample_report()
        report["provenance"]["tool_versions"] = {"before": {"codex": "1.0"}, "after": {"codex": None}, "changed": ["codex"]}
        self.assertEqual(self.build(report)["provenance"]["tool_versions"],
                         {"before": {"codex": "1.0"}, "after": {"codex": None}, "changed": ["codex"]})


class CommandTests(unittest.TestCase):
    """export_report and the export command, on a report file."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.report = self.root / "report.json"
        self.report.write_bytes(canonical_bytes(sample_report()) + b"\n")

    def run_cli(self, argv):
        stdout, stderr = io.StringIO(), io.StringIO()
        code = None
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                code = main(argv)
            except SystemExit as exc:
                code = exc.code
        return code, stdout.getvalue(), stderr.getvalue()

    def test_export_report_writes_the_allowlisted_json_with_a_newline(self):
        out = self.root / "export.json"
        result = export().export_report(self.report, out)
        self.assertEqual(result, EXPECTED)
        self.assertEqual(out.read_bytes(), canonical_bytes(EXPECTED) + b"\n")

    def test_export_report_never_overwrites_a_file(self):
        out = self.root / "export.json"
        out.write_bytes(b"keep")
        with self.assertRaises(FileExistsError):
            export().export_report(self.report, out)
        self.assertEqual(out.read_bytes(), b"keep")

    def test_a_refused_report_leaves_no_output_file(self):
        bad = sample_report()
        bad["counts"]["ties"] = MARK
        self.report.write_bytes(canonical_bytes(bad))
        out = self.root / "export.json"
        with self.assertRaises(ValueError):
            export().export_report(self.report, out)
        self.assertFalse(out.exists())

    def test_a_report_that_is_not_json_is_refused_without_echoing_its_text(self):
        self.report.write_bytes(("{not json " + MARK).encode())
        with self.assertRaises(ValueError) as caught:
            export().export_report(self.report, self.root / "export.json")
        self.assertNotIn(MARK, str(caught.exception))

    def test_the_command_prints_the_export_and_writes_the_file(self):
        out = self.root / "export.json"
        code, stdout, stderr = self.run_cli(["export", "--report", str(self.report), "--out", str(out)])
        self.assertEqual((code, stderr), (0, ""))
        self.assertEqual(json.loads(stdout), EXPECTED)
        self.assertEqual(json.loads(out.read_bytes()), EXPECTED)

    def test_the_command_refuses_a_bad_report_with_exit_code_2_and_no_private_text(self):
        bad = sample_report()
        bad["recommendation"] = MARK
        self.report.write_bytes(canonical_bytes(bad))
        out = self.root / "export.json"
        code, stdout, stderr = self.run_cli(["export", "--report", str(self.report), "--out", str(out)])
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "error: report field recommendation has an unexpected value\n")
        self.assertFalse(out.exists())

    def test_the_export_is_public_so_it_is_not_held_to_the_private_root(self):
        with mock.patch.dict(os.environ):
            os.environ.pop(ENV, None)
            code, _, _ = self.run_cli(["export", "--report", str(self.report), "--out", str(self.root / "public.json")])
        self.assertEqual(code, 0)


class EndToEndTests(unittest.TestCase):
    """A real compare run on an owner_session suite, inside a private root, exported."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name).resolve()
        cls.private = cls.root / "private"
        cls.private.mkdir()
        (cls.root / "writer.py").write_text(WRITER, encoding="utf-8")
        (cls.root / "judge.py").write_text(JUDGE.replace("__MARK__", MARK), encoding="utf-8")
        config = {"schema_version": 1,
                  "judges": [{"id": "j1", "family": "f1", "command": [PY, str(cls.root / "judge.py")]},
                             {"id": "j2", "family": "f2", "command": [PY, str(cls.root / "judge.py")]}],
                  "writer": {"id": "w", "family": "fw", "command": [PY, str(cls.root / "writer.py")]},
                  "version_commands": {"python": [PY, "--version"]}}
        config_path = cls.root / "config.json"
        config_path.write_bytes(canonical_bytes(config))
        suite_path = cls.root / "suite.json"
        suite_path.write_bytes(canonical_bytes(suite_dict()))
        candidate = cls.root / "candidate.md"
        candidate.write_bytes(b"# Candidate\nCANDIDATE-MARK\nWrite briefly.\n")
        from evaluation.benchmark_v2.automated.adapters import load_config
        certificate = cls.root / "certificate"
        certificate.mkdir()
        (certificate / "report.json").write_bytes(canonical_bytes({
            "schema_version": 1, "evaluation_type": "automated_proxy", "execution": "live", "mode": "calibrate",
            "complete": True, "eligible": True,
            "provenance": runner._provenance(suite_path, RUBRIC, config_path, load_config(config_path))}))
        cls.run_folder = cls.private / "run"
        with mock.patch.dict(os.environ, {ENV: str(cls.private)}):
            runner.compare(suite_path, RUBRIC, config_path, certificate, candidate, cls.run_folder)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_private_run_really_holds_the_planted_string(self):
        # The cases carry it in generated.json; the judge's quotes and reasons stay in the call folders.
        holders = {path.relative_to(self.run_folder).parts[0] for path in self.run_folder.rglob("*")
                   if path.is_file() and MARK.encode() in path.read_bytes()}
        self.assertIn("generated.json", holders)
        self.assertIn("calls", holders)

    def test_the_export_of_that_run_carries_none_of_it(self):
        out = self.root / "export.json"
        result = export().export_report(self.run_folder / "report.json", out)
        data = out.read_bytes()
        for private in (*PRIVATE_STRINGS, str(self.root), str(self.private), self.root.name):
            self.assertNotIn(private.encode(), data, private)
            self.assertNotIn(private.replace("\\", "\\\\").encode(), data, private)
        self.assertEqual(result["by_lane"]["editing"]["documents"], 3)
        self.assertEqual(result["mode"], "compare")
        self.assertEqual(result["counts"]["expected_records"], 12 * 1)
        self.assertTrue(all(set(check) == {"name", "passed"} for check in result["checks"]))
        self.assertIn("tool_versions_stable", [check["name"] for check in result["checks"]])
        report = json.loads((self.run_folder / "report.json").read_bytes())
        self.assertEqual(result["provenance"]["suite_sha256"], report["provenance"]["suite_sha256"])
        self.assertEqual(result["provenance"]["tool_versions"], report["provenance"]["tool_versions"])
        self.assertEqual(result["recommendation"], report["recommendation"])


if __name__ == "__main__":
    unittest.main()
