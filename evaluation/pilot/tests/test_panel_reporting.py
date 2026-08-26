from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tests.support import case, finding
from tests.test_cli_integration import freeze_corpus
from tests.test_output_evidence import Stage1EvidenceFixture
from wqeval.corpus_evidence import verify_frozen_scoring_corpus
from wqeval.output_evidence import finalize_stage1_output
from wqeval.panel import build_verified_stage1_panel


def _thresholds() -> dict:
    return {
        "schema_compliance_min": 1.0,
        "positive_opportunities_min": 1,
        "keep_opportunities_min": 0,
        "exact_precision_min": 0.8,
        "exact_recall_min": 0.6,
        "keep_accuracy_min": 0.0,
        "critical_meaning_risk_max": 0,
        "critical_miss_rate_max": 0.05,
        "human_gold_adjudication_required": True,
    }


class VerifiedStageOnePanelTests(unittest.TestCase):
    def test_infers_exact_system_panel_and_keeps_stage_two_locked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            run_root = project / "runs" / "sealed"
            run_root.mkdir(parents=True)
            fixture = Stage1EvidenceFixture(run_root)
            for system_id in ("system-b", "system-a"):
                for run_number in (1, 2, 3):
                    fixture.add_job(
                        system_id,
                        run_number,
                        valid=not (system_id == "system-b" and run_number == 2),
                    )
            jobs_sha, _ = fixture.publish()
            anchor = finalize_stage1_output(run_root, expected_jobs_manifest_sha256=jobs_sha)
            freeze_sha = freeze_corpus(
                project,
                [case("C001")],
                [finding("C001", "G001", severity="critical")],
            )
            corpus = verify_frozen_scoring_corpus(
                project,
                expected_freeze_manifest_sha256=freeze_sha,
                split="test",
            )

            panel = build_verified_stage1_panel(
                corpus,
                run_root=run_root,
                expected_output_evidence_sha256=anchor.sha256,
                expected_runs=3,
                thresholds=_thresholds(),
            )
            report = panel.report
            self.assertEqual(report["status"], "PILOT_UNADJUDICATED")
            self.assertFalse(report["stage2_eligible"])
            self.assertEqual(report["systems"], ["system-a", "system-b"])
            self.assertEqual(report["objective_pass_count"], 1)
            self.assertEqual(report["objective_fail_count"], 1)
            self.assertEqual(report["results"]["system-a"]["gate"]["status"], "PENDING_HUMAN_REVIEW")
            self.assertEqual(report["results"]["system-b"]["gate"]["status"], "FAIL")
            self.assertEqual(report["results"]["system-b"]["invalid_run_numbers"], [2])
            self.assertEqual(report["evidence"]["output_evidence_sha256"], anchor.sha256)
            self.assertEqual(report["evidence"]["corpus_freeze_manifest_sha256"], freeze_sha)
            self.assertEqual(len(report["evidence"]["thresholds_sha256"]), 64)
            self.assertEqual(len(panel.evaluations), 2)
            self.assertEqual(
                {prediction["system_id"] for prediction in panel.predictions},
                {"system-a", "system-b"},
            )

    def test_rejects_nonuniform_or_incomplete_run_panels_before_scoring(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            run_root = project / "runs" / "sealed"
            run_root.mkdir(parents=True)
            fixture = Stage1EvidenceFixture(run_root)
            fixture.add_job("system-a", 1)
            fixture.add_job("system-a", 2)
            jobs_sha, _ = fixture.publish()
            anchor = finalize_stage1_output(run_root, expected_jobs_manifest_sha256=jobs_sha)
            freeze_sha = freeze_corpus(project, [case("C001")], [finding("C001", "G001")])
            corpus = verify_frozen_scoring_corpus(
                project,
                expected_freeze_manifest_sha256=freeze_sha,
                split="test",
            )
            with self.assertRaisesRegex(ValueError, "exact run panel"):
                build_verified_stage1_panel(
                    corpus,
                    run_root=run_root,
                    expected_output_evidence_sha256=anchor.sha256,
                    expected_runs=3,
                    thresholds=_thresholds(),
                )


if __name__ == "__main__":
    unittest.main()
