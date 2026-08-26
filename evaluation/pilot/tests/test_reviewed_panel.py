from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tests.support import case, finding
from tests.test_cli_integration import freeze_corpus
from tests.test_output_evidence import Stage1EvidenceFixture
from wqeval.corpus_evidence import verify_frozen_scoring_corpus
from wqeval.output_evidence import finalize_stage1_output
from wqeval.panel import build_verified_stage1_panel
from wqeval.review_packets import (
    assemble_diagnostic_review_artifact,
    assemble_gold_review_artifact,
    build_stage1_review_packets,
)
from wqeval.reviewed_panel import (
    ReviewedPanelError,
    evaluate_reviewed_stage1_panel,
)
from wqeval.roster_anchor import build_human_roster_anchor


def _thresholds(*, precision: float = 0.8) -> dict:
    return {
        "schema_compliance_min": 1.0,
        "positive_opportunities_min": 1,
        "keep_opportunities_min": 0,
        "exact_precision_min": precision,
        "exact_recall_min": 0.6,
        "keep_accuracy_min": 0.0,
        "critical_meaning_risk_max": 0,
        "critical_miss_rate_max": 0.05,
        "human_gold_adjudication_required": True,
    }


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


_TRUSTED_HUMAN_ROSTER = {
    "schema_version": "1.0",
    "status": "CONFIRMED",
    "attestation_kind": "real_human_identity",
    "reviewer_ids": ["human-a", "human-b"],
    "adjudicator_id": "human-c",
    "attested_by": "evaluation-owner",
    "attestation_source": "direct identity confirmation",
    "real_humans_confirmed": True,
}
_SCORING_PROTOCOL_AMENDMENT_SHA256 = "d" * 64


def _trusted_roster_arguments(panel) -> dict:
    return {
        "human_roster_anchor": build_human_roster_anchor(
            human_roster=_TRUSTED_HUMAN_ROSTER,
            run_id="test-stage1-run",
            source_panel_report_sha256=panel.report_sha256,
        ),
    }


def _reviewed_panel_arguments(panel) -> dict:
    return {
        **_trusted_roster_arguments(panel),
        "expected_scoring_protocol_amendment_sha256": (
            _SCORING_PROTOCOL_AMENDMENT_SHA256
        ),
    }


class _MixedDecisionFixture(Stage1EvidenceFixture):
    """Emit CHANGE for the first system and KEEP for the second system."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self._payload_number = 0

    def raw_payload(self, case_id: str) -> bytes:
        self._payload_number += 1
        if self._payload_number <= 3:
            return super().raw_payload(case_id)
        return _canonical_json(
            {
                "schema_version": "1.0",
                "case_id": case_id,
                "case_decision": "KEEP",
                "findings": [
                    {
                        "finding_id": "K001",
                        "start": 0,
                        "end": 3,
                        "span": "The",
                        "decision": "KEEP",
                        "problem_name": "Legitimate passive",
                        "system_issue_code": "legitimate_passive",
                        "normalized_issue_code": "legitimate_passive",
                        "context_explanation": "The original wording should be preserved.",
                        "severity": "low",
                        "suggested_operation": {
                            "operation_code": "preserve",
                            "instruction": "Preserve the original wording.",
                            "replacement": None,
                        },
                        "field_origin": "authored",
                    }
                ],
            }
        )


def _build_panel(
    root: Path,
    *,
    keep_system_b: bool = False,
    precision: float = 0.8,
):
    project = root / "project"
    run_root = project / "runs" / "sealed"
    run_root.mkdir(parents=True)
    fixture = _MixedDecisionFixture(run_root) if keep_system_b else Stage1EvidenceFixture(run_root)
    for system_id in ("system-a", "system-b"):
        for run_number in (1, 2, 3):
            fixture.add_job(system_id, run_number)
    jobs_sha, errors = fixture.publish()
    if errors:
        raise AssertionError(errors)
    anchor = finalize_stage1_output(run_root, expected_jobs_manifest_sha256=jobs_sha)
    frozen_case = case("C001")
    frozen_gold = finding("C001", "G001")
    freeze_sha = freeze_corpus(project, [frozen_case], [frozen_gold])
    corpus = verify_frozen_scoring_corpus(
        project,
        expected_freeze_manifest_sha256=freeze_sha,
        split="test",
    )
    return build_verified_stage1_panel(
        corpus,
        run_root=run_root,
        expected_output_evidence_sha256=anchor.sha256,
        expected_runs=3,
        expected_systems=2,
        thresholds=_thresholds(precision=precision),
    )


def _completed_artifacts(
    panel,
    *,
    rejected_systems: set[str] | None = None,
    critical_systems: set[str] | None = None,
    gold_approved: bool = True,
):
    rejected = rejected_systems or set()
    critical = critical_systems or set()
    evaluations = {item.system_id: item for item in panel.evaluations}
    system_bindings = [
        {
            "system_id": evaluation.system_id,
            "prediction_count": len(evaluation.predictions),
            "change_count": sum(
                prediction["decision"] == "CHANGE"
                for prediction in evaluation.predictions
            ),
            "predictions_sha256": evaluation.predictions_sha256,
        }
        for evaluation in panel.evaluations
    ]
    bundle = build_stage1_review_packets(
        list(panel.evaluations[0].cases),
        list(panel.evaluations[0].gold),
        list(panel.predictions),
        seed=20260825,
        evidence={
            "panel_report_canonical_sha256": panel.report_sha256,
            "scoring_protocol_amendment_sha256": (
                _SCORING_PROTOCOL_AMENDMENT_SHA256
            ),
        },
        **_trusted_roster_arguments(panel),
        expected_run_id="test-stage1-run",
        system_prediction_bindings=system_bindings,
    )
    reviewers = [
        {"reviewer_id": "human-a", "actor_type": "human", "human": True},
        {"reviewer_id": "human-b", "actor_type": "human", "human": True},
    ]
    adjudicator = {"reviewer_id": "human-c", "actor_type": "human", "human": True}
    system_by_item = {
        item["review_item_id"]: item["prediction"]["system_id"]
        for item in bundle["diagnostic_private"]["review_items"]
    }
    diagnostic_reviews = []
    for reviewer in reviewers:
        for template in bundle["diagnostic_reviewer_template"]:
            system_id = system_by_item[template["review_item_id"]]
            accepted = system_id not in rejected
            diagnostic_reviews.append(
                {
                    **template,
                    "reviewer_id": reviewer["reviewer_id"],
                    "finding_valid": accepted,
                    "span_valid": accepted,
                    "problem_valid": accepted,
                    "context_valid": accepted,
                    "severity_valid": accepted,
                    "operation_valid": accepted,
                    "meaning_changed": False,
                    "meaning_risk": "none",
                }
            )
    diagnostic_adjudications = []
    for template in bundle["diagnostic_adjudicator_template"]:
        system_id = system_by_item[template["review_item_id"]]
        accepted = system_id not in rejected
        meaning_changed = system_id in critical
        diagnostic_adjudications.append(
            {
                **template,
                "reviewer_id": "human-c",
                "finding_valid": accepted,
                "span_valid": accepted,
                "problem_valid": accepted,
                "context_valid": accepted,
                "severity_valid": accepted,
                "operation_valid": accepted,
                "meaning_changed": meaning_changed,
                "meaning_risk": "critical" if meaning_changed else "none",
            }
        )
    diagnostic = assemble_diagnostic_review_artifact(
        bundle,
        expected_packet_id=bundle["manifest"]["packet_id"],
        **_trusted_roster_arguments(panel),
        reviewers=reviewers,
        adjudicator=adjudicator,
        reviews=diagnostic_reviews,
        adjudications=diagnostic_adjudications,
    )

    gold_reviews = [
        {
            **template,
            "reviewer_id": reviewer["reviewer_id"],
            "span_correct": True,
            "decision_correct": True,
            "label_correct": True,
            "severity_correct": True,
            "gold_complete": True,
        }
        for reviewer in reviewers
        for template in bundle["gold_reviewer_template"]
    ]
    gold_adjudications = [
        {
            **template,
            "reviewer_id": "human-c",
            "span_correct": True,
            "decision_correct": True,
            "label_correct": True,
            "severity_correct": True,
            "gold_complete": gold_approved,
        }
        for template in bundle["gold_adjudicator_template"]
    ]
    gold = assemble_gold_review_artifact(
        bundle,
        expected_packet_id=bundle["manifest"]["packet_id"],
        **_trusted_roster_arguments(panel),
        reviewers=reviewers,
        adjudicator=adjudicator,
        reviews=gold_reviews,
        adjudications=gold_adjudications,
    )
    self_check = {
        system_id: evaluations[system_id].predictions_sha256
        for system_id in sorted(evaluations)
    }
    return bundle["manifest"]["packet_id"], diagnostic, gold, self_check


class ReviewedStageOnePanelTests(unittest.TestCase):
    def test_projects_one_completed_panel_into_disjoint_system_gates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            panel = _build_panel(Path(directory))
            packet_id, diagnostic, gold, prediction_hashes = _completed_artifacts(
                panel,
                rejected_systems={"system-b"},
                critical_systems={"system-b"},
            )

            reviewed = evaluate_reviewed_stage1_panel(
                panel,
                expected_packet_id=packet_id,
                diagnostic_review_artifact=diagnostic,
                gold_review_artifact=gold,
                **_reviewed_panel_arguments(panel),
            )

            report = reviewed.report
            self.assertEqual(report["status"], "FAIL")
            self.assertEqual(report["human_review_status"], "COMPLETE")
            self.assertFalse(report["stage2_eligible"])
            self.assertEqual(report["review_packet_id"], packet_id)
            self.assertEqual(
                report["evidence"]["source_panel_report_sha256"],
                panel.report_sha256,
            )
            self.assertEqual(
                report["evidence"]["scoring_protocol_amendment_sha256"],
                _SCORING_PROTOCOL_AMENDMENT_SHA256,
            )
            self.assertEqual(
                report["results"]["system-a"]["human_metrics"]["reviewed_prediction_count"],
                3,
            )
            self.assertEqual(
                report["results"]["system-b"]["human_metrics"]["reviewed_prediction_count"],
                3,
            )
            self.assertEqual(
                report["results"]["system-a"]["human_metrics"]["human_finding_acceptance_rate"],
                1.0,
            )
            self.assertEqual(
                report["results"]["system-b"]["human_metrics"]["human_finding_acceptance_rate"],
                0.0,
            )
            self.assertEqual(
                report["results"]["system-a"]["human_metrics"]["critical_meaning_risk"],
                0,
            )
            self.assertEqual(
                report["results"]["system-b"]["human_metrics"]["critical_meaning_risk"],
                3,
            )
            self.assertEqual(report["results"]["system-a"]["gate"]["status"], "PASS")
            self.assertEqual(report["results"]["system-b"]["gate"]["status"], "FAIL")
            for system_id, expected_hash in prediction_hashes.items():
                result = report["results"][system_id]
                self.assertEqual(result["predictions_sha256"], expected_hash)
                self.assertEqual(
                    result["human_metrics"]["predictions_sha256"],
                    expected_hash,
                )
                self.assertEqual(
                    result["gate"]["verified_evidence"]["predictions_sha256"],
                    expected_hash,
                )
            reviewed.assert_verified()
            self.assertEqual(len(reviewed.report_sha256), 64)
            self.assertEqual(
                reviewed.diagnostic_completed_artifact_sha256,
                report["evidence"]["diagnostic_completed_artifact_sha256"],
            )
            self.assertEqual(
                reviewed.gold_completed_artifact_sha256,
                report["evidence"]["gold_completed_artifact_sha256"],
            )

    def test_completed_artifact_digest_binds_rating_rows(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            panel = _build_panel(Path(directory))
            packet_id, accepted_diagnostic, accepted_gold, _ = _completed_artifacts(panel)
            second_packet_id, rejected_diagnostic, rejected_gold, _ = _completed_artifacts(
                panel,
                rejected_systems={"system-b"},
            )
            self.assertEqual(packet_id, second_packet_id)
            accepted = evaluate_reviewed_stage1_panel(
                panel,
                expected_packet_id=packet_id,
                diagnostic_review_artifact=accepted_diagnostic,
                gold_review_artifact=accepted_gold,
                **_reviewed_panel_arguments(panel),
            )
            rejected = evaluate_reviewed_stage1_panel(
                panel,
                expected_packet_id=packet_id,
                diagnostic_review_artifact=rejected_diagnostic,
                gold_review_artifact=rejected_gold,
                **_reviewed_panel_arguments(panel),
            )
            expected_digest = hashlib.sha256(
                json.dumps(
                    accepted_diagnostic,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest()
            self.assertEqual(
                accepted.diagnostic_completed_artifact_sha256,
                expected_digest,
            )
            self.assertNotEqual(
                accepted.diagnostic_completed_artifact_sha256,
                rejected.diagnostic_completed_artifact_sha256,
            )
            self.assertEqual(
                accepted.gold_completed_artifact_sha256,
                rejected.gold_completed_artifact_sha256,
            )

    def test_every_system_must_pass_before_stage_two_is_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            panel = _build_panel(Path(directory))
            packet_id, diagnostic, gold, _ = _completed_artifacts(panel)
            reviewed = evaluate_reviewed_stage1_panel(
                panel,
                expected_packet_id=packet_id,
                diagnostic_review_artifact=diagnostic,
                gold_review_artifact=gold,
                **_reviewed_panel_arguments(panel),
            )
            self.assertEqual(reviewed.report["status"], "PASS")
            self.assertTrue(reviewed.report["stage2_eligible"])
            self.assertTrue(
                all(
                    result["gate"]["stage2_eligible"]
                    for result in reviewed.report["results"].values()
                )
            )

    def test_zero_acceptance_without_meaning_risk_fails_the_reviewed_panel(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            panel = _build_panel(Path(directory))
            packet_id, diagnostic, gold, _ = _completed_artifacts(
                panel,
                rejected_systems={"system-b"},
            )
            reviewed = evaluate_reviewed_stage1_panel(
                panel,
                expected_packet_id=packet_id,
                diagnostic_review_artifact=diagnostic,
                gold_review_artifact=gold,
                **_reviewed_panel_arguments(panel),
            )

            system = reviewed.report["results"]["system-b"]
            self.assertEqual(reviewed.report["status"], "FAIL")
            self.assertFalse(reviewed.report["stage2_eligible"])
            self.assertEqual(system["human_metrics"]["critical_meaning_risk"], 0)
            self.assertEqual(system["human_metrics"]["human_complete_acceptance_rate"], 0.0)
            self.assertEqual(system["gate"]["status"], "FAIL")
            self.assertEqual(
                system["gate"]["failed_conditions"]["human_complete_acceptance_rate"],
                {"operator": ">=", "threshold": 0.8, "observed": 0.0},
            )

    def test_zero_change_system_gets_zero_counts_and_null_rates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            panel = _build_panel(Path(directory), keep_system_b=True)
            packet_id, diagnostic, gold, _ = _completed_artifacts(panel)
            reviewed = evaluate_reviewed_stage1_panel(
                panel,
                expected_packet_id=packet_id,
                diagnostic_review_artifact=diagnostic,
                gold_review_artifact=gold,
                **_reviewed_panel_arguments(panel),
            )
            metrics = reviewed.report["results"]["system-b"]["human_metrics"]
            self.assertEqual(metrics["prediction_count"], 3)
            self.assertEqual(metrics["reviewed_prediction_count"], 0)
            self.assertEqual(metrics["meaning_reviewed_suggestions"], 0)
            self.assertEqual(metrics["critical_meaning_risk"], 0)
            self.assertIsNone(metrics["diagnostic_meaning_change_rate"])
            self.assertIsNone(metrics["human_finding_acceptance_rate"])
            self.assertIsNone(metrics["human_complete_acceptance_rate"])
            self.assertEqual(
                metrics["human_component_acceptance_rates"],
                {
                    "finding_valid": None,
                    "span_valid": None,
                    "problem_valid": None,
                    "context_valid": None,
                    "severity_valid": None,
                    "operation_valid": None,
                },
            )
            self.assertIsNone(metrics["human_reviewer_finding_valid_agreement"])
            self.assertIsNone(metrics["human_reviewer_finding_valid_kappa"])

    def test_packet_must_be_bound_to_the_exact_verified_panel_report(self) -> None:
        with tempfile.TemporaryDirectory() as first_directory, tempfile.TemporaryDirectory() as second_directory:
            source_panel = _build_panel(Path(first_directory))
            packet_id, diagnostic, gold, _ = _completed_artifacts(source_panel)
            different_panel = _build_panel(Path(second_directory), precision=0.9)
            with self.assertRaisesRegex(ReviewedPanelError, "panel report"):
                evaluate_reviewed_stage1_panel(
                    different_panel,
                    expected_packet_id=packet_id,
                    diagnostic_review_artifact=diagnostic,
                    gold_review_artifact=gold,
                    **_reviewed_panel_arguments(source_panel),
                )

    def test_absent_reviews_remain_unadjudicated_and_partial_reviews_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            panel = _build_panel(Path(directory))
            pending = evaluate_reviewed_stage1_panel(
                panel,
                expected_packet_id="a" * 64,
                expected_scoring_protocol_amendment_sha256=(
                    _SCORING_PROTOCOL_AMENDMENT_SHA256
                ),
            )
            self.assertEqual(pending.report["status"], "PILOT_UNADJUDICATED")
            self.assertEqual(pending.report["human_review_status"], "PENDING_HUMAN_REVIEW")
            self.assertFalse(pending.report["stage2_eligible"])

            packet_id, diagnostic, _, _ = _completed_artifacts(panel)
            with self.assertRaisesRegex(ReviewedPanelError, "both"):
                evaluate_reviewed_stage1_panel(
                    panel,
                    expected_packet_id=packet_id,
                    diagnostic_review_artifact=diagnostic,
                    expected_scoring_protocol_amendment_sha256=(
                        _SCORING_PROTOCOL_AMENDMENT_SHA256
                    ),
                )

    def test_completed_reviews_require_an_exact_detached_real_human_roster(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            panel = _build_panel(Path(directory))
            packet_id, diagnostic, gold, _ = _completed_artifacts(panel)
            with self.assertRaisesRegex(ReviewedPanelError, "roster anchor"):
                evaluate_reviewed_stage1_panel(
                    panel,
                    expected_packet_id=packet_id,
                    diagnostic_review_artifact=diagnostic,
                    gold_review_artifact=gold,
                    expected_scoring_protocol_amendment_sha256=(
                        _SCORING_PROTOCOL_AMENDMENT_SHA256
                    ),
                )

            forged_roster = {
                **_TRUSTED_HUMAN_ROSTER,
                "reviewer_ids": ["human-x", "human-y"],
                "adjudicator_id": "human-z",
            }
            forged_anchor = build_human_roster_anchor(
                human_roster=forged_roster,
                run_id="test-stage1-run",
                source_panel_report_sha256=panel.report_sha256,
            )
            with self.assertRaisesRegex(ReviewedPanelError, "anchor"):
                evaluate_reviewed_stage1_panel(
                    panel,
                    expected_packet_id=packet_id,
                    diagnostic_review_artifact=diagnostic,
                    gold_review_artifact=gold,
                    human_roster_anchor=forged_anchor,
                    expected_scoring_protocol_amendment_sha256=(
                        _SCORING_PROTOCOL_AMENDMENT_SHA256
                    ),
                )

            wrong_panel_anchor = build_human_roster_anchor(
                human_roster=_TRUSTED_HUMAN_ROSTER,
                run_id="test-stage1-run",
                source_panel_report_sha256="0" * 64,
            )
            with self.assertRaisesRegex(ReviewedPanelError, "panel report|anchor"):
                evaluate_reviewed_stage1_panel(
                    panel,
                    expected_packet_id=packet_id,
                    diagnostic_review_artifact=diagnostic,
                    gold_review_artifact=gold,
                    human_roster_anchor=wrong_panel_anchor,
                    expected_scoring_protocol_amendment_sha256=(
                        _SCORING_PROTOCOL_AMENDMENT_SHA256
                    ),
                )

            with self.assertRaisesRegex(ReviewedPanelError, "amendment"):
                evaluate_reviewed_stage1_panel(
                    panel,
                    expected_packet_id=packet_id,
                    diagnostic_review_artifact=diagnostic,
                    gold_review_artifact=gold,
                    human_roster_anchor=_trusted_roster_arguments(panel)[
                        "human_roster_anchor"
                    ],
                    expected_scoring_protocol_amendment_sha256="0" * 64,
                )

    def test_report_payload_is_hash_attested(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            panel = _build_panel(Path(directory))
            pending = evaluate_reviewed_stage1_panel(
                panel,
                expected_packet_id=hashlib.sha256(b"pending").hexdigest(),
                expected_scoring_protocol_amendment_sha256=(
                    _SCORING_PROTOCOL_AMENDMENT_SHA256
                ),
            )
            object.__setattr__(pending, "report_payload", b"{}")
            with self.assertRaisesRegex(ReviewedPanelError, "payload changed"):
                pending.assert_verified()


if __name__ == "__main__":
    unittest.main()
