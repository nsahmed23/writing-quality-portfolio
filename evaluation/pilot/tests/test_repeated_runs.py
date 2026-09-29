from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from wqeval.reconciliation import VerifiedStage1Run
from wqeval.repeats import aggregate_stage1_runs

from tests.support import case, finding, verified_scoring_corpus


class RepeatedRunAggregationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.corpus_counter = 0
        self.cases = [case("C001"), case("C002")]
        self.gold = [
            finding("C001", "G001", problem_code="vague_reference"),
            finding("C002", "G002", problem_code="vague_reference"),
        ]

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def corpus(self, gold: list[dict]):
        self.corpus_counter += 1
        root = Path(self.temporary.name) / f"corpus-{self.corpus_counter}"
        return verified_scoring_corpus(root, self.cases, gold)

    def prediction(self, gold_index: int, run_number: int, finding_id: str) -> dict:
        source = self.gold[gold_index]
        span = source["span"]
        return {
            "schema_version": "1.0",
            "case_id": source["case_id"],
            "finding_id": finding_id,
            "start": span["start"],
            "end": span["end"],
            "span": span["text"],
            "problem_name": source["problem"],
            "system_issue_code": source["problem_code"],
            "normalized_issue_code": source["problem_code"],
            "context_explanation": source["context"],
            "severity": source["severity"],
            "suggested_operation": {
                "operation_code": "revise",
                "instruction": source["suggested_operation"],
                "replacement": None,
            },
            "decision": source["decision"],
            "field_origin": "deterministic_adapter",
            "system_id": "candidate",
            "run_number": run_number,
        }

    def verified_run(
        self,
        run_number: int,
        predictions: list[dict],
        *,
        system_id: str = "candidate",
        cases: list[dict] | None = None,
        status: str = "valid",
    ) -> VerifiedStage1Run:
        payload = "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for item in predictions
        ).encode("utf-8")
        return VerifiedStage1Run(
            job_id=f"stage1-{system_id}-run-{run_number:02d}",
            system_id=system_id,
            run_number=run_number,
            raw_sha256="a" * 64,
            normalized_sha256=hashlib.sha256(payload).hexdigest() if status == "valid" else None,
            normalized_byte_count=len(payload) if status == "valid" else None,
            normalized_payload=payload if status == "valid" else None,
            cases_payload=(
                json.dumps(
                    self.cases if cases is None else cases,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8"),
            model_payload=b'{"selection":"inherited"}\n',
            error_type=None if status == "valid" else "StrictJsonError",
            error_message=None if status == "valid" else "invalid JSON",
            status=status,
            record_count=len(self.cases if cases is None else cases) if status == "valid" else 0,
        )

    def aggregate(self, runs: dict[int, list[dict]], *, gold: list[dict] | None = None) -> dict:
        verified = [self.verified_run(run, predictions) for run, predictions in sorted(runs.items())]
        with patch(
            "wqeval.repeats.reconcile_stage1_outputs",
            return_value={"runs": verified},
        ) as reconcile:
            result = aggregate_stage1_runs(
                self.corpus(self.gold if gold is None else gold),
                run_root="run",
                expected_output_evidence_sha256="f" * 64,
                system_id="candidate",
                expected_runs=3,
            )
        reconcile.assert_called_once()
        return result

    def test_reports_first_any_and_all_run_detection_without_pooling_false_positives(self) -> None:
        runs = {
            1: [self.prediction(0, 1, "P101")],
            2: [],
            3: [self.prediction(0, 3, "P301"), self.prediction(1, 3, "P302")],
        }

        result = self.aggregate(runs)

        self.assertEqual(result["run_numbers"], [1, 2, 3])
        self.assertEqual(result["gold_change_findings"], 2)
        self.assertEqual(result["pass_at_1"], 0.5)
        self.assertEqual(result["pass_at_3_any"], 1.0)
        self.assertEqual(result["pass_power_3"], 0.0)
        self.assertEqual(result["per_run"]["1"]["true_positives"], 1)
        self.assertEqual(result["per_run"]["2"]["true_positives"], 0)
        self.assertEqual(result["per_run"]["3"]["true_positives"], 2)
        self.assertEqual(result["mean_exact_precision"], 1.0)
        self.assertEqual(result["mean_exact_recall"], 0.5)
        self.assertEqual(result["precision_defined_run_count"], 2)
        self.assertEqual(result["precision_undefined_run_count"], 1)

    def test_requires_exact_run_panel_and_verified_prediction_identity(self) -> None:
        complete = {1: [], 2: [], 3: []}
        with self.assertRaisesRegex(ValueError, "run panel"):
            self.aggregate({1: [], 3: []})

        wrong_run = self.prediction(0, 2, "P001")
        with self.assertRaisesRegex(ValueError, "run_number"):
            self.aggregate({**complete, 1: [wrong_run]})

        wrong_system = {**self.prediction(0, 1, "P002"), "system_id": "other"}
        with self.assertRaisesRegex(ValueError, "system_id"):
            self.aggregate({**complete, 1: [wrong_system]})

        with self.assertRaisesRegex(ValueError, "run panel"):
            self.aggregate({1: []})

    def test_rejects_unknown_cases_instead_of_silently_discarding_false_findings(self) -> None:
        unknown = {
            **self.prediction(0, 1, "P999"),
            "case_id": "UNKNOWN",
        }
        with self.assertRaisesRegex(ValueError, "unknown case"):
            self.aggregate({1: [unknown], 2: [], 3: []})

    def test_rejects_equal_length_substituted_case_panel_from_verified_jobs(self) -> None:
        substituted = [case("C999"), case("C002")]
        verified = [
            self.verified_run(1, [], cases=self.cases),
            self.verified_run(2, [], cases=substituted),
            self.verified_run(3, [], cases=self.cases),
        ]
        with patch(
            "wqeval.repeats.reconcile_stage1_outputs",
            return_value={"runs": verified, "schema_compliance_rate": 1.0},
        ):
            with self.assertRaisesRegex(ValueError, "case panel"):
                aggregate_stage1_runs(
                    self.corpus(self.gold),
                    run_root="run",
                    expected_output_evidence_sha256="f" * 64,
                    system_id="candidate",
                    expected_runs=3,
                )

    def test_accepts_identical_verified_case_panels_in_different_job_orders(self) -> None:
        verified = [
            self.verified_run(1, [], cases=self.cases),
            self.verified_run(2, [], cases=list(reversed(self.cases))),
            self.verified_run(3, [], cases=self.cases),
        ]
        with patch(
            "wqeval.repeats.reconcile_stage1_outputs",
            return_value={"runs": verified, "schema_compliance_rate": 1.0},
        ):
            result = aggregate_stage1_runs(
                self.corpus(self.gold),
                run_root="run",
                expected_output_evidence_sha256="f" * 64,
                system_id="candidate",
                expected_runs=3,
            )
        self.assertEqual(result["run_numbers"], [1, 2, 3])

    def test_invalid_run_is_preserved_for_schema_compliance_without_scoring_it(self) -> None:
        verified = [
            self.verified_run(1, []),
            self.verified_run(2, [], status="invalid"),
            self.verified_run(3, []),
        ]
        with patch(
            "wqeval.repeats.reconcile_stage1_outputs",
            return_value={"runs": verified, "schema_compliance_rate": 2 / 3},
        ):
            result = aggregate_stage1_runs(
                self.corpus(self.gold),
                run_root="run",
                expected_output_evidence_sha256="f" * 64,
                system_id="candidate",
                expected_runs=3,
            )

        self.assertEqual(result["schema_compliance_rate"], 2 / 3)
        self.assertEqual(result["invalid_run_numbers"], [2])
        self.assertEqual(result["per_run"]["2"]["status"], "invalid")
        self.assertIsNone(result["pass_at_3_any"])
        self.assertEqual(
            result["undefined_repeat_metrics"],
            "one or more runs failed schema validation",
        )

    def test_undefined_repeat_metrics_are_null_when_gold_has_no_change_findings(self) -> None:
        keep_only = [finding("C001", "K001", problem_code="legitimate_passive", decision="KEEP")]
        result = self.aggregate({1: [], 2: [], 3: []}, gold=keep_only)
        self.assertIsNone(result["pass_at_1"])
        self.assertIsNone(result["pass_at_3_any"])
        self.assertIsNone(result["pass_power_3"])
        self.assertEqual(
            result["undefined_repeat_metrics"],
            "no gold CHANGE findings",
        )


if __name__ == "__main__":
    unittest.main()
