from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import random
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.support import case
from wqeval.ingest import ingest_diagnostic_bytes
from wqeval.output_evidence import (
    OutputEvidenceError,
    finalize_stage1_output,
)
from wqeval.reconciliation import ReconciliationError, reconcile_stage1_outputs
from wqeval.storage import RawStore


def canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def pretty_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class Stage1EvidenceFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.jobs: list[tuple[dict, bytes, bool]] = []
        references = root / "references"
        references.mkdir(parents=True)
        self.source = references / "source.md"
        self.common = references / "common.md"
        self.families = references / "problem-families.json"
        self.source.write_text("candidate instructions", encoding="utf-8")
        self.common.write_text("detect only", encoding="utf-8")
        self.families.write_bytes(
            pretty_json(
                {
                    "schema_version": "1.0",
                    "mapping_status": "frozen_before_sealed_generation",
                    "change_families": [
                        {"code": "vague_reference", "description": "Vague reference."}
                    ],
                    "keep_families": [
                        {"code": "legitimate_passive", "description": "Functional passive."}
                    ],
                }
            )
        )

    def reference(self, path: Path) -> dict:
        payload = path.read_bytes()
        return {"path": str(path.resolve()), "sha256": sha256(payload)}

    def add_job(
        self,
        system_id: str,
        run_number: int,
        *,
        valid: bool = True,
        case_id: str = "C001",
    ) -> None:
        job_id = f"stage1-{system_id}-run-{run_number:02d}"
        source_case = case(case_id)
        job = {
            "schema_version": "1.0",
            "job_id": job_id,
            "stage": 1,
            "system_id": system_id,
            "run_number": run_number,
            "model": {"selection": "inherited"},
            "source_files": [self.reference(self.source)],
            "expected_case_count": 1,
            "cases": [source_case],
            "common_envelope": self.reference(self.common),
            "problem_families": self.reference(self.families),
            "system_display_name": system_id,
            "family": "test",
            "fidelity_class": "F1",
            "diagnostic_status": "detect_only",
            "output_contract": {
                "format": "utf8_jsonl",
                "records": 1,
                "one_record_per_case": True,
                "surrounding_prose": False,
                "output_path": str((self.root / "inbox" / f"{job_id}.jsonl").resolve()),
            },
        }
        job_payload = pretty_json(job)
        self.jobs.append((job, job_payload, valid))

    def publish(
        self,
        *,
        mode: str = "development",
        random_seed: int = 20260825,
    ) -> tuple[str, dict[str, str]]:
        jobs_dir = self.root / "jobs"
        manifests_dir = self.root / "manifests"
        jobs_dir.mkdir(parents=True)
        manifests_dir.mkdir(parents=True)
        entries = []
        for job, payload, _ in self.jobs:
            path = jobs_dir / f"{job['job_id']}.json"
            path.write_bytes(payload)
            entries.append(
                {
                    "path": f"jobs/{job['job_id']}.json",
                    "sha256": sha256(payload),
                    "bytes": len(payload),
                }
            )
        manifest_payload = pretty_json(
            {
                "schema_version": "1.0",
                "stage": 1,
                "mode": mode,
                "random_seed": random_seed,
                "jobs": entries,
            }
        )
        (manifests_dir / "jobs.json").write_bytes(manifest_payload)
        manifest_sha = sha256(manifest_payload)
        errors: dict[str, str] = {}

        for job, job_payload, valid in self.jobs:
            source_case = job["cases"][0]
            raw_payload = self.raw_payload(source_case["case_id"]) if valid else b'{"case_id":}\n'
            result = ingest_diagnostic_bytes(
                raw_payload,
                cases=job["cases"],
                system_id=job["system_id"],
                run_number=job["run_number"],
                artifact_name=f"{job['job_id']}.jsonl",
                raw_store=RawStore(self.root / "raw", authorized_root=self.root),
                normalized_store=RawStore(self.root / "normalized", authorized_root=self.root),
                allowed_normalized_codes={"vague_reference", "legitimate_passive"},
            )
            receipt = asdict(result)
            receipt["job_sha256"] = sha256(job_payload)
            receipt["jobs_manifest_sha256"] = manifest_sha
            RawStore(self.root / "manifests" / "receipts", authorized_root=self.root).write_once(
                f"{job['job_id']}.json", pretty_json(receipt)
            )
            if result.error_message is not None:
                errors[job["job_id"]] = result.error_message
        return manifest_sha, errors

    @staticmethod
    def raw_payload(case_id: str) -> bytes:
        record = {
            "schema_version": "1.0",
            "case_id": case_id,
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
        return canonical_json(record)


class Stage1OutputEvidenceTests(unittest.TestCase):
    def build(self, root: Path, *, mixed: bool = False) -> tuple[str, str]:
        fixture = Stage1EvidenceFixture(root)
        fixture.add_job("candidate", 1)
        if mixed:
            fixture.add_job("other", 1, valid=False)
        jobs_sha, _ = fixture.publish()
        receipt = finalize_stage1_output(
            root,
            expected_jobs_manifest_sha256=jobs_sha,
        )
        return jobs_sha, receipt.sha256

    def test_finalizes_canonical_exact_anchor_once_and_reconciles_mixed_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            jobs_sha, anchor_sha = self.build(root, mixed=True)
            anchor_path = root / "manifests" / "stage1-output-evidence.json"
            payload = anchor_path.read_bytes()
            anchor = json.loads(payload)

            self.assertEqual(payload, canonical_json(anchor))
            self.assertEqual(
                set(anchor),
                {"schema_version", "stage", "jobs_manifest", "execution_order", "jobs"},
            )
            self.assertEqual(anchor["schema_version"], "1.0")
            self.assertEqual(anchor["stage"], 1)
            self.assertEqual(
                set(anchor["jobs_manifest"]),
                {"path", "sha256", "byte_count"},
            )
            self.assertEqual(anchor["jobs_manifest"]["path"], "manifests/jobs.json")
            self.assertEqual(anchor["jobs_manifest"]["sha256"], jobs_sha)
            self.assertIsNone(anchor["execution_order"])
            self.assertEqual([item["job_id"] for item in anchor["jobs"]], sorted(item["job_id"] for item in anchor["jobs"]))
            self.assertEqual(
                set(anchor["jobs"][0]),
                {"job_id", "status", "record_count", "job", "receipt", "raw", "normalized"},
            )
            for item in anchor["jobs"]:
                for name in ("job", "receipt", "raw"):
                    self.assertEqual(set(item[name]), {"path", "sha256", "byte_count"})
                if item["status"] == "invalid":
                    self.assertEqual(item["record_count"], 0)
                    self.assertIsNone(item["normalized"])

            repeat_receipt = finalize_stage1_output(
                root,
                expected_jobs_manifest_sha256=jobs_sha,
            )
            self.assertEqual(repeat_receipt.sha256, anchor_sha)
            result = reconcile_stage1_outputs(
                root,
                expected_output_evidence_sha256=anchor_sha,
            )
            self.assertEqual(result["valid_run_count"], 1)
            self.assertEqual(result["invalid_run_count"], 1)
            self.assertEqual(result["schema_compliance_rate"], 0.5)
            self.assertEqual(result["jobs_manifest_sha256"], jobs_sha)
            self.assertEqual(result["output_evidence_sha256"], anchor_sha)
            valid = next(run for run in result["runs"] if run.status == "valid")
            invalid = next(run for run in result["runs"] if run.status == "invalid")
            self.assertEqual(valid.cases[0]["case_id"], "C001")
            self.assertEqual(valid.predictions[0]["case_id"], "C001")
            self.assertEqual(invalid.predictions, ())

    def test_production_execution_order_is_hash_bound_and_replayed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = Stage1EvidenceFixture(root)
            fixture.add_job("candidate", 1)
            jobs_sha, _ = fixture.publish(mode="confirmatory")
            order = {
                "schema_version": "1.0",
                "stage": 1,
                "mode": "confirmatory",
                "order_policy": "deterministic_shuffle",
                "random_seed": 20260825,
                "jobs_manifest_sha256": jobs_sha,
                "job_count": 1,
                "job_ids": ["stage1-candidate-run-01"],
            }
            order_path = root / "manifests" / "execution-order.json"
            order_payload = pretty_json(order)
            order_path.write_bytes(order_payload)

            receipt = finalize_stage1_output(
                root,
                expected_jobs_manifest_sha256=jobs_sha,
            )
            anchor = json.loads((root / "manifests" / "stage1-output-evidence.json").read_bytes())
            self.assertEqual(
                anchor["execution_order"],
                {
                    "path": "manifests/execution-order.json",
                    "sha256": sha256(order_payload),
                    "byte_count": len(order_payload),
                },
            )
            reconcile_stage1_outputs(root, expected_output_evidence_sha256=receipt.sha256)

            order["job_ids"] = ["stage1-forged-run-01"]
            order_path.write_bytes(pretty_json(order))
            with self.assertRaises(ReconciliationError):
                reconcile_stage1_outputs(root, expected_output_evidence_sha256=receipt.sha256)

    def test_execution_order_rejects_a_wrong_permutation_of_the_exact_job_set(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = Stage1EvidenceFixture(root)
            for system_id in ("candidate", "other", "third"):
                fixture.add_job(system_id, 1)
            seed = 20260825
            jobs_sha, _ = fixture.publish(mode="confirmatory", random_seed=seed)
            expected = sorted(
                f"stage1-{system_id}-run-01"
                for system_id in ("candidate", "other", "third")
            )
            random.Random(seed).shuffle(expected)
            wrong = list(reversed(expected))
            self.assertNotEqual(wrong, expected)
            order = {
                "schema_version": "1.0",
                "stage": 1,
                "mode": "confirmatory",
                "order_policy": "deterministic_shuffle",
                "random_seed": seed,
                "jobs_manifest_sha256": jobs_sha,
                "job_count": len(wrong),
                "job_ids": wrong,
            }
            (root / "manifests" / "execution-order.json").write_bytes(pretty_json(order))

            with self.assertRaisesRegex(OutputEvidenceError, "shuffle|permutation|order"):
                finalize_stage1_output(root, expected_jobs_manifest_sha256=jobs_sha)

    def test_confirmatory_manifest_requires_order_and_rejects_a_declared_seed_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = Stage1EvidenceFixture(root)
            fixture.add_job("candidate", 1)
            jobs_sha, _ = fixture.publish(mode="confirmatory", random_seed=17)
            with self.assertRaisesRegex(OutputEvidenceError, "confirmatory|execution order"):
                finalize_stage1_output(root, expected_jobs_manifest_sha256=jobs_sha)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = Stage1EvidenceFixture(root)
            for system_id in ("candidate", "other", "third"):
                fixture.add_job(system_id, 1)
            jobs_sha, _ = fixture.publish(mode="confirmatory", random_seed=17)
            job_ids = sorted(
                f"stage1-{system_id}-run-01"
                for system_id in ("candidate", "other", "third")
            )
            declared_seed = 18
            random.Random(declared_seed).shuffle(job_ids)
            order = {
                "schema_version": "1.0",
                "stage": 1,
                "mode": "confirmatory",
                "order_policy": "deterministic_shuffle",
                "random_seed": declared_seed,
                "jobs_manifest_sha256": jobs_sha,
                "job_count": len(job_ids),
                "job_ids": job_ids,
            }
            (root / "manifests" / "execution-order.json").write_bytes(pretty_json(order))
            with self.assertRaisesRegex(OutputEvidenceError, "seed|manifest"):
                finalize_stage1_output(root, expected_jobs_manifest_sha256=jobs_sha)

    def test_detached_anchor_hash_rejects_replace_all_attack(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as replacement:
            first_root = Path(first)
            replacement_root = Path(replacement)
            _, trusted_sha = self.build(first_root)

            fixture = Stage1EvidenceFixture(replacement_root)
            fixture.add_job("candidate", 1, case_id="C999")
            jobs_sha, _ = fixture.publish()
            replacement_receipt = finalize_stage1_output(
                replacement_root,
                expected_jobs_manifest_sha256=jobs_sha,
            )
            self.assertNotEqual(replacement_receipt.sha256, trusted_sha)

            for name in ("jobs", "raw", "normalized", "manifests"):
                shutil.rmtree(first_root / name)
                shutil.copytree(replacement_root / name, first_root / name)

            with self.assertRaisesRegex(ReconciliationError, "output evidence.*SHA-256"):
                reconcile_stage1_outputs(
                    first_root,
                    expected_output_evidence_sha256=trusted_sha,
                )

    def test_exact_directory_sets_reject_missing_and_unexpected_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, anchor_sha = self.build(root)
            extra = root / "raw" / "unregistered.jsonl"
            extra.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ReconciliationError, "unexpected.*raw|raw.*unexpected"):
                reconcile_stage1_outputs(root, expected_output_evidence_sha256=anchor_sha)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, anchor_sha = self.build(root)
            (root / "raw" / "stage1-candidate-run-01.jsonl").unlink()
            with self.assertRaisesRegex(ReconciliationError, "missing"):
                reconcile_stage1_outputs(root, expected_output_evidence_sha256=anchor_sha)

    def test_finalization_rejects_extra_before_publish_and_leaves_no_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = Stage1EvidenceFixture(root)
            fixture.add_job("candidate", 1)
            jobs_sha, _ = fixture.publish()
            (root / "normalized" / "extra.jsonl").write_text("{}\n", encoding="utf-8")

            with self.assertRaisesRegex(OutputEvidenceError, "unexpected.*normalized|normalized.*unexpected"):
                finalize_stage1_output(root, expected_jobs_manifest_sha256=jobs_sha)
            self.assertFalse((root / "manifests" / "stage1-output-evidence.json").exists())

    def test_hashed_but_contradictory_or_unsafe_anchor_is_rejected(self) -> None:
        for mutation in ("contradictory", "unsafe"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                _, _ = self.build(root)
                anchor_path = root / "manifests" / "stage1-output-evidence.json"
                anchor = json.loads(anchor_path.read_bytes())
                if mutation == "contradictory":
                    anchor["jobs"][0]["status"] = "invalid"
                    anchor["jobs"][0]["record_count"] = 0
                    anchor["jobs"][0]["normalized"] = None
                else:
                    anchor["jobs"][0]["raw"]["path"] = "../outside.jsonl"
                forged = canonical_json(anchor)
                anchor_path.write_bytes(forged)

                with self.assertRaises(ReconciliationError):
                    reconcile_stage1_outputs(
                        root,
                        expected_output_evidence_sha256=sha256(forged),
                    )

    def test_hashed_receipts_cannot_bypass_normalization_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, _ = self.build(root)
            job_id = "stage1-candidate-run-01"
            normalized_path = root / "normalized" / f"{job_id}.jsonl"
            normalized_path.write_bytes(b"")

            receipt_path = root / "manifests" / "receipts" / f"{job_id}.json"
            receipt = json.loads(receipt_path.read_bytes())
            receipt["normalized_receipt"] = {
                "relative_path": f"{job_id}.jsonl",
                "sha256": sha256(b""),
                "byte_count": 0,
            }
            receipt_payload = pretty_json(receipt)
            receipt_path.write_bytes(receipt_payload)

            anchor_path = root / "manifests" / "stage1-output-evidence.json"
            anchor = json.loads(anchor_path.read_bytes())
            anchor["jobs"][0]["receipt"].update(
                {"sha256": sha256(receipt_payload), "byte_count": len(receipt_payload)}
            )
            anchor["jobs"][0]["normalized"].update(
                {"sha256": sha256(b""), "byte_count": 0}
            )
            forged = canonical_json(anchor)
            anchor_path.write_bytes(forged)

            with self.assertRaisesRegex(ReconciliationError, "deterministic raw projection"):
                reconcile_stage1_outputs(
                    root,
                    expected_output_evidence_sha256=sha256(forged),
                )


if __name__ == "__main__":
    unittest.main()
