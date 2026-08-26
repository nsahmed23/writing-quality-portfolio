from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tests.support import case, finding, write_jsonl
from wqeval.corpus_evidence import CorpusEvidenceError, verify_frozen_scoring_corpus


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CorpusEvidenceTests(unittest.TestCase):
    def build(self, root: Path) -> tuple[str, Path, Path]:
        cases_path = root / "corpus" / "cases.test.jsonl"
        gold_path = root / "private" / "gold" / "scoring.test.jsonl"
        cases_path.parent.mkdir(parents=True, exist_ok=True)
        gold_path.parent.mkdir(parents=True, exist_ok=True)
        write_jsonl(cases_path, [case("C001"), case("C002", "Already clear.")])
        write_jsonl(gold_path, [finding("C001", "G001")])
        files = []
        for relative, path in (
            ("corpus/cases.test.jsonl", cases_path),
            ("private/gold/scoring.test.jsonl", gold_path),
        ):
            files.append(
                {
                    "path": relative,
                    "sha256": _sha256(path),
                    "bytes": path.stat().st_size,
                }
            )
        manifest = {
            "schema_version": "1.0",
            "status": "frozen",
            "gold_status": "provisional_pending_human_adjudication",
            "files": files,
        }
        manifest_path = root / "corpus" / "freeze-manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        return _sha256(manifest_path), cases_path, gold_path

    def test_verifies_detached_manifest_cases_gold_and_complete_case_panel(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_sha, _, _ = self.build(root)
            evidence = verify_frozen_scoring_corpus(
                root,
                expected_freeze_manifest_sha256=manifest_sha,
                split="test",
            )

            self.assertEqual(evidence.freeze_manifest_sha256, manifest_sha)
            self.assertEqual(evidence.split, "test")
            self.assertEqual([item["case_id"] for item in evidence.cases], ["C001", "C002"])
            self.assertEqual([item["finding_id"] for item in evidence.gold], ["G001"])
            mutated = list(evidence.cases)
            mutated[0]["text"] = "forged"
            self.assertNotEqual(mutated[0], evidence.cases[0])

    def test_rejects_wrong_detached_hash_tampering_and_unknown_gold_case(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_sha, cases_path, gold_path = self.build(root)
            with self.assertRaises(CorpusEvidenceError):
                verify_frozen_scoring_corpus(
                    root,
                    expected_freeze_manifest_sha256="f" * 64,
                    split="test",
                )

            cases_path.write_bytes(cases_path.read_bytes() + b"\n")
            with self.assertRaises(CorpusEvidenceError):
                verify_frozen_scoring_corpus(
                    root,
                    expected_freeze_manifest_sha256=manifest_sha,
                    split="test",
                )

            manifest_sha, _, gold_path = self.build(root)
            write_jsonl(gold_path, [finding("UNKNOWN", "G999")])
            manifest_path = root / "corpus" / "freeze-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            entry = next(item for item in manifest["files"] if item["path"].endswith("scoring.test.jsonl"))
            entry["sha256"] = _sha256(gold_path)
            entry["bytes"] = gold_path.stat().st_size
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            with self.assertRaisesRegex(CorpusEvidenceError, "unknown case"):
                verify_frozen_scoring_corpus(
                    root,
                    expected_freeze_manifest_sha256=_sha256(manifest_path),
                    split="test",
                )


if __name__ == "__main__":
    unittest.main()
