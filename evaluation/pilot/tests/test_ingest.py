from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tests.support import case
from wqeval.ingest import PayloadLimitError, ingest_diagnostic_bytes
from wqeval.storage import RawStore


def diagnostic(case_id: str = "C001") -> dict:
    return {
        "schema_version": "1.0",
        "case_id": case_id,
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


class DiagnosticIngestTests(unittest.TestCase):
    def test_valid_jsonl_is_preserved_and_normalized_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_store = RawStore(root / "raw", authorized_root=root)
            normalized_store = RawStore(root / "normalized", authorized_root=root)
            payload = (json.dumps(diagnostic(), ensure_ascii=False) + "\n").encode("utf-8")

            result = ingest_diagnostic_bytes(
                payload,
                cases=[case()],
                system_id="union",
                run_number=2,
                artifact_name="union-run-02.jsonl",
                raw_store=raw_store,
                normalized_store=normalized_store,
            )

            self.assertEqual(result.status, "valid")
            self.assertEqual(result.record_count, 1)
            self.assertEqual((root / "raw" / result.raw_receipt.relative_path).read_bytes(), payload)
            normalized = (root / "normalized" / result.normalized_receipt.relative_path).read_text(encoding="utf-8")
            item = json.loads(normalized)
            self.assertEqual(item["system_id"], "union")
            self.assertEqual(item["run_number"], 2)
            self.assertEqual(item["case_id"], "C001")

    def test_invalid_json_is_preserved_without_normalized_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_store = RawStore(root / "raw", authorized_root=root)
            normalized_store = RawStore(root / "normalized", authorized_root=root)
            payload = b'{"case_id":"C001",}\n'

            result = ingest_diagnostic_bytes(
                payload,
                cases=[case()],
                system_id="union",
                run_number=1,
                artifact_name="broken.jsonl",
                raw_store=raw_store,
                normalized_store=normalized_store,
            )

            self.assertEqual(result.status, "invalid")
            self.assertEqual(result.error_type, "StrictJsonError")
            self.assertEqual((root / "raw" / "broken.jsonl").read_bytes(), payload)
            self.assertFalse((root / "normalized" / "broken.jsonl").exists())

    def test_excessive_json_nesting_is_preserved_as_an_invalid_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nested = "[" * 1100 + "0" + "]" * 1100
            payload = (
                '{"schema_version":"1.0","case_id":"C001","case_decision":"KEEP","findings":'
                + nested
                + "}\n"
            ).encode("utf-8")
            result = ingest_diagnostic_bytes(
                payload,
                cases=[case()],
                system_id="union",
                run_number=1,
                artifact_name="deep.jsonl",
                raw_store=RawStore(root / "raw", authorized_root=root),
                normalized_store=RawStore(root / "normalized", authorized_root=root),
            )
            self.assertEqual(result.status, "invalid")
            self.assertEqual(result.error_type, "StrictJsonError")
            self.assertIn("nesting", result.error_message)
            self.assertEqual((root / "raw" / "deep.jsonl").read_bytes(), payload)
            self.assertFalse((root / "normalized" / "deep.jsonl").exists())

    def test_schema_failure_is_not_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw_store = RawStore(root / "raw", authorized_root=root)
            normalized_store = RawStore(root / "normalized", authorized_root=root)
            malformed = diagnostic()
            malformed["findings"][0]["span"] = "API"
            payload = (json.dumps(malformed) + "\n").encode("utf-8")

            result = ingest_diagnostic_bytes(
                payload,
                cases=[case()],
                system_id="union",
                run_number=1,
                artifact_name="wrong-span.jsonl",
                raw_store=raw_store,
                normalized_store=normalized_store,
            )

            self.assertEqual(result.status, "invalid")
            self.assertEqual(result.error_type, "ValidationError")
            self.assertIn("span", result.error_message)
            self.assertFalse((root / "normalized" / "wrong-span.jsonl").exists())

    def test_missing_case_output_fails_the_whole_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = ingest_diagnostic_bytes(
                (json.dumps(diagnostic("C001")) + "\n").encode("utf-8"),
                cases=[case("C001"), case("C002", "The API passed.")],
                system_id="union",
                run_number=1,
                artifact_name="partial.jsonl",
                raw_store=RawStore(root / "raw", authorized_root=root),
                normalized_store=RawStore(root / "normalized", authorized_root=root),
            )
            self.assertEqual(result.status, "invalid")
            self.assertIn("missing cases", result.error_message)

    def test_payload_limit_is_checked_before_raw_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(PayloadLimitError):
                ingest_diagnostic_bytes(
                    b"x" * 33,
                    cases=[case()],
                    system_id="union",
                    run_number=1,
                    artifact_name="oversized.jsonl",
                    raw_store=RawStore(root / "raw", authorized_root=root),
                    normalized_store=RawStore(root / "normalized", authorized_root=root),
                    max_raw_bytes=32,
                )
            self.assertFalse((root / "raw" / "oversized.jsonl").exists())

    def test_per_case_finding_limit_rejects_pathological_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = diagnostic()
            record["findings"] = [dict(record["findings"][0], finding_id=f"F{index:03d}") for index in range(3)]
            result = ingest_diagnostic_bytes(
                (json.dumps(record) + "\n").encode("utf-8"),
                cases=[case()],
                system_id="union",
                run_number=1,
                artifact_name="too-many-findings.jsonl",
                raw_store=RawStore(root / "raw", authorized_root=root),
                normalized_store=RawStore(root / "normalized", authorized_root=root),
                max_findings_per_case=2,
            )
            self.assertEqual(result.status, "invalid")
            self.assertIn("finding limit", result.error_message)

    def test_normalized_issue_code_must_use_public_vocabulary_or_unmapped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record = diagnostic()
            record["findings"][0]["normalized_issue_code"] = "invented_family"
            result = ingest_diagnostic_bytes(
                (json.dumps(record) + "\n").encode("utf-8"),
                cases=[case()],
                system_id="union",
                run_number=1,
                artifact_name="bad-vocabulary.jsonl",
                raw_store=RawStore(root / "raw", authorized_root=root),
                normalized_store=RawStore(root / "normalized", authorized_root=root),
                allowed_normalized_codes={"vague_reference"},
            )
            self.assertEqual(result.status, "invalid")
            self.assertIn("normalized_issue_code", result.error_message)


if __name__ == "__main__":
    unittest.main()
