"""Evidence-bound Stage 1 panel reporting across every frozen system."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any

from .corpus_evidence import VerifiedScoringCorpus
from .evaluation import VerifiedStage1Evaluation, build_verified_stage1_evaluation
from .gates import evaluate_stage1_gate
from .output_evidence import verify_stage1_output_evidence
from .strict_json import loads


class PanelEvidenceError(ValueError):
    """Raised when the complete Stage 1 system panel is inconsistent."""


_ATTESTATION = object()


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
        raise PanelEvidenceError("panel report must be finite JSON data") from error


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class VerifiedStage1Panel:
    """Complete system panel reconstructed from two detached evidence roots."""

    evaluations: tuple[VerifiedStage1Evaluation, ...]
    report_payload: bytes = field(repr=False)
    report_sha256: str
    _attestation: object = field(repr=False, compare=False)

    def assert_verified(self) -> None:
        if self._attestation is not _ATTESTATION:
            raise PanelEvidenceError("panel was not created by the verified builder")
        if _sha256(self.report_payload) != self.report_sha256:
            raise PanelEvidenceError("verified panel report payload changed")
        for evaluation in self.evaluations:
            evaluation.assert_verified()

    @property
    def report(self) -> dict[str, Any]:
        self.assert_verified()
        value = loads(self.report_payload)
        if not isinstance(value, dict):
            raise PanelEvidenceError("verified panel report is not an object")
        return value

    @property
    def predictions(self) -> tuple[dict[str, Any], ...]:
        self.assert_verified()
        return tuple(
            prediction
            for evaluation in self.evaluations
            for prediction in evaluation.predictions
        )


def build_verified_stage1_panel(
    corpus: VerifiedScoringCorpus,
    *,
    run_root: str | Path,
    expected_output_evidence_sha256: str,
    expected_runs: int,
    thresholds: dict[str, Any],
    expected_systems: int | None = None,
) -> VerifiedStage1Panel:
    """Infer every system from frozen output evidence and produce a pending-human report."""

    if not isinstance(corpus, VerifiedScoringCorpus):
        raise PanelEvidenceError("corpus must be detached-hash-verified evidence")
    corpus.assert_verified()
    if isinstance(expected_runs, bool) or not isinstance(expected_runs, int) or expected_runs < 1:
        raise PanelEvidenceError("expected_runs must be a positive integer")
    if expected_systems is not None and (
        isinstance(expected_systems, bool)
        or not isinstance(expected_systems, int)
        or expected_systems < 1
    ):
        raise PanelEvidenceError("expected_systems must be a positive integer when supplied")
    if not isinstance(thresholds, dict):
        raise PanelEvidenceError("thresholds must be an object")

    output = verify_stage1_output_evidence(
        run_root,
        expected_output_evidence_sha256=expected_output_evidence_sha256,
    )
    by_system: dict[str, set[int]] = {}
    for run in output.runs:
        run_numbers = by_system.setdefault(run.system_id, set())
        if run.run_number in run_numbers:
            raise PanelEvidenceError(
                f"output evidence contains a duplicate system run: {run.system_id}:{run.run_number}"
            )
        run_numbers.add(run.run_number)
    if not by_system:
        raise PanelEvidenceError("output evidence contains no systems")
    if expected_systems is not None and len(by_system) != expected_systems:
        raise PanelEvidenceError(
            f"output evidence contains {len(by_system)} systems, expected {expected_systems}"
        )
    expected_run_numbers = set(range(1, expected_runs + 1))
    for system_id, run_numbers in by_system.items():
        if run_numbers != expected_run_numbers:
            raise PanelEvidenceError(
                f"system does not contain the exact run panel: {system_id}"
            )

    evaluations = tuple(
        build_verified_stage1_evaluation(
            corpus,
            run_root=run_root,
            expected_output_evidence_sha256=expected_output_evidence_sha256,
            system_id=system_id,
            expected_runs=expected_runs,
        )
        for system_id in sorted(by_system)
    )
    model_hashes = {evaluation.model_settings_sha256 for evaluation in evaluations}
    if len(model_hashes) != 1:
        raise PanelEvidenceError("systems do not use identical model settings")

    results: dict[str, Any] = {}
    objective_pass_count = 0
    for evaluation in evaluations:
        gate = evaluate_stage1_gate(evaluation, thresholds)
        if gate["stage2_eligible"]:
            raise PanelEvidenceError("Stage 2 cannot be eligible before human review")
        objective_pass_count += bool(gate["objective_pass"])
        results[evaluation.system_id] = {
            "valid_run_numbers": list(evaluation.valid_run_numbers),
            "invalid_run_numbers": list(evaluation.invalid_run_numbers),
            "gate_metrics": evaluation.gate_metrics,
            "descriptive_metrics": evaluation.report_metrics,
            "gate": gate,
        }

    threshold_payload = _canonical_json(thresholds)
    report = {
        "schema_version": "1.0",
        "stage": 1,
        "status": "PILOT_UNADJUDICATED",
        "human_review_status": "PENDING_HUMAN_REVIEW",
        "stage2_eligible": False,
        "systems": [evaluation.system_id for evaluation in evaluations],
        "system_count": len(evaluations),
        "expected_runs_per_system": expected_runs,
        "objective_pass_count": objective_pass_count,
        "objective_fail_count": len(evaluations) - objective_pass_count,
        "evidence": {
            "output_evidence_sha256": output.output_evidence_sha256,
            "jobs_manifest_sha256": output.jobs_manifest_sha256,
            "execution_order_sha256": output.execution_order_sha256,
            "corpus_freeze_manifest_sha256": corpus.freeze_manifest_sha256,
            "cases_sha256": corpus.cases_sha256,
            "gold_sha256": corpus.gold_sha256,
            "model_settings_sha256": next(iter(model_hashes)),
            "thresholds_sha256": _sha256(threshold_payload),
        },
        "thresholds": json.loads(json.dumps(thresholds, allow_nan=False)),
        "results": results,
    }
    payload = _canonical_json(report)
    return VerifiedStage1Panel(
        evaluations=evaluations,
        report_payload=payload,
        report_sha256=_sha256(payload),
        _attestation=_ATTESTATION,
    )
