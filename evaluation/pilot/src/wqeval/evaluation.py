"""Evidence-bound Stage 1 repeated-run evaluation."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any

from .corpus_evidence import VerifiedScoringCorpus
from .reconciliation import reconcile_stage1_outputs
from .scoring import exact_finding_key, score_stage1
from .strict_json import loads, loads_jsonl
from .validation import validate_case, validate_finding


class EvaluationEvidenceError(RuntimeError):
    """Raised when output and corpus evidence cannot form one exact evaluation."""


_ATTESTATION = object()
_SLICE_DIMENSIONS = ("by_genre", "by_author_type", "by_author_profile")


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _canonical_jsonl(records: list[dict[str, Any]]) -> bytes:
    return b"".join(_canonical_json(item) for item in records)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _case_index(records: list[dict[str, Any]], *, label: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for source_case in records:
        validate_case(source_case)
        case_id = source_case["case_id"]
        if case_id in indexed:
            raise EvaluationEvidenceError(f"{label} contains duplicate case: {case_id}")
        indexed[case_id] = source_case
    return indexed


def _worst_min(per_run: list[dict[str, Any]], key: str, *, invalid: bool) -> float:
    if invalid or not per_run:
        return 0.0
    values = [item.get(key) for item in per_run]
    return min(float(value) if value is not None else 0.0 for value in values)


def _worst_max(
    per_run: list[dict[str, Any]],
    key: str,
    *,
    invalid: bool,
    undefined_default: float,
) -> float:
    if invalid or not per_run:
        return 1.0
    values = [item.get(key) for item in per_run]
    return max(float(value) if value is not None else undefined_default for value in values)


@dataclass(frozen=True)
class VerifiedStage1Evaluation:
    """Immutable projection derived from verified corpus and output evidence."""

    system_id: str
    expected_runs: int
    run_numbers: tuple[int, ...]
    valid_run_numbers: tuple[int, ...]
    invalid_run_numbers: tuple[int, ...]
    output_evidence_sha256: str
    corpus_freeze_manifest_sha256: str
    cases_sha256: str
    gold_sha256: str
    model_settings_sha256: str
    predictions_sha256: str
    gate_metrics_sha256: str
    gate_metrics_payload: bytes = field(repr=False)
    report_metrics_payload: bytes = field(repr=False)
    model_settings_payload: bytes = field(repr=False)
    predictions_payload: bytes = field(repr=False)
    cases_payload: bytes = field(repr=False)
    gold_payload: bytes = field(repr=False)
    _attestation: object = field(repr=False, compare=False)

    def assert_verified(self) -> None:
        if self._attestation is not _ATTESTATION:
            raise EvaluationEvidenceError("evaluation was not created by the verified builder")
        if _sha256(self.cases_payload) != self.cases_sha256:
            raise EvaluationEvidenceError("verified evaluation case payload changed")
        if _sha256(self.gold_payload) != self.gold_sha256:
            raise EvaluationEvidenceError("verified evaluation gold payload changed")
        if _sha256(self.predictions_payload) != self.predictions_sha256:
            raise EvaluationEvidenceError("verified evaluation prediction payload changed")
        if _sha256(self.gate_metrics_payload) != self.gate_metrics_sha256:
            raise EvaluationEvidenceError("verified evaluation metric payload changed")
        if _sha256(self.model_settings_payload) != self.model_settings_sha256:
            raise EvaluationEvidenceError("verified evaluation model settings payload changed")

    @property
    def gate_metrics(self) -> dict[str, Any]:
        self.assert_verified()
        value = loads(self.gate_metrics_payload)
        if not isinstance(value, dict):
            raise EvaluationEvidenceError("verified gate metrics are not an object")
        return value

    @property
    def report_metrics(self) -> dict[str, Any]:
        self.assert_verified()
        value = loads(self.report_metrics_payload)
        if not isinstance(value, dict):
            raise EvaluationEvidenceError("verified report metrics are not an object")
        return value

    @property
    def predictions(self) -> tuple[dict[str, Any], ...]:
        self.assert_verified()
        return tuple(loads_jsonl(self.predictions_payload, source_name="verified evaluation predictions"))

    @property
    def cases(self) -> tuple[dict[str, Any], ...]:
        self.assert_verified()
        return tuple(loads_jsonl(self.cases_payload, source_name="verified evaluation cases"))

    @property
    def gold(self) -> tuple[dict[str, Any], ...]:
        self.assert_verified()
        return tuple(loads_jsonl(self.gold_payload, source_name="verified evaluation gold"))


def build_verified_stage1_evaluation(
    corpus: VerifiedScoringCorpus,
    *,
    run_root: str | Path,
    expected_output_evidence_sha256: str,
    system_id: str,
    expected_runs: int,
) -> VerifiedStage1Evaluation:
    """Reconstruct all repeated runs and derive conservative, worst-run gate metrics."""

    if not isinstance(corpus, VerifiedScoringCorpus):
        raise EvaluationEvidenceError("corpus must be detached-hash-verified evidence")
    corpus.assert_verified()
    if not isinstance(system_id, str) or not system_id:
        raise EvaluationEvidenceError("system_id must be non-empty text")
    if isinstance(expected_runs, bool) or not isinstance(expected_runs, int) or expected_runs < 1:
        raise EvaluationEvidenceError("expected_runs must be a positive integer")
    try:
        corpus_cases = list(corpus.cases)
        corpus_gold = list(corpus.gold)
        corpus_case_by_id = _case_index(corpus_cases, label="frozen corpus case panel")
        for gold_finding in corpus_gold:
            source_case = corpus_case_by_id.get(gold_finding.get("case_id"))
            if source_case is None:
                raise EvaluationEvidenceError(
                    f"gold finding references unknown case: {gold_finding.get('case_id')}"
                )
            validate_finding(gold_finding, source_case)

        reconciliation = reconcile_stage1_outputs(
            run_root,
            expected_output_evidence_sha256=expected_output_evidence_sha256,
        )
        selected = [run for run in reconciliation["runs"] if run.system_id == system_id]
        by_run: dict[int, Any] = {}
        for run in selected:
            if run.run_number in by_run:
                raise EvaluationEvidenceError("verified output contains a duplicate system-run")
            by_run[run.run_number] = run
        expected_panel = set(range(1, expected_runs + 1))
        if set(by_run) != expected_panel:
            raise EvaluationEvidenceError("verified output does not contain the exact repeated-run panel")

        per_run: dict[str, dict[str, Any]] = {}
        valid_metrics: list[dict[str, Any]] = []
        all_predictions: list[dict[str, Any]] = []
        predictions_by_run: dict[int, list[dict[str, Any]]] = {}
        invalid_run_numbers: list[int] = []
        model_payloads = {run.model_payload for run in by_run.values()}
        if len(model_payloads) != 1:
            raise EvaluationEvidenceError("repeated runs do not use identical model settings")
        model_settings_payload = next(iter(model_payloads))
        for run_number in sorted(by_run):
            run = by_run[run_number]
            run_cases = list(run.cases)
            if _case_index(run_cases, label=f"run {run_number} case panel") != corpus_case_by_id:
                raise EvaluationEvidenceError(
                    f"run {run_number} case panel differs from the detached frozen corpus"
                )
            if run.status == "invalid":
                invalid_run_numbers.append(run_number)
                per_run[str(run_number)] = {
                    "status": "invalid",
                    "error_type": run.error_type,
                    "error_message": run.error_message,
                }
                continue
            if run.status != "valid":
                raise EvaluationEvidenceError(f"run {run_number} has an invalid evidence status")
            predictions = list(run.predictions)
            predictions_by_run[run_number] = predictions
            for prediction in predictions:
                source_case = corpus_case_by_id.get(prediction.get("case_id"))
                if source_case is None:
                    raise EvaluationEvidenceError(
                        f"prediction references unknown case: {prediction.get('case_id')}"
                    )
                if prediction.get("system_id") != system_id or prediction.get("run_number") != run_number:
                    raise EvaluationEvidenceError("prediction identity differs from verified run identity")
                validate_finding(prediction, source_case)
            metrics = score_stage1(corpus_cases, corpus_gold, predictions)
            per_run[str(run_number)] = {"status": "valid", **metrics}
            valid_metrics.append(metrics)
            all_predictions.extend(predictions)

        has_invalid = bool(invalid_run_numbers)
        positive_opportunities = sum(item.get("decision") == "CHANGE" for item in corpus_gold)
        keep_opportunities = sum(item.get("decision") == "KEEP" for item in corpus_gold)
        gate_metrics: dict[str, Any] = {
            "aggregation_policy": "worst_run",
            "schema_compliance": (expected_runs - len(invalid_run_numbers)) / expected_runs,
            "positive_opportunities": positive_opportunities,
            "keep_opportunities": keep_opportunities,
            "precision": _worst_min(valid_metrics, "precision", invalid=has_invalid),
            "recall": _worst_min(valid_metrics, "recall", invalid=has_invalid),
            "keep_accuracy": _worst_min(valid_metrics, "keep_accuracy", invalid=has_invalid),
            "critical_miss_rate": _worst_max(
                valid_metrics,
                "critical_miss_rate",
                invalid=has_invalid,
                undefined_default=0.0,
            ),
            "critical_meaning_risk": None,
        }
        for dimension in _SLICE_DIMENSIONS:
            expected_names: dict[str, dict[str, int]] = {}
            field_name = {
                "by_genre": "genre",
                "by_author_type": "author_type",
                "by_author_profile": "author_profile",
            }[dimension]
            for name in sorted({item[field_name] for item in corpus_cases}):
                identifiers = {
                    item["case_id"] for item in corpus_cases if item[field_name] == name
                }
                expected_names[name] = {
                    "case_count": len(identifiers),
                    "positive_opportunities": sum(
                        item.get("decision") == "CHANGE" and item.get("case_id") in identifiers
                        for item in corpus_gold
                    ),
                }
            bundles: dict[str, dict[str, Any]] = {}
            for name, expected in expected_names.items():
                values = [metrics[dimension][name]["precision"] for metrics in valid_metrics]
                if expected["positive_opportunities"] == 0:
                    precision = None
                elif has_invalid:
                    precision = 0.0
                else:
                    precision = min(float(value) if value is not None else 0.0 for value in values)
                bundles[name] = {**expected, "precision": precision}
            gate_metrics[dimension] = bundles

        all_predictions.sort(
            key=lambda item: (
                item.get("run_number", 0),
                item.get("case_id", ""),
                item.get("finding_id", ""),
            )
        )
        predictions_payload = _canonical_jsonl(all_predictions)
        gate_payload = _canonical_json(gate_metrics)
        gold_counter = Counter(
            exact_finding_key(item) for item in corpus_gold if item.get("decision") == "CHANGE"
        )
        gold_occurrences = [
            (key, occurrence)
            for key in sorted(gold_counter, key=lambda value: tuple(str(part) for part in value))
            for occurrence in range(1, gold_counter[key] + 1)
        ]
        match_counters = {
            run_number: Counter(
                exact_finding_key(item)
                for item in predictions_by_run.get(run_number, [])
                if item.get("decision") == "CHANGE"
            )
            for run_number in sorted(expected_panel)
        }
        if invalid_run_numbers:
            pass_at_1 = None
            pass_at_3_any = None
            pass_power_3 = None
            repeat_undefined = "one or more runs failed schema validation"
        elif not gold_occurrences:
            pass_at_1 = None
            pass_at_3_any = None
            pass_power_3 = None
            repeat_undefined = "no gold CHANGE findings"
        else:
            denominator = len(gold_occurrences)
            pass_at_1 = sum(
                match_counters[1][key] >= occurrence for key, occurrence in gold_occurrences
            ) / denominator
            pass_at_3_any = sum(
                any(match_counters[run][key] >= occurrence for run in expected_panel)
                for key, occurrence in gold_occurrences
            ) / denominator
            pass_power_3 = sum(
                all(match_counters[run][key] >= occurrence for run in expected_panel)
                for key, occurrence in gold_occurrences
            ) / denominator
            repeat_undefined = None
        defined_precisions = [
            metrics["precision"] for metrics in valid_metrics if metrics["precision"] is not None
        ]
        defined_recalls = [
            metrics["recall"] for metrics in valid_metrics if metrics["recall"] is not None
        ]
        report_metrics = {
            "schema_version": "1.0",
            "system_id": system_id,
            "aggregation_policy": "worst_run",
            "output_evidence_sha256": expected_output_evidence_sha256,
            "corpus_freeze_manifest_sha256": corpus.freeze_manifest_sha256,
            "cases_sha256": corpus.cases_sha256,
            "gold_sha256": corpus.gold_sha256,
            "model_settings_sha256": _sha256(model_settings_payload),
            "run_numbers": sorted(expected_panel),
            "valid_run_numbers": sorted(expected_panel - set(invalid_run_numbers)),
            "invalid_run_numbers": invalid_run_numbers,
            "pass_at_1": pass_at_1,
            "pass_at_3_any": pass_at_3_any,
            "pass_power_3": pass_power_3,
            "undefined_repeat_metrics": repeat_undefined,
            "mean_exact_precision": (
                sum(defined_precisions) / len(defined_precisions) if defined_precisions else None
            ),
            "mean_exact_recall": (
                sum(defined_recalls) / len(defined_recalls) if defined_recalls else None
            ),
            "exact_precision_range": (
                {"min": min(defined_precisions), "max": max(defined_precisions)}
                if defined_precisions
                else None
            ),
            "exact_recall_range": (
                {"min": min(defined_recalls), "max": max(defined_recalls)}
                if defined_recalls
                else None
            ),
            "gate_metrics": gate_metrics,
            "per_run": per_run,
        }
        return VerifiedStage1Evaluation(
            system_id=system_id,
            expected_runs=expected_runs,
            run_numbers=tuple(sorted(expected_panel)),
            valid_run_numbers=tuple(sorted(expected_panel - set(invalid_run_numbers))),
            invalid_run_numbers=tuple(invalid_run_numbers),
            output_evidence_sha256=expected_output_evidence_sha256,
            corpus_freeze_manifest_sha256=corpus.freeze_manifest_sha256,
            cases_sha256=corpus.cases_sha256,
            gold_sha256=corpus.gold_sha256,
            model_settings_sha256=_sha256(model_settings_payload),
            predictions_sha256=_sha256(predictions_payload),
            gate_metrics_sha256=_sha256(gate_payload),
            gate_metrics_payload=gate_payload,
            report_metrics_payload=_canonical_json(report_metrics),
            model_settings_payload=model_settings_payload,
            predictions_payload=predictions_payload,
            cases_payload=corpus.cases_payload,
            gold_payload=corpus.gold_payload,
            _attestation=_ATTESTATION,
        )
    except EvaluationEvidenceError:
        raise
    except Exception as exc:
        raise EvaluationEvidenceError(str(exc)) from exc
