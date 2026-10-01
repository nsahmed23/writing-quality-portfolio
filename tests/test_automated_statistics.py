"""Per-lane statistics: the Wilson interval, the exact sign test, Holm's step-down and the decision rule.

The known values were computed apart from the code under test. A Wilson bound is a root of
(1 + z^2/n) p^2 - (2 phat + z^2/n) p + phat^2 = 0, solved in 50-digit decimal arithmetic, and the sign test is a sum of
binomial coefficients taken as integers over 2^n. No model is called."""

import inspect
import unittest
from pathlib import Path

from evaluation.benchmark_v2.automated.scoring import build_report

AUTOMATED = Path(__file__).resolve().parents[1] / "evaluation" / "benchmark_v2" / "automated"
JUDGES = [{"id": "j1", "family": "f1"}, {"id": "j2", "family": "f2"}]
CERTIFICATE = {"eligible": True, "execution": "live"}
LANE_FIELDS = {"cases", "documents", "decisive", "wins", "losses", "proportion", "wilson_lower", "wilson_upper",
               "mean", "sign_test_p", "recommendation"}


def stats():
    """The statistics module, loaded inside each test so a missing module fails that test and not the whole file."""
    from evaluation.benchmark_v2.automated import lane_stats
    return lane_stats


def docs(*outcomes, times=1):
    """`times` documents, each with one case per outcome ('a', 'b', 'tie' or 'split')."""
    return [list(outcomes) for _ in range(times)]


def case(case_id, document_id, lane, split):
    return {"id": case_id, "document_id": document_id, "split": split, "lane": lane,
            "prompt": f"Revise {case_id}", "context": "Context",
            "a": "The deadline is Tuesday.", "b": "The deadline is Friday.",
            "expected": "b" if split == "calibration" else None, "checks": {},
            "provenance": {"kind": "synthetic_control", "source": "authored fixture", "license": "CC0-1.0"}}


def winner_for(outcome, judge):
    """'split' makes the two judges disagree, which the engine counts as no preference."""
    if outcome == "split":
        return "a" if judge["id"] == "j1" else "b"
    return outcome


def report_for(lanes, mode="compare", split="test", skipped=()):
    """A report over documents given per lane as lists of per-case outcomes."""
    cases, records = [], []
    for lane, documents in lanes.items():
        for number, outcomes in enumerate(documents):
            for position, outcome in enumerate(outcomes):
                item = case(f"{lane}-{number}-{position}", f"{lane}-doc-{number}", lane, split)
                cases.append(item)
                for judge in JUDGES:
                    for order in (1, 2):
                        record = {"case_id": item["id"], "document_id": item["document_id"], "lane": lane,
                                  "split": split, "judge_id": judge["id"], "family": judge["family"], "order": order,
                                  "valid": True, "winner": winner_for(outcome, judge)}
                        if item["id"] in skipped:
                            record.update(valid=False, winner=None, failure_kind="skipped",
                                          error="oversized_prompt: test")
                        records.append(record)
    value = {"schema_version": 1, "name": "statistics-fixture", "cases": cases}
    extra = {"calibration": CERTIFICATE} if mode == "compare" else {}
    return build_report(value, records, JUDGES, mode=mode, **extra)


def five(outcome):
    return docs(outcome, times=5)


class WilsonIntervalTests(unittest.TestCase):
    def test_five_of_five_has_the_lower_bound_0_6489_and_is_not_an_interval_of_one_point(self):
        lower, upper = stats().wilson_interval(5, 5)
        self.assertEqual(round(lower, 4), 0.6489)
        self.assertAlmostEqual(lower, 0.648883499235, places=9)
        self.assertEqual(upper, 1.0)

    def test_zero_of_five_has_a_lower_bound_of_exactly_zero(self):
        lower, upper = stats().wilson_interval(0, 5)
        self.assertEqual(lower, 0.0)
        self.assertAlmostEqual(upper, 0.351116500765, places=9)

    def test_three_of_five(self):
        lower, upper = stats().wilson_interval(3, 5)
        self.assertAlmostEqual(lower, 0.272483171866, places=9)
        self.assertAlmostEqual(upper, 0.857293527981, places=9)

    def test_four_of_six(self):
        lower, upper = stats().wilson_interval(4, 6)
        self.assertAlmostEqual(lower, 0.347014767000, places=9)
        self.assertAlmostEqual(upper, 0.882723905898, places=9)

    def test_no_decisive_documents_gives_the_whole_unit_interval(self):
        self.assertEqual(stats().wilson_interval(0, 0), (0.0, 1.0))

    def test_other_known_values(self):
        for (wins, n), (lower, upper) in {(4, 5): (0.435292553422, 0.954037546119),
                                          (12, 12): (0.816018805253, 1.0),
                                          (9, 20): (0.284123491289, 0.627792292447)}.items():
            with self.subTest(wins=wins, n=n):
                got = stats().wilson_interval(wins, n)
                self.assertAlmostEqual(got[0], lower, places=9)
                self.assertAlmostEqual(got[1], upper, places=9)

    def test_the_interval_stays_inside_zero_and_one_and_around_the_proportion(self):
        for n in range(1, 31):
            for wins in range(n + 1):
                lower, upper = stats().wilson_interval(wins, n)
                self.assertTrue(0.0 <= lower <= wins / n <= upper <= 1.0, (wins, n, lower, upper))

    def test_swapping_wins_and_losses_mirrors_the_interval(self):
        for n in range(1, 21):
            for wins in range(n + 1):
                lower, upper = stats().wilson_interval(wins, n)
                mirror_lower, mirror_upper = stats().wilson_interval(n - wins, n)
                self.assertAlmostEqual(lower, 1 - mirror_upper, places=12)
                self.assertAlmostEqual(upper, 1 - mirror_lower, places=12)

    def test_counts_that_cannot_be_counts_are_refused(self):
        for wins, n in ((6, 5), (-1, 5), (1, -1), (1.5, 5), (True, 5), ("1", 5)):
            with self.subTest(wins=wins, n=n), self.assertRaises(ValueError):
                stats().wilson_interval(wins, n)


class SignTestTests(unittest.TestCase):
    def test_known_values_are_exact(self):
        for (wins, n), expected in {(5, 5): 0.03125, (0, 5): 1.0, (3, 5): 0.5, (4, 6): 0.34375, (4, 5): 0.1875,
                                    (1, 5): 0.96875, (12, 12): 2.0 ** -12, (0, 0): 1.0}.items():
            with self.subTest(wins=wins, n=n):
                self.assertEqual(stats().sign_test_p(wins, n), expected)

    def test_it_is_the_exact_binomial_tail_and_not_a_normal_approximation(self):
        self.assertAlmostEqual(stats().sign_test_p(9, 20), 0.748277664185, places=9)
        self.assertAlmostEqual(stats().sign_test_p(11, 20), 0.411901473999, places=9)

    def test_counts_that_cannot_be_counts_are_refused(self):
        for wins, n in ((6, 5), (-1, 5), (True, 5)):
            with self.subTest(wins=wins, n=n), self.assertRaises(ValueError):
                stats().sign_test_p(wins, n)


class HolmTests(unittest.TestCase):
    def test_the_textbook_example_rejects_the_two_smallest(self):
        # alpha / (m - i) for the sorted p-values 0.005, 0.01, 0.03, 0.04 is 0.0125, 0.01667, 0.025, 0.05: the first
        # two clear their threshold and 0.03 does not, so the walk stops there.
        self.assertEqual(stats().holm([0.01, 0.04, 0.03, 0.005], 0.05), [True, False, False, True])

    def test_it_rejects_what_plain_bonferroni_would_not(self):
        # Bonferroni compares both to 0.025; Holm's second threshold is 0.05.
        self.assertEqual(stats().holm([0.011, 0.04], 0.05), [True, True])

    def test_it_stops_at_the_first_failure_even_if_a_later_value_passes_its_own_threshold(self):
        # 0.018 fails 0.05/3, so 0.02 is not tried although it is below its own threshold of 0.05/2.
        self.assertEqual(stats().holm([0.018, 0.02, 0.2], 0.05), [False, False, False])

    def test_equal_p_values_and_the_order_of_the_input_are_handled(self):
        self.assertEqual(stats().holm([0.01, 0.01], 0.05), [True, True])
        self.assertEqual(stats().holm([0.2, 0.001], 0.05), [False, True])

    def test_nothing_is_rejected_when_the_smallest_fails_and_an_empty_family_is_empty(self):
        self.assertEqual(stats().holm([0.03, 0.03], 0.05), [False, False])
        self.assertEqual(stats().holm([], 0.05), [])

    def test_p_values_and_alpha_out_of_range_are_refused(self):
        for p_values, alpha in (([1.5], 0.05), ([-0.1], 0.05), ([0.1], 0), ([0.1], 1.5)):
            with self.subTest(p_values=p_values, alpha=alpha), self.assertRaises(ValueError):
                stats().holm(p_values, alpha)


class DecisionRuleTests(unittest.TestCase):
    def test_the_constants_are_named_in_one_module(self):
        module = stats()
        self.assertEqual((module.Z_90, module.NULL_PROPORTION, module.MIN_EFFECT), (1.6448536269514722, 0.5, 0.15))
        for path in sorted(AUTOMATED.glob("*.py")):
            if path.name != "lane_stats.py":
                self.assertNotIn("1.6448536269514722", path.read_text(encoding="utf-8"), path.name)

    def test_a_lane_wins_for_the_candidate_when_the_lower_bound_clears_one_half_and_the_mean_clears_0_15(self):
        decide = stats().lane_decision
        self.assertEqual(decide(0.6489, 1.0, 1.0), "candidate")
        self.assertEqual(decide(0.8160, 1.0, 0.15), "candidate")

    def test_a_lane_wins_for_the_baseline_when_the_upper_bound_is_under_one_half_and_the_mean_is_under_minus_0_15(self):
        decide = stats().lane_decision
        self.assertEqual(decide(0.0, 0.3511, -1.0), "baseline")
        self.assertEqual(decide(0.0, 0.2, -0.15), "baseline")

    def test_a_bound_on_one_half_does_not_decide(self):
        decide = stats().lane_decision
        self.assertEqual(decide(0.5, 1.0, 1.0), "inconclusive")
        self.assertEqual(decide(0.0, 0.5, -1.0), "inconclusive")

    def test_a_mean_inside_the_effect_floor_does_not_decide_however_firm_the_proportion(self):
        decide = stats().lane_decision
        self.assertEqual(decide(0.8160, 1.0, 0.1499), "inconclusive")
        self.assertEqual(decide(0.0, 0.2, -0.1499), "inconclusive")

    def test_an_interval_that_straddles_one_half_is_inconclusive_whatever_the_mean(self):
        self.assertEqual(stats().lane_decision(0.4353, 0.9540, 0.6), "inconclusive")
        self.assertEqual(stats().lane_decision(0.0, 1.0, 0.0), "inconclusive")

    def test_a_mean_that_points_the_other_way_never_wins(self):
        decide = stats().lane_decision
        self.assertEqual(decide(0.6, 1.0, -1.0), "inconclusive")
        self.assertEqual(decide(0.0, 0.4, 1.0), "inconclusive")


class LaneStatisticsTests(unittest.TestCase):
    def test_five_documents_all_for_the_candidate(self):
        got = stats().lane_statistics([1.0] * 5)
        self.assertEqual((got["decisive"], got["wins"], got["losses"], got["proportion"]), (5, 5, 0, 1.0))
        self.assertAlmostEqual(got["wilson_lower"], 0.648883499235, places=9)
        self.assertEqual((got["wilson_upper"], got["mean"], got["sign_test_p"]), (1.0, 1.0, 0.03125))

    def test_a_nonzero_net_preference_of_any_size_is_decisive_and_a_zero_is_not(self):
        got = stats().lane_statistics([1.0, 0.5, -0.25, 0.0, 0.0, -1.0])
        self.assertEqual((got["decisive"], got["wins"], got["losses"]), (4, 2, 2))
        self.assertEqual(got["proportion"], 0.5)
        self.assertAlmostEqual(got["mean"], 0.25 / 6, places=12)

    def test_no_decisive_document_gives_no_proportion_and_the_whole_interval(self):
        got = stats().lane_statistics([0.0] * 5)
        self.assertEqual((got["decisive"], got["wins"], got["losses"], got["proportion"]), (0, 0, 0, None))
        self.assertEqual((got["wilson_lower"], got["wilson_upper"], got["mean"], got["sign_test_p"]), (0.0, 1.0, 0.0, 1.0))

    def test_no_document_at_all_has_no_mean(self):
        got = stats().lane_statistics([])
        self.assertEqual((got["decisive"], got["proportion"], got["mean"]), (0, None, None))
        self.assertEqual((got["wilson_lower"], got["wilson_upper"], got["sign_test_p"]), (0.0, 1.0, 1.0))


class ReportTests(unittest.TestCase):
    def lane(self, report, name="editing"):
        return report["by_lane"][name]

    def test_five_of_five_recommends_the_candidate_and_reports_every_statistic(self):
        report = report_for({"editing": five("b"), "communication": five("b")})
        lane = self.lane(report)
        self.assertEqual(set(lane), LANE_FIELDS)
        self.assertEqual((lane["cases"], lane["documents"], lane["decisive"], lane["wins"], lane["losses"]),
                         (5, 5, 5, 5, 0))
        self.assertEqual((lane["proportion"], lane["mean"], lane["wilson_upper"], lane["sign_test_p"]),
                         (1.0, 1.0, 1.0, 0.03125))
        self.assertAlmostEqual(lane["wilson_lower"], 0.648883499235, places=9)
        self.assertEqual(lane["recommendation"], "candidate")
        self.assertEqual(report["recommendation"], "candidate")

    def test_zero_of_five_recommends_the_baseline(self):
        report = report_for({"editing": five("a"), "communication": five("a")})
        lane = self.lane(report)
        self.assertEqual((lane["decisive"], lane["wins"], lane["losses"], lane["proportion"]), (5, 0, 5, 0.0))
        self.assertEqual((lane["wilson_lower"], lane["mean"], lane["sign_test_p"]), (0.0, -1.0, 1.0))
        self.assertAlmostEqual(lane["wilson_upper"], 0.351116500765, places=9)
        self.assertEqual((lane["recommendation"], report["recommendation"]), ("baseline", "baseline"))

    def test_three_of_five_is_inconclusive(self):
        report = report_for({"editing": docs("b", times=3) + docs("a", times=2), "communication": five("b")})
        lane = self.lane(report)
        self.assertEqual((lane["decisive"], lane["wins"], lane["losses"], lane["proportion"]), (5, 3, 2, 0.6))
        self.assertAlmostEqual(lane["wilson_lower"], 0.272483171866, places=9)
        self.assertAlmostEqual(lane["wilson_upper"], 0.857293527981, places=9)
        self.assertAlmostEqual(lane["mean"], 0.2, places=12)
        self.assertEqual((lane["sign_test_p"], lane["recommendation"]), (0.5, "inconclusive"))
        self.assertEqual(report["recommendation"], "inconclusive")

    def test_four_of_six_is_inconclusive(self):
        report = report_for({"editing": docs("b", times=4) + docs("a", times=2), "communication": five("b")})
        lane = self.lane(report)
        self.assertEqual((lane["documents"], lane["decisive"], lane["wins"], lane["losses"]), (6, 6, 4, 2))
        self.assertAlmostEqual(lane["proportion"], 4 / 6, places=12)
        self.assertAlmostEqual(lane["wilson_lower"], 0.347014767000, places=9)
        self.assertAlmostEqual(lane["wilson_upper"], 0.882723905898, places=9)
        self.assertAlmostEqual(lane["mean"], 2 / 6, places=12)
        self.assertEqual((lane["sign_test_p"], lane["recommendation"]), (0.34375, "inconclusive"))

    def test_no_decisive_document_is_inconclusive_with_the_whole_interval(self):
        report = report_for({"editing": five("tie"), "communication": five("b")})
        lane = self.lane(report)
        self.assertEqual((lane["documents"], lane["decisive"], lane["wins"], lane["losses"]), (5, 0, 0, 0))
        self.assertEqual((lane["proportion"], lane["wilson_lower"], lane["wilson_upper"]), (None, 0.0, 1.0))
        self.assertEqual((lane["mean"], lane["sign_test_p"], lane["recommendation"]), (0.0, 1.0, "inconclusive"))

    def test_ties_abstentions_and_judge_disagreement_count_as_zero_preference(self):
        # A tie, two judges that disagree, and a document whose cases cancel each other all have d = 0.
        documents = [["tie"], ["split"], ["a", "b"], ["b"], ["b"]]
        lane = self.lane(report_for({"editing": documents, "communication": five("b")}))
        self.assertEqual((lane["documents"], lane["decisive"], lane["wins"], lane["losses"]), (5, 2, 2, 0))
        self.assertAlmostEqual(lane["mean"], 0.4, places=12)
        self.assertLess(lane["wilson_lower"], 0.5)
        self.assertEqual(lane["recommendation"], "inconclusive")

    def test_a_partial_preference_is_decisive_and_keeps_its_size_in_the_mean(self):
        lane = self.lane(report_for({"editing": docs("b", "tie", times=5), "communication": five("b")}))
        self.assertEqual((lane["decisive"], lane["wins"], lane["losses"]), (5, 5, 0))
        self.assertAlmostEqual(lane["mean"], 0.5, places=12)
        self.assertEqual(lane["recommendation"], "candidate")

    def test_a_firm_proportion_with_a_mean_under_0_15_is_not_a_win(self):
        # Twelve documents that each favour the candidate in one case of eight: wins 12 of 12 (lower bound 0.816) but d is 0.125.
        small = self.lane(report_for({"editing": docs("b", *["tie"] * 7, times=12), "communication": five("b")}))
        self.assertEqual((small["decisive"], small["wins"]), (12, 12))
        self.assertAlmostEqual(small["wilson_lower"], 0.816018805253, places=9)
        self.assertAlmostEqual(small["mean"], 0.125, places=12)
        self.assertEqual(small["recommendation"], "inconclusive")
        # One case in five is d = 0.2, over the floor, with the same proportion.
        large = self.lane(report_for({"editing": docs("b", *["tie"] * 4, times=12), "communication": five("b")}))
        self.assertAlmostEqual(large["mean"], 0.2, places=12)
        self.assertEqual(large["recommendation"], "candidate")

    def test_a_large_mean_with_a_lower_bound_under_one_half_is_not_a_win(self):
        lane = self.lane(report_for({"editing": docs("b", times=4) + docs("a"), "communication": five("b")}))
        self.assertEqual((lane["decisive"], lane["wins"], lane["losses"]), (5, 4, 1))
        self.assertAlmostEqual(lane["wilson_lower"], 0.435292553422, places=9)
        self.assertAlmostEqual(lane["wilson_upper"], 0.954037546119, places=9)
        self.assertAlmostEqual(lane["mean"], 0.6, places=12)
        self.assertEqual((lane["sign_test_p"], lane["recommendation"]), (0.1875, "inconclusive"))

    def test_the_five_document_gate_still_holds_for_a_perfect_lane(self):
        report = report_for({"editing": docs("b", times=4), "communication": five("b")})
        lane = self.lane(report)
        self.assertEqual((lane["documents"], lane["wins"], lane["recommendation"]), (4, 4, "inconclusive"))
        self.assertGreater(lane["wilson_lower"], 0.5)
        self.assertFalse(report["eligible"])
        self.assertIn("lane_documents_editing", [c["id"] for c in report["checks"] if not c["passed"]])

    def test_every_mode_carries_the_same_lane_fields_and_no_bootstrap_fields(self):
        for mode, split in (("compare", "test"), ("score", "test"), ("calibrate", "calibration")):
            with self.subTest(mode=mode):
                report = report_for({"editing": five("b"), "communication": five("b")}, mode=mode, split=split)
                for lane in report["by_lane"].values():
                    self.assertEqual(set(lane), LANE_FIELDS)
                    self.assertNotIn("ci_lower", lane)
                    self.assertNotIn("ci_upper", lane)

    def test_a_lane_whose_cases_were_all_skipped_reports_empty_statistics(self):
        report = report_for({"editing": five("b"), "communication": docs("b")}, skipped={"communication-0-0"})
        self.assertEqual(report["by_lane"]["communication"], {
            "cases": 0, "documents": 0, "decisive": 0, "wins": 0, "losses": 0, "proportion": None,
            "wilson_lower": 0.0, "wilson_upper": 1.0, "mean": None, "sign_test_p": 1.0,
            "recommendation": "inconclusive"})

    def test_the_percentile_bootstrap_and_its_seed_are_gone(self):
        source = (AUTOMATED / "scoring.py").read_text(encoding="utf-8")
        self.assertNotIn("import random", source)
        self.assertNotIn("_interval", source)
        self.assertNotIn("seed", inspect.signature(build_report).parameters)


if __name__ == "__main__":
    unittest.main()
