from __future__ import annotations

import json
import unittest

from wqeval.blinding import (
    IdentityLeakError,
    assert_no_identity_leak,
    blind_records,
    blind_review_records,
    build_blind_map,
)
from wqeval.scoring import agreement_summary, cohen_kappa, percent_agreement


class AgreementTests(unittest.TestCase):
    def test_percent_agreement_and_cohen_kappa(self) -> None:
        left = ["CHANGE", "CHANGE", "KEEP", "KEEP"]
        right = ["CHANGE", "KEEP", "KEEP", "KEEP"]
        self.assertAlmostEqual(percent_agreement(left, right), 0.75)
        self.assertAlmostEqual(cohen_kappa(left, right), 0.5)

    def test_constant_kappa_is_undefined_and_length_mismatch_fails(self) -> None:
        self.assertIsNone(cohen_kappa(["KEEP", "KEEP"], ["KEEP", "KEEP"]))
        with self.assertRaises(ValueError):
            percent_agreement(["KEEP"], ["KEEP", "CHANGE"])
        with self.assertRaises(ValueError):
            cohen_kappa([], [])

    def test_agreement_summary_requires_complete_blinded_panels(self) -> None:
        ratings = {
            "human-a": {"BLIND-1": "CHANGE", "BLIND-2": "KEEP", "BLIND-3": "KEEP"},
            "human-b": {"BLIND-1": "CHANGE", "BLIND-2": "CHANGE", "BLIND-4": "KEEP"},
        }
        with self.assertRaises(ValueError):
            agreement_summary(ratings)

        complete = {
            "human-a": {"BLIND-1": "CHANGE", "BLIND-2": "KEEP"},
            "human-b": {"BLIND-1": "CHANGE", "BLIND-2": "CHANGE"},
        }
        summary = agreement_summary(complete)
        self.assertEqual(summary["pair_count"], 1)
        self.assertEqual(summary["pairs"][0]["common_items"], 2)
        self.assertAlmostEqual(summary["pairs"][0]["percent_agreement"], 0.5)

    def test_agreement_summary_explains_undefined_constant_kappa(self) -> None:
        ratings = {
            "human-a": {"BLIND-1": "KEEP", "BLIND-2": "KEEP"},
            "human-b": {"BLIND-1": "KEEP", "BLIND-2": "KEEP"},
        }
        pair = agreement_summary(ratings)["pairs"][0]
        self.assertIsNone(pair["cohen_kappa"])
        self.assertIn("expected agreement is 1", pair["cohen_kappa_undefined_reason"])


class BlindingTests(unittest.TestCase):
    def test_identity_mapping_is_deterministic_order_independent_and_bijective(self) -> None:
        systems = ["current-seven", "soundshuman", "normalized-union", "kami-writing"]
        first = build_blind_map(systems, seed=20260825)
        second = build_blind_map(list(reversed(systems)), seed=20260825)
        different = build_blind_map(systems, seed=20260826)

        self.assertEqual(first, second)
        self.assertNotEqual(first, different)
        self.assertEqual(set(first), set(systems))
        self.assertEqual(len(set(first.values())), len(systems))
        for alias in first.values():
            self.assertRegex(alias, r"^System-[A-Z]{3}$")

    def test_blind_records_remove_identity_fields_and_shuffle_deterministically(self) -> None:
        records = [
            {"system_id": "current-seven", "system_name": "Current Seven", "case_id": "C001", "findings": []},
            {"system_id": "soundshuman", "system_name": "Sounds Human", "case_id": "C001", "findings": []},
            {"system_id": "current-seven", "system_name": "Current Seven", "case_id": "C002", "findings": []},
        ]
        mapping = build_blind_map(["current-seven", "soundshuman"], seed=7)
        first = blind_records(records, mapping, seed=99)
        second = blind_records(records, mapping, seed=99)

        self.assertEqual(first, second)
        self.assertEqual(len(first), 3)
        for record in first:
            self.assertNotIn("system_id", record)
            self.assertNotIn("system_name", record)
            self.assertIn("system_alias", record)
        serialized = json.dumps(first, sort_keys=True)
        self.assertNotIn("current-seven", serialized)
        self.assertNotIn("soundshuman", serialized)
        self.assertNotIn("Current Seven", serialized)
        self.assertNotIn("Sounds Human", serialized)

    def test_recursive_leakage_check_catches_nested_and_case_insensitive_terms(self) -> None:
        assert_no_identity_leak({"system_alias": "System-ABC", "notes": "No identity here"}, ["soundshuman"])
        with self.assertRaises(IdentityLeakError):
            assert_no_identity_leak(
                {"system_alias": "System-ABC", "metadata": {"adapter": "SOUNDSHUMAN v1"}},
                ["soundshuman"],
            )

    def test_real_output_identifiers_and_native_labels_are_privately_realiased(self) -> None:
        records = [
            {
                "system_id": "humanizer",
                "run_number": 1,
                "case_id": "C001",
                "finding_id": "HU-001",
                "system_issue_code": "humanizer_rule_7",
                "normalized_issue_code": "generic_filler",
                "problem_name": "Generic filler",
                "field_origin": "model_adapter",
            }
        ]
        public, private = blind_review_records(
            records,
            build_blind_map(["humanizer"], seed=7),
            seed=99,
        )
        serialized = json.dumps(public, sort_keys=True).casefold()
        self.assertNotIn("humanizer", serialized)
        self.assertNotIn("hu-001", serialized)
        self.assertNotIn("system_issue_code", serialized)
        self.assertNotIn("field_origin", serialized)
        self.assertRegex(public[0]["review_item_id"], r"^Item-[0-9]{6}$")
        self.assertEqual(private[0]["finding_id"], "HU-001")
        self.assertEqual(private[0]["system_id"], "humanizer")

        leaked_text = [dict(records[0], context_explanation="This follows Humanizer rule 7.")]
        with self.assertRaises(IdentityLeakError):
            blind_review_records(leaked_text, build_blind_map(["humanizer"], seed=7), seed=99)


if __name__ == "__main__":
    unittest.main()
