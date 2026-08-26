from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from wqeval.ingest import ingest_diagnostic_bytes
from wqeval.output_evidence import finalize_stage1_output
from wqeval.reconciliation import ReconciliationError, reconcile_stage1_outputs
from wqeval.storage import RawStore

from tests.support import case


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def jsonl_bytes(records: list[dict]) -> bytes:
    return b"".join(
        (json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        for record in records
    )


class ReconciliationTests(unittest.TestCase):
    def build_valid_run(self, root: Path, *, valid: bool = True) -> tuple[Path, str]:
        source_case = case()
        common = root / "references" / "common.md"
        source = root / "references" / "source.md"
        families = root / "references" / "problem-families.json"
        common.parent.mkdir(parents=True)
        common.write_text("detect only", encoding="utf-8")
        source.write_text("candidate instructions", encoding="utf-8")
        families.write_bytes(
            json_bytes(
                {
                    "schema_version": "1.0",
                    "mapping_status": "frozen_before_sealed_generation",
                    "change_families": [{"code": "vague_reference", "description": "Vague reference."}],
                    "keep_families": [{"code": "legitimate_passive", "description": "Functional passive."}],
                }
            )
        )

        def reference(path: Path) -> dict:
            return {
                "path": str(path.resolve()),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }

        job_id = "stage1-candidate-run-01"
        job = {
            "schema_version": "1.0",
            "job_id": job_id,
            "stage": 1,
            "system_id": "candidate",
            "run_number": 1,
            "model": {"selection": "inherited"},
            "source_files": [reference(source)],
            "expected_case_count": 1,
            "cases": [source_case],
            "common_envelope": reference(common),
            "problem_families": reference(families),
            "system_display_name": "Candidate",
            "family": "test",
            "fidelity_class": "F1",
            "diagnostic_status": "detect_only",
            "output_contract": {
                "format": "utf8_jsonl",
                "records": 1,
                "one_record_per_case": True,
                "surrounding_prose": False,
                "output_path": str((root / "inbox" / f"{job_id}.jsonl").resolve()),
            },
        }
        job_path = root / "jobs" / f"{job_id}.json"
        job_path.parent.mkdir(parents=True)
        job_payload = json_bytes(job)
        job_path.write_bytes(job_payload)
        manifest_path = root / "manifests" / "jobs.json"
        manifest_path.parent.mkdir(parents=True)
        manifest_payload = json_bytes(
            {
                "schema_version": "1.0",
                "stage": 1,
                "mode": "development",
                "random_seed": 20260825,
                "jobs": [
                    {
                        "path": f"jobs/{job_id}.json",
                        "sha256": hashlib.sha256(job_payload).hexdigest(),
                        "bytes": len(job_payload),
                    }
                ],
            }
        )
        manifest_path.write_bytes(manifest_payload)
        manifest_sha = hashlib.sha256(manifest_payload).hexdigest()

        raw_records = [
            {
                "schema_version": "1.0",
                "case_id": "C001",
                "case_decision": "CHANGE",
                "findings": [
                    {
                        "finding_id": "P001",
                        "start": 0,
                        "end": 3,
                        "span": "The",
                        "decision": "CHANGE",
                        "problem_name": "Vague reference",
                        "system_issue_code": "vague_reference",
                        "normalized_issue_code": "vague_reference",
                        "context_explanation": "The referent is not named.",
                        "severity": "medium",
                        "suggested_operation": {
                            "operation_code": "name_referent",
                            "instruction": "Name the referent.",
                            "replacement": None,
                        },
                        "field_origin": "authored",
                    }
                ],
            }
        ]
        raw_payload = jsonl_bytes(raw_records) if valid else b'{"case_id":}\n'
        result = ingest_diagnostic_bytes(
            raw_payload,
            cases=[source_case],
            system_id="candidate",
            run_number=1,
            artifact_name=f"{job_id}.jsonl",
            raw_store=RawStore(root / "raw", authorized_root=root),
            normalized_store=RawStore(root / "normalized", authorized_root=root),
            allowed_normalized_codes={"vague_reference", "legitimate_passive"},
        )
        self.assertEqual(result.status, "valid" if valid else "invalid")
        receipt_payload = asdict(result)
        receipt_payload["job_sha256"] = hashlib.sha256(job_payload).hexdigest()
        receipt_payload["jobs_manifest_sha256"] = manifest_sha
        RawStore(root / "manifests" / "receipts", authorized_root=root).write_once(
            f"{job_id}.json", json_bytes(receipt_payload)
        )
        return manifest_path, manifest_sha

    def test_reconciles_receipts_jobs_raw_and_normalized_bytes_into_verified_runs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, digest = self.build_valid_run(root)
            anchor = finalize_stage1_output(root, expected_jobs_manifest_sha256=digest)
            result = reconcile_stage1_outputs(
                root,
                expected_output_evidence_sha256=anchor.sha256,
            )

            self.assertEqual(result["job_count"], 1)
            self.assertEqual(result["valid_run_count"], 1)
            run = result["runs"][0]
            self.assertEqual(run.system_id, "candidate")
            self.assertEqual(run.run_number, 1)
            self.assertEqual(run.record_count, 1)
            self.assertEqual(len(run.predictions), 1)
            self.assertEqual(run.predictions[0]["case_id"], "C001")
            first_projection = run.predictions
            first_projection[0]["case_id"] = "MUTATED"
            self.assertEqual(run.predictions[0]["case_id"], "C001")

    def test_tampered_normalized_bytes_fail_before_scoring(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, digest = self.build_valid_run(root)
            anchor = finalize_stage1_output(root, expected_jobs_manifest_sha256=digest)
            target = root / "normalized" / "stage1-candidate-run-01.jsonl"
            target.write_bytes(target.read_bytes() + b" ")

            with self.assertRaises(ReconciliationError):
                reconcile_stage1_outputs(
                    root,
                    expected_output_evidence_sha256=anchor.sha256,
                )

    def test_verified_invalid_receipt_is_reported_without_blocking_manifest_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, digest = self.build_valid_run(root, valid=False)
            anchor = finalize_stage1_output(root, expected_jobs_manifest_sha256=digest)
            result = reconcile_stage1_outputs(
                root,
                expected_output_evidence_sha256=anchor.sha256,
            )

            self.assertEqual(result["job_count"], 1)
            self.assertEqual(result["valid_run_count"], 0)
            self.assertEqual(result["invalid_run_count"], 1)
            self.assertEqual(result["schema_compliance_rate"], 0.0)
            run = result["runs"][0]
            self.assertEqual(run.status, "invalid")
            self.assertEqual(run.error_type, "StrictJsonError")
            self.assertEqual(run.predictions, ())

    def test_receipt_job_hash_and_complete_receipt_set_are_mandatory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest, digest = self.build_valid_run(root)
            anchor = finalize_stage1_output(root, expected_jobs_manifest_sha256=digest)
            receipt = root / "manifests" / "receipts" / "stage1-candidate-run-01.json"
            receipt.unlink()
            with self.assertRaisesRegex(ReconciliationError, "receipt"):
                reconcile_stage1_outputs(
                    root,
                    expected_output_evidence_sha256=anchor.sha256,
                )


if __name__ == "__main__":
    unittest.main()
