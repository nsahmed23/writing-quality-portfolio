from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from wqeval.gates import _evaluate_stage1_gate_metrics as evaluate_stage1_gate
from wqeval.human_review import trusted_human_roster_sha256
from wqeval.jobs import GoldLeakError, assert_no_gold_leak, prepare_stage1_jobs, validate_stage1_job

from tests.support import (
    case,
    finding,
    human_gold_review_artifact,
    human_review_artifact,
    trusted_human_roster,
)


class JobPreparationTests(unittest.TestCase):
    def test_jobs_are_deterministic_complete_and_gold_free(self) -> None:
        cases = [case(f"C{index:03d}", f"Text {index}.") for index in range(1, 5)]
        systems = [
            {"system_id": "portfolio-current", "source_files": [{"path": "portfolio.md", "sha256": "a" * 64}]},
            {"system_id": "normalized-union", "source_files": [{"path": "union.md", "sha256": "b" * 64}]},
        ]
        model = {"selection": "session_inherited", "override": False}
        first = prepare_stage1_jobs(cases, systems, runs=3, seed=20260825, model=model)
        second = prepare_stage1_jobs(list(reversed(cases)), list(reversed(systems)), runs=3, seed=20260825, model=model)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 6)
        self.assertEqual(len({job["job_id"] for job in first}), 6)
        self.assertEqual({job["run_number"] for job in first}, {1, 2, 3})
        for job in first:
            self.assertEqual(len(job["cases"]), 4)
            self.assertEqual(job["model"], model)
            assert_no_gold_leak(job)

    def test_seed_changes_case_order_without_changing_membership(self) -> None:
        cases = [case(f"C{index:03d}", f"Text {index}.") for index in range(1, 7)]
        systems = [{"system_id": "union", "source_files": []}]
        first = prepare_stage1_jobs(cases, systems, runs=1, seed=1, model={})
        second = prepare_stage1_jobs(cases, systems, runs=1, seed=2, model={})
        first_ids = [item["case_id"] for item in first[0]["cases"]]
        second_ids = [item["case_id"] for item in second[0]["cases"]]
        self.assertCountEqual(first_ids, second_ids)
        self.assertNotEqual(first_ids, second_ids)

    def test_recursive_gold_leak_check_blocks_hidden_labels(self) -> None:
        assert_no_gold_leak({"cases": [{"case_id": "C001", "text": "Clean."}]})
        for key in (
            "gold_findings",
            "case_decision",
            "propositions",
            "voice_signals",
            "features",
            "source_refs",
            "primary_source_id",
        ):
            with self.subTest(key=key), self.assertRaises(GoldLeakError):
                assert_no_gold_leak({"cases": [{"case_id": "C001", key: []}]})

    def test_unsafe_system_ids_are_rejected_before_job_paths_are_derived(self) -> None:
        cases = [case()]
        for system_id in ("../outside", "x/../../../outside", "C:stream", "with space", "CON"):
            with self.subTest(system_id=system_id), self.assertRaises(ValueError):
                prepare_stage1_jobs(cases, [{"system_id": system_id, "source_files": []}], runs=1, seed=1, model={})

    def test_final_job_schema_binds_public_vocabulary_counts_identity_and_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_root = Path(directory)
            job = prepare_stage1_jobs(
                [case()],
                [{"system_id": "union", "source_files": [{"path": "C:/source.md", "sha256": "a" * 64}]}],
                runs=1,
                seed=1,
                model={"selection": "inherited"},
            )[0]
            job.update(
                {
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
                        "output_path": str((run_root / "inbox" / f"{job['job_id']}.jsonl").resolve()),
                    },
                }
            )
            validate_stage1_job(job, run_root=run_root)

            for broken in (
                dict(job, expected_case_count=2),
                dict(job, job_id="stage1-forged-run-99"),
                dict(job, problem_families=None),
                dict(job, output_contract=dict(job["output_contract"], output_path=str(run_root / "outside.jsonl"))),
                dict(job, extra="not allowed"),
            ):
                with self.subTest(broken=broken), self.assertRaises(ValueError):
                    validate_stage1_job(broken, run_root=run_root)


class StageGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.thresholds = {
            "schema_compliance_min": 1.0,
            "positive_opportunities_min": 10,
            "keep_opportunities_min": 10,
            "exact_precision_min": 0.8,
            "exact_recall_min": 0.6,
            "keep_accuracy_min": 0.9,
            "critical_meaning_risk_max": 0,
            "critical_miss_rate_max": 0.05,
            "human_gold_adjudication_required": True,
        }
        self.passing = {
            "schema_compliance": 1.0,
            "positive_opportunities": 20,
            "keep_opportunities": 20,
            "precision": 0.9,
            "recall": 0.8,
            "keep_accuracy": 0.95,
            "critical_meaning_risk": 0,
            "critical_miss_rate": 0.0,
        }
        self.predictions = [finding("C001", "P001")]
        self.review_artifact = human_review_artifact(self.predictions)
        self.cases = [case("C001")]
        self.gold = [finding("C001", "G001")]
        self.gold_review_artifact = human_gold_review_artifact(self.cases, self.gold)
        self.roster = trusted_human_roster()
        self.roster_sha256 = trusted_human_roster_sha256(self.roster)

    def test_objective_pass_remains_locked_without_human_adjudication(self) -> None:
        result = evaluate_stage1_gate(self.passing, self.thresholds)
        self.assertTrue(result["objective_pass"])
        self.assertFalse(result["stage2_eligible"])
        self.assertEqual(result["status"], "PENDING_HUMAN_REVIEW")
        with self.assertRaises(TypeError):
            evaluate_stage1_gate(self.passing, self.thresholds, human_adjudicated="yes")

    def test_legacy_metric_gate_rejects_caller_supplied_human_material(self) -> None:
        with self.assertRaises(TypeError):
            evaluate_stage1_gate(
                self.passing,
                self.thresholds,
                predictions=self.predictions,
                human_review_artifact=self.review_artifact,
                cases=self.cases,
                gold_findings=self.gold,
                human_gold_review_artifact=self.gold_review_artifact,
                trusted_human_roster=self.roster,
                expected_human_roster_sha256=self.roster_sha256,
            )

        failed_metrics = dict(self.passing, precision=0.79)
        failed = evaluate_stage1_gate(failed_metrics, self.thresholds)
        self.assertFalse(failed["stage2_eligible"])
        self.assertEqual(failed["status"], "FAIL")
        self.assertIn("precision", failed["failed_conditions"])

    def test_unavailable_human_metric_is_pending_not_an_objective_failure(self) -> None:
        provisional = dict(self.passing, critical_meaning_risk=None)
        result = evaluate_stage1_gate(provisional, self.thresholds)
        self.assertTrue(result["objective_pass"])
        self.assertFalse(result["stage2_eligible"])
        self.assertEqual(result["status"], "PENDING_HUMAN_REVIEW")
        self.assertIn("critical_meaning_risk", result["pending_conditions"])

        with self.assertRaises(TypeError):
            evaluate_stage1_gate(
                provisional,
                self.thresholds,
                human_review_artifact=self.review_artifact,
            )

    def test_sized_slice_precision_is_enforced(self) -> None:
        thresholds = dict(
            self.thresholds,
            sized_slice_positive_opportunities_min=5,
            sized_slice_precision_min=0.65,
        )
        metrics = dict(
            self.passing,
            by_genre={
                "technical": {"case_count": 12, "positive_opportunities": 6, "precision": 0.6},
                "reference": {"case_count": 12, "positive_opportunities": 4, "precision": 0.2},
            },
            by_author_type={},
            by_author_profile={
                "domain_expert": {"case_count": 12, "positive_opportunities": 5, "precision": 0.8}
            },
        )
        result = evaluate_stage1_gate(
            metrics,
            thresholds,
        )
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("by_genre.technical.precision", result["failed_conditions"])


if __name__ == "__main__":
    unittest.main()
