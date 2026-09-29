from __future__ import annotations

import time
import unittest

from wqeval.scoring import score_stage1

from tests.support import case, finding


class DeterministicPerformanceTests(unittest.TestCase):
    def test_ten_thousand_cases_are_deterministic_and_complete_within_ten_seconds(self) -> None:
        cases = []
        gold = []
        predictions = []
        for index in range(10_000):
            case_id = f"P{index:05d}"
            cases.append(case(case_id, "The API failed."))
            gold_item = finding(case_id, f"G{index:05d}")
            gold.append(gold_item)
            predictions.append(dict(gold_item, finding_id=f"R{index:05d}"))

        started = time.perf_counter()
        first = score_stage1(cases, gold, predictions)
        second = score_stage1(cases, gold, predictions)
        elapsed = time.perf_counter() - started

        self.assertEqual(first, second)
        self.assertEqual(first["true_positives"], 10_000)
        self.assertEqual(first["false_positives"], 0)
        self.assertEqual(first["false_negatives"], 0)
        self.assertLess(elapsed, 10.0, f"Two 10,000-case scoring passes took {elapsed:.3f}s")


if __name__ == "__main__":
    unittest.main()
