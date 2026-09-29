from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wqeval.ingest import ingest_diagnostic_bytes, read_registered_inbox_artifact  # noqa: E402
from wqeval.provenance import (  # noqa: E402
    load_public_problem_vocabulary,
    verify_job_artifacts,
    verify_job_artifact_from_manifest,
)
from wqeval.storage import RawStore  # noqa: E402


def ingest_stage1_output(
    *,
    job_path: str | Path,
    input_path: str | Path,
    run_root: str | Path,
    jobs_manifest_path: str | Path,
    expected_manifest_sha256: str,
    failure_injector: Callable[[str], None] | None = None,
) -> dict:
    """Ingest one registered job, resuming only exact prior publications."""

    run_root = Path(os.path.abspath(os.fspath(run_root)))
    verified_job = verify_job_artifact_from_manifest(
        job_path,
        jobs_manifest_path,
        run_root=run_root,
        expected_manifest_sha256=expected_manifest_sha256,
    )
    job = verified_job.job
    artifact_name = f"{job['job_id']}.jsonl"
    verify_job_artifacts(job)
    allowed_normalized_codes = load_public_problem_vocabulary(job["problem_families"])
    input_payload = read_registered_inbox_artifact(
        input_path,
        run_root=run_root,
        artifact_name=artifact_name,
        registered_output_path=job["output_contract"]["output_path"],
    )

    result = ingest_diagnostic_bytes(
        input_payload,
        cases=job["cases"],
        system_id=job["system_id"],
        run_number=job["run_number"],
        artifact_name=artifact_name,
        raw_store=RawStore(run_root / "raw", authorized_root=run_root),
        normalized_store=RawStore(run_root / "normalized", authorized_root=run_root),
        allowed_normalized_codes=allowed_normalized_codes,
        recover_existing=True,
        failure_injector=failure_injector,
    )
    payload = asdict(result)
    payload["job_sha256"] = verified_job.sha256
    payload["jobs_manifest_sha256"] = expected_manifest_sha256
    receipt_payload = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    receipt_store = RawStore(run_root / "manifests" / "receipts", authorized_root=run_root)
    receipt = receipt_store.publish_or_verify(
        artifact_name.removesuffix(".jsonl") + ".json",
        receipt_payload,
    )
    receipt_store.verify(receipt)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--jobs-manifest", required=True, type=Path)
    parser.add_argument("--expected-manifest-sha256", required=True)
    args = parser.parse_args()

    payload = ingest_stage1_output(
        job_path=args.job,
        input_path=args.input,
        run_root=args.run_root,
        jobs_manifest_path=args.jobs_manifest,
        expected_manifest_sha256=args.expected_manifest_sha256,
    )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0 if payload["status"] == "valid" else 2


if __name__ == "__main__":
    raise SystemExit(main())
