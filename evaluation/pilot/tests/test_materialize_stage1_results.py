from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tests.support import case, finding, trusted_human_roster
from tests.test_cli_integration import freeze_corpus
from tests.test_output_evidence import Stage1EvidenceFixture
from tools.materialize_stage1_results import materialize_stage1_results
from wqeval.output_evidence import finalize_stage1_output
from wqeval.roster_anchor import build_human_roster_anchor


def _threshold_document() -> dict:
    return {
        "schema_version": "1.0",
        "stage1": {
            "schema_compliance_min": 1.0,
            "positive_opportunities_min": 1,
            "keep_opportunities_min": 0,
            "exact_precision_min": 0.8,
            "exact_recall_min": 0.6,
            "keep_accuracy_min": 0.0,
            "critical_meaning_risk_max": 0,
            "critical_miss_rate_max": 0.05,
            "human_gold_adjudication_required": True,
        },
        "stage2": {"locked": True},
    }


def _freeze_scoring_protocol_amendment(project: Path) -> str:
    document = {
        "schema_version": "1.0",
        "checkpoint": "stage1_scoring_protocol_prospective_safety_amendment",
        "status": "frozen_before_human_review",
        "human_review_state_at_freeze": {
            "human_ratings_observed": 0,
            "human_adjudications_observed": 0,
        },
        "policy": {"stage2_remains_locked": True},
    }
    path = project / ".checkpoints" / "07a_scoring_protocol_amendment.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MaterializeStageOneResultsTests(unittest.TestCase):
    def assert_isolated_distribution_package(
        self,
        destination: Path,
        *,
        package_name: str,
        role: str,
        expected_packet_id: str,
        expected_payload_names: set[str],
        forbidden_terms: set[str],
    ) -> None:
        package_root = destination / "distributions" / package_name
        observed_names = {
            path.relative_to(package_root).as_posix()
            for path in package_root.rglob("*")
            if path.is_file()
        }
        self.assertEqual(
            observed_names,
            {*expected_payload_names, "distribution-manifest.json"},
        )

        manifest_path = package_root / "distribution-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(
            set(manifest),
            {
                "schema_version",
                "package_kind",
                "status",
                "role",
                "review_packet_id",
                "manifest_scope",
                "package_paths",
                "files",
            },
        )
        self.assertEqual(manifest["schema_version"], "1.0")
        self.assertEqual(manifest["package_kind"], "stage1_review_distribution")
        self.assertEqual(manifest["status"], "PENDING_HUMAN_REVIEW")
        self.assertEqual(manifest["role"], role)
        self.assertEqual(manifest["review_packet_id"], expected_packet_id)
        self.assertEqual(
            set(manifest["package_paths"]),
            observed_names,
            "the package manifest must enumerate every package member, including itself",
        )
        self.assertEqual(
            {reference["path"] for reference in manifest["files"]},
            expected_payload_names,
            "the hash inventory must enumerate every non-manifest package member",
        )
        for reference in manifest["files"]:
            payload = (package_root / reference["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), reference["sha256"])
            self.assertEqual(len(payload), reference["bytes"])

        package_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(package_root.rglob("*.json"))
        ).casefold()
        for forbidden in forbidden_terms:
            self.assertNotIn(forbidden.casefold(), package_text)

    def test_rejects_a_destination_inside_the_immutable_run_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            run_root = project / "runs" / "sealed"
            run_root.mkdir(parents=True)
            fixture = Stage1EvidenceFixture(run_root)
            fixture.add_job("system-a", 1)
            jobs_sha, _ = fixture.publish()
            anchor = finalize_stage1_output(run_root, expected_jobs_manifest_sha256=jobs_sha)
            freeze_sha = freeze_corpus(project, [case("C001")], [finding("C001", "G001")])
            thresholds_path = project / "config" / "thresholds.json"
            thresholds_path.parent.mkdir(parents=True)
            thresholds_path.write_text(
                json.dumps(_threshold_document(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            thresholds_sha = hashlib.sha256(thresholds_path.read_bytes()).hexdigest()

            with self.assertRaisesRegex(ValueError, "run root|immutable"):
                materialize_stage1_results(
                    project_root=project,
                    run_root=run_root,
                    expected_output_evidence_sha256=anchor.sha256,
                    expected_corpus_freeze_sha256=freeze_sha,
                    expected_thresholds_sha256=thresholds_sha,
                    expected_scoring_protocol_amendment_sha256="d" * 64,
                    expected_runs=1,
                    expected_systems=1,
                    review_seed=20260825,
                    destination_root=run_root / "published-results",
                    authorized_root=project,
                )

    def test_rejects_a_missing_scoring_protocol_amendment_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            run_root = project / "runs" / "sealed"
            run_root.mkdir(parents=True)
            thresholds_path = project / "config" / "thresholds.json"
            thresholds_path.parent.mkdir(parents=True)
            thresholds_path.write_text(
                json.dumps(
                    _threshold_document(),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            thresholds_sha = hashlib.sha256(thresholds_path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "amendment checkpoint is missing"):
                materialize_stage1_results(
                    project_root=project,
                    run_root=run_root,
                    expected_output_evidence_sha256="a" * 64,
                    expected_corpus_freeze_sha256="b" * 64,
                    expected_thresholds_sha256=thresholds_sha,
                    expected_scoring_protocol_amendment_sha256="c" * 64,
                    expected_runs=1,
                    expected_systems=1,
                    review_seed=20260825,
                    destination_root=project / "artifacts" / "missing-amendment",
                    authorized_root=project,
                )

    def test_publishes_isolated_role_packages_and_refuses_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "project"
            run_root = project / "runs" / "sealed"
            run_root.mkdir(parents=True)
            fixture = Stage1EvidenceFixture(run_root)
            for system_id in ("system-a", "system-b"):
                for run_number in (1, 2, 3):
                    fixture.add_job(system_id, run_number)
            jobs_sha, _ = fixture.publish()
            anchor = finalize_stage1_output(run_root, expected_jobs_manifest_sha256=jobs_sha)
            freeze_sha = freeze_corpus(project, [case("C001")], [finding("C001", "G001")])
            thresholds_path = project / "config" / "thresholds.json"
            thresholds_path.parent.mkdir(parents=True)
            thresholds_path.write_text(
                json.dumps(_threshold_document(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            thresholds_sha = hashlib.sha256(thresholds_path.read_bytes()).hexdigest()
            amendment_sha = _freeze_scoring_protocol_amendment(project)
            destination = project / "artifacts" / "stage1-sealed-v1"
            provisional_destination = project / "artifacts" / "stage1-provisional-v1"

            provisional = materialize_stage1_results(
                project_root=project,
                run_root=run_root,
                expected_output_evidence_sha256=anchor.sha256,
                expected_corpus_freeze_sha256=freeze_sha,
                expected_thresholds_sha256=thresholds_sha,
                expected_scoring_protocol_amendment_sha256=amendment_sha,
                expected_runs=3,
                expected_systems=2,
                review_seed=20260825,
                destination_root=provisional_destination,
                authorized_root=project,
            )
            self.assertEqual(provisional["materialization_phase"], "provisional_report_only")
            self.assertIsNone(provisional["review_packet_id"])
            self.assertIsNone(provisional["human_roster_anchor_sha256"])
            self.assertEqual(
                provisional["scoring_protocol_amendment_sha256"],
                amendment_sha,
            )
            self.assertEqual(
                {
                    path.relative_to(provisional_destination).as_posix()
                    for path in provisional_destination.rglob("*")
                    if path.is_file()
                },
                {
                    "reports/stage1-provisional-report.json",
                    "tree-manifest.json",
                },
            )
            provisional_text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in provisional_destination.rglob("*.json")
            ).casefold()
            for forbidden in ("reviewer_template", "adjudicator_template", "review-bundle"):
                self.assertNotIn(forbidden, provisional_text)
            provisional_tree = json.loads(
                (provisional_destination / "tree-manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                provisional_tree["scoring_protocol_amendment_sha256"],
                amendment_sha,
            )

            roster_anchor = build_human_roster_anchor(
                human_roster=trusted_human_roster(),
                run_id=run_root.name,
                source_panel_report_sha256=provisional[
                    "panel_report_canonical_sha256"
                ],
            )
            with self.assertRaisesRegex(ValueError, "panel report"):
                materialize_stage1_results(
                    project_root=project,
                    run_root=run_root,
                    expected_output_evidence_sha256=anchor.sha256,
                    expected_corpus_freeze_sha256=freeze_sha,
                    expected_thresholds_sha256=thresholds_sha,
                    expected_scoring_protocol_amendment_sha256=amendment_sha,
                    expected_runs=3,
                    expected_systems=2,
                    review_seed=20260825,
                    destination_root=project / "artifacts" / "wrong-anchor",
                    authorized_root=project,
                    human_roster_anchor=dict(
                        roster_anchor,
                        source_panel_report_sha256="f" * 64,
                    ),
                )

            with self.assertRaisesRegex(ValueError, "amendment"):
                materialize_stage1_results(
                    project_root=project,
                    run_root=run_root,
                    expected_output_evidence_sha256=anchor.sha256,
                    expected_corpus_freeze_sha256=freeze_sha,
                    expected_thresholds_sha256=thresholds_sha,
                    expected_scoring_protocol_amendment_sha256="0" * 64,
                    expected_runs=3,
                    expected_systems=2,
                    review_seed=20260825,
                    destination_root=project / "artifacts" / "wrong-amendment",
                    authorized_root=project,
                    human_roster_anchor=roster_anchor,
                )

            summary = materialize_stage1_results(
                project_root=project,
                run_root=run_root,
                expected_output_evidence_sha256=anchor.sha256,
                expected_corpus_freeze_sha256=freeze_sha,
                expected_thresholds_sha256=thresholds_sha,
                expected_scoring_protocol_amendment_sha256=amendment_sha,
                expected_runs=3,
                expected_systems=2,
                review_seed=20260825,
                destination_root=destination,
                authorized_root=project,
                human_roster_anchor=roster_anchor,
            )

            self.assertEqual(summary["status"], "PILOT_UNADJUDICATED")
            self.assertEqual(summary["materialization_phase"], "review_packages")
            self.assertFalse(summary["stage2_eligible"])
            self.assertEqual(summary["system_count"], 2)
            self.assertEqual(len(summary["tree_manifest_sha256"]), 64)
            self.assertEqual(len(summary["human_roster_anchor_sha256"]), 64)
            self.assertEqual(
                summary["scoring_protocol_amendment_sha256"],
                amendment_sha,
            )
            expected = {
                "reports/stage1-provisional-report.json",
                "distributions/diagnostic-reviewer/diagnostic-review-packet.json",
                "distributions/diagnostic-reviewer/diagnostic-reviewer-template.json",
                "distributions/diagnostic-reviewer/distribution-manifest.json",
                "distributions/diagnostic-adjudicator/diagnostic-review-packet.json",
                "distributions/diagnostic-adjudicator/diagnostic-adjudicator-template.json",
                "distributions/diagnostic-adjudicator/distribution-manifest.json",
                "distributions/gold-reviewer/gold-review-packet.json",
                "distributions/gold-reviewer/gold-reviewer-template.json",
                "distributions/gold-reviewer/distribution-manifest.json",
                "distributions/gold-adjudicator/gold-review-packet.json",
                "distributions/gold-adjudicator/gold-adjudicator-template.json",
                "distributions/gold-adjudicator/distribution-manifest.json",
                "private/review-bundle.json",
                "private/panel-evidence.json",
                "tree-manifest.json",
            }
            observed = {
                path.relative_to(destination).as_posix()
                for path in destination.rglob("*")
                if path.is_file()
            }
            self.assertEqual(observed, expected)

            identity_terms = {
                "system-a",
                "system-b",
                "system_id",
                "system_alias",
                "system_bindings",
                "predictions_sha256",
                "prediction_sha256",
                "diagnostic_private",
                "gold_private",
                "private_crosswalk",
            }
            self.assert_isolated_distribution_package(
                destination,
                package_name="diagnostic-reviewer",
                role="diagnostic_reviewer",
                expected_packet_id=summary["review_packet_id"],
                expected_payload_names={
                    "diagnostic-review-packet.json",
                    "diagnostic-reviewer-template.json",
                },
                forbidden_terms={*identity_terms, "gold_findings", "stage1_gold_review"},
            )
            distributed_diagnostic = json.loads(
                (
                    destination
                    / "distributions"
                    / "diagnostic-reviewer"
                    / "diagnostic-review-packet.json"
                ).read_text(encoding="utf-8")
            )
            distributed_instructions = distributed_diagnostic["instructions"]
            for required_rule in (
                "finding_valid must equal span_valid AND problem_valid AND context_valid AND severity_valid AND operation_valid",
                "meaning_changed must be true if and only if meaning_risk is not none",
                "meaning_risk must be exactly one of: none, low, medium, high, critical",
            ):
                self.assertIn(required_rule, distributed_instructions)
            self.assert_isolated_distribution_package(
                destination,
                package_name="diagnostic-adjudicator",
                role="diagnostic_adjudicator",
                expected_packet_id=summary["review_packet_id"],
                expected_payload_names={
                    "diagnostic-review-packet.json",
                    "diagnostic-adjudicator-template.json",
                },
                forbidden_terms={*identity_terms, "gold_findings", "stage1_gold_review"},
            )
            self.assert_isolated_distribution_package(
                destination,
                package_name="gold-reviewer",
                role="gold_reviewer",
                expected_packet_id=summary["review_packet_id"],
                expected_payload_names={
                    "gold-review-packet.json",
                    "gold-reviewer-template.json",
                },
                forbidden_terms={*identity_terms, "stage1_diagnostic_review"},
            )
            self.assert_isolated_distribution_package(
                destination,
                package_name="gold-adjudicator",
                role="gold_adjudicator",
                expected_packet_id=summary["review_packet_id"],
                expected_payload_names={
                    "gold-review-packet.json",
                    "gold-adjudicator-template.json",
                },
                forbidden_terms={*identity_terms, "stage1_diagnostic_review"},
            )

            report_path = destination / "reports" / "stage1-provisional-report.json"
            self.assertTrue(report_path.is_file())
            self.assertNotIn("distributions", report_path.relative_to(destination).parts)
            private_text = (destination / "private" / "review-bundle.json").read_text(encoding="utf-8")
            self.assertIn("system-a", private_text)
            self.assertIn("system-b", private_text)
            private_bundle = json.loads(private_text)
            self.assertEqual(
                private_bundle["manifest"]["evidence"][
                    "scoring_protocol_amendment_sha256"
                ],
                amendment_sha,
            )
            bindings = private_bundle["diagnostic_private"]["system_bindings"]
            self.assertEqual(
                {item["system_id"] for item in bindings},
                {"system-a", "system-b"},
            )
            self.assertTrue(all(len(item["predictions_sha256"]) == 64 for item in bindings))

            tree_manifest_path = destination / "tree-manifest.json"
            self.assertEqual(
                hashlib.sha256(tree_manifest_path.read_bytes()).hexdigest(),
                summary["tree_manifest_sha256"],
            )
            tree_manifest = json.loads(tree_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(
                tree_manifest["scoring_protocol_amendment_sha256"],
                amendment_sha,
            )
            for reference in tree_manifest["files"]:
                payload = (destination / Path(reference["path"])).read_bytes()
                self.assertEqual(hashlib.sha256(payload).hexdigest(), reference["sha256"])
                self.assertEqual(len(payload), reference["bytes"])

            with self.assertRaises(FileExistsError):
                materialize_stage1_results(
                    project_root=project,
                    run_root=run_root,
                    expected_output_evidence_sha256=anchor.sha256,
                    expected_corpus_freeze_sha256=freeze_sha,
                    expected_thresholds_sha256=thresholds_sha,
                    expected_scoring_protocol_amendment_sha256=amendment_sha,
                    expected_runs=3,
                    expected_systems=2,
                    review_seed=20260825,
                    destination_root=destination,
                    authorized_root=project,
                    human_roster_anchor=roster_anchor,
                )


if __name__ == "__main__":
    unittest.main()
