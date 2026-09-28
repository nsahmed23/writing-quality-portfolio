"""Hash-bound Stage 1 panel gating from completed human-review packets."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any

from .gates import _evaluate_stage1_gate_with_verified_reviews
from .panel import VerifiedStage1Panel
from .review_packets import (
    ReviewPacketError,
    verify_completed_diagnostic_review_artifact,
    verify_completed_gold_review_artifact,
)
from .strict_json import loads


class ReviewedPanelError(ValueError):
    """Raised when reviewed results do not bind to one verified Stage 1 panel."""


_ATTESTATION = object()
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")


def _canonical_json(value: Any) -> bytes:
    try:
        return (
            json.dumps(
                value,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ReviewedPanelError("reviewed panel report must be finite JSON data") from error


def _canonical_value(value: Any, *, label: str) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ReviewedPanelError(f"{label} must be finite JSON data") from error


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _digest(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or _HEX_64.fullmatch(value) is None:
        raise ReviewedPanelError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _snapshot_artifact(value: Any, *, label: str) -> tuple[dict[str, Any], str]:
    payload = _canonical_value(value, label=label)
    snapshot = loads(payload)
    if not isinstance(snapshot, dict):
        raise ReviewedPanelError(f"{label} must be an object")
    return snapshot, _sha256(payload)


def _verified_evaluation_evidence(evaluation: Any) -> dict[str, Any]:
    return {
        "system_id": evaluation.system_id,
        "output_evidence_sha256": evaluation.output_evidence_sha256,
        "corpus_freeze_manifest_sha256": evaluation.corpus_freeze_manifest_sha256,
        "cases_sha256": evaluation.cases_sha256,
        "gold_sha256": evaluation.gold_sha256,
        "model_settings_sha256": evaluation.model_settings_sha256,
        "predictions_sha256": evaluation.predictions_sha256,
        "gate_metrics_sha256": evaluation.gate_metrics_sha256,
        "run_numbers": list(evaluation.run_numbers),
    }


def _assert_gold_projection_matches_panel(
    panel: VerifiedStage1Panel,
    artifact: dict[str, Any],
) -> None:
    evaluations = panel.evaluations
    case_hashes = {evaluation.cases_sha256 for evaluation in evaluations}
    gold_hashes = {evaluation.gold_sha256 for evaluation in evaluations}
    if len(case_hashes) != 1 or len(gold_hashes) != 1:
        raise ReviewedPanelError("verified evaluations do not share one gold corpus")

    expected_cases = {
        item["case_id"]: item
        for item in evaluations[0].cases
    }
    expected_gold = {
        (item["case_id"], item["finding_id"]): item
        for item in evaluations[0].gold
    }
    observed_cases: dict[str, dict[str, Any]] = {}
    observed_gold: dict[tuple[str, str], dict[str, Any]] = {}
    for item in artifact["private_packet"]["review_items"]:
        source_case = item["case"]
        case_id = source_case["case_id"]
        if case_id in observed_cases:
            raise ReviewedPanelError(f"gold review repeats case: {case_id}")
        observed_cases[case_id] = source_case
        for finding in item["gold_findings"]:
            identity = (finding["case_id"], finding["finding_id"])
            if identity in observed_gold:
                raise ReviewedPanelError(
                    f"gold review repeats finding: {identity[0]}:{identity[1]}"
                )
            observed_gold[identity] = finding
    if observed_cases != expected_cases or observed_gold != expected_gold:
        raise ReviewedPanelError("completed gold review does not match the verified panel corpus")


def _require_panel_report_binding(
    panel: VerifiedStage1Panel,
    diagnostic_artifact: dict[str, Any],
    gold_artifact: dict[str, Any],
    *,
    expected_scoring_protocol_amendment_sha256: str,
) -> None:
    for label, artifact in (
        ("diagnostic", diagnostic_artifact),
        ("gold", gold_artifact),
    ):
        evidence = artifact["source_manifest"]["evidence"]
        if evidence.get("panel_report_canonical_sha256") != panel.report_sha256:
            raise ReviewedPanelError(
                f"completed {label} review is not bound to the verified panel report"
            )
        if (
            evidence.get("scoring_protocol_amendment_sha256")
            != expected_scoring_protocol_amendment_sha256
        ):
            raise ReviewedPanelError(
                f"completed {label} review is not bound to the expected scoring protocol amendment"
            )


@dataclass(frozen=True)
class VerifiedReviewedStage1Panel:
    """Attested reviewed report derived from a verified objective panel."""

    source_panel: VerifiedStage1Panel = field(repr=False)
    source_panel_report_sha256: str
    scoring_protocol_amendment_sha256: str
    review_packet_id: str
    human_roster_anchor_sha256: str | None
    diagnostic_completed_artifact_sha256: str | None
    gold_completed_artifact_sha256: str | None
    report_payload: bytes = field(repr=False)
    report_sha256: str
    _attestation: object = field(repr=False, compare=False)

    def assert_verified(self) -> None:
        if self._attestation is not _ATTESTATION:
            raise ReviewedPanelError("reviewed panel was not created by the verified builder")
        self.source_panel.assert_verified()
        if self.source_panel.report_sha256 != self.source_panel_report_sha256:
            raise ReviewedPanelError("reviewed panel source report binding changed")
        if _sha256(self.report_payload) != self.report_sha256:
            raise ReviewedPanelError("verified reviewed panel report payload changed")
        report = loads(self.report_payload)
        if not isinstance(report, dict) or not isinstance(report.get("evidence"), dict):
            raise ReviewedPanelError("verified reviewed panel evidence is invalid")
        if (
            report.get("review_packet_id") != self.review_packet_id
            or report["evidence"].get("source_panel_report_sha256")
            != self.source_panel_report_sha256
        ):
            raise ReviewedPanelError("verified reviewed panel evidence binding changed")
        if (
            report["evidence"].get("scoring_protocol_amendment_sha256")
            != self.scoring_protocol_amendment_sha256
        ):
            raise ReviewedPanelError("verified reviewed panel amendment binding changed")
        if (
            report["evidence"].get("diagnostic_completed_artifact_sha256")
            != self.diagnostic_completed_artifact_sha256
            or report["evidence"].get("gold_completed_artifact_sha256")
            != self.gold_completed_artifact_sha256
        ):
            raise ReviewedPanelError("verified reviewed panel artifact binding changed")
        if (
            report["evidence"].get("human_roster_anchor_sha256")
            != self.human_roster_anchor_sha256
        ):
            raise ReviewedPanelError("verified reviewed panel roster binding changed")

    @property
    def report(self) -> dict[str, Any]:
        self.assert_verified()
        value = loads(self.report_payload)
        if not isinstance(value, dict):
            raise ReviewedPanelError("verified reviewed panel report is not an object")
        return value


def evaluate_reviewed_stage1_panel(
    panel: VerifiedStage1Panel,
    *,
    expected_packet_id: str,
    expected_scoring_protocol_amendment_sha256: str,
    diagnostic_review_artifact: dict[str, Any] | None = None,
    gold_review_artifact: dict[str, Any] | None = None,
    human_roster_anchor: dict[str, Any] | None = None,
) -> VerifiedReviewedStage1Panel:
    """Verify completed panel reviews, project them by system, and apply gates."""

    if not isinstance(panel, VerifiedStage1Panel):
        raise TypeError("panel must be a VerifiedStage1Panel")
    panel.assert_verified()
    packet_id = _digest(expected_packet_id, label="expected_packet_id")
    amendment_sha256 = _digest(
        expected_scoring_protocol_amendment_sha256,
        label="expected_scoring_protocol_amendment_sha256",
    )
    if (diagnostic_review_artifact is None) != (gold_review_artifact is None):
        raise ReviewedPanelError(
            "both diagnostic and gold review artifacts are required for completed review"
        )
    panel_report = panel.report
    thresholds = panel_report["thresholds"]
    if diagnostic_review_artifact is None:
        results = {
            evaluation.system_id: {
                "predictions_sha256": evaluation.predictions_sha256,
                "human_metrics": None,
                "gate": copy.deepcopy(
                    panel_report["results"][evaluation.system_id]["gate"]
                ),
            }
            for evaluation in panel.evaluations
        }
        report = {
            "schema_version": "1.0",
            "stage": 1,
            "status": "PILOT_UNADJUDICATED",
            "human_review_status": "PENDING_HUMAN_REVIEW",
            "stage2_eligible": False,
            "review_packet_id": packet_id,
            "system_count": len(panel.evaluations),
            "systems": [evaluation.system_id for evaluation in panel.evaluations],
            "evidence": {
                "source_panel_report_sha256": panel.report_sha256,
                "scoring_protocol_amendment_sha256": amendment_sha256,
                "diagnostic_public_packet_sha256": None,
                "gold_public_packet_sha256": None,
                "human_roster_anchor_sha256": None,
                "diagnostic_completed_artifact_sha256": None,
                "gold_completed_artifact_sha256": None,
            },
            "gold_review_metrics": None,
            "results": results,
        }
        payload = _canonical_json(report)
        return VerifiedReviewedStage1Panel(
            source_panel=panel,
            source_panel_report_sha256=panel.report_sha256,
            scoring_protocol_amendment_sha256=amendment_sha256,
            review_packet_id=packet_id,
            human_roster_anchor_sha256=None,
            diagnostic_completed_artifact_sha256=None,
            gold_completed_artifact_sha256=None,
            report_payload=payload,
            report_sha256=_sha256(payload),
            _attestation=_ATTESTATION,
        )

    assert gold_review_artifact is not None
    if human_roster_anchor is None:
        raise ReviewedPanelError(
            "completed review requires the pre-review human roster anchor"
        )
    diagnostic_snapshot, diagnostic_artifact_sha256 = _snapshot_artifact(
        diagnostic_review_artifact,
        label="completed diagnostic review artifact",
    )
    gold_snapshot, gold_artifact_sha256 = _snapshot_artifact(
        gold_review_artifact,
        label="completed gold review artifact",
    )
    try:
        panel_diagnostic_metrics = verify_completed_diagnostic_review_artifact(
            diagnostic_snapshot,
            expected_packet_id=packet_id,
            human_roster_anchor=human_roster_anchor,
        )
        gold_metrics = verify_completed_gold_review_artifact(
            gold_snapshot,
            expected_packet_id=packet_id,
            human_roster_anchor=human_roster_anchor,
        )
    except (ReviewPacketError, TypeError, ValueError) as error:
        raise ReviewedPanelError(str(error)) from error

    diagnostic_roster_anchor_sha256 = diagnostic_snapshot["source_manifest"][
        "human_roster_anchor_sha256"
    ]
    gold_roster_anchor_sha256 = gold_snapshot["source_manifest"][
        "human_roster_anchor_sha256"
    ]
    if diagnostic_roster_anchor_sha256 != gold_roster_anchor_sha256:
        raise ReviewedPanelError(
            "completed reviews are bound to different human roster anchors"
        )
    roster_anchor_sha256 = _digest(
        diagnostic_roster_anchor_sha256,
        label="packet-bound human_roster_anchor_sha256",
    )
    _require_panel_report_binding(
        panel,
        diagnostic_snapshot,
        gold_snapshot,
        expected_scoring_protocol_amendment_sha256=amendment_sha256,
    )
    _assert_gold_projection_matches_panel(panel, gold_snapshot)

    evaluations = {evaluation.system_id: evaluation for evaluation in panel.evaluations}
    if len(evaluations) != len(panel.evaluations):
        raise ReviewedPanelError("verified panel contains duplicate system identities")
    raw_bindings = diagnostic_snapshot["private_packet"]["system_bindings"]
    bindings = {item["system_id"]: item for item in raw_bindings}
    if set(bindings) != set(evaluations):
        raise ReviewedPanelError(
            "completed diagnostic review system panel differs from the verified panel"
        )
    expected_total_predictions = sum(
        len(evaluation.predictions) for evaluation in panel.evaluations
    )
    if (
        diagnostic_snapshot["private_packet"]["total_prediction_count"]
        != expected_total_predictions
    ):
        raise ReviewedPanelError(
            "completed diagnostic review prediction count differs from the verified panel"
        )

    results: dict[str, Any] = {}
    projected_review_count = 0
    for system_id in sorted(evaluations):
        evaluation = evaluations[system_id]
        binding = bindings[system_id]
        prediction_count = len(evaluation.predictions)
        change_count = sum(
            prediction["decision"] == "CHANGE"
            for prediction in evaluation.predictions
        )
        if (
            binding["prediction_count"] != prediction_count
            or binding["change_count"] != change_count
        ):
            raise ReviewedPanelError(
                f"completed diagnostic counts differ for system: {system_id}"
            )
        try:
            projected = verify_completed_diagnostic_review_artifact(
                diagnostic_snapshot,
                expected_packet_id=packet_id,
                system_id=system_id,
                expected_predictions_sha256=evaluation.predictions_sha256,
                human_roster_anchor=human_roster_anchor,
            )
        except (ReviewPacketError, TypeError, ValueError) as error:
            raise ReviewedPanelError(str(error)) from error
        if projected["reviewed_prediction_count"] != change_count:
            raise ReviewedPanelError(
                f"completed diagnostic projection is incomplete for system: {system_id}"
            )
        projected_review_count += projected["reviewed_prediction_count"]
        human_metrics = {
            **projected,
            "prediction_count": prediction_count,
            "change_count": change_count,
        }
        gate = _evaluate_stage1_gate_with_verified_reviews(
            evaluation.gate_metrics,
            thresholds,
            human_review=human_metrics,
            human_gold_review=gold_metrics,
        )
        gate["verified_evidence"] = {
            **_verified_evaluation_evidence(evaluation),
            "source_panel_report_sha256": panel.report_sha256,
            "scoring_protocol_amendment_sha256": amendment_sha256,
            "review_packet_id": packet_id,
            "diagnostic_public_packet_sha256": projected["public_packet_sha256"],
            "gold_public_packet_sha256": gold_metrics["public_packet_sha256"],
        }
        results[system_id] = {
            "predictions_sha256": evaluation.predictions_sha256,
            "human_metrics": human_metrics,
            "gate": gate,
        }

    if projected_review_count != panel_diagnostic_metrics["reviewed_prediction_count"]:
        raise ReviewedPanelError("per-system diagnostic projections are not disjoint and complete")

    all_eligible = all(item["gate"]["stage2_eligible"] for item in results.values())
    if not gold_metrics["human_gold_approved"]:
        status = "GOLD_REVIEW_REQUIRES_REPAIR"
    elif all_eligible:
        status = "PASS"
    else:
        status = "FAIL"
    report = {
        "schema_version": "1.0",
        "stage": 1,
        "status": status,
        "human_review_status": "COMPLETE",
        "stage2_eligible": all_eligible,
        "review_packet_id": packet_id,
        "system_count": len(panel.evaluations),
        "systems": sorted(evaluations),
        "system_pass_count": sum(
            item["gate"]["stage2_eligible"] for item in results.values()
        ),
        "system_fail_count": sum(
            not item["gate"]["stage2_eligible"] for item in results.values()
        ),
        "evidence": {
            "source_panel_report_sha256": panel.report_sha256,
            "scoring_protocol_amendment_sha256": amendment_sha256,
            "diagnostic_public_packet_sha256": panel_diagnostic_metrics[
                "public_packet_sha256"
            ],
            "gold_public_packet_sha256": gold_metrics["public_packet_sha256"],
            "human_roster_anchor_sha256": roster_anchor_sha256,
            "diagnostic_completed_artifact_sha256": diagnostic_artifact_sha256,
            "gold_completed_artifact_sha256": gold_artifact_sha256,
        },
        "gold_review_metrics": gold_metrics,
        "results": results,
    }
    payload = _canonical_json(report)
    return VerifiedReviewedStage1Panel(
        source_panel=panel,
        source_panel_report_sha256=panel.report_sha256,
        scoring_protocol_amendment_sha256=amendment_sha256,
        review_packet_id=packet_id,
        human_roster_anchor_sha256=roster_anchor_sha256,
        diagnostic_completed_artifact_sha256=diagnostic_artifact_sha256,
        gold_completed_artifact_sha256=gold_artifact_sha256,
        report_payload=payload,
        report_sha256=_sha256(payload),
        _attestation=_ATTESTATION,
    )
