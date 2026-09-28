from __future__ import annotations

import copy
import json
import unittest

from wqeval.review_packets import (
    ReviewPacketError,
    _verify_bundle,
    assemble_diagnostic_review_artifact,
    assemble_gold_review_artifact,
    build_stage1_review_packets as _build_stage1_review_packets,
    verify_completed_diagnostic_review_artifact,
)
from wqeval.roster_anchor import build_human_roster_anchor

from tests.support import case, finding, trusted_human_roster


def build_stage1_review_packets(*args, **kwargs):
    evidence = kwargs["evidence"]
    anchor = kwargs.pop(
        "human_roster_anchor",
        build_human_roster_anchor(
            human_roster=trusted_human_roster(),
            run_id="test-stage1-run",
            source_panel_report_sha256=evidence["panel_report_canonical_sha256"],
        ),
    )
    return _build_stage1_review_packets(
        *args,
        **kwargs,
        human_roster_anchor=anchor,
        expected_run_id=anchor["run_id"],
    )


class StageOneReviewPacketTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cases = [
            case("C001", "The report says experts agree."),
            case("C002", "The parser preserves `--dry-run`."),
        ]
        self.gold = [
            finding("C001", "G001", problem_code="vague_attribution"),
        ]
        self.predictions = [
            dict(
                finding("C001", "P001", problem_code="vague_attribution"),
                system_id="portfolio-current",
                run_number=1,
                field_origin="model_adapter",
                system_issue_code="PORT-7",
            ),
            dict(
                finding("C002", "P002", decision="KEEP", problem_code="technical_terminology"),
                system_id="soundshuman",
                run_number=1,
                field_origin="model_adapter",
                system_issue_code="SH-2",
            ),
            dict(
                finding("C001", "P003", problem_code="generic_filler"),
                system_id="soundshuman",
                run_number=2,
                field_origin="model_adapter",
                system_issue_code="SH-9",
            ),
        ]
        self.evidence = {
            "corpus_freeze_sha256": "a" * 64,
            "output_anchor_sha256": "b" * 64,
            "panel_report_canonical_sha256": "c" * 64,
            "scoring_protocol_amendment_sha256": "d" * 64,
        }
        self.roster = trusted_human_roster()
        self.anchor = build_human_roster_anchor(
            human_roster=self.roster,
            run_id="test-stage1-run",
            source_panel_report_sha256=self.evidence[
                "panel_report_canonical_sha256"
            ],
        )

    def test_packets_are_deterministic_blinded_complete_and_hash_bound(self) -> None:
        first = build_stage1_review_packets(
            self.cases,
            self.gold,
            self.predictions,
            seed=20260825,
            evidence=self.evidence,
        )
        second = build_stage1_review_packets(
            list(reversed(self.cases)),
            list(reversed(self.gold)),
            list(reversed(self.predictions)),
            seed=20260825,
            evidence=self.evidence,
        )
        self.assertEqual(first, second)

        public = first["diagnostic_public"]
        instructions = public["instructions"]
        self.assertIn(
            "finding_valid must equal span_valid AND problem_valid AND context_valid AND severity_valid AND operation_valid",
            instructions,
        )
        self.assertIn(
            "meaning_changed must be true if and only if meaning_risk is not none",
            instructions,
        )
        self.assertIn(
            "meaning_risk must be exactly one of: none, low, medium, high, critical",
            instructions,
        )
        serialized = json.dumps(public, sort_keys=True).casefold()
        self.assertNotIn("portfolio-current", serialized)
        self.assertNotIn("soundshuman", serialized)
        self.assertNotIn("system_id", serialized)
        self.assertNotIn("finding_id", serialized)
        self.assertNotIn("system_issue_code", serialized)
        self.assertEqual(len(public["review_items"]), 2)
        self.assertTrue(all(item["prediction"]["decision"] == "CHANGE" for item in public["review_items"]))
        self.assertTrue(all("case" in item for item in public["review_items"]))
        self.assertTrue(all(item["case"]["text"] for item in public["review_items"]))

        private = first["diagnostic_private"]
        self.assertEqual(len(private["review_items"]), 2)
        self.assertEqual(
            {item["prediction"]["finding_id"] for item in private["review_items"]},
            {"P001", "P003"},
        )
        self.assertTrue(all(len(item["prediction_sha256"]) == 64 for item in private["review_items"]))

        gold = first["gold_public"]
        self.assertEqual(len(gold["review_items"]), 2)
        by_case = {item["case"]["case_id"]: item for item in gold["review_items"]}
        self.assertEqual(len(by_case["C001"]["gold_findings"]), 1)
        self.assertEqual(by_case["C002"]["gold_findings"], [])

        self.assertEqual(len(first["diagnostic_reviewer_template"]), 2)
        self.assertEqual(len(first["diagnostic_adjudicator_template"]), 2)
        self.assertEqual(len(first["gold_reviewer_template"]), 2)
        for name in (
            "diagnostic_reviewer_template",
            "diagnostic_adjudicator_template",
            "gold_reviewer_template",
            "gold_adjudicator_template",
        ):
            self.assertTrue(
                all(
                    item["packet_id"] == first["manifest"]["packet_id"]
                    and len(item["public_packet_sha256"]) == 64
                    and len(item["review_item_sha256"]) == 64
                    for item in first[name]
                )
            )
        self.assertEqual(first["manifest"]["evidence"], self.evidence)
        self.assertEqual(set(first["manifest"]["artifact_sha256"]), {
            "diagnostic_public",
            "diagnostic_private",
            "diagnostic_reviewer_template",
            "diagnostic_adjudicator_template",
            "gold_public",
            "gold_private",
            "gold_reviewer_template",
            "gold_adjudicator_template",
        })

    def test_manifest_identity_binds_seed_status_counts_and_exact_fields(self) -> None:
        bundle = build_stage1_review_packets(
            self.cases,
            self.gold,
            self.predictions,
            seed=7,
            evidence=self.evidence,
        )
        _verify_bundle(bundle, expected_packet_id=bundle["manifest"]["packet_id"])

        mutations = {
            "seed": lambda value: value["manifest"].__setitem__("seed", 8),
            "status": lambda value: value["manifest"].__setitem__("status", "COMPLETE"),
            "counts": lambda value: value["manifest"]["counts"].__setitem__("cases", 999),
            "extra": lambda value: value["manifest"].__setitem__("unexpected", True),
        }
        for name, mutate in mutations.items():
            forged = copy.deepcopy(bundle)
            mutate(forged)
            with self.subTest(name=name), self.assertRaises(ReviewPacketError):
                _verify_bundle(
                    forged,
                    expected_packet_id=bundle["manifest"]["packet_id"],
                )

    def test_supplied_prediction_digest_binds_exact_evaluation_payload_order(self) -> None:
        canonical = build_stage1_review_packets(
            self.cases,
            self.gold,
            self.predictions,
            seed=7,
            evidence=self.evidence,
        )
        bindings = canonical["diagnostic_private"]["system_bindings"]
        build_stage1_review_packets(
            self.cases,
            self.gold,
            self.predictions,
            seed=7,
            evidence=self.evidence,
            system_prediction_bindings=bindings,
        )
        with self.assertRaisesRegex(ReviewPacketError, "binding mismatch"):
            build_stage1_review_packets(
                self.cases,
                self.gold,
                list(reversed(self.predictions)),
                seed=7,
                evidence=self.evidence,
                system_prediction_bindings=bindings,
            )

    def test_public_packet_has_no_gold_or_private_crosswalk(self) -> None:
        bundle = build_stage1_review_packets(
            self.cases,
            self.gold,
            self.predictions,
            seed=7,
            evidence=self.evidence,
        )
        public = bundle["diagnostic_public"]
        serialized = json.dumps(public, sort_keys=True)
        self.assertNotIn("gold_findings", serialized)
        self.assertNotIn("G001", serialized)
        self.assertNotIn("prediction_sha256", serialized)
        self.assertNotIn("private", serialized.casefold())

    def test_review_packet_requires_the_frozen_scoring_protocol_amendment(self) -> None:
        evidence = dict(self.evidence)
        evidence.pop("scoring_protocol_amendment_sha256")
        with self.assertRaisesRegex(ReviewPacketError, "amendment"):
            build_stage1_review_packets(
                self.cases,
                self.gold,
                self.predictions,
                seed=7,
                evidence=evidence,
            )

    def test_input_identity_leak_in_free_text_is_rejected(self) -> None:
        leaked = copy.deepcopy(self.predictions)
        leaked[0]["context_explanation"] = "The portfolio-current adapter calls this vague."
        with self.assertRaises(ReviewPacketError):
            build_stage1_review_packets(
                self.cases,
                self.gold,
                leaked,
                seed=7,
                evidence=self.evidence,
            )

    def test_duplicate_or_unbound_records_are_rejected(self) -> None:
        duplicate_cases = [self.cases[0], copy.deepcopy(self.cases[0])]
        with self.assertRaises(ReviewPacketError):
            build_stage1_review_packets(
                duplicate_cases,
                self.gold,
                self.predictions,
                seed=7,
                evidence=self.evidence,
            )

        unbound = copy.deepcopy(self.predictions)
        unbound[0]["case_id"] = "MISSING"
        with self.assertRaises(ReviewPacketError):
            build_stage1_review_packets(
                self.cases,
                self.gold,
                unbound,
                seed=7,
                evidence=self.evidence,
            )

    def test_assemblers_restore_preserved_evidence_and_require_complete_panels(self) -> None:
        bundle = build_stage1_review_packets(
            self.cases,
            self.gold,
            self.predictions,
            seed=7,
            evidence=self.evidence,
        )
        reviewers = [
            {"reviewer_id": "human-a", "actor_type": "human", "human": True},
            {"reviewer_id": "human-b", "actor_type": "human", "human": True},
        ]
        adjudicator = {"reviewer_id": "human-c", "actor_type": "human", "human": True}

        diagnostic_reviews = []
        for reviewer in reviewers:
            for template in bundle["diagnostic_reviewer_template"]:
                diagnostic_reviews.append(
                    dict(
                        template,
                        reviewer_id=reviewer["reviewer_id"],
                        finding_valid=True,
                        span_valid=True,
                        problem_valid=True,
                        context_valid=True,
                        severity_valid=True,
                        operation_valid=True,
                        meaning_changed=False,
                        meaning_risk="none",
                    )
                )
        diagnostic_adjudications = [
            dict(
                template,
                reviewer_id="human-c",
                finding_valid=True,
                span_valid=True,
                problem_valid=True,
                context_valid=True,
                severity_valid=True,
                operation_valid=True,
                meaning_changed=False,
                meaning_risk="none",
            )
            for template in bundle["diagnostic_adjudicator_template"]
        ]
        diagnostic = assemble_diagnostic_review_artifact(
            bundle,
            expected_packet_id=bundle["manifest"]["packet_id"],
            human_roster_anchor=self.anchor,
            reviewers=reviewers,
            adjudicator=adjudicator,
            reviews=diagnostic_reviews,
            adjudications=diagnostic_adjudications,
        )
        self.assertEqual(
            {
                item["prediction"]["finding_id"]
                for item in diagnostic["private_packet"]["review_items"]
            },
            {"P001", "P003"},
        )

        gold_reviews = []
        for reviewer in reviewers:
            for template in bundle["gold_reviewer_template"]:
                gold_reviews.append(
                    dict(
                        template,
                        reviewer_id=reviewer["reviewer_id"],
                        span_correct=True,
                        decision_correct=True,
                        label_correct=True,
                        severity_correct=True,
                        gold_complete=True,
                    )
                )
        gold_adjudications = [
            dict(
                template,
                reviewer_id="human-c",
                span_correct=True,
                decision_correct=True,
                label_correct=True,
                severity_correct=True,
                gold_complete=True,
            )
            for template in bundle["gold_adjudicator_template"]
        ]
        gold_artifact = assemble_gold_review_artifact(
            bundle,
            expected_packet_id=bundle["manifest"]["packet_id"],
            human_roster_anchor=self.anchor,
            reviewers=reviewers,
            adjudicator=adjudicator,
            reviews=gold_reviews,
            adjudications=gold_adjudications,
        )
        self.assertEqual(len(gold_artifact["private_packet"]["review_items"]), 2)

        with self.assertRaises(ReviewPacketError):
            assemble_diagnostic_review_artifact(
                bundle,
                expected_packet_id=bundle["manifest"]["packet_id"],
                human_roster_anchor=self.anchor,
                reviewers=reviewers,
                adjudicator=adjudicator,
                reviews=diagnostic_reviews[:-1],
                adjudications=diagnostic_adjudications,
            )

    def test_ratings_from_one_packet_cannot_be_replayed_against_another(self) -> None:
        first = build_stage1_review_packets(
            self.cases,
            self.gold,
            self.predictions,
            seed=7,
            evidence=self.evidence,
        )
        altered_predictions = copy.deepcopy(self.predictions)
        altered_predictions[0]["problem"] = "A materially different diagnosis"
        second = build_stage1_review_packets(
            self.cases,
            self.gold,
            altered_predictions,
            seed=7,
            evidence={**self.evidence, "output_anchor_sha256": "c" * 64},
        )
        self.assertNotEqual(first["manifest"]["packet_id"], second["manifest"]["packet_id"])

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

        reviews = [
            completed(template, reviewer["reviewer_id"])
            for reviewer in reviewers
            for template in first["diagnostic_reviewer_template"]
        ]
        adjudications = [
            completed(template, "human-c")
            for template in first["diagnostic_adjudicator_template"]
        ]
        with self.assertRaisesRegex(ReviewPacketError, "packet|binding|review item"):
            assemble_diagnostic_review_artifact(
                second,
                expected_packet_id=second["manifest"]["packet_id"],
                human_roster_anchor=self.anchor,
                reviewers=reviewers,
                adjudicator=adjudicator,
                reviews=reviews,
                adjudications=adjudications,
            )

    def test_completed_artifact_retains_and_verifies_exact_public_evidence(self) -> None:
        bundle = build_stage1_review_packets(
            self.cases,
            self.gold,
            self.predictions,
            seed=7,
            evidence=self.evidence,
        )
        packet_id = bundle["manifest"]["packet_id"]
        reviewers = [
            {"reviewer_id": "human-a", "actor_type": "human", "human": True},
            {"reviewer_id": "human-b", "actor_type": "human", "human": True},
        ]

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
            expected_packet_id=packet_id,
            human_roster_anchor=self.anchor,
            reviewers=reviewers,
            adjudicator={"reviewer_id": "human-c", "actor_type": "human", "human": True},
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
        verified = verify_completed_diagnostic_review_artifact(
            artifact,
            expected_packet_id=packet_id,
            human_roster_anchor=self.anchor,
        )
        self.assertTrue(verified["human_review_verified"])
        structural_only = verify_completed_diagnostic_review_artifact(
            artifact,
            expected_packet_id=packet_id,
        )
        self.assertTrue(structural_only["review_structure_verified"])
        self.assertFalse(structural_only["human_identity_attested"])
        self.assertFalse(structural_only["human_review_verified"])
        with self.assertRaisesRegex(ReviewPacketError, "roster"):
            verify_completed_diagnostic_review_artifact(
                artifact,
                expected_packet_id=packet_id,
                human_roster_anchor=dict(self.anchor, run_id="tampered"),
            )
        bindings = {
            item["system_id"]: item
            for item in artifact["private_packet"]["system_bindings"]
        }
        projected = verify_completed_diagnostic_review_artifact(
            artifact,
            expected_packet_id=packet_id,
            system_id="portfolio-current",
            expected_predictions_sha256=bindings["portfolio-current"]["predictions_sha256"],
            human_roster_anchor=self.anchor,
        )
        self.assertEqual(projected["system_id"], "portfolio-current")
        self.assertEqual(projected["reviewed_prediction_count"], 1)

        with self.assertRaisesRegex(ReviewPacketError, "not registered"):
            verify_completed_diagnostic_review_artifact(
                artifact,
                expected_packet_id=packet_id,
                system_id="missing-system",
                expected_predictions_sha256="f" * 64,
                human_roster_anchor=self.anchor,
            )

        incomplete = copy.deepcopy(artifact)
        sound_item_id = next(
            item["review_item_id"]
            for item in incomplete["private_packet"]["review_items"]
            if item["prediction"]["system_id"] == "soundshuman"
        )
        incomplete["reviews"] = [
            item for item in incomplete["reviews"] if item["review_item_id"] != sound_item_id
        ]
        incomplete["adjudications"] = [
            item
            for item in incomplete["adjudications"]
            if item["review_item_id"] != sound_item_id
        ]
        with self.assertRaises(ReviewPacketError):
            verify_completed_diagnostic_review_artifact(
                incomplete,
                expected_packet_id=packet_id,
                system_id="portfolio-current",
                expected_predictions_sha256=bindings["portfolio-current"][
                    "predictions_sha256"
                ],
                human_roster_anchor=self.anchor,
            )

        mutations = {
            "case text": lambda value: value["public_packet"]["review_items"][0]["case"].__setitem__(
                "text", "Altered after review."
            ),
            "public prediction": lambda value: value["public_packet"]["review_items"][0][
                "prediction"
            ].__setitem__("problem", "Altered diagnosis"),
            "private prediction": lambda value: value["private_packet"]["review_items"][0][
                "prediction"
            ].__setitem__("problem", "Altered private diagnosis"),
        }
        for name, mutate in mutations.items():
            forged = copy.deepcopy(artifact)
            mutate(forged)
            with self.subTest(name=name), self.assertRaises(ReviewPacketError):
                verify_completed_diagnostic_review_artifact(
                    forged,
                    expected_packet_id=packet_id,
                    human_roster_anchor=self.anchor,
                )


if __name__ == "__main__":
    unittest.main()
