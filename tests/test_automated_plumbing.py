"""Failure kinds, the judge-command size pre-check, and the report counts that separate them.

No model is called. Judges are stand-in scripts run by the real runner; the size check is compared with
the real prompt_arg_adapter.py, which refuses an oversized command line before it touches git or a model CLI."""

import importlib.util
import re
import sys
import tempfile
import unittest
from pathlib import Path

from evaluation.benchmark_v2.automated import runner
from evaluation.benchmark_v2.automated.adapters import Budget, run_call
from evaluation.benchmark_v2.automated.scoring import build_report

AUTOMATED = Path(__file__).resolve().parents[1] / "evaluation" / "benchmark_v2" / "automated"
REAL_ARG_ADAPTER = AUTOMATED / "adapters" / "prompt_arg_adapter.py"
REAL_BUILDER = AUTOMATED / "adapters" / "generic_json_adapter.py"
REQUEST = {"role": "judge", "request_id": "opaque", "prompt": "inspect", "context": "", "rubric": [],
           "A": "alpha", "B": "beta"}
RUBRIC = {"schema_version": 1, "id": "r", "criteria": [{"id": "meaning", "description": "Preserve the meaning."}]}
JUDGES = [{"id": "j1", "family": "f1"}, {"id": "j2", "family": "f2"}]
FAMILY = {"j1": "f1", "j2": "f2"}
CERT = {"eligible": True, "execution": "live"}

# A stand-in judge. The context prefix chooses its behavior: "exit" stops with status 3, "prose" answers
# without JSON, anything else picks the text that starts with "beta" and quotes the start of both texts.
FAKE_JUDGE = '''import json, sys
request = json.load(sys.stdin)
context = request["context"]
if context.startswith("exit"):
    sys.exit(3)
if context.startswith("prose"):
    print("I prefer the second one.")
    sys.exit(0)
a, b = request["A"], request["B"]
winner = "A" if a.startswith("beta") else "B"
print(json.dumps({"winner": winner, "reason": "because",
                  "evidence": [{"candidate": "A", "quote": a[:5]}, {"candidate": "B", "quote": b[:5]}]}))
'''


def load_real_adapter():
    """Load prompt_arg_adapter.py by path. The script adds its own folder to sys.path while it imports."""
    saved = list(sys.path)
    spec = importlib.util.spec_from_file_location("wq_test_real_prompt_arg_adapter", REAL_ARG_ADAPTER)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = saved
        sys.modules.pop("generic_json_adapter", None)
    return module


def load_builder():
    spec = importlib.util.spec_from_file_location("wq_test_real_builder", REAL_BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def case(n, *, a="alpha", b="beta", split="test", lane="editing", context=None, expected=None):
    return {"id": f"c{n}", "document_id": f"d{n}", "split": split, "lane": lane, "prompt": "inspect",
            "context": context if context is not None else f"case {n}", "a": a, "b": b, "expected": expected,
            "checks": {}, "provenance": {"kind": "synthetic_control", "source": "test fixture", "license": "CC0"}}


def suite_of(cases):
    return {"schema_version": 1, "name": "t", "cases": cases}


def record(c, judge, order, *, valid=True, kind=None, error=None):
    out = {"case_id": c["id"], "document_id": c["document_id"], "lane": c["lane"], "split": c["split"],
           "judge_id": judge, "family": FAMILY[judge], "order": order, "valid": valid,
           "winner": "b" if valid else None}
    if kind:
        out["failure_kind"] = kind
    if error:
        out["error"] = error
    return out


def make_records(cases, special=None):
    """One record per (case, judge, order); `special` maps (case id, judge, order) to record() keywords."""
    special = special or {}
    return [record(c, judge, order, **special.get((c["id"], judge, order), {}))
            for c in cases for judge in ("j1", "j2") for order in (1, 2)]


def skip_all(case_id):
    return {(case_id, j, o): {"valid": False, "kind": "skipped", "error": "oversized_prompt: test"}
            for j in ("j1", "j2") for o in (1, 2)}


def compare_report(cases, records):
    return build_report(suite_of(cases), records, JUDGES, mode="compare", calibration=CERT, seed=7)


class UnitCountTests(unittest.TestCase):
    def test_units_counts_utf16_code_units(self):
        self.assertEqual(runner._units(["ab", "cd"]), 5)

    def test_astral_characters_count_two_units(self):
        self.assertEqual(runner._units(["a", chr(0x1F600)]), 4)

    def test_units_quotes_an_argument_with_spaces(self):
        self.assertEqual(runner._units(["a b"]), 5)

    def test_a_lone_surrogate_counts_one_unit_instead_of_raising(self):
        # The real adapter refuses such a prompt itself (exit 2); the pre-check must not crash the run first.
        self.assertEqual(runner._units(["a", chr(0xD800)]), 3)

    def test_limit_and_unit_count_match_the_real_adapter(self):
        module = load_real_adapter()
        self.assertEqual(runner.MAX_COMMAND_LINE_UNITS, module.MAX_COMMAND_LINE_UNITS)
        for command in (["agy", "-p", "x"], ["a b", chr(0x1F600)], ["q", 'say "hi"']):
            self.assertEqual(runner._units(command), module.command_line_units(command))


class CommandUnitsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def adapter_folder(self, name, with_builder=True):
        """A folder shaped like adapters/: a stand-in prompt_arg_adapter.py and, optionally, the real builder."""
        folder = self.root / name
        folder.mkdir()
        (folder / "prompt_arg_adapter.py").write_text("# stand-in\n", encoding="utf-8")
        if with_builder:
            (folder / "generic_json_adapter.py").write_bytes(REAL_BUILDER.read_bytes())
        return folder

    def test_a_stdin_judge_has_no_command_line_to_measure(self):
        command = [sys.executable, str(self.root / "judge.py")]
        self.assertIsNone(runner._command_units(command, REQUEST))

    def test_an_argument_judge_is_measured_with_the_builder_beside_the_adapter(self):
        folder = self.adapter_folder("good")
        command = [sys.executable, str(folder / "prompt_arg_adapter.py"), "--", "agy", "--model", "m"]
        expected = load_real_adapter().command_line_units(
            ["agy", "--model", "m", "-p", load_builder().build_prompt(REQUEST)])
        self.assertEqual(runner._command_units(command, REQUEST), expected)

    def test_a_missing_builder_fails_open(self):
        folder = self.adapter_folder("nobuilder", with_builder=False)
        command = [sys.executable, str(folder / "prompt_arg_adapter.py"), "--", "agy"]
        self.assertIsNone(runner._command_units(command, REQUEST))

    def test_nothing_after_the_adapter_fails_open(self):
        folder = self.adapter_folder("bare")
        command = [sys.executable, str(folder / "prompt_arg_adapter.py"), "--"]
        self.assertIsNone(runner._command_units(command, REQUEST))

    def test_precheck_measures_what_the_real_adapter_refuses(self):
        request = dict(REQUEST, A="alpha " + "x" * 40000)
        command = [sys.executable, str(REAL_ARG_ADAPTER), "--", "agy"]
        measured = runner._command_units(command, request)
        result = run_call(command, request, self.root / "real-call", timeout_seconds=60)
        self.assertFalse(result["ok"])
        self.assertEqual(result["returncode"], 2)
        stderr = result["stderr"].decode("utf-8", "replace")
        found = re.search(r"makes a command line of (\d+) UTF-16 units", stderr)
        self.assertIsNotNone(found, stderr)
        self.assertEqual(measured, int(found.group(1)))

    def test_the_count_grows_one_unit_per_character(self):
        folder = self.adapter_folder("edge")
        command = [sys.executable, str(folder / "prompt_arg_adapter.py"), "--", "agy"]
        base = runner._command_units(command, dict(REQUEST, A=""))
        self.assertEqual(runner._command_units(command, dict(REQUEST, A="x" * 100)), base + 100)

    def test_oversized_units_is_none_at_the_limit_and_the_count_just_above_it(self):
        folder = self.adapter_folder("limit")
        command = [sys.executable, str(folder / "prompt_arg_adapter.py"), "--", "agy"]
        judge = {"id": "j", "family": "f", "command": command}
        config = {"judges": [judge]}

        def case_with(n):
            return {"id": "c1", "prompt": "p", "context": "c", "a": "x" * n, "b": "y"}

        limit = runner.MAX_COMMAND_LINE_UNITS
        base = runner._command_units(command, runner._judge_request(case_with(0), judge, 1, RUBRIC))
        self.assertIsNone(runner._oversized_units(case_with(limit - base), RUBRIC, config))
        self.assertEqual(runner._oversized_units(case_with(limit - base + 1), RUBRIC, config), limit + 1)


class JudgeCasesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.stdin_judge = self.root / "judge.py"
        self.stdin_judge.write_text(FAKE_JUDGE, encoding="utf-8")
        # An argument-transport judge: the stand-in sits where the runner looks for prompt_arg_adapter.py,
        # next to a byte copy of the real prompt builder the pre-check imports.
        folder = self.root / "adapters"
        folder.mkdir()
        self.fake_adapter = folder / "prompt_arg_adapter.py"
        self.fake_adapter.write_text(FAKE_JUDGE, encoding="utf-8")
        (folder / "generic_json_adapter.py").write_bytes(REAL_BUILDER.read_bytes())
        self.out = self.root / "out"
        (self.out / "calls").mkdir(parents=True)

    def argument_judge(self, judge_id="gem", family="f1"):
        return {"id": judge_id, "family": family, "command": [sys.executable, str(self.fake_adapter), "--", "agy"]}

    def stdin_judge_entry(self, judge_id="sol", family="f2"):
        return {"id": judge_id, "family": family, "command": [sys.executable, str(self.stdin_judge)]}

    def test_oversized_pair_is_skipped_and_run_stays_complete(self):
        cases = [case(1), case(2), case(3, a="alpha " + "x" * 40000)]
        judges = [self.argument_judge(), self.stdin_judge_entry()]
        config = {"judges": judges, "timeout_seconds": 60}
        budget = Budget(100)
        records = runner._judge_cases(cases, RUBRIC, config, self.out, budget)
        self.assertEqual(budget.used, 8)
        self.assertEqual(len(records), 12)
        skipped = [r for r in records if r.get("failure_kind") == "skipped"]
        self.assertEqual({r["case_id"] for r in skipped}, {"c3"})
        self.assertEqual({(r["judge_id"], r["order"]) for r in skipped},
                         {("gem", 1), ("gem", 2), ("sol", 1), ("sol", 2)})
        for r in skipped:
            self.assertFalse(r["valid"])
            self.assertIsNone(r["winner"])
            self.assertTrue(r["error"].startswith("oversized_prompt: a judge command line of "), r["error"])
        self.assertEqual(sorted(p.name for p in (self.out / "calls").iterdir()),
                         [f"{n:05d}" for n in range(1, 9)])
        report = build_report(suite_of(cases), records, [{"id": "gem", "family": "f1"}, {"id": "sol", "family": "f2"}],
                              mode="compare", calibration=CERT, seed=7)
        self.assertTrue(report["complete"])
        self.assertEqual(report["counts"]["skipped_cases"], 1)
        self.assertEqual(report["counts"]["skipped_records"], 4)
        self.assertEqual(report["counts"]["invalid_records"], 0)

    def test_a_stdin_judge_never_skips_a_long_pair(self):
        cases = [case(1, a="alpha " + "x" * 40000)]
        config = {"judges": [self.stdin_judge_entry("s1", "f1"), self.stdin_judge_entry("s2", "f2")],
                  "timeout_seconds": 60}
        budget = Budget(100)
        records = runner._judge_cases(cases, RUBRIC, config, self.out, budget)
        self.assertEqual(budget.used, 4)
        self.assertEqual(len(records), 4)
        for r in records:
            self.assertTrue(r["valid"], r)
            self.assertNotIn("failure_kind", r)

    def test_failure_kinds_are_recorded(self):
        cases = [case(1, context="exit please"), case(2, context="prose please"), case(3)]
        config = {"judges": [self.stdin_judge_entry()], "timeout_seconds": 60}
        records = runner._judge_cases(cases, RUBRIC, config, self.out, Budget(100))
        by_case = {}
        for r in records:
            by_case.setdefault(r["case_id"], []).append(r)
        for r in by_case["c1"]:
            self.assertEqual((r["valid"], r["failure_kind"], r["error"]), (False, "plumbing", "process_exit_3"))
        for r in by_case["c2"]:
            self.assertEqual((r["valid"], r["failure_kind"]), (False, "judgment"))
            self.assertTrue(r["error"])
        for r in by_case["c3"]:
            self.assertTrue(r["valid"])
            self.assertNotIn("failure_kind", r)
            self.assertNotIn("error", r)

    def test_a_launch_error_is_a_plumbing_failure(self):
        judge = {"id": "j", "family": "f", "command": [str(self.root / "no-such-program")]}
        records = runner._judge_cases([case(1)], RUBRIC, {"judges": [judge], "timeout_seconds": 30}, self.out, Budget(10))
        self.assertEqual([r["failure_kind"] for r in records], ["plumbing", "plumbing"])
        for r in records:
            self.assertTrue(r["error"].startswith("launch_error"), r["error"])


class ReportFailureKindTests(unittest.TestCase):
    def test_counts_separate_plumbing_judgment_and_legacy_failures(self):
        cases = [case(i) for i in range(1, 4)]
        special = {("c1", "j1", 1): {"valid": False, "kind": "plumbing", "error": "timeout"},
                   ("c2", "j1", 1): {"valid": False, "kind": "judgment", "error": "evidence must be nonempty"},
                   ("c3", "j1", 1): {"valid": False, "error": "written before failure kinds existed"}}
        counts = compare_report(cases, make_records(cases, special))["counts"]
        self.assertEqual((counts["plumbing_failures"], counts["judgment_failures"]), (1, 2))
        self.assertEqual((counts["invalid_records"], counts["missing_records"]), (3, 0))

    def test_a_malformed_record_counts_as_invalid_only(self):
        cases = [case(i) for i in range(1, 4)]
        records = make_records(cases)
        records[0] = dict(records[0], document_id="wrong")
        counts = compare_report(cases, records)["counts"]
        self.assertEqual((counts["invalid_records"], counts["plumbing_failures"], counts["judgment_failures"]), (1, 0, 0))
        self.assertEqual(counts["missing_records"], 1)

    def test_a_skipped_case_leaves_the_scored_set(self):
        cases = [case(i) for i in range(1, 7)]
        report = compare_report(cases, make_records(cases, skip_all("c6")))
        counts = report["counts"]
        self.assertTrue(report["complete"])
        self.assertEqual((counts["expected_records"], counts["received_records"]), (20, 24))
        self.assertEqual((counts["skipped_records"], counts["skipped_cases"]), (4, 1))
        self.assertEqual((counts["invalid_records"], counts["unexpected_records"]), (0, 0))
        self.assertTrue(report["eligible"])
        self.assertEqual(report["recommendation"], "candidate")

    def test_a_judged_record_for_a_skipped_case_is_unexpected(self):
        cases = [case(i) for i in range(1, 7)]
        special = skip_all("c6")
        del special[("c6", "j2", 2)]
        counts = compare_report(cases, make_records(cases, special))["counts"]
        self.assertEqual((counts["skipped_records"], counts["unexpected_records"]), (3, 1))
        self.assertFalse(compare_report(cases, make_records(cases, special))["complete"])

    def test_a_skip_record_for_an_unknown_case_is_unexpected(self):
        cases = [case(i) for i in range(1, 4)]
        records = make_records(cases) + [record(case(99), "j1", 1, valid=False, kind="skipped", error="oversized_prompt: test")]
        report = compare_report(cases, records)
        self.assertEqual((report["counts"]["skipped_records"], report["counts"]["unexpected_records"]), (0, 1))
        self.assertFalse(report["complete"])

    def test_a_run_whose_cases_are_all_skipped_stays_complete_and_counts_the_skips(self):
        cases = [case(1), case(2)]
        special = {**skip_all("c1"), **skip_all("c2")}
        report = compare_report(cases, make_records(cases, special))
        counts = report["counts"]
        self.assertTrue(report["complete"])
        self.assertEqual((counts["skipped_cases"], counts["skipped_records"]), (2, 8))
        self.assertEqual((counts["expected_records"], counts["received_records"]), (0, 8))
        self.assertEqual((counts["invalid_records"], counts["unexpected_records"], counts["missing_records"]), (0, 0, 0))
        coverage = [c for c in report["checks"] if c["id"] == "coverage"]
        self.assertEqual([c["passed"] for c in coverage], [True])
        # Nothing was scored, so the run can never be eligible or recommend either side.
        self.assertFalse(report["eligible"])
        self.assertEqual(report["recommendation"], "inconclusive")

    def test_all_skipped_with_one_stray_judged_record_is_still_incomplete(self):
        cases = [case(1), case(2)]
        special = {**skip_all("c1"), **skip_all("c2")}
        del special[("c2", "j2", 2)]
        report = compare_report(cases, make_records(cases, special))
        self.assertEqual(report["counts"]["unexpected_records"], 1)
        self.assertFalse(report["complete"])

    def test_an_empty_split_is_still_refused(self):
        with self.assertRaises(ValueError) as caught:
            compare_report([case(1, split="calibration")], [])
        self.assertEqual(str(caught.exception), "compare requires test cases")

    def test_a_lane_with_only_skipped_cases_blocks_eligibility(self):
        cases = [case(i) for i in range(1, 6)] + [case(6, lane="communication")]
        report = compare_report(cases, make_records(cases, skip_all("c6")))
        self.assertEqual(report["by_lane"]["editing"]["recommendation"], "candidate")
        self.assertEqual(report["by_lane"]["communication"]["documents"], 0)
        failed = [c["id"] for c in report["checks"] if not c["passed"]]
        self.assertIn("lane_documents_communication", failed)
        self.assertFalse(report["eligible"])
        self.assertEqual(report["recommendation"], "inconclusive")

    def test_calibrate_mode_drops_a_skipped_control_and_needs_eight(self):
        controls = [case(i, split="calibration", expected="b") for i in range(1, 9)]
        full = build_report(suite_of(controls), make_records(controls), JUDGES, mode="calibrate")
        self.assertTrue(full["eligible"])
        cut = build_report(suite_of(controls), make_records(controls, skip_all("c8")), JUDGES, mode="calibrate")
        self.assertTrue(cut["complete"])
        self.assertEqual(cut["counts"]["skipped_cases"], 1)
        self.assertFalse(cut["eligible"])


if __name__ == "__main__":
    unittest.main()
