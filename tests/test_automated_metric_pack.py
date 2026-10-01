"""Exercise the metric pack as Plugin Eval does: a fresh subprocess per target."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "evaluation/benchmark_v2/automated/plugin_eval/manifest.json"


class MetricPackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.skill = self.dir / "SKILL.md"
        self.skill.write_text("# Candidate\n", encoding="utf-8")
        self.report = self.dir / "report.json"

    def report_value(self, **changes):
        value = {
            "schema_version": 1,
            "evaluation_type": "automated_proxy",
            "execution": "live", "mode": "compare", "complete": True,
            "eligible": True, "recommendation": "candidate",
            "metrics": {"candidate_preference": 0.6, "wilson_lower": 0.6892, "sign_test_p_candidate": 0.015625,
                        "sign_test_p_baseline": 1.0},
            "checks": [{"id": "coverage", "passed": True, "message": "complete"}],
            "by_judge": {}, "by_lane": {}, "counts": {},
            "provenance": {
                "candidate_skill_sha256": hashlib.sha256(self.skill.read_bytes()).hexdigest(),
                "suite_sha256": "a" * 64, "rubric_sha256": "b" * 64,
                "config_sha256": "c" * 64, "judge_signature": "d" * 64,
            },
        }
        value.update(changes)
        return value

    @staticmethod
    def lane(**changes):
        """Six documents that all favour the candidate: 6 of 6 decisive, Wilson interval from 0.6892 to 1."""
        value = {"cases": 7, "documents": 6, "decisive": 6, "wins": 6, "losses": 0, "proportion": 1.0,
                 "wilson_lower": 0.6892, "wilson_upper": 1.0, "mean": 0.6, "sign_test_p_candidate": 0.015625,
                 "sign_test_p_baseline": 1.0, "recommendation": "candidate"}
        value.update(changes)
        return value

    def invoke(self, report=True):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        env = os.environ.copy()
        env.pop("WQ_EVAL_REPORT", None)
        if report:
            env["WQ_EVAL_REPORT"] = str(self.report)
        command = [sys.executable if part == "python" else part for part in manifest["command"]]
        result = subprocess.run(command + [str(self.skill), "skill"], cwd=MANIFEST.parent,
                                env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(set(payload), {"checks", "metrics", "artifacts"})
        return payload

    def test_missing_report_is_warning_only(self):
        payload = self.invoke(report=False)
        self.assertEqual(payload["metrics"], [])
        self.assertTrue(all(c["status"] == "warn" for c in payload["checks"]))
        missing_path = self.invoke()
        self.assertEqual(missing_path["metrics"], [])
        self.assertTrue(all(c["status"] == "warn" for c in missing_path["checks"]))

    def test_invalid_schema_is_warning_only(self):
        self.report.write_text('{"schema_version": 1, "execution": "live"}', encoding="utf-8")
        payload = self.invoke()
        self.assertEqual(payload["metrics"], [])
        self.assertTrue(all(c["status"] == "warn" for c in payload["checks"]))
        self.report.write_text(json.dumps(self.report_value(by_lane={"editing": {
            "documents": 6, "wilson_lower": float("inf"), "recommendation": "candidate"}})), encoding="utf-8")
        nonfinite = self.invoke()
        self.assertEqual(nonfinite["metrics"], [])
        self.assertTrue(all(c["status"] == "warn" for c in nonfinite["checks"]))

    def test_stale_skill_and_missing_provenance_are_warnings(self):
        for change in ({"provenance": {"candidate_skill_sha256": "0" * 64}},
                       {"provenance": {**self.report_value()["provenance"],
                                       "candidate_skill_sha256": "0" * 64}}):
            with self.subTest(change=change):
                self.report.write_text(json.dumps(self.report_value(**change)), encoding="utf-8")
                payload = self.invoke()
                self.assertEqual(payload["metrics"], [])
                self.assertTrue(all(c["status"] == "warn" for c in payload["checks"]))

    def test_verified_live_comparison_emits_extension_metrics(self):
        self.report.write_text(json.dumps(self.report_value(by_lane={"editing": self.lane()})), encoding="utf-8")
        payload = self.invoke()
        self.assertEqual({m["id"] for m in payload["metrics"]},
                         {"wq-automated-candidate-preference", "wq-automated-wilson-lower",
                          "wq-automated-sign-test-p-candidate", "wq-automated-sign-test-p-baseline",
                          "wq-automated-editing-cases", "wq-automated-editing-documents",
                          "wq-automated-editing-decisive", "wq-automated-editing-wins",
                          "wq-automated-editing-losses", "wq-automated-editing-proportion",
                          "wq-automated-editing-wilson-lower", "wq-automated-editing-wilson-upper",
                          "wq-automated-editing-mean", "wq-automated-editing-sign-test-p-candidate",
                          "wq-automated-editing-sign-test-p-baseline"})
        self.assertNotIn("wq-automated-lower-bound", {m["id"] for m in payload["metrics"]})
        self.assertNotIn("wq-automated-editing-sign-test-p", {m["id"] for m in payload["metrics"]})
        self.assertTrue(any(c["status"] == "pass" for c in payload["checks"]))

    def test_lane_gate_rechecks_the_wilson_bound_the_effect_floor_and_the_candidate_p_value(self):
        # 0.0501 is just over the one-sided alpha; a missing or non-numeric p-value cannot pass either.
        cases = ({"wilson_lower": 0.5}, {"mean": 0.1499}, {"wilson_lower": None}, {"mean": None},
                 {"wilson_lower": 0.4999}, {"documents": 4}, {"sign_test_p_candidate": 0.0501},
                 {"sign_test_p_candidate": None}, {"sign_test_p_candidate": "0.01"})
        for change in cases:
            with self.subTest(change=change):
                self.report.write_text(json.dumps(self.report_value(by_lane={"editing": self.lane(**change)})),
                                       encoding="utf-8")
                status = {c["id"]: c["status"] for c in self.invoke()["checks"]}
                self.assertEqual(status["wq-automated-evidence"], "warn")
        for boundary in ({"mean": 0.15}, {"sign_test_p_candidate": 0.05}):
            with self.subTest(boundary=boundary):
                self.report.write_text(json.dumps(self.report_value(by_lane={"editing": self.lane(**boundary)})),
                                       encoding="utf-8")
                status = {c["id"]: c["status"] for c in self.invoke()["checks"]}
                self.assertEqual(status["wq-automated-evidence"], "pass")

    def test_demo_is_informative_only_even_with_claimed_eligibility(self):
        self.report.write_text(json.dumps(self.report_value(execution="demo")), encoding="utf-8")
        payload = self.invoke()
        self.assertTrue(all(c["status"] == "warn" for c in payload["checks"]))
        self.assertEqual(payload["metrics"], [])

    def test_failed_gate_cannot_pass_even_if_recommendation_claims_candidate(self):
        for failed_id in ("coverage", "candidate_checks", "calibration_certificate"):
            with self.subTest(failed_id=failed_id):
                self.report.write_text(json.dumps(self.report_value(
                    by_lane={"editing": self.lane()},
                    checks=[{"id": failed_id, "passed": False, "message": "gate failed"}])),
                    encoding="utf-8")
                payload = self.invoke()
                self.assertTrue(all(c["status"] == "warn" for c in payload["checks"]))

    def test_baseline_failure_does_not_veto_eligible_candidate(self):
        self.report.write_text(json.dumps(self.report_value(
            by_lane={"editing": self.lane()},
            checks=[{"id": "coverage", "passed": True, "message": "complete"},
                    {"id": "candidate_checks", "passed": True, "message": "candidate preserved facts"},
                    {"id": "baseline_checks", "passed": False, "message": "baseline omitted a fact"}])),
            encoding="utf-8")
        payload = self.invoke()
        status = {c["id"]: c["status"] for c in payload["checks"]}
        self.assertEqual(status["wq-automated-evidence"], "pass")
        self.assertEqual(status["wq-automated-baseline_checks"], "warn")
        self.assertEqual(status["wq-automated-candidate_checks"], "pass")

    def test_reference_text_hashes_and_unlabeled_split(self):
        path = ROOT / "evaluation/benchmark_v2/automated/data/references.json"
        cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
        self.assertGreaterEqual(len(cases), 3)
        for case in cases:
            with self.subTest(id=case["id"]):
                self.assertEqual((case["split"], case["expected"]), ("development", None))
                for label in ("a", "b"):
                    digest = hashlib.sha256(case[label].encode("utf-8")).hexdigest()
                    self.assertIn(f"{label}_utf8_sha256={digest}", case["provenance"]["note"])


if __name__ == "__main__":
    unittest.main()
