import tempfile
import unittest
from pathlib import Path

from main import run_pipeline


class TestRunPipeline(unittest.TestCase):
    def write_csv(self, content):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "usage.csv"
        path.write_text(content)
        return path

    def test_returns_dashboard_results_for_each_plan(self):
        path = self.write_csv("timestamp,kwh\n2026-01-01 00:00,1.5\n2026-01-01 17:00,2.0\n")

        bill_results, warnings = run_pipeline(path)

        self.assertEqual(set(bill_results), {"Flat Rate", "Time of Use", "Tiered Rate"})
        for result in bill_results.values():
            self.assertAlmostEqual(result["total"], result["fixed"] + result["variable"])
        self.assertEqual(warnings, [])

    def test_bad_file_raises_value_error(self):
        path = self.write_csv("date,usage\n2026-01-01 00:00,1.5\n")

        with self.assertRaises(ValueError):
            run_pipeline(path)


if __name__ == "__main__":
    unittest.main()
