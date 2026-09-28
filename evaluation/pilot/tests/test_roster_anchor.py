from __future__ import annotations

import copy
import hashlib
import inspect
import json
import tempfile
import unittest
from pathlib import Path

from tests.support import case, finding, trusted_human_roster
from tools.freeze_human_roster_anchor import freeze_human_roster_anchor_file
from wqeval.roster_anchor import (
    HumanRosterAnchorError,
    build_human_roster_anchor,
    human_roster_anchor_sha256,
    panel_report_sha256,
    verify_human_roster_anchor,
)
from wqeval.review_packets import (
    ReviewPacketError,
    _verify_bundle,
    assemble_diagnostic_review_artifact,
    build_stage1_review_packets,
    verify_completed_diagnostic_review_artifact,
    verify_completed_gold_review_artifact,
)


class HumanRosterAnchorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.panel_report = {
            "schema_version": "1.0",
            "stage": 1,
            "status": "PILOT_UNADJUDICATED",
            "system_count": 1,
        }
        self.panel_sha256 = panel_report_sha256(self.panel_report)
        self.roster = trusted_human_roster()

    def test_builds_and_verifies_exact_pre_review_anchor(self) -> None:
        anchor = build_human_roster_anchor(
            human_roster=self.roster,
            run_id="stage1-sealed-v1",
            source_panel_report_sha256=self.panel_sha256,
        )

        self.assertEqual(
            set(anchor),
            {
                "schema_version",
                "anchor_kind",
                "status",
                "run_id",
                "source_panel_report_sha256",
                "human_roster",
            },
        )
        self.assertEqual(anchor["schema_version"], "1.0")
        self.assertEqual(anchor["anchor_kind"], "stage1_human_roster_pre_review")
        self.assertEqual(anchor["status"], "FROZEN_PRE_REVIEW")
        self.assertEqual(anchor["human_roster"], self.roster)
        verified = verify_human_roster_anchor(
            anchor,
            expected_source_panel_report_sha256=self.panel_sha256,
            expected_run_id="stage1-sealed-v1",
        )
        self.assertEqual(verified, anchor)
        self.assertEqual(len(human_roster_anchor_sha256(anchor)), 64)

    def test_exact_schema_and_panel_report_binding_are_required(self) -> None:
        anchor = build_human_roster_anchor(
            human_roster=self.roster,
            run_id="stage1-sealed-v1",
            source_panel_report_sha256=self.panel_sha256,
        )
        forged = copy.deepcopy(anchor)
        forged["extra"] = True
        with self.assertRaisesRegex(HumanRosterAnchorError, "fields"):
            verify_human_roster_anchor(forged)
        with self.assertRaisesRegex(HumanRosterAnchorError, "panel report"):
            verify_human_roster_anchor(
                anchor,
                expected_source_panel_report_sha256="0" * 64,
            )

    def test_freeze_cli_helper_derives_report_digest_and_refuses_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            roster_path = root / "roster.json"
            report_path = root / "panel-report.json"
            destination = root / "anchor.json"
            roster_path.write_text(
                json.dumps(self.roster, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            report_path.write_text(
                json.dumps(self.panel_report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
                newline="\n",
            )

            receipt = freeze_human_roster_anchor_file(
                roster_path=roster_path,
                source_panel_report_path=report_path,
                run_id="stage1-sealed-v1",
                destination_path=destination,
                authorized_root=root,
            )
            payload = destination.read_bytes()
            observed = json.loads(payload)
            self.assertEqual(
                observed["source_panel_report_sha256"],
                self.panel_sha256,
            )
            self.assertEqual(receipt["human_roster_anchor_sha256"], hashlib.sha256(payload).hexdigest())
            with self.assertRaises(FileExistsError):
                freeze_human_roster_anchor_file(
                    roster_path=roster_path,
                    source_panel_report_path=report_path,
                    run_id="stage1-sealed-v1",
                    destination_path=destination,
                    authorized_root=root,
                )

    def test_packet_identity_binds_anchor_and_rejects_wrong_panel(self) -> None:
        anchor = build_human_roster_anchor(
            human_roster=self.roster,
            run_id="stage1-sealed-v1",
            source_panel_report_sha256=self.panel_sha256,
        )
        evidence = {
            "panel_report_canonical_sha256": self.panel_sha256,
            "output_anchor_sha256": "a" * 64,
            "scoring_protocol_amendment_sha256": "b" * 64,
        }
        bundle = build_stage1_review_packets(
            [case("C001")],
            [finding("C001", "G001")],
            [dict(finding("C001", "P001"), system_id="system-a", run_number=1)],
            seed=20260825,
            evidence=evidence,
            human_roster_anchor=anchor,
            expected_run_id="stage1-sealed-v1",
        )
        self.assertEqual(
            bundle["manifest"]["human_roster_anchor_sha256"],
            human_roster_anchor_sha256(anchor),
        )
        self.assertEqual(
            bundle["manifest"]["rating_contract"]["contract_id"],
            "stage1-bound-rating/2.1",
        )
        forged = copy.deepcopy(bundle)
        forged["manifest"]["human_roster_anchor_sha256"] = "f" * 64
        with self.assertRaisesRegex(ReviewPacketError, "identity|anchor"):
            _verify_bundle(forged, expected_packet_id=bundle["manifest"]["packet_id"])

        wrong_panel_anchor = build_human_roster_anchor(
            human_roster=self.roster,
            run_id="stage1-sealed-v1",
            source_panel_report_sha256="e" * 64,
        )
        with self.assertRaisesRegex(ReviewPacketError, "panel report"):
            build_stage1_review_packets(
                [case("C001")],
                [finding("C001", "G001")],
                [dict(finding("C001", "P001"), system_id="system-a", run_number=1)],
                seed=20260825,
                evidence=evidence,
                human_roster_anchor=wrong_panel_anchor,
                expected_run_id="stage1-sealed-v1",
            )

        with self.assertRaisesRegex(ReviewPacketError, "run_id"):
            build_stage1_review_packets(
                [case("C001")],
                [finding("C001", "G001")],
                [dict(finding("C001", "P001"), system_id="system-a", run_number=1)],
                seed=20260825,
                evidence=evidence,
                human_roster_anchor=anchor,
                expected_run_id="different-run",
            )

    def test_packet_frozen_for_roster_a_rejects_roster_b_without_digest_escape_hatch(self) -> None:
        anchor_a = build_human_roster_anchor(
            human_roster=self.roster,
            run_id="stage1-sealed-v1",
            source_panel_report_sha256=self.panel_sha256,
        )
        roster_b = copy.deepcopy(self.roster)
        roster_b["reviewer_ids"] = ["human-x", "human-y"]
        roster_b["adjudicator_id"] = "human-z"
        anchor_b = build_human_roster_anchor(
            human_roster=roster_b,
            run_id="stage1-sealed-v1",
            source_panel_report_sha256=self.panel_sha256,
        )
        evidence = {
            "panel_report_canonical_sha256": self.panel_sha256,
            "output_anchor_sha256": "a" * 64,
            "scoring_protocol_amendment_sha256": "b" * 64,
        }
        bundle = build_stage1_review_packets(
            [case("C001")],
            [finding("C001", "G001")],
            [dict(finding("C001", "P001"), system_id="system-a", run_number=1)],
            seed=7,
            evidence=evidence,
            human_roster_anchor=anchor_a,
            expected_run_id="stage1-sealed-v1",
        )
        reviewers = [
            {"reviewer_id": "human-a", "actor_type": "human", "human": True},
            {"reviewer_id": "human-b", "actor_type": "human", "human": True},
        ]
        adjudicator = {"reviewer_id": "human-c", "actor_type": "human", "human": True}

        def completed(template: dict, reviewer_id: str) -> dict:
            return dict(
                template,
                reviewer_id=reviewer_id,
                finding_valid=True,
                span_valid=True,
                problem_valid=True,
                context_valid=True,
                severity_valid=True,
                operation_valid=True,
                meaning_changed=False,
                meaning_risk="none",
            )

        artifact = assemble_diagnostic_review_artifact(
            bundle,
            expected_packet_id=bundle["manifest"]["packet_id"],
            human_roster_anchor=anchor_a,
            reviewers=reviewers,
            adjudicator=adjudicator,
            reviews=[
                completed(template, reviewer["reviewer_id"])
                for reviewer in reviewers
                for template in bundle["diagnostic_reviewer_template"]
            ],
            adjudications=[
                completed(template, "human-c")
                for template in bundle["diagnostic_adjudicator_template"]
            ],
        )
        with self.assertRaisesRegex(ReviewPacketError, "anchor"):
            verify_completed_diagnostic_review_artifact(
                artifact,
                expected_packet_id=bundle["manifest"]["packet_id"],
                human_roster_anchor=anchor_b,
            )
        legacy = copy.deepcopy(artifact)
        legacy["source_manifest"].pop("human_roster_anchor_sha256")
        legacy["source_manifest"]["rating_contract"] = {
            **legacy["source_manifest"]["rating_contract"],
            "schema_version": "2.0",
            "contract_id": "stage1-bound-rating/2.0",
        }
        with self.assertRaisesRegex(ReviewPacketError, "manifest"):
            verify_completed_diagnostic_review_artifact(
                legacy,
                expected_packet_id=bundle["manifest"]["packet_id"],
                human_roster_anchor=anchor_a,
            )
        self.assertNotEqual(
            human_roster_anchor_sha256(anchor_a),
            human_roster_anchor_sha256(anchor_b),
        )
        for function in (
            assemble_diagnostic_review_artifact,
            verify_completed_diagnostic_review_artifact,
            verify_completed_gold_review_artifact,
        ):
            parameters = inspect.signature(function).parameters
            self.assertNotIn("expected_human_roster_sha256", parameters)
            self.assertNotIn("trusted_human_roster", parameters)


if __name__ == "__main__":
    unittest.main()
