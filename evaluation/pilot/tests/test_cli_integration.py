from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_output_evidence import Stage1EvidenceFixture
from tests.support import case, finding, write_jsonl
from wqeval.output_evidence import finalize_stage1_output


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"


def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(SRC_ROOT) + os.pathsep + environment.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "wqeval.cli", *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=15,
        check=False,
    )


def freeze_corpus(project: Path, cases: list[dict], gold: list[dict]) -> str:
    corpus_path = project / "corpus" / "cases.test.jsonl"
    gold_path = project / "private" / "gold" / "scoring.test.jsonl"
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    gold_path.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(corpus_path, cases)
    write_jsonl(gold_path, gold)
    entries = []
    for relative, path in (
        ("corpus/cases.test.jsonl", corpus_path),
        ("private/gold/scoring.test.jsonl", gold_path),
    ):
        payload = path.read_bytes()
        entries.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
            }
        )
    manifest = {
        "schema_version": "1.0",
        "status": "frozen",
        "gold_status": "provisional_pending_human_adjudication",
        "files": entries,
    }
    manifest_path = project / "corpus" / "freeze-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return hashlib.sha256(manifest_path.read_bytes()).hexdigest()


class CliIntegrationTests(unittest.TestCase):
    def test_validate_cases_returns_machine_readable_summary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "cases.jsonl"
            write_jsonl(source, [case("C001"), case("C002", "A personal note.", genre="personal")])
            result = run_cli("validate", "--kind", "cases", "--input", str(source))
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(result.stdout)
            self.assertEqual(summary, {"kind": "cases", "valid_records": 2})

    def test_validate_rejects_strict_json_error_without_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "cases.jsonl"
            source.write_text('{"case_id":"C001","case_id":"C002"}\n', encoding="utf-8")
            result = run_cli("validate", "--kind", "cases", "--input", str(source))
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "")
            self.assertIn("error", result.stderr.lower())
            self.assertNotIn("Traceback", result.stderr)

    def test_score_stage1_writes_metrics_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "run"
            root.mkdir()
            gold_path = base / "gold.jsonl"
            output_path = base / "metrics.json"
            gold = [finding("C001", "G001")]
            fixture = Stage1EvidenceFixture(root)
            fixture.add_job("candidate", 1)
            jobs_sha, _ = fixture.publish()
            anchor = finalize_stage1_output(
                root,
                expected_jobs_manifest_sha256=jobs_sha,
            )
            manifest_sha = freeze_corpus(base, [case("C001")], gold)

            result = run_cli(
                "score-stage1",
                "--project-root",
                str(base),
                "--corpus-freeze-sha256",
                manifest_sha,
                "--split",
                "test",
                "--run-root",
                str(root),
                "--output-evidence-sha256",
                anchor.sha256,
                "--system-id",
                "candidate",
                "--expected-runs",
                "1",
                "--output",
                str(output_path),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output_path.exists())
            metrics = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(metrics["gate_metrics"]["precision"], 1.0)
            self.assertEqual(metrics["gate_metrics"]["recall"], 1.0)

    def test_score_stage1_rejects_caller_selected_predictions_and_cases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ignored = root / "attacker.jsonl"
            write_jsonl(ignored, [finding("C001", "P999")])

            result = run_cli(
                "score-stage1",
                "--project-root",
                str(root),
                "--corpus-freeze-sha256",
                "e" * 64,
                "--split",
                "test",
                "--gold",
                str(ignored),
                "--run-root",
                str(root),
                "--output-evidence-sha256",
                "f" * 64,
                "--system-id",
                "candidate",
                "--expected-runs",
                "1",
                "--run-number",
                "1",
                "--predictions",
                str(ignored),
                "--cases",
                str(ignored),
                "--output",
                str(root / "metrics.json"),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unrecognized arguments", result.stderr)
            self.assertFalse((root / "metrics.json").exists())

    def test_score_stage1_cannot_overwrite_any_run_evidence_or_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gold_path = root / "gold.jsonl"
            fixture = Stage1EvidenceFixture(root)
            fixture.add_job("candidate", 1)
            jobs_sha, _ = fixture.publish()
            anchor = finalize_stage1_output(root, expected_jobs_manifest_sha256=jobs_sha)
            manifest_sha = freeze_corpus(root.parent, [case("C001")], [finding("C001", "G001")])
            job_id = "stage1-candidate-run-01"
            protected = (
                root / "manifests" / "jobs.json",
                root / "manifests" / "stage1-output-evidence.json",
                root / "manifests" / "receipts" / f"{job_id}.json",
                root / "raw" / f"{job_id}.jsonl",
                root / "normalized" / f"{job_id}.jsonl",
            )
            before = {path: path.read_bytes() for path in protected}
            for output in protected:
                with self.subTest(output=output):
                    result = run_cli(
                        "score-stage1",
                        "--project-root",
                        str(root.parent),
                        "--corpus-freeze-sha256",
                        manifest_sha,
                        "--split",
                        "test",
                        "--run-root",
                        str(root),
                        "--output-evidence-sha256",
                        anchor.sha256,
                        "--system-id",
                        "candidate",
                        "--expected-runs",
                        "1",
                        "--output",
                        str(output),
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(output.read_bytes(), before[output])

            outside_existing = root.parent / f"{root.name}-existing-metrics.json"
            outside_existing.write_text("preserve me\n", encoding="utf-8")
            try:
                result = run_cli(
                    "score-stage1",
                    "--project-root",
                    str(root.parent),
                    "--corpus-freeze-sha256",
                    manifest_sha,
                    "--split",
                    "test",
                    "--run-root",
                    str(root),
                    "--output-evidence-sha256",
                    anchor.sha256,
                    "--system-id",
                    "candidate",
                    "--expected-runs",
                    "1",
                    "--output",
                    str(outside_existing),
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(outside_existing.read_text(encoding="utf-8"), "preserve me\n")
            finally:
                outside_existing.unlink()


if __name__ == "__main__":
    unittest.main()
