import tempfile
import unittest
from datetime import time
from pathlib import Path

from main import DEFAULT_FORM, parse_tariffs, run_pipeline


class TestParseTariffs(unittest.TestCase):
    def test_default_form_parses(self):
        tariffs = parse_tariffs(DEFAULT_FORM)

        self.assertEqual(tariffs["tou_windows"]["peak"], (time(18), time(22)))
        self.assertEqual(tariffs["tiers"][-1]["limit"], float("inf"))

    def test_non_numeric_rate_names_the_field(self):
        with self.assertRaisesRegex(ValueError, "Flat rate"):
            parse_tariffs({**DEFAULT_FORM, "flat_rate": "abc"})

    def test_malformed_hours_names_the_field(self):
        with self.assertRaisesRegex(ValueError, "Peak hours"):
            parse_tariffs({**DEFAULT_FORM, "peak_hours": "6pm"})


class TestRunPipeline(unittest.TestCase):
    def write_csv(self, content):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "usage.csv"
        path.write_text(content)
        return path

    def test_returns_dashboard_results_for_each_plan(self):
        path = self.write_csv("timestamp,kwh\n2026-01-01 00:00,1.5\n2026-01-01 19:00,2.0\n")

        bill_results, warnings = run_pipeline(path, parse_tariffs(DEFAULT_FORM))

        self.assertEqual(set(bill_results), {"Flat Rate", "Time of Use", "Tiered Rate"})
        self.assertAlmostEqual(bill_results["Flat Rate"]["total"], 30.00 + 3.5 * 0.30)
        self.assertAlmostEqual(bill_results["Time of Use"]["variable"], 1.5 * 0.18 + 2.0 * 0.45)
        self.assertEqual(warnings, [])

    def test_bad_file_raises_value_error(self):
        path = self.write_csv("date,usage\n2026-01-01 00:00,1.5\n")

        with self.assertRaises(ValueError):
            run_pipeline(path, parse_tariffs(DEFAULT_FORM))


if __name__ == "__main__":
    unittest.main()
