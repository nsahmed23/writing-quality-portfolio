from __future__ import annotations

import unittest

from wqeval.human_review import trusted_human_roster_sha256
from wqeval.scoring import exact_finding_key, score_stage1

from tests.support import case, finding, human_review_artifact, trusted_human_roster


class StageOneScoringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = [
            case("C001", "The API failed.", genre="technical", author_type="professional"),
            case("C002", "The report was approved by the board.", genre="executive", author_type="professional"),
            case("C003", "We definitely might ship on 3 May.", genre="second_language", author_type="second_language"),
        ]
        self.gold = [
            finding("C001", "G001", problem_code="vague_reference", decision="CHANGE", severity="medium"),
            finding(
                "C002",
                "G002",
                start=11,
                end=23,
                span_text="was approved",
                problem_code="legitimate_passive",
                decision="KEEP",
                severity="low",
            ),
            finding(
                "C003",
                "G003",
                start=3,
                end=19,
                span_text="definitely might",
                problem_code="contradictory_modality",
                decision="CHANGE",
                severity="critical",
            ),
        ]

    def test_exact_key_uses_case_span_problem_and_not_finding_id(self) -> None:
        left = self.gold[0]
        right = dict(left, finding_id="P999", severity="high")
        self.assertEqual(exact_finding_key(left), exact_finding_key(right))

        shifted = {**right, "span": {"start": 0, "end": 4, "text": "The "}}
        relabeled = dict(right, problem_code="generic_language")
        self.assertNotEqual(exact_finding_key(left), exact_finding_key(shifted))
        self.assertNotEqual(exact_finding_key(left), exact_finding_key(relabeled))

    def test_metrics_count_correct_change_false_alarm_and_high_severity_miss(self) -> None:
        predictions = [
            dict(self.gold[0], finding_id="P001"),
            dict(self.gold[1], finding_id="P002", decision="CHANGE"),
        ]
        metrics = score_stage1(self.cases, self.gold, predictions)

        self.assertEqual(metrics["true_positives"], 1)
        self.assertEqual(metrics["false_positives"], 1)
        self.assertEqual(metrics["false_negatives"], 1)
        self.assertEqual(metrics["explicit_keep_matches"], 0)
        self.assertAlmostEqual(metrics["precision"], 0.5)
        self.assertAlmostEqual(metrics["recall"], 0.5)
        self.assertAlmostEqual(metrics["f1"], 0.5)
        self.assertAlmostEqual(metrics["false_discovery_proportion"], 0.5)
        self.assertNotIn("false_positive_rate", metrics)
        self.assertEqual(metrics["important_issues_missed"], 1)
        self.assertEqual(metrics["positive_opportunities"], 2)
        self.assertEqual(metrics["keep_opportunities"], 1)
        self.assertEqual(metrics["critical_issues"], 1)
        self.assertEqual(metrics["critical_issues_missed"], 1)
        self.assertAlmostEqual(metrics["critical_miss_rate"], 1.0)
        self.assertAlmostEqual(metrics["clean_control_case_false_positive_rate"], 1.0)
        self.assertAlmostEqual(metrics["by_genre"]["technical"]["recall"], 1.0)
        self.assertAlmostEqual(metrics["by_genre"]["second_language"]["recall"], 0.0)
        self.assertAlmostEqual(metrics["by_author_type"]["second_language"]["recall"], 0.0)
        self.assertAlmostEqual(metrics["by_author_profile"]["second_language_professional"]["recall"], 0.0)

    def test_correct_keep_is_a_true_negative_and_extraneous_change_is_false_positive(self) -> None:
        predictions = [dict(item, finding_id=f"P{index:03d}") for index, item in enumerate(self.gold, start=1)]
        predictions.append(
            finding(
                "C001",
                "P999",
                start=4,
                end=7,
                span_text="API",
                problem_code="invented_problem",
                decision="CHANGE",
            )
        )
        metrics = score_stage1(self.cases, self.gold, predictions)

        self.assertEqual(metrics["true_positives"], 2)
        self.assertEqual(metrics["explicit_keep_matches"], 1)
        self.assertEqual(metrics["false_positives"], 1)
        self.assertEqual(metrics["false_negatives"], 0)
        self.assertAlmostEqual(metrics["explicit_keep_recognition_rate"], 1.0)
        self.assertAlmostEqual(metrics["clean_control_case_false_positive_rate"], 0.0)

    def test_meaning_change_is_scored_only_from_independent_reviews(self) -> None:
        predictions = [
            dict(self.gold[0], finding_id="P001"),
            dict(self.gold[1], finding_id="P002", decision="CHANGE"),
        ]
        artifact = human_review_artifact(predictions, changed_finding_ids={"P002"})
        roster = trusted_human_roster()
        metrics = score_stage1(
            self.cases,
            self.gold,
            predictions,
            human_review_artifact=artifact,
            trusted_human_roster=roster,
            expected_human_roster_sha256=trusted_human_roster_sha256(roster),
        )
        self.assertTrue(metrics["human_review_verified"])
        self.assertEqual(metrics["meaning_reviewed_suggestions"], 2)
        self.assertAlmostEqual(metrics["diagnostic_meaning_change_rate"], 0.5)

        self_review = human_review_artifact(predictions)
        self_review["adjudicator"]["reviewer_id"] = "human-a"
        with self.assertRaises(ValueError):
            score_stage1(self.cases, self.gold, predictions, human_review_artifact=self_review)

        nonhuman = human_review_artifact(predictions)
        nonhuman["reviewers"][0]["actor_type"] = "agent"
        with self.assertRaises(ValueError):
            score_stage1(
                self.cases,
                self.gold,
                predictions,
                human_review_artifact=nonhuman,
            )

    def test_keep_accuracy_catches_change_on_keep_bait_inside_mixed_case(self) -> None:
        source = "The request was approved, and it may fail."
        cases = [case("M001", source)]
        gold = [
            finding(
                "M001",
                "G001",
                start=12,
                end=24,
                span_text="was approved",
                problem_code="legitimate_passive",
                decision="KEEP",
                severity="none",
            ),
            finding(
                "M001",
                "G002",
                start=33,
                end=36,
                span_text="may",
                problem_code="unjustified_modality",
                decision="CHANGE",
                severity="high",
            ),
        ]
        predictions = [
            dict(gold[1], finding_id="P001"),
            finding(
                "M001",
                "P002",
                start=12,
                end=24,
                span_text="was approved",
                problem_code="passive_voice",
                decision="CHANGE",
            ),
        ]
        metrics = score_stage1(cases, gold, predictions)
        self.assertEqual(metrics["keep_opportunities"], 1)
        self.assertEqual(metrics["keep_false_positive_count"], 1)
        self.assertEqual(metrics["keep_accuracy"], 0.0)

    def test_empty_denominators_are_null_with_explanation(self) -> None:
        clean = [case("K001", "Purposeful repetition.")]
        keep = [finding("K001", "G001", problem_code="purposeful_repetition", decision="KEEP")]
        metrics = score_stage1(clean, keep, [])
        self.assertIsNone(metrics["precision"])
        self.assertIsNone(metrics["recall"])
        self.assertIsNone(metrics["f1"])
        self.assertIn("precision", metrics["undefined_metrics"])
        self.assertIn("recall", metrics["undefined_metrics"])
        self.assertIn("f1", metrics["undefined_metrics"])

    def test_overlap_analysis_never_replaces_exact_primary_matching(self) -> None:
        predictions = [
            finding(
                "C001",
                "P001",
                start=0,
                end=4,
                span_text="The ",
                problem_code="vague_reference",
                decision="CHANGE",
            )
        ]
        metrics = score_stage1(self.cases, self.gold, predictions)
        self.assertEqual(metrics["true_positives"], 0)
        self.assertEqual(metrics["overlap_sensitivity"]["true_positives"], 1)
        self.assertEqual(metrics["overlap_sensitivity"]["false_positives"], 0)
        self.assertEqual(metrics["overlap_sensitivity"]["false_negatives"], 1)

    def test_macro_and_false_findings_per_thousand_words_are_reported(self) -> None:
        predictions = [dict(self.gold[0], finding_id="P001")]
        metrics = score_stage1(self.cases, self.gold, predictions)
        self.assertAlmostEqual(metrics["macro_precision"], 1.0)
        self.assertAlmostEqual(metrics["macro_recall"], 0.5)
        self.assertEqual(metrics["false_findings_per_1000_words"], 0.0)
        self.assertGreater(metrics["word_count"], 0)


if __name__ == "__main__":
    unittest.main()
