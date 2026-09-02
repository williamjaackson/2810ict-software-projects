"""
test_comparison_dashboard.py

Unit tests for comparison_dashboard.py (WBS 1.4.4, issue #7).

Covers both pure functions (find_cheapest_plan, build_comparison_figure)
with positive and negative cases, plus a rendering-time check against the
issue's <1.5s acceptance criterion. embed_dashboard() itself requires a
live Tkinter display and is intended for manual/visual verification
rather than automated headless testing.
"""

import sys
import os
import time
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from comparison_dashboard import find_cheapest_plan, build_comparison_figure


SAMPLE_RESULTS = {
    "Flat Rate":   {"fixed": 10.00, "variable": 75.00, "total": 85.00},
    "Time-of-Use": {"fixed": 8.00,  "variable": 84.00, "total": 92.00},
    "Tiered":      {"fixed": 12.00, "variable": 98.00, "total": 110.00},
}

PERFORMANCE_LIMIT_SECONDS = 1.5


class TestFindCheapestPlan(unittest.TestCase):
    def setUp(self):
        self.data = SAMPLE_RESULTS

    def test_positive_identifies_correct_cheapest_plan(self):
        plan, savings = find_cheapest_plan(self.data)
        self.assertEqual(plan, "Flat Rate")

    def test_positive_calculates_correct_savings_amount(self):
        # Cheapest ($85) vs most expensive ($110) = $25 savings
        result = find_cheapest_plan(self.data)
        savings_amount = result[1]
        self.assertEqual(savings_amount, 25.00)

    def test_positive_handles_tied_plans(self):
        tied_plans_dict = {
            "Flat Rate": {"fixed": 10, "variable": 75, "total": 85},
            "Tiered":    {"fixed": 12, "variable": 73, "total": 85},
        }
        plan, savings = find_cheapest_plan(tied_plans_dict)
        # don't know which one it'll pick (dict order ig) so just check it's a valid plan
        self.assertTrue(plan in tied_plans_dict)
        self.assertEqual(savings, 0.0)

    def test_negative_empty_dict_raises_value_error(self):
        empty_dict = {}
        with self.assertRaises(ValueError):
            find_cheapest_plan(empty_dict)

    def test_negative_missing_total_key_raises_key_error(self):
        malformed = {"Flat Rate": {"fixed": 10, "variable": 75}}
        try:
            find_cheapest_plan(malformed)
            self.fail("expected a KeyError but nothing was raised")
        except KeyError:
            pass


class TestBuildComparisonFigure(unittest.TestCase):

    def test_positive_returns_a_figure_for_valid_data(self):

        fig = build_comparison_figure(SAMPLE_RESULTS)
        num_axes = len(fig.axes)
        self.assertEqual(num_axes, 2)

    def test_positive_renders_within_performance_target(self):

        start = time.perf_counter()
        build_comparison_figure(SAMPLE_RESULTS)
        end = time.perf_counter()
        elapsed = end - start
        print("build_comparison_figure took", elapsed, "seconds")  # just for my own sanity check
        self.assertLess(elapsed, PERFORMANCE_LIMIT_SECONDS,
                         "Dashboard figure should render in under 1.5s")

    def test_negative_empty_dict_raises_value_error(self):
        
        with self.assertRaises(ValueError):
            build_comparison_figure({})

    def test_negative_missing_fixed_key_raises_key_error(self):
        malformed_data = {"Flat Rate": {"variable": 75.00, "total": 85.00}}
        with self.assertRaises(KeyError):
            build_comparison_figure(malformed_data)

    def test_negative_missing_variable_key_raises_key_error(self):
       
        malformed_data = {"Flat Rate": {"fixed": 10.00, "total": 85.00}}
        with self.assertRaises(KeyError):
            build_comparison_figure(malformed_data)


if __name__ == "__main__":
    print("running tests for comparison_dashboard.py...")
    unittest.main()
