from __future__ import annotations

import hashlib
import unittest

from wqeval.rewrite import apply_edits, protected_region_violations
from wqeval.scoring import compare_fact_ledgers, score_stage2

from tests.support import case, rewrite


class RewriteTests(unittest.TestCase):
    PROTECTED_SAMPLES = {
        "frontmatter": "---\ntitle: Test\n---",
        "code": "`x = 1`",
        "table": "| A | B |\n| --- | --- |",
        "link": "[source](https://example.test)",
        "quotation": '"quoted words"',
    }

    @staticmethod
    def protected_case(kind: str, span: str, policy: str) -> tuple[str, dict[str, object]]:
        source = f"Prefix.\n{span}\nSuffix."
        start = source.index(span)
        region = {
            "region_id": f"R-{kind}",
            "start": start,
            "end": start + len(span),
            "span": span,
            "type": kind,
            "policy": policy,
        }
        return source, case(text=source, protected_regions=[region])

    def test_edits_apply_against_source_offsets_regardless_of_input_order(self) -> None:
        source = "Alpha beta gamma."
        edits = [
            {"start": 11, "end": 16, "replacement": "delta", "finding_id": "F002"},
            {"start": 6, "end": 10, "replacement": "BETA", "finding_id": "F001"},
        ]
        self.assertEqual(apply_edits(source, edits), "Alpha BETA delta.")

    def test_unicode_edit_offsets_use_code_points(self) -> None:
        source = "🙂 café works."
        edits = [{"start": 2, "end": 6, "replacement": "coffee", "finding_id": "F001"}]
        self.assertEqual(apply_edits(source, edits), "🙂 coffee works.")

    def test_overlapping_and_out_of_bounds_edits_fail(self) -> None:
        source = "abcdef"
        overlapping = [
            {"start": 1, "end": 4, "replacement": "x", "finding_id": "F001"},
            {"start": 3, "end": 5, "replacement": "y", "finding_id": "F002"},
        ]
        out_of_bounds = [{"start": 0, "end": 99, "replacement": "x", "finding_id": "F001"}]
        with self.assertRaises(ValueError):
            apply_edits(source, overlapping)
        with self.assertRaises(ValueError):
            apply_edits(source, out_of_bounds)

    def test_protected_regions_cover_frontmatter_code_table_link_and_quotation(self) -> None:
        parts = [
            "---\ntitle: Test\n---",
            "`x = 1`",
            "| A | B |",
            "[source](https://example.test)",
            '"quoted words"',
        ]
        source = "\n".join(parts) + "\nUnprotected tail."
        regions = []
        cursor = 0
        for kind, part in zip(("frontmatter", "code", "table", "link", "quotation"), parts, strict=True):
            start = source.index(part, cursor)
            end = start + len(part)
            regions.append({"kind": kind, "start": start, "end": end, "text": part})
            cursor = end
        source_case = case(text=source, protected_regions=regions)

        safe = rewrite(source, source + "\nClear prose.", [{"start": len(source), "end": len(source), "replacement": "\nClear prose.", "finding_id": "F001"}])
        self.assertEqual(protected_region_violations(source_case, safe), [])

        for index, region in enumerate(regions):
            edit = {"start": region["start"], "end": region["start"] + 1, "replacement": "X", "finding_id": f"F{index:03d}"}
            revised = apply_edits(source, [edit])
            unsafe = rewrite(source, revised, [edit])
            with self.subTest(kind=region["kind"]):
                violations = protected_region_violations(source_case, unsafe)
                self.assertEqual(len(violations), 1)
                self.assertEqual(violations[0]["kind"], region["kind"])

    def test_exact_policy_rejects_boundary_insertions_deletions_and_substitutions(self) -> None:
        for kind, span in self.PROTECTED_SAMPLES.items():
            source, source_case = self.protected_case(kind, span, "exact")
            region = source_case["protected_regions"][0]
            start = region["start"]
            end = region["end"]
            mutations = {
                "insert_at_start": {"start": start, "end": start, "replacement": "X"},
                "insert_at_end": {"start": end, "end": end, "replacement": "X"},
                "delete": {"start": start + 1, "end": start + 2, "replacement": ""},
                "substitute": {"start": start + 1, "end": start + 2, "replacement": "X"},
            }
            for operation, mutation in mutations.items():
                edit = {**mutation, "finding_id": "F001"}
                unsafe = rewrite(source, apply_edits(source, [edit]), [edit])
                with self.subTest(kind=kind, operation=operation):
                    self.assertEqual(protected_region_violations(source_case, unsafe), [region])

    def test_layout_only_policy_allows_content_edits_but_rejects_layout_changes(self) -> None:
        replacements = {
            "frontmatter": ("Test", "Demo"),
            "code": ("x", "y"),
            "table": ("A", "C"),
            "link": ("source", "record"),
            "quotation": ("quoted", "spoken"),
        }
        for kind, span in self.PROTECTED_SAMPLES.items():
            source, source_case = self.protected_case(kind, span, "layout_only")
            region = source_case["protected_regions"][0]
            old, new = replacements[kind]
            content_start = source.index(old, region["start"], region["end"])
            content_edit = {
                "start": content_start,
                "end": content_start + len(old),
                "replacement": new,
                "finding_id": "F001",
            }
            content_rewrite = rewrite(source, apply_edits(source, [content_edit]), [content_edit])
            with self.subTest(kind=kind, operation="content_edit"):
                self.assertEqual(protected_region_violations(source_case, content_rewrite), [])

            layout_edit = {
                "start": region["start"],
                "end": region["start"] + 1,
                "replacement": "",
                "finding_id": "F002",
            }
            layout_rewrite = rewrite(source, apply_edits(source, [layout_edit]), [layout_edit])
            with self.subTest(kind=kind, operation="layout_edit"):
                self.assertEqual(protected_region_violations(source_case, layout_rewrite), [region])

    def test_protected_region_verification_rejects_revised_text_that_disagrees_with_edits(self) -> None:
        source, source_case = self.protected_case("code", "`x = 1`", "exact")
        dishonest = rewrite(source, source.replace("x = 1", "x = 2"), [])

        with self.assertRaisesRegex(ValueError, "revised_text does not match"):
            protected_region_violations(source_case, dishonest)


class FactAndStageTwoScoringTests(unittest.TestCase):
    def test_fact_ledger_catches_each_registered_factual_trap(self) -> None:
        expected = [
            {"fact_id": "number", "kind": "number", "value": "12"},
            {"fact_id": "attribution", "kind": "attribution", "value": "the audit"},
            {"fact_id": "modality", "kind": "modality", "value": "may"},
            {"fact_id": "negation", "kind": "negation", "value": "not approved"},
            {"fact_id": "date", "kind": "date", "value": "2026-05-03"},
            {"fact_id": "actor", "kind": "actor", "value": "the board"},
        ]
        observed = [
            {"fact_id": "number", "kind": "number", "value": "21"},
            {"fact_id": "attribution", "kind": "attribution", "value": "the company"},
            {"fact_id": "modality", "kind": "modality", "value": "will"},
            {"fact_id": "negation", "kind": "negation", "value": "approved"},
            {"fact_id": "date", "kind": "date", "value": "2026-05-04"},
            {"fact_id": "actor", "kind": "actor", "value": "the CEO"},
        ]
        violations = compare_fact_ledgers(expected, observed)
        self.assertEqual({item["kind"] for item in violations}, {"number", "attribution", "modality", "negation", "date", "actor"})
        self.assertEqual(len(violations), 6)

    def test_fact_ledger_reports_missing_and_unexpected_facts(self) -> None:
        expected = [{"fact_id": "a", "kind": "actor", "value": "the board"}]
        observed = [{"fact_id": "b", "kind": "number", "value": "3"}]
        violations = compare_fact_ledgers(expected, observed)
        self.assertEqual({item["status"] for item in violations}, {"missing", "unexpected"})

    def test_fact_ledger_rejects_duplicate_ids_and_unknown_fields(self) -> None:
        valid = {"fact_id": "F1", "kind": "date", "value": "2026-05-03"}
        with self.assertRaises(ValueError):
            compare_fact_ledgers([valid, dict(valid, value="2026-05-04")], [valid])
        with self.assertRaises(ValueError):
            compare_fact_ledgers([valid], [valid, dict(valid, value="2026-05-04")])
        with self.assertRaises(ValueError):
            compare_fact_ledgers([dict(valid, confidence=1.0)], [valid])

    def test_stage_two_metrics_are_externally_reviewed_and_aggregate_exactly(self) -> None:
        outcomes = [
            {
                "case_id": "C001",
                "generator_id": "current-seven",
                "run_number": 1,
                "rewrite_sha256": "a" * 64,
                "reviewer_id": "human-01",
                "human": True,
                "semantic_preserved": True,
                "voice_retained": True,
                "unnecessary_edits": 0,
                "total_edits": 2,
                "protected_violations": 0,
                "clarity_delta": 1,
                "reader_preference": "revised",
                "problem_reduced": True,
            },
            {
                "case_id": "C002",
                "generator_id": "current-seven",
                "run_number": 1,
                "rewrite_sha256": "b" * 64,
                "reviewer_id": "human-02",
                "human": True,
                "semantic_preserved": False,
                "voice_retained": False,
                "unnecessary_edits": 1,
                "total_edits": 2,
                "protected_violations": 1,
                "clarity_delta": 0,
                "reader_preference": "source",
                "problem_reduced": False,
            },
        ]
        metrics = score_stage2(outcomes)
        self.assertEqual(metrics["case_count"], 2)
        self.assertAlmostEqual(metrics["semantic_preservation_rate"], 0.5)
        self.assertAlmostEqual(metrics["voice_retention_rate"], 0.5)
        self.assertAlmostEqual(metrics["unnecessary_edit_rate"], 0.25)
        self.assertAlmostEqual(metrics["protected_region_integrity_rate"], 0.5)
        self.assertAlmostEqual(metrics["mean_clarity_delta"], 0.5)
        self.assertAlmostEqual(metrics["reader_preference_rate"], 0.5)
        self.assertAlmostEqual(metrics["specific_problem_reduction_rate"], 0.5)

    def test_stage_two_rejects_self_grading_and_impossible_counts(self) -> None:
        base = {
            "case_id": "C001",
            "generator_id": "union",
            "run_number": 1,
            "rewrite_sha256": "c" * 64,
            "reviewer_id": "human-01",
            "human": True,
            "semantic_preserved": True,
            "voice_retained": True,
            "unnecessary_edits": 0,
            "total_edits": 1,
            "protected_violations": 0,
            "clarity_delta": 1,
            "reader_preference": "revised",
            "problem_reduced": True,
        }
        with self.assertRaises(ValueError):
            score_stage2([dict(base, reviewer_id="union")])
        with self.assertRaises(ValueError):
            score_stage2([dict(base, unnecessary_edits=2)])
        with self.assertRaises(ValueError):
            score_stage2([dict(base, human="yes")])

    def test_stage_two_rejects_malformed_outcomes_and_duplicate_ratings(self) -> None:
        base = {
            "case_id": "C001",
            "generator_id": "union",
            "run_number": 1,
            "rewrite_sha256": "d" * 64,
            "reviewer_id": "human-01",
            "human": True,
            "semantic_preserved": True,
            "voice_retained": True,
            "unnecessary_edits": 0,
            "total_edits": 1,
            "protected_violations": 0,
            "clarity_delta": 1,
            "reader_preference": "revised",
            "problem_reduced": True,
        }
        malformed = {
            "negative protected violations": dict(base, protected_violations=-99),
            "boolean protected violations": dict(base, protected_violations=False),
            "NaN clarity": dict(base, clarity_delta=float("nan")),
            "infinite clarity": dict(base, clarity_delta=float("inf")),
            "text clarity": dict(base, clarity_delta="better"),
            "non-boolean semantic": dict(base, semantic_preserved=1),
            "non-boolean voice": dict(base, voice_retained="yes"),
            "non-boolean reduction": dict(base, problem_reduced=1),
            "invalid preference": dict(base, reader_preference="both"),
            "blank case": dict(base, case_id=" "),
            "unknown field": dict(base, confidence=0.9),
            "zero run": dict(base, run_number=0),
            "invalid rewrite digest": dict(base, rewrite_sha256="not-a-digest"),
        }
        for name, outcome in malformed.items():
            with self.subTest(name=name), self.assertRaises(ValueError):
                score_stage2([outcome])

        with self.assertRaisesRegex(ValueError, "duplicate"):
            score_stage2([base, dict(base)])

        repeated = [base, dict(base, run_number=2, rewrite_sha256="e" * 64)]
        self.assertEqual(score_stage2(repeated)["case_count"], 2)


if __name__ == "__main__":
    unittest.main()
