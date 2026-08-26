from __future__ import annotations

import copy
import math
import unittest

from wqeval.gates import (
    _evaluate_stage1_gate_metrics as _evaluate_stage1_gate_metrics,
    _evaluate_stage1_gate_with_verified_reviews,
)
from wqeval.human_review import (
    trusted_human_roster_sha256,
    verify_stage1_human_gold_review_artifact,
    verify_stage1_human_review_artifact,
)
from wqeval.scoring import agreement_summary, score_stage1

from tests.support import case, finding, human_gold_review_artifact, trusted_human_roster


def evaluate_stage1_gate(metrics, thresholds, **kwargs):
    """Test the verified-review primitive without reopening the legacy API."""

    if "human_review_artifact" not in kwargs and "human_gold_review_artifact" not in kwargs:
        return _evaluate_stage1_gate_metrics(metrics, thresholds, **kwargs)
    roster = kwargs.pop("trusted_human_roster", trusted_human_roster())
    roster_sha256 = kwargs.pop(
        "expected_human_roster_sha256",
        trusted_human_roster_sha256(roster),
    )
    predictions = kwargs.pop("predictions", None)
    cases = kwargs.pop("cases", None)
    gold_findings = kwargs.pop("gold_findings", None)
    diagnostic_artifact = kwargs.pop("human_review_artifact", None)
    gold_artifact = kwargs.pop("human_gold_review_artifact", None)
    if kwargs:
        unexpected = next(iter(kwargs))
        raise TypeError(f"unexpected keyword argument: {unexpected}")
    verified_review = None
    if diagnostic_artifact is not None:
        if predictions is None:
            raise ValueError("predictions are required to verify a human-review artifact")
        verified_review = verify_stage1_human_review_artifact(
            diagnostic_artifact,
            predictions,
            trusted_human_roster=roster,
            expected_human_roster_sha256=roster_sha256,
        )
    verified_gold = None
    if gold_artifact is not None:
        if cases is None or gold_findings is None:
            raise ValueError(
                "cases and gold_findings are required to verify a human gold-review artifact"
            )
        verified_gold = verify_stage1_human_gold_review_artifact(
            gold_artifact,
            cases,
            gold_findings,
            trusted_human_roster=roster,
            expected_human_roster_sha256=roster_sha256,
        )
    return _evaluate_stage1_gate_with_verified_reviews(
        metrics,
        thresholds,
        human_review=verified_review,
        human_gold_review=verified_gold,
    )


def _review_artifact(predictions: list[dict], *, critical: bool = False) -> dict:
    change_predictions = [item for item in predictions if item["decision"] == "CHANGE"]
    review_items = [
        {"review_item_id": f"Item-{index:06d}", "prediction": copy.deepcopy(prediction)}
        for index, prediction in enumerate(change_predictions, start=1)
    ]
    reviews = []
    for reviewer_id in ("human-a", "human-b"):
        reviews.extend(
            {
                "review_item_id": item["review_item_id"],
                "reviewer_id": reviewer_id,
                "finding_valid": True,
                "span_valid": True,
                "problem_valid": True,
                "context_valid": True,
                "severity_valid": True,
                "operation_valid": True,
                "meaning_changed": False,
                "meaning_risk": "none",
            }
            for item in review_items
        )
    adjudications = [
        {
            "review_item_id": item["review_item_id"],
            "reviewer_id": "human-c",
            "finding_valid": True,
            "span_valid": True,
            "problem_valid": True,
            "context_valid": True,
            "severity_valid": True,
            "operation_valid": True,
            "meaning_changed": critical and index == len(review_items),
            "meaning_risk": "critical" if critical and index == len(review_items) else "none",
        }
        for index, item in enumerate(review_items, start=1)
    ]
    return {
        "schema_version": "1.0",
        "reviewers": [
            {"reviewer_id": "human-a", "actor_type": "human", "human": True},
            {"reviewer_id": "human-b", "actor_type": "human", "human": True},
        ],
        "adjudicator": {"reviewer_id": "human-c", "actor_type": "human", "human": True},
        "review_items": review_items,
        "reviews": reviews,
        "adjudications": adjudications,
    }


class HumanReviewIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = [case("C001", "The API failed."), case("C002", "The queue stalled.")]
        self.gold = [
            finding("C001", "G001", problem_code="vague_reference"),
            finding("C002", "G002", problem_code="generic_filler"),
        ]
        self.predictions = [
            dict(self.gold[0], finding_id="P001"),
            dict(self.gold[1], finding_id="P002"),
        ]
        self.roster = trusted_human_roster()
        self.roster_sha256 = trusted_human_roster_sha256(self.roster)

    def test_verified_two_reviewer_panel_and_separate_adjudicator_drive_metrics(self) -> None:
        artifact = _review_artifact(self.predictions, critical=True)
        metrics = score_stage1(
            self.cases,
            self.gold,
            self.predictions,
            human_review_artifact=artifact,
            trusted_human_roster=self.roster,
            expected_human_roster_sha256=self.roster_sha256,
        )

        self.assertTrue(metrics["human_review_verified"])
        self.assertEqual(metrics["meaning_reviewed_suggestions"], 2)
        self.assertAlmostEqual(metrics["diagnostic_meaning_change_rate"], 0.5)
        self.assertEqual(metrics["critical_meaning_risk"], 1)
        self.assertEqual(metrics["human_finding_acceptance_rate"], 1.0)
        self.assertEqual(metrics["human_reviewer_finding_valid_agreement"], 1.0)

    def test_complete_acceptance_requires_every_adjudicated_diagnostic_component(self) -> None:
        artifact = _review_artifact(self.predictions)
        artifact["adjudications"][0]["finding_valid"] = False
        artifact["adjudications"][0]["span_valid"] = False

        metrics = score_stage1(
            self.cases,
            self.gold,
            self.predictions,
            human_review_artifact=artifact,
            trusted_human_roster=self.roster,
            expected_human_roster_sha256=self.roster_sha256,
        )

        self.assertEqual(metrics["human_complete_acceptance_rate"], 0.5)
        self.assertEqual(metrics["human_finding_acceptance_rate"], 0.5)
        self.assertEqual(
            metrics["human_component_acceptance_rates"],
            {
                "finding_valid": 0.5,
                "span_valid": 0.5,
                "problem_valid": 1.0,
                "context_valid": 1.0,
                "severity_valid": 1.0,
                "operation_valid": 1.0,
            },
        )

    def test_finding_valid_summary_must_match_all_diagnostic_components(self) -> None:
        valid = _review_artifact(self.predictions)
        variants = []

        summary_true_with_invalid_component = copy.deepcopy(valid)
        summary_true_with_invalid_component["reviews"][0]["span_valid"] = False
        variants.append(summary_true_with_invalid_component)

        summary_false_with_all_components_valid = copy.deepcopy(valid)
        summary_false_with_all_components_valid["adjudications"][0]["finding_valid"] = False
        variants.append(summary_false_with_all_components_valid)

        for artifact in variants:
            with self.subTest(artifact=artifact), self.assertRaisesRegex(
                ValueError,
                "finding_valid.*components",
            ):
                score_stage1(
                    self.cases,
                    self.gold,
                    self.predictions,
                    human_review_artifact=artifact,
                )

    def test_malformed_unbound_duplicate_and_incomplete_review_artifacts_are_rejected(self) -> None:
        valid = _review_artifact(self.predictions)
        variants = []

        malformed = copy.deepcopy(valid)
        malformed["unexpected"] = True
        variants.append(("malformed", malformed))

        unbound = copy.deepcopy(valid)
        unbound["review_items"][0]["prediction"]["finding_id"] = "P999"
        variants.append(("unbound", unbound))

        duplicate_item = copy.deepcopy(valid)
        duplicate_item["review_items"].append(copy.deepcopy(duplicate_item["review_items"][0]))
        variants.append(("duplicate item", duplicate_item))

        duplicate_review = copy.deepcopy(valid)
        duplicate_review["reviews"].append(copy.deepcopy(duplicate_review["reviews"][0]))
        variants.append(("duplicate review", duplicate_review))

        incomplete_panel = copy.deepcopy(valid)
        incomplete_panel["reviews"].pop()
        variants.append(("incomplete reviewer panel", incomplete_panel))

        incomplete_adjudication = copy.deepcopy(valid)
        incomplete_adjudication["adjudications"].pop()
        variants.append(("incomplete adjudication", incomplete_adjudication))

        missing_prediction_item = copy.deepcopy(valid)
        missing_prediction_item["review_items"].pop()
        variants.append(("missing prediction item", missing_prediction_item))

        for name, artifact in variants:
            with self.subTest(name=name), self.assertRaises(ValueError):
                score_stage1(
                    self.cases,
                    self.gold,
                    self.predictions,
                    human_review_artifact=artifact,
                )

    def test_human_and_meaning_flags_must_be_actual_booleans(self) -> None:
        valid = _review_artifact(self.predictions)
        variants = []

        numeric_human = copy.deepcopy(valid)
        numeric_human["reviewers"][0]["human"] = 1
        variants.append(numeric_human)

        text_human = copy.deepcopy(valid)
        text_human["adjudicator"]["human"] = "yes"
        variants.append(text_human)

        numeric_review = copy.deepcopy(valid)
        numeric_review["reviews"][0]["meaning_changed"] = 0
        variants.append(numeric_review)

        numeric_adjudication = copy.deepcopy(valid)
        numeric_adjudication["adjudications"][0]["meaning_changed"] = 1
        variants.append(numeric_adjudication)

        for artifact in variants:
            with self.subTest(artifact=artifact), self.assertRaises(ValueError):
                score_stage1(
                    self.cases,
                    self.gold,
                    self.predictions,
                    human_review_artifact=artifact,
                )

    def test_meaning_changed_and_meaning_risk_must_be_consistent(self) -> None:
        valid = _review_artifact(self.predictions)
        contradictory = []

        unchanged_critical = copy.deepcopy(valid)
        unchanged_critical["adjudications"][0]["meaning_risk"] = "critical"
        contradictory.append(unchanged_critical)

        changed_none = copy.deepcopy(valid)
        changed_none["adjudications"][0]["meaning_changed"] = True
        contradictory.append(changed_none)

        for artifact in contradictory:
            with self.subTest(artifact=artifact), self.assertRaises(ValueError):
                score_stage1(
                    self.cases,
                    self.gold,
                    self.predictions,
                    human_review_artifact=artifact,
                )

    def test_reviewers_are_two_unique_humans_and_adjudicator_is_a_separate_human(self) -> None:
        valid = _review_artifact(self.predictions)
        variants = []

        one_reviewer = copy.deepcopy(valid)
        one_reviewer["reviewers"].pop()
        variants.append(one_reviewer)

        duplicate_identity = copy.deepcopy(valid)
        duplicate_identity["reviewers"][1]["reviewer_id"] = "HUMAN-A"
        variants.append(duplicate_identity)

        agent_reviewer = copy.deepcopy(valid)
        agent_reviewer["reviewers"][0]["actor_type"] = "agent"
        variants.append(agent_reviewer)

        same_adjudicator = copy.deepcopy(valid)
        same_adjudicator["adjudicator"]["reviewer_id"] = "human-a"
        variants.append(same_adjudicator)

        for artifact in variants:
            with self.subTest(artifact=artifact), self.assertRaises(ValueError):
                score_stage1(
                    self.cases,
                    self.gold,
                    self.predictions,
                    human_review_artifact=artifact,
                )

    def test_system_identity_cannot_serve_as_human_reviewer(self) -> None:
        predictions = [dict(self.predictions[0], system_id="human-a")]
        with self.assertRaisesRegex(ValueError, "generator cannot serve"):
            score_stage1(
                self.cases,
                self.gold,
                predictions,
                human_review_artifact=_review_artifact(predictions),
            )

    def test_flat_unverified_meaning_reviews_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            score_stage1(
                self.cases,
                self.gold,
                self.predictions,
                meaning_reviews=[{"human": True}],
            )


class StageOneGateIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.thresholds = {
            "schema_compliance_min": 1.0,
            "positive_opportunities_min": 1,
            "keep_opportunities_min": 1,
            "exact_precision_min": 0.8,
            "exact_recall_min": 0.6,
            "keep_accuracy_min": 0.9,
            "critical_meaning_risk_max": 0,
            "critical_miss_rate_max": 0.05,
            "human_gold_adjudication_required": True,
        }
        self.metrics = {
            "schema_compliance": 1.0,
            "positive_opportunities": 2,
            "keep_opportunities": 2,
            "precision": 0.9,
            "recall": 0.8,
            "keep_accuracy": 0.95,
            "critical_meaning_risk": 0,
            "critical_miss_rate": 0.0,
        }
        self.predictions = [finding("C001", "P001"), finding("C002", "P002")]
        self.cases = [case("C001"), case("C002")]
        self.gold = [finding("C001", "G001"), finding("C002", "G002")]
        self.gold_review_artifact = human_gold_review_artifact(self.cases, self.gold)
        self.roster = trusted_human_roster()
        self.roster_sha256 = trusted_human_roster_sha256(self.roster)

    def test_gate_opens_only_from_verified_review_artifact_not_caller_boolean_or_metric(self) -> None:
        pending = evaluate_stage1_gate(self.metrics, self.thresholds)
        self.assertFalse(pending["human_adjudicated"])
        self.assertEqual(pending["status"], "PENDING_HUMAN_REVIEW")
        self.assertIn("human_complete_acceptance_rate", pending["pending_conditions"])

        with self.assertRaises(TypeError):
            evaluate_stage1_gate(self.metrics, self.thresholds, human_adjudicated=True)

        passed = evaluate_stage1_gate(
            self.metrics,
            self.thresholds,
            predictions=self.predictions,
            human_review_artifact=_review_artifact(self.predictions),
            cases=self.cases,
            gold_findings=self.gold,
            human_gold_review_artifact=self.gold_review_artifact,
        )
        self.assertTrue(passed["human_adjudicated"])
        self.assertTrue(passed["stage2_eligible"])
        self.assertEqual(passed["status"], "PASS")

        with self.assertRaises(TypeError):
            _evaluate_stage1_gate_metrics(
                self.metrics,
                self.thresholds,
                predictions=self.predictions,
                human_review_artifact=_review_artifact(self.predictions),
            )
        structurally_valid = verify_stage1_human_review_artifact(
            _review_artifact(self.predictions),
            self.predictions,
        )
        self.assertTrue(structurally_valid["review_structure_verified"])
        self.assertFalse(structurally_valid["human_identity_attested"])
        untrusted = _evaluate_stage1_gate_metrics(self.metrics, self.thresholds)
        self.assertFalse(untrusted["human_adjudicated"])
        self.assertFalse(untrusted["human_gold_adjudicated"])
        self.assertFalse(untrusted["stage2_eligible"])
        self.assertEqual(untrusted["status"], "PENDING_HUMAN_REVIEW")

    def test_gate_uses_adjudicated_risk_from_artifact_instead_of_caller_metric(self) -> None:
        result = evaluate_stage1_gate(
            self.metrics,
            self.thresholds,
            predictions=self.predictions,
            human_review_artifact=_review_artifact(self.predictions, critical=True),
            cases=self.cases,
            gold_findings=self.gold,
            human_gold_review_artifact=self.gold_review_artifact,
        )
        self.assertFalse(result["stage2_eligible"])
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["failed_conditions"]["critical_meaning_risk"]["observed"], 1)

    def test_gate_rejects_zero_complete_acceptance_without_meaning_risk(self) -> None:
        artifact = _review_artifact(self.predictions)
        verdict_fields = (
            "finding_valid",
            "span_valid",
            "problem_valid",
            "context_valid",
            "severity_valid",
            "operation_valid",
        )
        for row in [*artifact["reviews"], *artifact["adjudications"]]:
            for field in verdict_fields:
                row[field] = False

        result = evaluate_stage1_gate(
            self.metrics,
            self.thresholds,
            predictions=self.predictions,
            human_review_artifact=artifact,
            cases=self.cases,
            gold_findings=self.gold,
            human_gold_review_artifact=self.gold_review_artifact,
        )

        self.assertEqual(result["status"], "FAIL")
        self.assertFalse(result["stage2_eligible"])
        self.assertEqual(
            result["failed_conditions"]["human_complete_acceptance_rate"],
            {"operator": ">=", "threshold": 0.8, "observed": 0.0},
        )

    def test_zero_change_review_has_not_applicable_acceptance_and_can_pass(self) -> None:
        keep_prediction = dict(self.predictions[0], decision="KEEP")
        result = evaluate_stage1_gate(
            self.metrics,
            self.thresholds,
            predictions=[keep_prediction],
            human_review_artifact=_review_artifact([keep_prediction]),
            cases=self.cases,
            gold_findings=self.gold,
            human_gold_review_artifact=self.gold_review_artifact,
        )

        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["stage2_eligible"])
        self.assertNotIn(
            "human_complete_acceptance_rate",
            result["failed_conditions"],
        )

    def test_nonfinite_boolean_or_incomplete_metric_schema_is_rejected(self) -> None:
        invalid_metrics = []
        for value in (math.nan, math.inf, -math.inf, True):
            invalid_metrics.append(dict(self.metrics, precision=value))
        incomplete = dict(self.metrics)
        del incomplete["recall"]
        invalid_metrics.append(incomplete)

        for metrics in invalid_metrics:
            with self.subTest(metrics=metrics), self.assertRaises(ValueError):
                evaluate_stage1_gate(metrics, self.thresholds)

        for value in (math.nan, math.inf, -math.inf, True):
            thresholds = dict(self.thresholds, exact_precision_min=value)
            with self.subTest(thresholds=thresholds), self.assertRaises(ValueError):
                evaluate_stage1_gate(self.metrics, thresholds)

        thresholds = dict(self.thresholds)
        del thresholds["exact_recall_min"]
        with self.assertRaises(ValueError):
            evaluate_stage1_gate(self.metrics, thresholds)

    def test_enabled_slice_gate_requires_all_slice_metric_dimensions(self) -> None:
        thresholds = dict(
            self.thresholds,
            sized_slice_positive_opportunities_min=5,
            sized_slice_precision_min=0.65,
        )
        metrics = dict(self.metrics, by_genre={}, by_author_type={})
        with self.assertRaises(ValueError):
            evaluate_stage1_gate(metrics, thresholds)

    def test_prediction_meaning_review_cannot_substitute_for_human_gold_adjudication(self) -> None:
        result = evaluate_stage1_gate(
            self.metrics,
            self.thresholds,
            predictions=self.predictions,
            human_review_artifact=_review_artifact(self.predictions),
        )
        self.assertFalse(result["human_gold_adjudicated"])
        self.assertFalse(result["stage2_eligible"])
        self.assertEqual(result["status"], "PENDING_HUMAN_REVIEW")
        self.assertIn("human_gold_adjudication", result["pending_conditions"])

    def test_adjudicated_gold_rejection_requires_gold_repair(self) -> None:
        result = evaluate_stage1_gate(
            self.metrics,
            self.thresholds,
            predictions=self.predictions,
            human_review_artifact=_review_artifact(self.predictions),
            cases=self.cases,
            gold_findings=self.gold,
            human_gold_review_artifact=human_gold_review_artifact(self.cases, self.gold, approved=False),
        )
        self.assertTrue(result["human_gold_adjudicated"])
        self.assertFalse(result["human_gold_approved"])
        self.assertFalse(result["stage2_eligible"])
        self.assertEqual(result["status"], "GOLD_REVIEW_REQUIRES_REPAIR")

    def test_gold_review_requires_the_complete_case_panel_including_zero_finding_cases(self) -> None:
        zero_finding_case = case("C003", "Already clear.")
        full_cases = [*self.cases, zero_finding_case]
        valid = human_gold_review_artifact(full_cases, self.gold)

        with self.assertRaises(ValueError):
            evaluate_stage1_gate(
                self.metrics,
                self.thresholds,
                predictions=self.predictions,
                human_review_artifact=_review_artifact(self.predictions),
                cases=full_cases,
                gold_findings=self.gold,
                human_gold_review_artifact=human_gold_review_artifact(self.cases, self.gold),
            )

        missing_finding = human_gold_review_artifact(full_cases, self.gold[:1])
        with self.assertRaises(ValueError):
            evaluate_stage1_gate(
                self.metrics,
                self.thresholds,
                predictions=self.predictions,
                human_review_artifact=_review_artifact(self.predictions),
                cases=full_cases,
                gold_findings=self.gold,
                human_gold_review_artifact=missing_finding,
            )

        passed = evaluate_stage1_gate(
            self.metrics,
            self.thresholds,
            predictions=self.predictions,
            human_review_artifact=_review_artifact(self.predictions),
            cases=full_cases,
            gold_findings=self.gold,
            human_gold_review_artifact=valid,
        )
        self.assertTrue(passed["human_gold_approved"])

    def test_impossible_finite_gate_metrics_are_rejected(self) -> None:
        invalid = (
            dict(self.metrics, schema_compliance=2.0),
            dict(self.metrics, precision=2.0),
            dict(self.metrics, recall=-0.1),
            dict(self.metrics, keep_accuracy=1.1),
            dict(self.metrics, critical_miss_rate=-1.0),
            dict(self.metrics, positive_opportunities=1.5),
            dict(self.metrics, keep_opportunities=-1),
        )
        for metrics in invalid:
            with self.subTest(metrics=metrics), self.assertRaises(ValueError):
                evaluate_stage1_gate(metrics, self.thresholds)


class ReviewerAgreementIntegrityTests(unittest.TestCase):
    def test_agreement_requires_exactly_two_unique_complete_reviewer_panels(self) -> None:
        valid = {
            "human-a": {"Item-1": "KEEP", "Item-2": "CHANGE"},
            "human-b": {"Item-1": "KEEP", "Item-2": "KEEP"},
        }
        self.assertEqual(agreement_summary(valid)["pair_count"], 1)

        invalid = (
            {"human-a": valid["human-a"]},
            {**valid, "human-c": valid["human-a"]},
            {"human-a": valid["human-a"], "HUMAN-A": valid["human-b"]},
            {"human-a": {}, "human-b": {}},
        )
        for ratings in invalid:
            with self.subTest(ratings=ratings), self.assertRaises(ValueError):
                agreement_summary(ratings)


if __name__ == "__main__":
    unittest.main()
