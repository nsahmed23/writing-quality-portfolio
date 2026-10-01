"""Behavioral boundaries for the unattended proxy scoring engine."""

import copy
import json
import re
import unittest
from pathlib import Path

from evaluation.benchmark_v2.automated.contracts import (
    load_rubric, load_suite, strict_json, validate_rubric, validate_suite,
)
from evaluation.benchmark_v2.automated.scoring import (
    build_report, check_text, parse_judgment,
)


DATA = Path(__file__).resolve().parents[1] / "evaluation/benchmark_v2/automated/data"
JUDGES = [{"id": "j1", "family": "f1"}, {"id": "j2", "family": "f2"}]


def case(case_id, doc, split="calibration", lane="editing", expected="b"):
    return {"id": case_id, "document_id": doc, "split": split,
            "lane": lane, "prompt": f"Revise document {doc}", "context": "Context",
            "a": "The deadline is Tuesday.", "b": "The deadline is Friday.",
            "expected": expected, "checks": {},
            "provenance": {"kind": "synthetic_control", "source": "authored fixture", "license": "CC0-1.0"}}


def suite(split="calibration", per_lane=4):
    cases = []
    for lane in ("editing", "communication"):
        for i in range(per_lane):
            cases.append(case(f"{lane}-{i}", f"{lane}-doc-{i}", split, lane,
                              "b" if split == "calibration" else None))
    return {"schema_version": 1, "name": "fixtures", "cases": cases}


def records_for(value, winner="b"):
    return [{"case_id": c["id"], "document_id": c["document_id"],
             "lane": c["lane"], "split": c["split"], "judge_id": j["id"],
             "family": j["family"], "order": order, "valid": True,
             "winner": winner}
            for c in value["cases"] for j in JUDGES for order in (1, 2)]


class ContractTests(unittest.TestCase):
    def test_starter_controls_are_usable_and_honestly_labeled(self):
        value = load_suite(DATA / "controls.json")
        calibration = [c for c in value["cases"] if c["split"] == "calibration"]
        self.assertGreaterEqual(len(calibration), 8)
        self.assertGreaterEqual(len({c["document_id"] for c in calibration}), 4)
        for lane in ("editing", "communication"):
            self.assertGreaterEqual(len({c["document_id"] for c in value["cases"]
                                         if c["split"] == "test" and c["lane"] == lane}), 5)
        self.assertTrue(all(c["provenance"]["kind"] == "synthetic_control" for c in value["cases"]))
        self.assertEqual(load_rubric(DATA / "rubric.json")["schema_version"], 1)

    def test_calibration_pairs_have_visible_source_truth_and_shared_documents(self):
        controls = [c for c in load_suite(DATA / "controls.json")["cases"]
                    if c["split"] == "calibration"]
        by_id = {c["id"]: c for c in controls}
        source_requirements = {
            "edit-deadline-control": ("Tuesday", "Tuesday", "Thursday", "b"),
            "edit-fact-control": ("80 people", "80 people", "18 people", "a"),
            "edit-scope-control": ("Chicago office", "Chicago office", "all locations", "b"),
            "edit-economy-control": ("considering a delay", "considering a delay", "At this point in time", "b"),
            "comm-qualification-control": ("may help some people", "may help some people", "proves", "b"),
            "comm-action-control": ("Friday at noon", "Friday at noon", "at some point", "b"),
            "comm-padding-control": ("meeting is at noon", "meeting is at noon", "broad importance", "b"),
            "comm-unchanged-control": ("draft by 3 p.m.", "draft by 3 p.m.", "", "tie"),
        }
        self.assertEqual(set(by_id), set(source_requirements))
        for case_id, (source_fact, correct_text, faulty_text, expected) in source_requirements.items():
            c = by_id[case_id]
            with self.subTest(case_id=case_id):
                self.assertIn(source_fact, c["context"])
                self.assertEqual(c["expected"], expected)
                if expected == "tie":
                    self.assertEqual(c["a"], c["b"])
                    self.assertIn(correct_text, c["a"])
                else:
                    preferred = c[expected]
                    rejected = c["a" if expected == "b" else "b"]
                    self.assertIn(correct_text, preferred)
                    self.assertIn(faulty_text, rejected)
                    self.assertIn("preserve", c["prompt"].lower())
        groups = {}
        for c in controls:
            groups.setdefault(c["document_id"], []).append(c)
        self.assertEqual(len(groups), 4)
        for members in groups.values():
            self.assertEqual(len(members), 2)
            self.assertEqual(len({c["context"] for c in members}), 1)
            self.assertTrue(all(c["provenance"]["note"] == members[0]["provenance"]["note"]
                                for c in members))

    def test_strict_json_rejects_duplicate_keys_nonfinite_and_invalid_unicode(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'"\\ud800"', b'\xff'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                strict_json(raw)

    def test_suite_rejects_split_alias_even_with_new_document_id(self):
        value = suite()
        alias = copy.deepcopy(value["cases"][0])
        alias.update(id="alias", document_id="other-document", split="test", expected=None)
        value["cases"].append(alias)
        with self.assertRaises(ValueError):
            validate_suite(value)

    def test_same_split_copies_cannot_inflate_independent_documents(self):
        for split, copies in (("calibration", 4), ("test", 5)):
            with self.subTest(split=split):
                original = case("first", "source-document", split,
                                expected="b" if split == "calibration" else None)
                aliases = []
                for index in range(1, copies):
                    alias = copy.deepcopy(original)
                    alias.update(id=f"copy-{index}", document_id=f"false-document-{index}",
                                 prompt="  Revise   document source-document  ",
                                 a=original["b"], b=original["a"])
                    aliases.append(alias)
                with self.assertRaisesRegex(ValueError, "copied pair"):
                    validate_suite({"schema_version": 1, "name": "copies",
                                    "cases": [original, *aliases]})

                # Repetitions of the same input remain one statistical document.
                for alias in aliases:
                    alias["document_id"] = original["document_id"]
                validate_suite({"schema_version": 1, "name": "repetitions",
                                "cases": [original, *aliases]})

    def test_suite_split_alias_cannot_hide_behind_intermediate_same_split_copy(self):
        value = suite()
        original = value["cases"][0]
        same_split = copy.deepcopy(original)
        same_split.update(id="same-split", document_id="another-cal-doc")
        value["cases"].append(same_split)
        test_alias = copy.deepcopy(original)
        test_alias.update(id="test-alias", document_id="unrelated-test-doc",
                          split="test", expected=None,
                          a=original["b"], b=original["a"])
        value["cases"].append(test_alias)
        with self.assertRaises(ValueError):
            validate_suite(value)

    def test_suite_rejects_unknown_fields_published_gold_and_mixed_document_splits(self):
        value = suite()
        value["cases"][0]["unknown"] = 1
        with self.assertRaises(ValueError):
            validate_suite(value)
        del value["cases"][0]["unknown"]
        value["cases"][0]["provenance"]["kind"] = "published_reference"
        with self.assertRaises(ValueError):
            validate_suite(value)
        value["cases"][0]["expected"] = None
        value["cases"].append(case("second", "editing-doc-0", "test", expected=None))
        with self.assertRaises(ValueError):
            validate_suite(value)

    def test_rubric_rejects_duplicate_criterion_and_oversized_descriptions(self):
        rubric = {"schema_version": 1, "id": "r", "criteria": [
            {"id": "meaning", "description": "Preserve meaning"},
            {"id": "meaning", "description": "Preserve facts"}]}
        with self.assertRaises(ValueError):
            validate_rubric(rubric)
        rubric["criteria"].pop()
        rubric["criteria"][0]["description"] = "a" * 6001
        with self.assertRaises(ValueError):
            validate_rubric(rubric)


class JudgmentTests(unittest.TestCase):
    def test_literal_anchors_are_required_on_both_decisive_candidates(self):
        raw = {"winner": "B", "reason": "Different dates", "evidence": [
            {"candidate": "A", "quote": "Tuesday"},
            {"candidate": "B", "quote": "Saturday"}]}
        self.assertFalse(parse_judgment(json.dumps(raw).encode(),
                                        "Tuesday", "Friday")["valid"])
        raw["evidence"][1]["quote"] = "Friday"
        self.assertEqual(parse_judgment(json.dumps(raw).encode(),
                                        "Tuesday", "Friday")["winner"], "B")

    def test_ambiguous_quote_needs_occurrence_and_prose_envelope_is_invalid(self):
        raw = {"winner": "tie", "reason": "same", "evidence": [
            {"candidate": "A", "quote": "repeat"}]}
        self.assertFalse(parse_judgment(json.dumps(raw).encode(),
                                        "repeat repeat", "other")["valid"])
        raw["evidence"][0]["occurrence"] = 2
        self.assertTrue(parse_judgment(json.dumps(raw).encode(),
                                       "repeat repeat", "other")["valid"])
        self.assertFalse(parse_judgment(("prefix " + json.dumps(raw)).encode(),
                                        "repeat repeat", "other")["valid"])

    def test_explicit_occurrence_must_be_positive_integer(self):
        raw = {"winner": "tie", "reason": "same", "evidence": [
            {"candidate": "A", "quote": "unique", "occurrence": 1}]}
        for invalid in (None, True, False, 0, -1, 1.5):
            with self.subTest(occurrence=invalid):
                raw["evidence"][0]["occurrence"] = invalid
                self.assertFalse(parse_judgment(json.dumps(raw).encode(),
                                                "unique", "other")["valid"])
        raw["evidence"][0]["occurrence"] = 1
        self.assertTrue(parse_judgment(json.dumps(raw).encode(),
                                       "unique", "other")["valid"])

    def test_literal_candidate_checks_fail_independently(self):
        checks = {"required": ["Friday"], "forbidden": ["Tuesday"], "max_words": 4,
                  "exact": "Send Friday."}
        self.assertTrue(all(c["passed"] for c in check_text("Send Friday.", checks)))
        self.assertTrue(any(not c["passed"] for c in check_text("Send Tuesday now please.", checks)))


class ReportTests(unittest.TestCase):
    def test_missing_or_duplicate_records_invalidate_complete_coverage(self):
        value = suite()
        records = records_for(value)
        missing = build_report(value, records[:-1], JUDGES, mode="calibrate")
        self.assertFalse(missing["complete"])
        self.assertFalse(missing["eligible"])
        duplicate = build_report(value, records + [records[0]], JUDGES, mode="calibrate")
        self.assertFalse(duplicate["complete"])
        self.assertFalse(duplicate["eligible"])

    def test_invalid_and_unexpected_records_cannot_be_silently_dropped(self):
        value = suite()
        records = records_for(value)
        records[0]["valid"] = False
        records[0]["winner"] = None
        invalid = build_report(value, records, JUDGES, mode="calibrate")
        self.assertFalse(invalid["complete"])
        self.assertEqual(invalid["counts"]["invalid_records"], 1)
        records = records_for(value)
        records.append({**records[0], "case_id": "unknown"})
        unexpected = build_report(value, records, JUDGES, mode="calibrate")
        self.assertFalse(unexpected["complete"])
        self.assertEqual(unexpected["counts"]["unexpected_records"], 1)

    def test_unhashable_record_keys_are_invalid_incomplete_not_exceptions(self):
        value = suite()
        records = records_for(value)
        for malformed in ([], {}, {"nested": "id"}):
            with self.subTest(malformed=malformed):
                broken = [dict(r) for r in records]
                broken[0]["case_id"] = malformed
                report = build_report(value, broken, JUDGES, mode="calibrate")
                self.assertFalse(report["complete"])
                self.assertFalse(report["eligible"])
                self.assertGreater(report["counts"]["invalid_records"], 0)

    def test_order_disagreement_and_bad_judge_are_visible_and_disqualifying(self):
        value = suite()
        records = records_for(value)
        records[1]["winner"] = "a"
        report = build_report(value, records, JUDGES, mode="calibrate")
        self.assertFalse(report["eligible"])
        self.assertGreater(report["counts"]["order_disagreements"], 0)
        self.assertLess(report["by_judge"]["j1"]["accuracy"], 0.90)

    def test_calibration_requires_eight_controls_four_documents_per_judge(self):
        value = suite(per_lane=3)
        report = build_report(value, records_for(value), JUDGES, mode="calibrate")
        self.assertFalse(report["eligible"])
        self.assertEqual(report["recommendation"], "not_applicable")

    def test_single_family_can_calibrate_even_though_compare_needs_two(self):
        value = suite()
        one_judge = [JUDGES[0]]
        one_records = [r for r in records_for(value) if r["judge_id"] == "j1"]
        report = build_report(value, one_records, one_judge, mode="calibrate")
        self.assertTrue(report["eligible"])
        self.assertTrue(all(c["passed"] for c in report["checks"]))

    def test_demo_cannot_recommend_even_with_positive_controls(self):
        value = suite("test", per_lane=5)
        report = build_report(value, records_for(value), JUDGES, mode="compare",
                              calibration={"eligible": True, "execution": "live"}, execution="demo")
        self.assertFalse(report["eligible"])
        self.assertNotEqual(report["recommendation"], "candidate")

    def test_comparison_counts_decisive_documents_and_keeps_lanes_separate(self):
        value = suite("test", per_lane=5)
        report = build_report(value, records_for(value), JUDGES, mode="compare",
                              calibration={"eligible": True, "execution": "live"})
        self.assertEqual(report["recommendation"], "candidate")
        self.assertEqual(report["by_lane"]["editing"]["documents"], 5)
        self.assertEqual(round(report["by_lane"]["communication"]["wilson_lower"], 4), 0.6489)
        self.assertEqual(report["by_lane"]["editing"]["mean"], 1)

    def test_repetitions_share_document_weight_and_candidate_check_blocks_win(self):
        value = suite("test", per_lane=5)
        value["cases"].append(case("rep", "editing-doc-0", "test", "editing", None))
        value["cases"][-1]["prompt"] = "Second repetition"
        records = records_for(value)
        for record in records:
            if record["case_id"] == "rep":
                record["winner"] = "a"
        report = build_report(value, records, JUDGES, mode="compare",
                              calibration={"eligible": True, "execution": "live"})
        self.assertEqual(report["by_lane"]["editing"]["documents"], 5)
        self.assertAlmostEqual(report["by_lane"]["editing"]["mean"], .8)
        value["cases"][0]["checks"] = {"required": ["Tuesday"]}
        blocked = build_report(value, records, JUDGES, mode="compare",
                               calibration={"eligible": True, "execution": "live"})
        self.assertNotEqual(blocked["recommendation"], "candidate")
        self.assertGreater(blocked["counts"]["candidate_check_failures"], 0)

    def test_report_check_ids_are_stable_plugin_metric_ids(self):
        value = suite()
        report = build_report(value, records_for(value),
                              [{"id": "judge/one", "family": "f1"}], mode="calibrate")
        self.assertTrue(all(re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]*", c["id"])
                            for c in report["checks"]))

    def test_test_split_labels_do_not_become_calibration_accuracy(self):
        value = suite("test", per_lane=5)
        for item in value["cases"]:
            item["expected"] = "b"
        report = build_report(value, records_for(value), JUDGES, mode="compare",
                              calibration={"eligible": True, "execution": "live"})
        self.assertNotIn("accuracy", report["by_judge"]["j1"])
        self.assertNotIn("calibration_accuracy", report["metrics"])


if __name__ == "__main__":
    unittest.main()
