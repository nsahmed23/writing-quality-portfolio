"""Suite contract tests: splits, clusters and report split selection. No model calls."""

import unittest
from pathlib import Path

from evaluation.benchmark_v2.automated import contracts
from evaluation.benchmark_v2.automated.contracts import validate_suite
from evaluation.benchmark_v2.automated.scoring import build_report

JUDGES = [{"id": "j1", "family": "f1"}, {"id": "j2", "family": "f2"}]
NO_CLUSTER = object()


def make_case(case_id, doc, split="test", cluster=NO_CLUSTER, text_key=None):
    key = text_key or doc
    value = {
        "id": case_id,
        "document_id": doc,
        "split": split,
        "lane": "editing",
        "prompt": f"Revise the notice for {key}.",
        "context": f"Context for {key}.",
        "a": f"First draft for {key}.",
        "b": f"Second draft for {key}.",
        "expected": None,
        "checks": {},
        "provenance": {"kind": "synthetic_control", "source": "unit test", "license": "CC0-1.0"},
    }
    if cluster is not NO_CLUSTER:
        value["cluster_id"] = cluster
    return value


def make_suite(*cases):
    return {"schema_version": 1, "name": "unit", "cases": list(cases)}


class ClusterFieldTests(unittest.TestCase):
    def test_cluster_id_is_optional(self):
        validate_suite(make_suite(make_case("c1", "d1")))

    def test_cluster_id_accepts_a_nonblank_string(self):
        validate_suite(make_suite(make_case("c1", "d1", cluster="thread-a")))

    def test_cluster_id_rejects_null_blank_and_non_string(self):
        for bad in (None, "", "   ", 7):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "cluster_id"):
                    validate_suite(make_suite(make_case("c1", "d1", cluster=bad)))

    def test_one_document_cannot_sit_in_two_clusters(self):
        suite = make_suite(make_case("c1", "d1", cluster="a"), make_case("c2", "d1", cluster="b"))
        with self.assertRaisesRegex(ValueError, "document assigned to more than one cluster"):
            validate_suite(suite)

    def test_a_document_is_clustered_in_every_case_or_in_none(self):
        clustered_first = make_suite(make_case("c1", "d1", cluster="a"), make_case("c2", "d1"))
        unclustered_first = make_suite(make_case("c1", "d1"), make_case("c2", "d1", cluster="a"))
        for label, suite in (("clustered first", clustered_first), ("unclustered first", unclustered_first)):
            with self.subTest(label):
                with self.assertRaisesRegex(ValueError, "more than one cluster"):
                    validate_suite(suite)

    def test_a_cluster_cannot_span_splits(self):
        suite = make_suite(make_case("c1", "d1", split="calibration", cluster="a"),
                           make_case("c2", "d2", split="test", cluster="a"))
        with self.assertRaisesRegex(ValueError, "cluster spans splits"):
            validate_suite(suite)

    def test_repetitions_and_sibling_documents_in_one_cluster_are_valid(self):
        validate_suite(make_suite(make_case("c1", "d1", cluster="a"),
                                  make_case("c2", "d1", cluster="a"),
                                  make_case("c3", "d2", cluster="a")))

    def test_earlier_leak_checks_still_fire(self):
        reused = make_suite(make_case("c1", "d1", split="calibration"), make_case("c2", "d1", split="test"))
        with self.assertRaisesRegex(ValueError, "document reused across splits"):
            validate_suite(reused)
        copied = make_suite(make_case("c1", "d1"), make_case("c2", "d2", text_key="d1"))
        with self.assertRaisesRegex(ValueError, "copied pair assigned to another document id"):
            validate_suite(copied)

    def test_unknown_case_fields_are_still_rejected(self):
        case = make_case("c1", "d1")
        case["cluster"] = "a"
        with self.assertRaisesRegex(ValueError, "invalid case fields"):
            validate_suite(make_suite(case))


class FingerprintTests(unittest.TestCase):
    def test_fingerprint_ignores_presentation_order_whitespace_and_unicode_form(self):
        first = make_case("c1", "d1")
        first["a"], first["b"] = "caf\u00e9 note", "plain"
        second = make_case("c2", "d2")
        second["prompt"] = "  " + first["prompt"].replace(" ", "  ") + " "
        second["context"] = first["context"]
        second["a"], second["b"] = "plain", "cafe\u0301 note"
        self.assertEqual(contracts.case_fingerprint(first), contracts.case_fingerprint(second))


class SplitConstantTests(unittest.TestCase):
    def test_splits_are_the_three_documented_names(self):
        self.assertEqual(contracts.SPLITS, ("calibration", "development", "test"))


def split_suite():
    calibration = make_case("cal1", "dc1", split="calibration")
    calibration["expected"] = "b"
    return make_suite(
        calibration,
        make_case("dev1", "dd1", split="development"),
        make_case("dev2", "dd2", split="development"),
        make_case("tst1", "dt1", split="test"),
        make_case("tst2", "dt2", split="test"),
        make_case("tst3", "dt3", split="test"),
    )


class SplitSelectionTests(unittest.TestCase):
    def expected_records(self, **kwargs):
        report = build_report(split_suite(), [], JUDGES, mode="compare", **kwargs)
        return report["counts"]["expected_records"]

    def test_compare_defaults_to_the_test_split(self):
        self.assertEqual(self.expected_records(), 12)

    def test_compare_can_score_the_development_split(self):
        self.assertEqual(self.expected_records(split="development"), 8)

    def test_compare_can_score_the_calibration_split(self):
        self.assertEqual(self.expected_records(split="calibration"), 4)

    def test_unknown_split_is_refused(self):
        with self.assertRaisesRegex(ValueError, "invalid split"):
            self.expected_records(split="holdout")

    def test_calibrate_scores_only_the_calibration_split(self):
        report = build_report(split_suite(), [], JUDGES, mode="calibrate")
        self.assertEqual(report["counts"]["expected_records"], 4)
        with self.assertRaisesRegex(ValueError, "calibrate scores the calibration split"):
            build_report(split_suite(), [], JUDGES, mode="calibrate", split="test")

    def test_compare_refuses_a_split_with_no_cases_and_names_the_split(self):
        suite = make_suite(make_case("tst1", "dt1", split="test"))
        with self.assertRaisesRegex(ValueError, "compare requires development cases"):
            build_report(suite, [], JUDGES, mode="compare", split="development")
        with self.assertRaisesRegex(ValueError, "compare requires calibration cases"):
            build_report(suite, [], JUDGES, mode="compare", split="calibration")

    def test_calibrate_refuses_a_calibration_split_with_no_labeled_cases(self):
        unlabeled = make_suite(make_case("cal1", "dc1", split="calibration"))
        with self.assertRaisesRegex(ValueError, "calibrate requires labeled calibration cases"):
            build_report(unlabeled, [], JUDGES, mode="calibrate")
        with self.assertRaisesRegex(ValueError, "calibrate requires labeled calibration cases"):
            build_report(make_suite(make_case("tst1", "dt1", split="test")), [], JUDGES, mode="calibrate")

    def test_score_mode_still_falls_back_to_every_case(self):
        suite = make_suite(make_case("dev1", "dd1", split="development"))
        report = build_report(suite, [], JUDGES, mode="score")
        self.assertEqual(report["counts"]["expected_records"], 4)


if __name__ == "__main__":
    unittest.main()


class ContractDocumentTests(unittest.TestCase):
    """CONTRACT.md is part of the deliverable. These tests keep it in step with the code and the README."""

    AUTOMATED = Path(__file__).resolve().parents[1] / "evaluation" / "benchmark_v2" / "automated"
    REQUIRED_HEADINGS = (
        "## Suites, splits and clusters",
        "## Split selection",
        "## Certificates and the judge signature",
        "## Calibration-suite leakage guard",
        "## Run provenance",
        "## Judge output",
        "## Literal checks",
        "## Claims",
    )
    REQUIRED_NAMES = (
        "suite_sha256", "rubric_sha256", "config_sha256", "judge_signature", "adapter_sha256",
        "candidate_skill_sha256", "provenance.split", "provenance.certificate_suite_sha256",
        "provenance.calibration_overlap", "provenance.tool_versions", "tool_versions_stable",
        "version_commands", "cluster_id", "minItems",
        # The last name carries backticks because the bare word is a substring of the two counts.
        "owner_session", "candidate_check_diagnostics", "baseline_check_diagnostics", "`diagnostics`",
    )
    REFUSAL_MESSAGES = (
        "document reused across splits",
        "document assigned to more than one cluster",
        "cluster spans splits",
        "copied pair assigned to another document id",
        "invalid split",
        "calibrate scores the calibration split",
        "matching eligible live calibration required",
        "certificate was issued on another suite",
        "calibration suite does not match the certificate",
        "overlaps a calibration control",
        "evidence must be nonempty",
        "decisive or both_bad judgment requires both candidate quotes",
        "invalid provenance kind",
        "owner session case cannot have expected winner",
    )

    def contract(self):
        return (self.AUTOMATED / "CONTRACT.md").read_text(encoding="utf-8")

    def test_contract_has_every_required_section(self):
        headings = [line for line in self.contract().splitlines() if line.startswith("## ")]
        for required in self.REQUIRED_HEADINGS:
            self.assertTrue(any(line.startswith(required) for line in headings), required)

    def test_contract_names_every_split_and_provenance_key(self):
        text = self.contract()
        for name in contracts.SPLITS:
            self.assertIn(f"`{name}`", text)
        for name in self.REQUIRED_NAMES:
            self.assertIn(name, text, name)

    def test_contract_quotes_the_refusal_messages(self):
        text = self.contract()
        for message in self.REFUSAL_MESSAGES:
            self.assertIn(message, text, message)

    def test_contract_has_no_em_dash(self):
        self.assertNotIn(chr(0x2014), self.contract())

    def test_readme_points_to_the_contract(self):
        readme = (self.AUTOMATED / "README.md").read_text(encoding="utf-8")
        self.assertIn("CONTRACT.md", readme)
        self.assertIn("--calibration-suite", readme)
