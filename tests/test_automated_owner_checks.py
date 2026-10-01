"""Literal checks on owner-session cases are diagnostics, never a veto.

Pure validation and scoring tests: no subprocess, no model call, and only invented text. The fixtures
carry the provenance kind owner_session, but every sentence in them is made up for the test."""

import unittest

from evaluation.benchmark_v2.automated import scoring
from evaluation.benchmark_v2.automated.contracts import validate_suite

JUDGES = [{"id": "j1", "family": "f1"}, {"id": "j2", "family": "f2"}]
CERTIFICATE = {"eligible": True, "execution": "live"}
BASELINE_TEXT = "The deadline is Tuesday."
CANDIDATE_TEXT = "The deadline is Friday."
REQUIRED_TUESDAY = {"required": ["Tuesday"]}
REQUIRED_FRIDAY = {"required": ["Friday"]}


def case(case_id, document_id, kind, lane="editing", checks=None):
    """One compare-ready case: `a` is the baseline text, `b` the candidate text."""
    return {"id": case_id, "document_id": document_id, "split": "test", "lane": lane,
            "prompt": f"Revise document {document_id}", "context": "Context",
            "a": BASELINE_TEXT, "b": CANDIDATE_TEXT, "expected": None,
            "checks": dict(checks or {}),
            "provenance": {"kind": kind, "source": "invented fixture", "license": "CC0-1.0"}}


def suite_of(kind, checks=None, per_lane=5):
    cases = [case(f"{lane}-{i}", f"{lane}-doc-{i}", kind, lane, checks)
             for lane in ("editing", "communication") for i in range(per_lane)]
    return {"schema_version": 1, "name": "owner-checks fixtures", "cases": cases}


def records_for(value, winner):
    """Both judges, both orders, every case, all answering `winner` (canonical: a baseline, b candidate)."""
    return [{"case_id": c["id"], "document_id": c["document_id"], "lane": c["lane"],
             "split": c["split"], "judge_id": j["id"], "family": j["family"], "order": order,
             "valid": True, "winner": winner}
            for c in value["cases"] for j in JUDGES for order in (1, 2)]


def compare_report(value, winner):
    return scoring.build_report(value, records_for(value, winner), JUDGES, mode="compare",
                                calibration=CERTIFICATE)


class OwnerSessionSchemaTests(unittest.TestCase):
    def test_owner_session_kind_is_accepted_with_checks(self):
        value = suite_of("owner_session", REQUIRED_TUESDAY)
        self.assertIs(validate_suite(value), value)

    def test_owner_session_case_cannot_carry_an_expected_winner(self):
        value = suite_of("owner_session")
        value["cases"][0]["expected"] = "b"
        with self.assertRaisesRegex(ValueError, "owner session case cannot have expected winner"):
            validate_suite(value)

    def test_unknown_provenance_kind_is_still_refused(self):
        with self.assertRaisesRegex(ValueError, "invalid provenance kind"):
            validate_suite(suite_of("owner-session"))

    def test_owner_session_still_needs_a_source(self):
        value = suite_of("owner_session")
        value["cases"][0]["provenance"]["source"] = " "
        with self.assertRaisesRegex(ValueError, "source must be nonblank"):
            validate_suite(value)


class LiteralTallyTests(unittest.TestCase):
    def test_owner_session_misses_are_diagnostics_not_failures(self):
        cases = [case("c1", "d1", "owner_session", "editing", REQUIRED_TUESDAY)]
        self.assertEqual(scoring.literal_tallies(cases),
                         (0, 0, [{"document_id": "d1", "lane": "editing",
                                  "candidate_misses": 1, "baseline_misses": 0}]))

    def test_other_provenance_kinds_keep_the_veto(self):
        for kind in ("synthetic_control", "published_reference"):
            cases = [case("c1", "d1", kind, "editing", REQUIRED_TUESDAY)]
            self.assertEqual(scoring.literal_tallies(cases), (1, 0, []), kind)

    def test_mixed_cases_split_the_tallies_by_kind(self):
        cases = [case("c1", "d1", "owner_session", "editing", REQUIRED_TUESDAY),
                 case("c2", "d2", "synthetic_control", "communication", REQUIRED_TUESDAY)]
        self.assertEqual(scoring.literal_tallies(cases),
                         (1, 0, [{"document_id": "d1", "lane": "editing",
                                  "candidate_misses": 1, "baseline_misses": 0}]))

    def test_diagnostics_sum_one_documents_cases_and_sort_by_document(self):
        both_sides = {"required": ["Tuesday", "Friday"]}
        cases = [case("c1", "d2", "owner_session", "editing", both_sides),
                 case("c2", "d1", "owner_session", "editing", REQUIRED_TUESDAY),
                 case("c3", "d2", "owner_session", "editing", both_sides),
                 case("c4", "d3", "owner_session", "editing", {})]
        self.assertEqual(scoring.literal_tallies(cases), (0, 0, [
            {"document_id": "d1", "lane": "editing", "candidate_misses": 1, "baseline_misses": 0},
            {"document_id": "d2", "lane": "editing", "candidate_misses": 2, "baseline_misses": 2}]))


class OwnerSessionReportTests(unittest.TestCase):
    def lane_verdicts(self, report):
        return {lane: entry["recommendation"] for lane, entry in report["by_lane"].items()}

    def test_owner_session_literal_miss_is_a_diagnostic_not_a_veto(self):
        report = compare_report(suite_of("owner_session", REQUIRED_TUESDAY), "b")
        self.assertEqual(report["recommendation"], "candidate")
        self.assertEqual(self.lane_verdicts(report), {"editing": "candidate", "communication": "candidate"})
        self.assertEqual(report["counts"]["candidate_check_failures"], 0)
        self.assertEqual(report["counts"]["candidate_check_diagnostics"], 10)
        self.assertEqual(report["counts"]["baseline_check_diagnostics"], 0)
        self.assertTrue(all(c["passed"] for c in report["checks"]))
        self.assertEqual(len(report["diagnostics"]), 10)
        self.assertEqual(report["diagnostics"][0],
                         {"document_id": "communication-doc-0", "lane": "communication",
                          "candidate_misses": 1, "baseline_misses": 0})

    def test_owner_session_baseline_miss_is_a_diagnostic_too(self):
        report = compare_report(suite_of("owner_session", REQUIRED_FRIDAY), "b")
        self.assertEqual(report["recommendation"], "candidate")
        self.assertEqual(report["counts"]["baseline_check_failures"], 0)
        self.assertEqual(report["counts"]["baseline_check_diagnostics"], 10)
        self.assertEqual(report["counts"]["candidate_check_diagnostics"], 0)
        baseline_check = next(c for c in report["checks"] if c["id"] == "baseline_checks")
        self.assertTrue(baseline_check["passed"])

    def test_owner_session_judgments_decide_a_baseline_recommendation(self):
        report = compare_report(suite_of("owner_session", REQUIRED_FRIDAY), "a")
        self.assertEqual(report["recommendation"], "baseline")
        self.assertEqual(self.lane_verdicts(report), {"editing": "baseline", "communication": "baseline"})
        self.assertEqual(report["counts"]["baseline_check_failures"], 0)

    def test_literal_miss_on_labeled_kinds_still_vetoes(self):
        for kind in ("synthetic_control", "published_reference"):
            report = compare_report(suite_of(kind, REQUIRED_TUESDAY), "b")
            self.assertNotEqual(report["recommendation"], "candidate", kind)
            self.assertEqual(report["counts"]["candidate_check_failures"], 10, kind)
            self.assertEqual([c["id"] for c in report["checks"] if not c["passed"]],
                             ["candidate_checks"], kind)

    def test_reports_without_owner_cases_carry_empty_diagnostics(self):
        report = compare_report(suite_of("synthetic_control"), "b")
        self.assertEqual(report["diagnostics"], [])
        self.assertEqual(report["counts"]["candidate_check_diagnostics"], 0)
        self.assertEqual(report["counts"]["baseline_check_diagnostics"], 0)


if __name__ == "__main__":
    unittest.main()
