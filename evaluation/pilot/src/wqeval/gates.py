"""Preregistered eligibility gates."""

from __future__ import annotations

import math
from typing import Any

from .evaluation import VerifiedStage1Evaluation


_MINIMUMS = {
    "schema_compliance": "schema_compliance_min",
    "positive_opportunities": "positive_opportunities_min",
    "keep_opportunities": "keep_opportunities_min",
    "precision": "exact_precision_min",
    "recall": "exact_recall_min",
    "keep_accuracy": "keep_accuracy_min",
}
_MAXIMUMS = {"critical_miss_rate": "critical_miss_rate_max"}
_HUMAN_MAXIMUMS = {"critical_meaning_risk": "critical_meaning_risk_max"}
_SLICE_DIMENSIONS = ("by_genre", "by_author_type", "by_author_profile")
_RATIO_METRICS = {
    "schema_compliance",
    "precision",
    "recall",
    "keep_accuracy",
    "critical_miss_rate",
}
_COUNT_METRICS = {"positive_opportunities", "keep_opportunities"}
_RATIO_THRESHOLDS = {
    "schema_compliance_min",
    "exact_precision_min",
    "exact_recall_min",
    "keep_accuracy_min",
    "critical_miss_rate_max",
}
_COUNT_THRESHOLDS = {
    "positive_opportunities_min",
    "keep_opportunities_min",
    "critical_meaning_risk_max",
}
_DIAGNOSTIC_VERDICT_FIELDS = (
    "finding_valid",
    "span_valid",
    "problem_valid",
    "context_valid",
    "severity_valid",
    "operation_valid",
)


def _finite_number(mapping: dict[str, Any], key: str, label: str) -> int | float:
    if key not in mapping:
        raise ValueError(f"{label} is missing required field: {key}")
    value = mapping[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label}.{key} must be a finite number")
    return value


def _ratio(mapping: dict[str, Any], key: str, label: str) -> int | float:
    value = _finite_number(mapping, key, label)
    if value < 0 or value > 1:
        raise ValueError(f"{label}.{key} must be between 0 and 1")
    return value


def _count(mapping: dict[str, Any], key: str, label: str) -> int:
    if key not in mapping:
        raise ValueError(f"{label} is missing required field: {key}")
    value = mapping[key]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label}.{key} must be a nonnegative integer")
    return value


def _validate_gate_inputs(
    metrics: dict[str, Any],
    thresholds: dict[str, Any],
) -> tuple[int | float | None, int | float | None]:
    if not isinstance(metrics, dict) or not isinstance(thresholds, dict):
        raise ValueError("metrics and thresholds must be objects")
    for metric_name in _RATIO_METRICS:
        _ratio(metrics, metric_name, "metrics")
    for metric_name in _COUNT_METRICS:
        _count(metrics, metric_name, "metrics")
    for threshold_name in _RATIO_THRESHOLDS:
        _ratio(thresholds, threshold_name, "thresholds")
    for threshold_name in _COUNT_THRESHOLDS:
        _count(thresholds, threshold_name, "thresholds")
    if thresholds.get("human_gold_adjudication_required") is not True:
        raise ValueError("thresholds.human_gold_adjudication_required must be the boolean true")

    caller_human_metric = metrics.get("critical_meaning_risk")
    if caller_human_metric is not None:
        _count(metrics, "critical_meaning_risk", "metrics")

    slice_threshold_names = (
        "sized_slice_positive_opportunities_min",
        "sized_slice_precision_min",
    )
    slice_threshold_presence = [name in thresholds for name in slice_threshold_names]
    if any(slice_threshold_presence) and not all(slice_threshold_presence):
        raise ValueError("both sized-slice thresholds are required when slice gating is enabled")
    if not any(slice_threshold_presence):
        return None, None

    slice_minimum_opportunities = _count(thresholds, slice_threshold_names[0], "thresholds")
    slice_precision_min = _ratio(thresholds, slice_threshold_names[1], "thresholds")
    for dimension in _SLICE_DIMENSIONS:
        if dimension not in metrics or not isinstance(metrics[dimension], dict):
            raise ValueError(f"metrics is missing required slice dimension: {dimension}")
        for name, bundle in metrics[dimension].items():
            if not isinstance(name, str) or not name or not isinstance(bundle, dict):
                raise ValueError(f"metrics.{dimension} contains an invalid slice bundle")
            opportunities = _count(bundle, "positive_opportunities", f"metrics.{dimension}.{name}")
            if "precision" not in bundle:
                raise ValueError(f"metrics.{dimension}.{name} is missing required field: precision")
            precision = bundle["precision"]
            if precision is not None:
                _ratio(bundle, "precision", f"metrics.{dimension}.{name}")
            elif opportunities >= slice_minimum_opportunities:
                raise ValueError(f"metrics.{dimension}.{name}.precision cannot be null for a sized slice")
    return slice_minimum_opportunities, slice_precision_min


def _evaluate_stage1_gate_metrics(
    metrics: dict[str, Any],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate objective Stage 1 metrics while keeping every human gate pending."""

    return _evaluate_stage1_gate_with_verified_reviews(
        metrics,
        thresholds,
        human_review=None,
        human_gold_review=None,
    )


def _evaluate_stage1_gate_with_verified_reviews(
    metrics: dict[str, Any],
    thresholds: dict[str, Any],
    *,
    human_review: dict[str, Any] | None,
    human_gold_review: dict[str, Any] | None,
) -> dict[str, Any]:
    """Apply gates to review metrics already verified against detached evidence."""

    slice_minimum_opportunities, slice_precision_min = _validate_gate_inputs(metrics, thresholds)
    human_complete_acceptance_rate: int | float | None = None
    human_component_acceptance_rates: dict[str, int | float | None] | None = None
    human_reviewed_count = 0
    if human_review is not None:
        if (
            not isinstance(human_review, dict)
            or human_review.get("review_structure_verified") is not True
            or human_review.get("human_identity_attested") is not True
            or human_review.get("human_review_verified") is not True
            or human_review.get("human_adjudicated") is not True
        ):
            raise ValueError("human_review must contain verified, adjudicated review metrics")
        _count(human_review, "critical_meaning_risk", "human_review")
        human_reviewed_count = _count(
            human_review,
            "meaning_reviewed_suggestions",
            "human_review",
        )
        raw_complete_rate = human_review.get("human_complete_acceptance_rate")
        raw_legacy_rate = human_review.get("human_finding_acceptance_rate")
        raw_component_rates = human_review.get("human_component_acceptance_rates")
        if not isinstance(raw_component_rates, dict) or set(raw_component_rates) != set(
            _DIAGNOSTIC_VERDICT_FIELDS
        ):
            raise ValueError(
                "human_review.human_component_acceptance_rates fields are invalid"
            )
        if human_reviewed_count == 0:
            if raw_complete_rate is not None or raw_legacy_rate is not None or any(
                value is not None for value in raw_component_rates.values()
            ):
                raise ValueError(
                    "human review acceptance rates must be null when no findings were reviewed"
                )
        else:
            human_complete_acceptance_rate = _ratio(
                human_review,
                "human_complete_acceptance_rate",
                "human_review",
            )
            legacy_rate = _ratio(
                human_review,
                "human_finding_acceptance_rate",
                "human_review",
            )
            if legacy_rate != human_complete_acceptance_rate:
                raise ValueError(
                    "human_review finding and complete acceptance rates must match"
                )
            for field in _DIAGNOSTIC_VERDICT_FIELDS:
                _ratio(
                    raw_component_rates,
                    field,
                    "human_review.human_component_acceptance_rates",
                )
        human_component_acceptance_rates = dict(raw_component_rates)
    if human_gold_review is not None:
        if (
            not isinstance(human_gold_review, dict)
            or human_gold_review.get("gold_review_structure_verified") is not True
            or human_gold_review.get("human_identity_attested") is not True
            or human_gold_review.get("human_gold_review_verified") is not True
            or human_gold_review.get("human_gold_adjudicated") is not True
            or type(human_gold_review.get("human_gold_approved")) is not bool
        ):
            raise ValueError("human_gold_review must contain verified, adjudicated gold metrics")
    human_adjudicated = human_review is not None
    human_gold_adjudicated = human_gold_review is not None
    human_gold_approved = bool(human_gold_review and human_gold_review["human_gold_approved"])

    failed: dict[str, dict[str, Any]] = {}
    pending: dict[str, dict[str, Any]] = {}
    for metric_name, threshold_name in _MINIMUMS.items():
        observed = metrics[metric_name]
        threshold = thresholds[threshold_name]
        if observed < threshold:
            failed[metric_name] = {"operator": ">=", "threshold": threshold, "observed": observed}
    for metric_name, threshold_name in _MAXIMUMS.items():
        observed = metrics[metric_name]
        threshold = thresholds[threshold_name]
        if observed > threshold:
            failed[metric_name] = {"operator": "<=", "threshold": threshold, "observed": observed}
    for metric_name, threshold_name in _HUMAN_MAXIMUMS.items():
        threshold = thresholds[threshold_name]
        if human_review is None:
            pending[metric_name] = {
                "reason": "requires two independent human reviews and separate human adjudication",
                "threshold": threshold,
                "observed": None,
            }
            continue
        observed = human_review[metric_name]
        if observed > threshold:
            failed[metric_name] = {"operator": "<=", "threshold": threshold, "observed": observed}

    diagnostic_acceptance_threshold = thresholds["exact_precision_min"]
    if human_review is None:
        pending["human_complete_acceptance_rate"] = {
            "reason": "requires two independent human reviews and separate human adjudication",
            "threshold": diagnostic_acceptance_threshold,
            "observed": None,
        }
    elif human_reviewed_count and human_complete_acceptance_rate < diagnostic_acceptance_threshold:
        failed["human_complete_acceptance_rate"] = {
            "operator": ">=",
            "threshold": diagnostic_acceptance_threshold,
            "observed": human_complete_acceptance_rate,
        }

    if not human_gold_adjudicated:
        pending["human_gold_adjudication"] = {
            "reason": "requires two independent human gold reviews and separate human adjudication",
            "required": True,
            "observed": None,
        }

    if slice_minimum_opportunities is not None and slice_precision_min is not None:
        for dimension in _SLICE_DIMENSIONS:
            for name, bundle in metrics[dimension].items():
                if bundle["positive_opportunities"] < slice_minimum_opportunities:
                    continue
                observed = bundle["precision"]
                key = f"{dimension}.{name}.precision"
                if observed < slice_precision_min:
                    failed[key] = {
                        "operator": ">=",
                        "threshold": slice_precision_min,
                        "observed": observed,
                    }
    objective_pass = not failed
    if not objective_pass:
        status = "FAIL"
    elif human_gold_adjudicated and not human_gold_approved:
        status = "GOLD_REVIEW_REQUIRES_REPAIR"
    elif pending or not human_adjudicated or not human_gold_adjudicated:
        status = "PENDING_HUMAN_REVIEW"
    else:
        status = "PASS"
    stage2_eligible = (
        objective_pass
        and human_adjudicated
        and human_gold_adjudicated
        and human_gold_approved
        and not pending
    )
    return {
        "objective_pass": objective_pass,
        "human_adjudicated": human_adjudicated,
        "human_review_verified": human_adjudicated,
        "human_gold_adjudicated": human_gold_adjudicated,
        "human_gold_review_verified": human_gold_adjudicated,
        "human_gold_approved": human_gold_approved,
        "human_complete_acceptance_rate": human_complete_acceptance_rate,
        "human_component_acceptance_rates": human_component_acceptance_rates,
        "stage2_eligible": stage2_eligible,
        "status": status,
        "failed_conditions": failed,
        "pending_conditions": pending,
    }


def evaluate_stage1_gate(
    evaluation: VerifiedStage1Evaluation,
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    """Evaluate objective evidence; only reviewed_panel may unlock human gates."""

    if not isinstance(evaluation, VerifiedStage1Evaluation):
        raise TypeError("evaluation must be a VerifiedStage1Evaluation")
    evaluation.assert_verified()
    result = _evaluate_stage1_gate_metrics(
        evaluation.gate_metrics,
        thresholds,
    )
    result["verified_evidence"] = {
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
    return result
