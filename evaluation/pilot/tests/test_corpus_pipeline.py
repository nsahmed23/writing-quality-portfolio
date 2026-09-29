from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from wqeval.corpus import (
    CorpusError,
    case_has_registered_term,
    normalize_draft_record,
    split_annotated_cases,
    validate_annotated_case,
    validate_corpus_quotas,
)
from tools.build_corpus import publish_frozen_set, write_atomic


def annotated(case_id: str, source_id: str, decision: str, *, genre: str = "technical") -> dict:
    text = "The service may fail."
    finding_decision = "CHANGE" if decision == "CHANGE" else "KEEP"
    return {
        "schema_version": "1.0",
        "case_id": case_id,
        "primary_source_id": source_id,
        "source_refs": [
            {
                "source_id": source_id,
                "commit": "a" * 40,
                "path": "SKILL.md",
                "lines": None,
                "derivation": "independent_adaptation",
            }
        ],
        "text": text,
        "offset_unit": "unicode_codepoint",
        "genre": genre,
        "author_type": "domain_expert",
        "author_profile": {
            "technical": "domain_expert",
            "executive": "institutional_executive",
            "personal": "personal_author",
            "marketing": "brand_marketer",
            "reference": "reference_editor",
            "second_language": "second_language_professional",
        }[genre],
        "artifact_type": "plain_text",
        "features": ["factual_trap", "required_technical_term"],
        "case_decision": decision,
        "gold_findings": [
            {
                "finding_id": f"{case_id}-F1",
                "start": 12,
                "end": 15,
                "span": "may",
                "decision": finding_decision,
                "issue_family": "unjustified_certainty" if decision == "CHANGE" else "justified_modality",
                "source_native_label": "hedge",
                "problem_name": "Contextual modality",
                "severity": "high" if decision == "CHANGE" else "none",
                "context_explanation": "The evidence determines whether this modal is functional.",
                "allowed_operations": ["preserve"],
                "forbidden_changes": ["change_fact"],
                "importance": "primary",
            }
        ],
        "propositions": [
            {"proposition_id": f"{case_id}-P1", "type": "modality", "text": "The service may fail.", "criticality": "high"}
        ],
        "voice_signals": [],
        "protected_regions": [],
        "provisional_gold": True,
    }


class CanonicalCorpusTests(unittest.TestCase):
    def test_frozen_corpus_writer_refuses_to_replace_an_existing_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "cases.test.jsonl"
            write_atomic(target, b"first\n")
            with self.assertRaises(FileExistsError):
                write_atomic(target, b"second\n")
            self.assertEqual(target.read_bytes(), b"first\n")

    def test_frozen_set_preflights_every_target_before_publishing_any_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.jsonl"
            existing = root / "existing.jsonl"
            existing.write_bytes(b"old\n")
            with self.assertRaises(FileExistsError):
                publish_frozen_set(
                    [(first, b"new\n"), (existing, b"replacement\n")],
                )
            self.assertFalse(first.exists())
            self.assertEqual(existing.read_bytes(), b"old\n")

    def test_draft_normalizer_records_mechanical_schema_repairs(self) -> None:
        draft = annotated("C000", "S-007", "CHANGE")
        draft["primary_source_id"] = "avoid-ai-writing"
        draft["source_refs"][0].pop("source_id")
        draft["source_refs"][0].pop("lines")
        draft["source_refs"][0]["unexpected"] = "must be logged before removal"
        finding = draft["gold_findings"][0]
        finding.pop("finding_id")
        finding.pop("source_native_label")
        finding["normalized_issue_family"] = finding.pop("issue_family")
        draft["propositions"] = ["The service may fail."]
        draft["voice_signals"] = ["measured technical voice"]
        draft["protected_regions"] = [{"kind": "technical_term", "start": 4, "end": 11, "text": "service"}]

        normalized, repairs = normalize_draft_record(draft)
        validate_annotated_case(normalized)
        self.assertEqual(normalized["primary_source_id"], "S-007")
        self.assertEqual(normalized["source_refs"][0]["source_id"], "S-007")
        self.assertEqual(normalized["gold_findings"][0]["finding_id"], "C000-F01")
        self.assertEqual(normalized["propositions"][0]["type"], "claim")
        self.assertEqual(normalized["author_profile"], "domain_expert")
        self.assertEqual(normalized["protected_regions"][0]["policy"], "exact")
        self.assertTrue(any("removed unknown fields" in repair for repair in repairs))
        self.assertTrue(any("added source_native_label" in repair for repair in repairs))
        self.assertGreaterEqual(len(repairs), 6)

    def test_canonical_annotated_case_validates_and_exact_offsets_are_required(self) -> None:
        item = annotated("C001", "S-001", "CHANGE")
        validate_annotated_case(item)

        wrong = annotated("C002", "S-001", "CHANGE")
        wrong["gold_findings"][0]["span"] = "will"
        with self.assertRaises(CorpusError):
            validate_annotated_case(wrong)

    def test_source_refs_and_case_decision_must_be_consistent(self) -> None:
        wrong_source = annotated("C001", "S-001", "CHANGE")
        wrong_source["source_refs"][0]["source_id"] = "S-002"
        with self.assertRaises(CorpusError):
            validate_annotated_case(wrong_source)

        wrong_decision = annotated("C002", "S-001", "KEEP")
        wrong_decision["gold_findings"][0]["decision"] = "CHANGE"
        with self.assertRaises(CorpusError):
            validate_annotated_case(wrong_decision)

    def test_split_hides_gold_from_public_cases_and_text_from_gold(self) -> None:
        records = []
        for source_index in range(1, 3):
            source = f"S-{source_index:03d}"
            for decision in ("CHANGE", "KEEP"):
                for case_index in range(2):
                    records.append(annotated(f"{source}-{decision}-{case_index}", source, decision))
        public_dev, public_test, gold_dev, gold_test = split_annotated_cases(records, dev_per_source_decision=1)
        self.assertEqual((len(public_dev), len(public_test), len(gold_dev), len(gold_test)), (4, 4, 4, 4))
        for item in public_dev + public_test:
            self.assertEqual(
                set(item),
                {
                    "schema_version",
                    "case_id",
                    "split",
                    "text",
                    "offset_unit",
                    "genre",
                    "author_type",
                    "author_profile",
                    "artifact_type",
                    "protected_regions",
                },
            )
            self.assertNotIn("gold_findings", item)
            self.assertNotIn("propositions", item)
            self.assertNotIn("case_decision", item)
            self.assertNotIn("features", item)
            self.assertNotIn("source_refs", item)
            self.assertNotIn("primary_source_id", item)
        for item in gold_dev + gold_test:
            self.assertNotIn("text", item)
            self.assertIn("gold_findings", item)

    def test_quota_validator_reports_shortfalls_with_actual_counts(self) -> None:
        records = [annotated("C001", "S-001", "CHANGE"), annotated("C002", "S-001", "KEEP")]
        with self.assertRaises(CorpusError) as context:
            validate_corpus_quotas(
                records,
                {
                    "total_cases": 3,
                    "per_source_cases": 2,
                    "per_source_change": 1,
                    "per_source_keep": 1,
                    "genres": ["technical", "executive"],
                    "min_per_genre": 1,
                },
            )
        self.assertIn("total_cases expected 3, observed 2", str(context.exception))
        self.assertIn("genre executive expected at least 1, observed 0", str(context.exception))

    def test_registered_term_matching_does_not_count_substrings(self) -> None:
        item = annotated("C001", "S-001", "CHANGE")
        item["features"] = ["reference_only_projection_candidate"]
        item["gold_findings"][0]["issue_family"] = "generic_filler"
        item["gold_findings"][0]["source_native_label"] = "filler"
        item["gold_findings"][0]["problem_name"] = "Portable filler"
        item["propositions"][0]["type"] = "claim"
        self.assertFalse(case_has_registered_term(item, "date"))
        item["features"].append("fact_trap:date")
        self.assertTrue(case_has_registered_term(item, "date"))


if __name__ == "__main__":
    unittest.main()
