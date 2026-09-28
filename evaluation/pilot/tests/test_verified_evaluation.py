from __future__ import annotations

import hashlib
import inspect
import json
import tempfile
import unittest
from pathlib import Path

from tests.support import case, finding, write_jsonl
from tests.test_output_evidence import Stage1EvidenceFixture
from wqeval.corpus_evidence import verify_frozen_scoring_corpus
from wqeval.evaluation import EvaluationEvidenceError, build_verified_stage1_evaluation
from wqeval.gates import _evaluate_stage1_gate_metrics, evaluate_stage1_gate
from wqeval.output_evidence import finalize_stage1_output


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _freeze_corpus(project: Path, source_case: dict) -> str:
    cases_path = project / "corpus" / "cases.test.jsonl"
    gold_path = project / "private" / "gold" / "scoring.test.jsonl"
    cases_path.parent.mkdir(parents=True, exist_ok=True)
    gold_path.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(cases_path, [source_case])
    span_text = source_case["text"][:3]
    write_jsonl(
        gold_path,
        [finding("C001", "G001", severity="critical", span_text=span_text)],
    )
    manifest = {
        "schema_version": "1.0",
        "status": "frozen",
        "gold_status": "provisional_pending_human_adjudication",
        "files": [
            {
                "path": "corpus/cases.test.jsonl",
                "sha256": _sha256(cases_path),
                "bytes": cases_path.stat().st_size,
            },
            {
                "path": "private/gold/scoring.test.jsonl",
                "sha256": _sha256(gold_path),
                "bytes": gold_path.stat().st_size,
            },
        ],
    }
    manifest_path = project / "corpus" / "freeze-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return _sha256(manifest_path)


class VerifiedEvaluationTests(unittest.TestCase):
    def test_legacy_gate_entry_points_expose_no_human_trust_arguments(self) -> None:
        self.assertEqual(
            list(inspect.signature(evaluate_stage1_gate).parameters),
            ["evaluation", "thresholds"],
        )
        self.assertEqual(
            list(inspect.signature(_evaluate_stage1_gate_metrics).parameters),
            ["metrics", "thresholds"],
        )

    def build(self, root: Path, *, invalid_run: int | None = None, corpus_case: dict | None = None):
        project = root / "project"
        run_root = project / "runs" / "sealed"
        run_root.mkdir(parents=True)
        fixture = Stage1EvidenceFixture(run_root)
        for run_number in (1, 2, 3):
            fixture.add_job("candidate", run_number, valid=run_number != invalid_run)
        jobs_sha, _ = fixture.publish()
        anchor = finalize_stage1_output(run_root, expected_jobs_manifest_sha256=jobs_sha)
        manifest_sha = _freeze_corpus(project, corpus_case or case("C001"))
        corpus = verify_frozen_scoring_corpus(
            project,
            expected_freeze_manifest_sha256=manifest_sha,
            split="test",
        )
        return project, run_root, anchor.sha256, corpus

    def test_builds_worst_run_gate_bundle_from_two_detached_evidence_roots(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, run_root, anchor_sha, corpus = self.build(Path(directory))
            evaluation = build_verified_stage1_evaluation(
                corpus,
                run_root=run_root,
                expected_output_evidence_sha256=anchor_sha,
                system_id="candidate",
                expected_runs=3,
            )

            metrics = evaluation.gate_metrics
            self.assertEqual(metrics["aggregation_policy"], "worst_run")
            self.assertEqual(metrics["schema_compliance"], 1.0)
            self.assertEqual(metrics["precision"], 1.0)
            self.assertEqual(metrics["recall"], 1.0)
            self.assertEqual(metrics["critical_miss_rate"], 0.0)
            self.assertEqual(len(evaluation.predictions), 3)
            self.assertEqual(evaluation.corpus_freeze_manifest_sha256, corpus.freeze_manifest_sha256)
            self.assertEqual(evaluation.output_evidence_sha256, anchor_sha)
            thresholds = {
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
            pending = evaluate_stage1_gate(evaluation, thresholds)
            self.assertEqual(pending["status"], "PENDING_HUMAN_REVIEW")
            self.assertFalse(pending["stage2_eligible"])
            self.assertEqual(
                pending["verified_evidence"]["predictions_sha256"],
                evaluation.predictions_sha256,
            )

            with self.assertRaises(TypeError):
                evaluate_stage1_gate(evaluation.gate_metrics, thresholds)

    def test_invalid_run_is_preserved_and_forces_conservative_gate_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, run_root, anchor_sha, corpus = self.build(Path(directory), invalid_run=2)
            evaluation = build_verified_stage1_evaluation(
                corpus,
                run_root=run_root,
                expected_output_evidence_sha256=anchor_sha,
                system_id="candidate",
                expected_runs=3,
            )
            self.assertEqual(evaluation.gate_metrics["schema_compliance"], 2 / 3)
            self.assertEqual(evaluation.gate_metrics["precision"], 0.0)
            self.assertEqual(evaluation.gate_metrics["recall"], 0.0)
            self.assertEqual(evaluation.gate_metrics["critical_miss_rate"], 1.0)
            self.assertEqual(evaluation.invalid_run_numbers, (2,))

    def test_rejects_a_hash_valid_corpus_whose_case_content_differs_from_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            _, run_root, anchor_sha, corpus = self.build(
                Path(directory),
                corpus_case=case("C001", "Different frozen text."),
            )
            with self.assertRaisesRegex(EvaluationEvidenceError, "case panel"):
                build_verified_stage1_evaluation(
                    corpus,
                    run_root=run_root,
                    expected_output_evidence_sha256=anchor_sha,
                    system_id="candidate",
                    expected_runs=3,
                )


if __name__ == "__main__":
    unittest.main()
