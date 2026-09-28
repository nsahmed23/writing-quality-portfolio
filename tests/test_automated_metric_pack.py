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
            "metrics": {"candidate_preference": 0.6, "lower_bound": 0.2},
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

    def invoke(self, report=True):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        env = os.environ.copy()
        env.pop("WQ_EVAL_REPORT", None)
        if report:
            env["WQ_EVAL_REPORT"] = str(self.report)
        command = [sys.executable if part == "python3" else part for part in manifest["command"]]
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
            "documents": 6, "ci_lower": float("inf"), "recommendation": "candidate"}})), encoding="utf-8")
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
        self.report.write_text(json.dumps(self.report_value(by_lane={"editing": {
            "cases": 7, "documents": 6, "mean": 0.6, "ci_lower": 0.2,
            "ci_upper": 0.8, "recommendation": "candidate"}})), encoding="utf-8")
        payload = self.invoke()
        self.assertEqual({m["id"] for m in payload["metrics"]},
                         {"wq-automated-candidate-preference", "wq-automated-lower-bound",
                          "wq-automated-editing-cases", "wq-automated-editing-documents",
                          "wq-automated-editing-mean", "wq-automated-editing-ci-lower",
                          "wq-automated-editing-ci-upper"})
        self.assertTrue(any(c["status"] == "pass" for c in payload["checks"]))

    def test_demo_is_informative_only_even_with_claimed_eligibility(self):
        self.report.write_text(json.dumps(self.report_value(execution="demo")), encoding="utf-8")
        payload = self.invoke()
        self.assertTrue(all(c["status"] == "warn" for c in payload["checks"]))
        self.assertEqual(payload["metrics"], [])

    def test_failed_gate_cannot_pass_even_if_recommendation_claims_candidate(self):
        self.report.write_text(json.dumps(self.report_value(
            by_lane={"editing": {"documents": 6, "ci_lower": 0.2,
                                 "recommendation": "candidate"}},
            checks=[{"id": "coverage", "passed": False, "message": "incomplete"}])), encoding="utf-8")
        payload = self.invoke()
        self.assertTrue(all(c["status"] == "warn" for c in payload["checks"]))

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
