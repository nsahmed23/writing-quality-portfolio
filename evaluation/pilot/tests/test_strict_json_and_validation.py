from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from wqeval.strict_json import StrictJsonError, load_jsonl, loads
from wqeval.validation import (
    ValidationError,
    validate_case,
    validate_finding,
    validate_review_assignment,
    validate_rewrite,
)

from tests.support import case, finding, rewrite


class StrictJsonTests(unittest.TestCase):
    def test_rejects_duplicate_keys_nonfinite_numbers_and_trailing_values(self) -> None:
        invalid = (
            '{"case_id":"C001","case_id":"C002"}',
            '{"score":NaN}',
            '{"score":Infinity}',
            '{"score":-Infinity}',
            '{"score":1e9999}',
            '{"text":"\\ud800"}',
            '{"case_id":"C001"} {"case_id":"C002"}',
        )
        for document in invalid:
            with self.subTest(document=document), self.assertRaises(StrictJsonError):
                loads(document)

    def test_jsonl_rejects_blank_lines_primitives_and_invalid_utf8(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            blank = root / "blank.jsonl"
            blank.write_text('{"case_id":"C001"}\n\n', encoding="utf-8")
            with self.assertRaises(StrictJsonError):
                load_jsonl(blank)

            primitive = root / "primitive.jsonl"
            primitive.write_text('"not an object"\n', encoding="utf-8")
            with self.assertRaises(StrictJsonError):
                load_jsonl(primitive)

            invalid_utf8 = root / "invalid.jsonl"
            invalid_utf8.write_bytes(b'{"text":"\xff"}\n')
            with self.assertRaises(StrictJsonError):
                load_jsonl(invalid_utf8)

            alternate_separator = root / "alternate-separator.jsonl"
            alternate_separator.write_bytes(b'{"case_id":"C001"}\x0b{"case_id":"C002"}\n')
            with self.assertRaises(StrictJsonError):
                load_jsonl(alternate_separator)

    def test_valid_unicode_jsonl_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.jsonl"
            path.write_text('{"case_id":"C001","text":"🙂 café"}\n', encoding="utf-8")
            self.assertEqual(load_jsonl(path)[0]["text"], "🙂 café")

    def test_rejects_excessive_nesting_without_counting_brackets_inside_strings(self) -> None:
        with self.assertRaisesRegex(StrictJsonError, "nesting"):
            loads("[" * 129 + "0" + "]" * 129)
        self.assertEqual(loads(r'{"text":"[[[{{{ still text"}'), {"text": "[[[{{{ still text"})


class ValidationTests(unittest.TestCase):
    def test_valid_case_and_all_required_genres(self) -> None:
        for genre in ("technical", "executive", "personal", "marketing", "reference", "second_language"):
            with self.subTest(genre=genre):
                validate_case(case(genre=genre))

    def test_case_rejects_missing_unknown_and_malformed_protected_regions(self) -> None:
        missing = case()
        del missing["text"]
        unknown = case()
        unknown["gold_answer"] = "must never be exposed to generators"
        malformed_region = case(
            text="Use `x = 1` here.",
            protected_regions=[{"kind": "code", "start": 4, "end": 11, "text": "wrong"}],
        )
        bad_genre = case(genre="miscellaneous")
        leaky = dict(case(), features=["clean_control"], primary_source_id="S-001")
        for value in (missing, unknown, malformed_region, bad_genre, leaky):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                validate_case(value)

    def test_finding_requires_exact_span_named_problem_and_complete_operation(self) -> None:
        source_case = case()
        validate_finding(finding(), source_case)

        missing_context = finding()
        del missing_context["context"]
        wrong_span = finding(span_text="API")
        empty_problem = finding()
        empty_problem["problem"] = ""
        empty_operation = finding()
        empty_operation["suggested_operation"] = " "
        invalid_severity = finding(severity="urgent")
        invalid_decision = finding(decision="MAYBE")
        unknown = finding()
        unknown["confidence"] = 0.9
        for value in (
            missing_context,
            wrong_span,
            empty_problem,
            empty_operation,
            invalid_severity,
            invalid_decision,
            unknown,
        ):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                validate_finding(value, source_case)

    def test_unicode_offsets_are_python_code_point_offsets(self) -> None:
        source_case = case(text="🙂 café works.")
        valid = finding(start=2, end=6, span_text="café")
        validate_finding(valid, source_case)

        utf16_offset = finding(start=3, end=7, span_text="café")
        with self.assertRaises(ValidationError):
            validate_finding(utf16_offset, source_case)

    def test_rewrite_validates_digest_reconstruction_and_nonoverlap(self) -> None:
        source = "The API failed."
        source_case = case(text=source)
        valid = rewrite(
            source,
            "The service failed.",
            [{"start": 4, "end": 7, "replacement": "service", "finding_id": "F001"}],
        )
        validate_rewrite(valid, source_case)

        wrong_digest = dict(valid, source_sha256="0" * 64)
        wrong_result = dict(valid, revised_text="The system failed.")
        overlapping = rewrite(
            source,
            "irrelevant",
            [
                {"start": 0, "end": 7, "replacement": "A", "finding_id": "F001"},
                {"start": 4, "end": 10, "replacement": "B", "finding_id": "F002"},
            ],
        )
        unknown = dict(valid, model_score=1.0)
        for value in (wrong_digest, wrong_result, overlapping, unknown):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                validate_rewrite(value, source_case)

        self.assertEqual(valid["source_sha256"], hashlib.sha256(source.encode("utf-8")).hexdigest())

    def test_system_cannot_grade_its_own_output(self) -> None:
        validate_review_assignment(
            {"item_id": "C001:F001", "generator_id": "current", "reviewer_id": "human-01", "human": True}
        )
        with self.assertRaises(ValidationError):
            validate_review_assignment(
                {"item_id": "C001:F001", "generator_id": "current", "reviewer_id": "current", "human": False}
            )


if __name__ == "__main__":
    unittest.main()
