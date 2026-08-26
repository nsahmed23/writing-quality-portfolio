from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.test_output_evidence import Stage1EvidenceFixture


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
TOOL = PROJECT_ROOT / "tools" / "finalize_stage1_output.py"


def run_tool(*arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(SRC_ROOT) + os.pathsep + environment.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, str(TOOL), *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
        encoding="utf-8",
        capture_output=True,
        timeout=15,
        check=False,
    )


class FinalizeStage1OutputToolTests(unittest.TestCase):
    def test_tool_returns_fixed_anchor_receipt_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = Stage1EvidenceFixture(root)
            fixture.add_job("candidate", 1)
            jobs_sha, _ = fixture.publish()

            first = run_tool(
                "--run-root",
                str(root),
                "--expected-jobs-manifest-sha256",
                jobs_sha,
            )
            second = run_tool(
                "--run-root",
                str(root),
                "--expected-jobs-manifest-sha256",
                jobs_sha,
            )

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            receipt = json.loads(first.stdout)
            self.assertEqual(receipt, json.loads(second.stdout))
            self.assertEqual(
                receipt["relative_path"],
                "manifests/stage1-output-evidence.json",
            )
            self.assertEqual(len(receipt["sha256"]), 64)

    def test_tool_rejects_wrong_detached_jobs_hash_without_traceback_or_anchor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = Stage1EvidenceFixture(root)
            fixture.add_job("candidate", 1)
            fixture.publish()

            result = run_tool(
                "--run-root",
                str(root),
                "--expected-jobs-manifest-sha256",
                "f" * 64,
            )

            self.assertEqual(result.returncode, 2)
            self.assertEqual(result.stdout, "")
            self.assertIn("error:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse((root / "manifests" / "stage1-output-evidence.json").exists())


if __name__ == "__main__":
    unittest.main()
