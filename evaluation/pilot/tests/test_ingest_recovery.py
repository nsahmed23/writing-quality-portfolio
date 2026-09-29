from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tests.support import case
from tools.ingest_stage1_output import ingest_stage1_output, main
from wqeval.ingest import UnsafeInputPathError
from wqeval.storage import ImmutableWriteError


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def diagnostic_bytes() -> bytes:
    value = {
        "schema_version": "1.0",
        "case_id": "C001",
        "case_decision": "CHANGE",
        "findings": [
            {
                "finding_id": "F001",
                "start": 0,
                "end": 3,
                "span": "The",
                "decision": "CHANGE",
                "problem_name": "Vague reference",
                "system_issue_code": "vague_reference",
                "normalized_issue_code": "vague_reference",
                "context_explanation": "The antecedent is missing in this isolated sentence.",
                "severity": "medium",
                "suggested_operation": {
                    "operation_code": "resolve_reference",
                    "instruction": "Name the subject.",
                    "replacement": None,
                },
                "field_origin": "authored",
            }
        ],
    }
    return (json.dumps(value, ensure_ascii=False) + "\n").encode("utf-8")


class InjectedFailure(RuntimeError):
    pass


class Stage1IngestRecoveryTests(unittest.TestCase):
    def build_registered_job(self, root: Path) -> tuple[Path, Path, Path, str]:
        source = root / "references" / "source.md"
        common = root / "references" / "common.md"
        families = root / "references" / "problem-families.json"
        source.parent.mkdir(parents=True)
        source.write_text("detect vague references", encoding="utf-8")
        common.write_text("detect only", encoding="utf-8")
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
            payload = path.read_bytes()
            return {"path": str(path.resolve()), "sha256": hashlib.sha256(payload).hexdigest()}

        job_id = "stage1-candidate-run-01"
        inbox = root / "inbox" / f"{job_id}.jsonl"
        inbox.parent.mkdir()
        inbox.write_bytes(diagnostic_bytes())
        job = {
            "schema_version": "1.0",
            "job_id": job_id,
            "stage": 1,
            "system_id": "candidate",
            "run_number": 1,
            "model": {"selection": "inherited"},
            "source_files": [reference(source)],
            "expected_case_count": 1,
            "cases": [case()],
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
                "output_path": str(inbox.resolve()),
            },
        }
        job_path = root / "jobs" / f"{job_id}.json"
        job_path.parent.mkdir()
        job_payload = json_bytes(job)
        job_path.write_bytes(job_payload)
        manifest = root / "manifests" / "jobs.json"
        manifest.parent.mkdir()
        manifest_payload = json_bytes(
            {
                "schema_version": "1.0",
                "jobs": [
                    {
                        "path": f"jobs/{job_id}.json",
                        "sha256": hashlib.sha256(job_payload).hexdigest(),
                        "bytes": len(job_payload),
                    }
                ],
            }
        )
        manifest.write_bytes(manifest_payload)
        return job_path, inbox, manifest, hashlib.sha256(manifest_payload).hexdigest()

    def run_ingest(
        self,
        root: Path,
        job_path: Path,
        inbox: Path,
        manifest: Path,
        manifest_sha256: str,
        *,
        fail_at: str | None = None,
    ) -> dict:
        def inject(stage: str) -> None:
            if stage == fail_at:
                raise InjectedFailure(stage)

        return ingest_stage1_output(
            job_path=job_path,
            input_path=inbox,
            run_root=root,
            jobs_manifest_path=manifest,
            expected_manifest_sha256=manifest_sha256,
            failure_injector=inject if fail_at else None,
        )

    def test_recovers_after_raw_publication_only_when_inbox_bytes_match(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "run"
            root.mkdir()
            job_path, inbox, manifest, manifest_sha = self.build_registered_job(root)
            artifact = "stage1-candidate-run-01.jsonl"

            with self.assertRaisesRegex(InjectedFailure, "raw_published"):
                self.run_ingest(root, job_path, inbox, manifest, manifest_sha, fail_at="raw_published")

            raw_payload = (root / "raw" / artifact).read_bytes()
            self.assertEqual(raw_payload, diagnostic_bytes())
            self.assertFalse((root / "normalized" / artifact).exists())
            self.assertFalse((root / "manifests" / "receipts" / artifact.replace(".jsonl", ".json")).exists())

            result = self.run_ingest(root, job_path, inbox, manifest, manifest_sha)
            self.assertEqual(result["status"], "valid")
            self.assertTrue((root / "normalized" / artifact).is_file())
            self.assertTrue((root / "manifests" / "receipts" / artifact.replace(".jsonl", ".json")).is_file())

            rerun = self.run_ingest(root, job_path, inbox, manifest, manifest_sha)
            self.assertEqual(rerun, result)
            self.assertEqual((root / "raw" / artifact).read_bytes(), raw_payload)

    def test_recovery_rejects_changed_inbox_after_raw_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "run"
            root.mkdir()
            job_path, inbox, manifest, manifest_sha = self.build_registered_job(root)

            with self.assertRaises(InjectedFailure):
                self.run_ingest(root, job_path, inbox, manifest, manifest_sha, fail_at="raw_published")
            inbox.unlink()
            inbox.write_bytes(diagnostic_bytes() + b" ")
            inbox.read_bytes()

            with self.assertRaises((ImmutableWriteError, UnsafeInputPathError)):
                self.run_ingest(root, job_path, inbox, manifest, manifest_sha)
            self.assertFalse((root / "normalized" / "stage1-candidate-run-01.jsonl").exists())

    def test_recovers_after_normalized_publication_and_publishes_missing_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "run"
            root.mkdir()
            job_path, inbox, manifest, manifest_sha = self.build_registered_job(root)
            artifact = "stage1-candidate-run-01.jsonl"

            with self.assertRaisesRegex(InjectedFailure, "normalized_published"):
                self.run_ingest(root, job_path, inbox, manifest, manifest_sha, fail_at="normalized_published")

            normalized_before = (root / "normalized" / artifact).read_bytes()
            receipt_path = root / "manifests" / "receipts" / artifact.replace(".jsonl", ".json")
            self.assertFalse(receipt_path.exists())

            result = self.run_ingest(root, job_path, inbox, manifest, manifest_sha)
            self.assertEqual(result["status"], "valid")
            self.assertEqual((root / "normalized" / artifact).read_bytes(), normalized_before)
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(receipt, result)

    def test_recovery_does_not_overwrite_changed_normalized_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "run"
            root.mkdir()
            job_path, inbox, manifest, manifest_sha = self.build_registered_job(root)
            normalized = root / "normalized" / "stage1-candidate-run-01.jsonl"

            with self.assertRaises(InjectedFailure):
                self.run_ingest(root, job_path, inbox, manifest, manifest_sha, fail_at="normalized_published")
            normalized.write_bytes(b"changed\n")

            with self.assertRaisesRegex(ImmutableWriteError, "different bytes"):
                self.run_ingest(root, job_path, inbox, manifest, manifest_sha)
            self.assertEqual(normalized.read_bytes(), b"changed\n")
            self.assertFalse((root / "manifests" / "receipts" / "stage1-candidate-run-01.json").exists())

    def test_idempotent_rerun_does_not_overwrite_changed_receipt_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "run"
            root.mkdir()
            job_path, inbox, manifest, manifest_sha = self.build_registered_job(root)
            self.run_ingest(root, job_path, inbox, manifest, manifest_sha)
            receipt = root / "manifests" / "receipts" / "stage1-candidate-run-01.json"
            receipt.write_bytes(b"changed\n")

            with self.assertRaisesRegex(ImmutableWriteError, "different bytes"):
                self.run_ingest(root, job_path, inbox, manifest, manifest_sha)
            self.assertEqual(receipt.read_bytes(), b"changed\n")

    def test_cli_uses_the_same_recovery_safe_ingestion_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "run"
            root.mkdir()
            job_path, inbox, manifest, manifest_sha = self.build_registered_job(root)
            arguments = [
                "ingest_stage1_output.py",
                "--job",
                str(job_path),
                "--input",
                str(inbox),
                "--run-root",
                str(root),
                "--jobs-manifest",
                str(manifest),
                "--expected-manifest-sha256",
                manifest_sha,
            ]
            output = io.StringIO()

            with patch("tools.ingest_stage1_output.sys.argv", arguments), redirect_stdout(output):
                exit_code = main()

            self.assertEqual(exit_code, 0)
            self.assertEqual(json.loads(output.getvalue())["status"], "valid")


if __name__ == "__main__":
    unittest.main()
