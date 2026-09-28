"""Boundary tests for development-only quote anchoring and response ingestion."""

import hashlib
import json
import unittest

from evaluation.benchmark_v2 import AnchorError, ingest_response, resolve_anchor


class AnchorTests(unittest.TestCase):
    def assert_anchor_error(self, reason, text, quote, **options):
        with self.assertRaises(AnchorError) as caught:
            resolve_anchor(text, quote, **options)
        self.assertEqual(caught.exception.reason, reason)

    def test_literal_code_point_offsets_include_emoji_and_combining_mark(self):
        self.assertEqual(resolve_anchor("😀e\u0301 END", "e\u0301"), (1, 3))
        self.assert_anchor_error("ANCHOR_NOT_FOUND", "😀é END", "e\u0301")

    def test_overlapping_occurrences_are_counted_before_context_filter(self):
        self.assertEqual(resolve_anchor("aaaa", "aa", occurrence=2), (1, 3))
        self.assertEqual(resolve_anchor("aaaa", "aa", occurrence=3), (2, 4))
        self.assert_anchor_error("ANCHOR_NOT_FOUND", "aaaa", "aa", occurrence=2, left_context="aa")

    def test_immediately_adjacent_context_disambiguates(self):
        self.assertEqual(resolve_anchor("one: x; two: x", "x", left_context="two: "), (13, 14))
        self.assertEqual(resolve_anchor("x-A x-B", "x", right_context="-B"), (4, 5))
        self.assert_anchor_error("ANCHOR_NOT_FOUND", "x-A x-B", "x", right_context=" -B")
        self.assert_anchor_error("AMBIGUOUS_ANCHOR", "x-A x-B", "x")

    def test_literal_crlf_code_and_table_text(self):
        self.assertEqual(resolve_anchor("`x`\r\n| x |", "`x`\r\n| x |"), (0, 10))
        self.assert_anchor_error("ANCHOR_NOT_FOUND", "`x`\r\n| x |", "`x`\n| x |")
        self.assertEqual(resolve_anchor("a | b\na | c", "a | c"), (6, 11))

    def test_rejects_invalid_quote_text_context_and_occurrence(self):
        self.assert_anchor_error("INVALID_TEXT", 42, "a")
        self.assert_anchor_error("INVALID_QUOTE", "abc", 2)
        self.assert_anchor_error("EMPTY_QUOTE", "abc", "")
        self.assert_anchor_error("INVALID_CONTEXT", "abc", "a", left_context=4)
        self.assert_anchor_error("INVALID_CONTEXT", "abc", "a", right_context=False)
        for occurrence in (True, False, 0, -1, 1.0, "1"):
            with self.subTest(occurrence=occurrence):
                self.assert_anchor_error("INVALID_OCCURRENCE", "aa", "a", occurrence=occurrence)
        self.assert_anchor_error("OCCURRENCE_OUT_OF_RANGE", "aa", "a", occurrence=3)
        self.assert_anchor_error("ANCHOR_NOT_FOUND", "abc", "z")


class IngestTests(unittest.TestCase):
    def ingest(self, body, text="x", case_id="case-1"):
        return ingest_response(case_id, text, json.dumps(body, ensure_ascii=False).encode("utf-8"))

    def test_provenance_hashes_supplied_bytes_and_utf8_case_text(self):
        raw = b'{ "findings": [] }\n'
        result = ingest_response("case-7", "😀e\u0301", raw)
        self.assertEqual(result, {
            "status": "development_only", "case_id": "case-7",
            "text_sha256": hashlib.sha256("😀e\u0301".encode("utf-8")).hexdigest(),
            "response_sha256": hashlib.sha256(raw).hexdigest(),
            "accepted_findings": [], "rejected_findings": [], "response_error": None,
        })

    def test_accepts_valid_findings_with_original_index_and_offsets(self):
        result = self.ingest({"findings": [
            {"native_label": "tone", "quote": "x", "explanation": "too abrupt", "occurrence": 2},
            {"native_label": "style", "quote": "x", "explanation": "too abrupt", "left_context": "a "},
        ]}, text="a x, x")
        self.assertEqual(result["accepted_findings"], [
            {"index": 0, "native_label": "tone", "quote": "x", "explanation": "too abrupt", "occurrence": 2, "start": 5, "end": 6},
            {"index": 1, "native_label": "style", "quote": "x", "explanation": "too abrupt", "left_context": "a ", "start": 2, "end": 3},
        ])
        self.assertEqual(result["rejected_findings"], [])

    def test_rejects_bad_finding_locally_and_preserves_valid_siblings(self):
        result = self.ingest({"findings": [
            {"native_label": "tone", "quote": "x", "explanation": "one"},
            {"native_label": "tone", "quote": "missing", "explanation": "two"},
            {"native_label": "tone", "quote": "y", "explanation": "three"},
        ]}, text="x y")
        self.assertEqual([f["index"] for f in result["accepted_findings"]], [0, 2])
        self.assertEqual(result["rejected_findings"], [{"index": 1, "code": "ANCHOR_NOT_FOUND"}])
        self.assertIsNone(result["response_error"])

    def test_missing_blank_wrong_type_and_unknown_fields_are_local(self):
        good = {"native_label": "tone", "quote": "x", "explanation": "reason"}
        bad = [None, {}, {**good, "native_label": " \t"}, {**good, "quote": 4},
               {**good, "explanation": ""}, {**good, "other": "z"},
               {**good, "occurrence": True}, {**good, "left_context": 4}]
        result = self.ingest({"findings": [*bad, good]})
        self.assertEqual([r["index"] for r in result["rejected_findings"]], list(range(len(bad))))
        self.assertEqual([r["code"] for r in result["rejected_findings"]], [
            "INVALID_FINDING", "INVALID_FINDING", "INVALID_FINDING", "INVALID_FINDING",
            "INVALID_FINDING", "UNKNOWN_FIELD", "INVALID_OCCURRENCE", "INVALID_CONTEXT",
        ])
        self.assertEqual([f["index"] for f in result["accepted_findings"]], [8])

    def test_duplicate_diagnoses_keep_distinct_labels_explanations_and_spans(self):
        one = {"native_label": "tone", "quote": "x", "explanation": "one", "occurrence": 1}
        result = self.ingest({"findings": [one, dict(one), {**one, "native_label": "style"},
                                            {**one, "explanation": "two"},
                                            {**one, "occurrence": 2},
                                            {**one, "left_context": "", "occurrence": 1}]}, text="x x")
        self.assertEqual([f["index"] for f in result["accepted_findings"]], [0, 2, 3, 4])
        self.assertEqual(result["rejected_findings"], [
            {"index": 1, "code": "DUPLICATE_FINDING"}, {"index": 5, "code": "DUPLICATE_FINDING"}])

    def test_json_syntax_duplicate_keys_nonfinite_and_utf8_are_response_errors(self):
        for raw in (b'{', b'{"findings":[],"findings":[]}',
                    b'{"findings":[{"quote":"x","quote":"x"}]}',
                    b'{"findings": [NaN]}', b'{"findings":[1e999]}',
                    b'{"findings":[]}' + b'\xff'):
            with self.subTest(raw=raw):
                result = ingest_response("a", "x", raw)
                self.assertEqual(result["response_error"], "INVALID_JSON")
                self.assertEqual(result["accepted_findings"], [])
                self.assertEqual(result["rejected_findings"], [])

    def test_json_unicode_scalar_and_excessive_nesting_are_response_errors(self):
        for raw in (b'{"findings":[{"native_label":"\\ud800","quote":"x","explanation":"why"}]}',
                    b'{"findings":' + b'[' * 2000 + b'0' + b']' * 2000 + b'}'):
            with self.subTest(raw_length=len(raw)):
                result = ingest_response("a", "x", raw)
                self.assertEqual(result["response_error"], "INVALID_JSON")
                self.assertEqual(result["accepted_findings"], [])

    def test_invalid_envelopes_reject_whole_response(self):
        for body in ([], None, {}, {"findings": None}, {"findings": {}},
                     {"findings": [], "status": "ready"}):
            with self.subTest(body=body):
                result = self.ingest(body)
                self.assertEqual(result["response_error"], "INVALID_ENVELOPE")
                self.assertEqual(result["accepted_findings"], [])

    def test_caller_argument_types_raise_value_error(self):
        for arguments in (("", "x", b'{}'), (2, "x", b'{}'),
                          ("a", 1, b'{}'), ("a", "x", '{}'),
                          ("a", "x", bytearray(b'{}'))):
            with self.subTest(arguments=arguments), self.assertRaises(ValueError):
                ingest_response(*arguments)


if __name__ == "__main__":
    unittest.main()
