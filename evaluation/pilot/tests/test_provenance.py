from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from wqeval.provenance import (
    ProvenanceError,
    load_public_problem_vocabulary,
    resolve_pinned_source,
    verify_frozen_corpus_file,
    verify_job_artifact_from_manifest,
    verify_job_from_manifest,
)
from tests.support import case


def write_json(path: Path, value: dict) -> bytes:
    payload = (json.dumps(value, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return payload


def stage1_job(root: Path) -> dict:
    return {
        "schema_version": "1.0",
        "job_id": "stage1-union-run-01",
        "stage": 1,
        "system_id": "union",
        "run_number": 1,
        "model": {"selection": "inherited"},
        "source_files": [{"path": "C:/source.md", "sha256": "a" * 64}],
        "expected_case_count": 1,
        "cases": [case()],
        "common_envelope": {"path": "C:/common.md", "sha256": "b" * 64},
        "problem_families": {"path": "C:/families.json", "sha256": "c" * 64},
        "system_display_name": "Union",
        "family": "normalized_union",
        "fidelity_class": "NATIVE_EVAL",
        "diagnostic_status": "detect_only",
        "output_contract": {
            "format": "utf8_jsonl",
            "records": 1,
            "one_record_per_case": True,
            "surrounding_prose": False,
            "output_path": str((root / "inbox" / "stage1-union-run-01.jsonl").resolve()),
        },
    }


class JobProvenanceTests(unittest.TestCase):
    def test_cases_must_be_registered_in_expected_corpus_freeze_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            cases = project / "corpus" / "cases.dev.jsonl"
            cases.parent.mkdir(parents=True)
            case_bytes = b'{"case_id":"C001"}\n'
            cases.write_bytes(case_bytes)
            substitute = project / "corpus" / "substitute.jsonl"
            substitute.write_bytes(case_bytes)
            freeze = project / "corpus" / "freeze-manifest.json"
            freeze_bytes = write_json(
                freeze,
                {
                    "schema_version": "1.0",
                    "status": "frozen",
                    "gold_status": "provisional_pending_human_adjudication",
                    "files": [
                        {
                            "path": "corpus/cases.dev.jsonl",
                            "sha256": hashlib.sha256(case_bytes).hexdigest(),
                            "bytes": len(case_bytes),
                        }
                    ],
                },
            )
            expected = hashlib.sha256(freeze_bytes).hexdigest()
            verify_frozen_corpus_file(cases, project=project, freeze_manifest_path=freeze, expected_freeze_sha256=expected)
            with self.assertRaises(ProvenanceError):
                verify_frozen_corpus_file(
                    substitute,
                    project=project,
                    freeze_manifest_path=freeze,
                    expected_freeze_sha256=expected,
                )

    def test_public_problem_vocabulary_is_hash_bound_and_exact_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "problem-families.json"
            value = {
                "schema_version": "1.0",
                "mapping_status": "frozen_before_sealed_generation",
                "change_families": [{"code": "generic_filler", "description": "Filler."}],
                "keep_families": [{"code": "legitimate_passive", "description": "Functional passive."}],
            }
            payload = write_json(path, value)
            reference = {"path": str(path.resolve()), "sha256": hashlib.sha256(payload).hexdigest()}
            self.assertEqual(
                load_public_problem_vocabulary(reference),
                {"generic_filler", "legitimate_passive"},
            )

            path.write_bytes(payload + b" ")
            with self.assertRaises(ProvenanceError):
                load_public_problem_vocabulary(reference)

            malformed_payload = write_json(path, dict(value, answers=[]))
            malformed_ref = {"path": str(path.resolve()), "sha256": hashlib.sha256(malformed_payload).hexdigest()}
            with self.assertRaises(ProvenanceError):
                load_public_problem_vocabulary(malformed_ref)

    def test_source_resolution_is_confined_to_allowlisted_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            project = workspace / "work" / "writing-quality-eval"
            allowed_project = project / "systems" / "union.md"
            allowed_workspace = workspace / "work" / "research-writing-repos" / "sources" / "repo" / "SKILL.md"
            private = project / "private" / "gold" / "answers.json"
            for path, payload in (
                (allowed_project, b"union"),
                (allowed_workspace, b"source"),
                (private, b"gold"),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)

            project_ref = resolve_pinned_source(
                project,
                workspace,
                {"path": "systems/union.md", "sha256": hashlib.sha256(b"union").hexdigest()},
            )
            workspace_ref = resolve_pinned_source(
                project,
                workspace,
                {
                    "path": "work/research-writing-repos/sources/repo/SKILL.md",
                    "sha256": hashlib.sha256(b"source").hexdigest(),
                },
            )
            self.assertEqual(Path(project_ref["path"]), allowed_project.resolve())
            self.assertEqual(Path(workspace_ref["path"]), allowed_workspace.resolve())

            for record in (
                {"path": "private/gold/answers.json", "sha256": hashlib.sha256(b"gold").hexdigest()},
                {"path": "../outside.txt", "sha256": "0" * 64},
                {"path": str(private), "sha256": hashlib.sha256(b"gold").hexdigest()},
            ):
                with self.subTest(record=record), self.assertRaises(ProvenanceError):
                    resolve_pinned_source(project, workspace, record)

    def test_registered_job_and_expected_manifest_hash_verify(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job_path = root / "jobs" / "stage1-union-run-01.json"
            job_bytes = write_json(job_path, stage1_job(root))
            manifest_path = root / "manifests" / "jobs.json"
            manifest_bytes = write_json(
                manifest_path,
                {
                    "schema_version": "1.0",
                    "jobs": [
                        {
                            "path": "jobs/stage1-union-run-01.json",
                            "sha256": hashlib.sha256(job_bytes).hexdigest(),
                            "bytes": len(job_bytes),
                        }
                    ],
                },
            )
            verified = verify_job_from_manifest(
                job_path,
                manifest_path,
                run_root=root,
                expected_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
            )
            self.assertEqual(verified["job_id"], "stage1-union-run-01")

    def test_verified_job_artifact_carries_the_manifest_bound_digest_without_a_second_read(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job_path = root / "jobs" / "stage1-union-run-01.json"
            job_bytes = write_json(job_path, stage1_job(root))
            job_sha256 = hashlib.sha256(job_bytes).hexdigest()
            manifest_path = root / "manifests" / "jobs.json"
            manifest_bytes = write_json(
                manifest_path,
                {
                    "schema_version": "1.0",
                    "jobs": [
                        {
                            "path": "jobs/stage1-union-run-01.json",
                            "sha256": job_sha256,
                            "bytes": len(job_bytes),
                        }
                    ],
                },
            )

            verified = verify_job_artifact_from_manifest(
                job_path,
                manifest_path,
                run_root=root,
                expected_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
            )

            self.assertEqual(verified.job["job_id"], "stage1-union-run-01")
            self.assertEqual(verified.sha256, job_sha256)
            self.assertEqual(verified.byte_count, len(job_bytes))

    def test_modified_job_forged_manifest_and_escaping_entry_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job_path = root / "jobs" / "stage1-union-run-01.json"
            job_bytes = write_json(job_path, stage1_job(root))
            manifest_path = root / "manifests" / "jobs.json"
            manifest = {
                "schema_version": "1.0",
                "jobs": [
                    {
                        "path": "jobs/stage1-union-run-01.json",
                        "sha256": hashlib.sha256(job_bytes).hexdigest(),
                        "bytes": len(job_bytes),
                    }
                ],
            }
            manifest_bytes = write_json(manifest_path, manifest)
            expected = hashlib.sha256(manifest_bytes).hexdigest()

            job_path.write_bytes(job_bytes + b" ")
            with self.assertRaises(ProvenanceError):
                verify_job_from_manifest(job_path, manifest_path, run_root=root, expected_manifest_sha256=expected)

            job_path.write_bytes(job_bytes)
            with self.assertRaises(ProvenanceError):
                verify_job_from_manifest(job_path, manifest_path, run_root=root, expected_manifest_sha256="0" * 64)

            escaping = dict(manifest)
            escaping["jobs"] = [dict(manifest["jobs"][0], path="../outside.json")]
            escaping_bytes = write_json(manifest_path, escaping)
            with self.assertRaises(ProvenanceError):
                verify_job_from_manifest(
                    job_path,
                    manifest_path,
                    run_root=root,
                    expected_manifest_sha256=hashlib.sha256(escaping_bytes).hexdigest(),
                )

    def test_registered_job_with_invalid_internal_schema_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            job = stage1_job(root)
            job["expected_case_count"] = 2
            job_path = root / "jobs" / "stage1-union-run-01.json"
            job_bytes = write_json(job_path, job)
            manifest_path = root / "manifests" / "jobs.json"
            manifest_bytes = write_json(
                manifest_path,
                {
                    "schema_version": "1.0",
                    "jobs": [
                        {
                            "path": "jobs/stage1-union-run-01.json",
                            "sha256": hashlib.sha256(job_bytes).hexdigest(),
                            "bytes": len(job_bytes),
                        }
                    ],
                },
            )
            with self.assertRaises(ProvenanceError):
                verify_job_from_manifest(
                    job_path,
                    manifest_path,
                    run_root=root,
                    expected_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
                )


if __name__ == "__main__":
    unittest.main()
