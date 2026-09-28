"""Reconcile Stage 1 runs from a detached output-evidence trust root."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .output_evidence import (
    OutputEvidenceError,
    VerifiedStage1Run,
    verify_stage1_output_evidence,
)


class ReconciliationError(RuntimeError):
    """Raised when a Stage 1 evidence chain cannot be verified and replayed."""


def reconcile_stage1_outputs(
    run_root: str | Path,
    *,
    expected_output_evidence_sha256: str,
    maximum_artifact_bytes: int = 50_000_000,
) -> dict[str, Any]:
    """Return runs derived only from a caller-hash-bound fixed evidence anchor."""

    try:
        evidence = verify_stage1_output_evidence(
            run_root,
            expected_output_evidence_sha256=expected_output_evidence_sha256,
            maximum_artifact_bytes=maximum_artifact_bytes,
        )
    except OutputEvidenceError as exc:
        raise ReconciliationError(str(exc)) from exc
    runs = list(evidence.runs)
    valid_count = sum(run.status == "valid" for run in runs)
    invalid_count = sum(run.status == "invalid" for run in runs)
    return {
        "jobs_manifest_sha256": evidence.jobs_manifest_sha256,
        "output_evidence_sha256": evidence.output_evidence_sha256,
        "job_count": len(runs),
        "valid_run_count": valid_count,
        "invalid_run_count": invalid_count,
        "schema_compliance_rate": valid_count / len(runs),
        "runs": runs,
    }
