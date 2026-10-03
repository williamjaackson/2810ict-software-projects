"""
Module: test_tariff_calculators.py
Author: Shromm Gaind

AI Assistance Declaration:
I declare that I am the primary author of this module. AI tools
(Codex / GPT-5.3 Sol) were used strictly as an assistive tool for:
-Generating the unit tests within this file
Everything within this file has been readthrough and I hold responsibility for the code.
"""
import unittest
from datetime import datetime, time

import numpy as np
import pandas as pd

from src.tariff_calculators import EnergyBillCalculator


def sample_consumption():
    """Provides a standard 5-reading usage profile totaling 8.0 kWh."""
    return {
        datetime(2025, 1, 1, 10, 0): 1.0,  # 10:00 - Shoulder
        datetime(2025, 1, 1, 18, 0): 2.5,  # 18:00 - Peak
        datetime(2025, 1, 1, 19, 0): 2.5,  # 19:00 - Peak
        datetime(2025, 1, 1, 23, 0): 1.0,  # 23:00 - Off-Peak
        datetime(2025, 1, 2, 1, 0): 1.0,  # 01:00 - Off-Peak (Next day)
    }


class TestInit(unittest.TestCase):
    def setUp(self):
        self.consumption = sample_consumption()
        self.calc = EnergyBillCalculator(self.consumption)

    def test_init_valid(self):
        """Test standard initialization and cached total."""
        self.assertEqual(self.calc.total_kwh, 8.0)
        self.assertEqual(len(self.calc.timestamps), 5)
        self.assertEqual(len(self.calc.kwh_usage), 5)

    def test_init_empty_dict(self):
        """Test that empty data raises a ValueError."""
        with self.assertRaisesRegex(ValueError, "cannot be empty"):
            EnergyBillCalculator({})

    def test_init_negative_consumption(self):
        """Test that negative consumption raises an error."""
        self.consumption[datetime(2025, 1, 1, 12, 0)] = -5.0
        with self.assertRaisesRegex(ValueError, "Negative consumption"):
            EnergyBillCalculator(self.consumption)

    def test_init_nan_consumption(self):
        """Test that NaN values are blocked."""
        self.consumption[datetime(2025, 1, 1, 12, 0)] = np.nan
        with self.assertRaisesRegex(ValueError, "NaN or infinite"):
            EnergyBillCalculator(self.consumption)

    def test_init_out_of_order_sorting(self):
        """Test that out-of-order timestamps are automatically sorted."""
        unsorted_data = {
            datetime(2025, 1, 2, 0, 0): 2.0,
            datetime(2025, 1, 1, 0, 0): 1.0,
        }
        c = EnergyBillCalculator(unsorted_data, sort=True)
        self.assertEqual(c.timestamps[0], pd.Timestamp("2025-01-01 00:00:00"))
        self.assertEqual(c.kwh_usage[0], 1.0)

    def test_minute_of_day_calculation(self):
        """Test that timestamps are correctly mapped to 0-1439 minutes."""
        mod = self.calc.minute_of_day
        self.assertEqual(mod[0], 600)  # 10:00 -> 10 * 60 = 600
        self.assertEqual(mod[1], 1080)  # 18:00 -> 18 * 60 = 1080


class TestFlatRate(unittest.TestCase):
    def setUp(self):
        self.calc = EnergyBillCalculator(sample_consumption())

    def test_flat_rate_valid(self):
        """Test accurate flat rate mathematics."""
        res = self.calc.calculate_flat_rate(rate_per_kwh=0.20, fixed_fee=10.0)

        self.assertEqual(res["model"], "Flat Rate")
        self.assertEqual(res["total_kwh"], 8.0)
        self.assertEqual(res["fixed_fee"], 10.0)
        # 8.0 * 0.20 = 1.6
        self.assertAlmostEqual(res["energy_fee"], 1.6)
        self.assertAlmostEqual(res["total_bill"], 11.6)

    def test_flat_rate_invalid_rates(self):
        """Test negative rates raise errors."""
        with self.assertRaisesRegex(ValueError, "non-negative"):
            self.calc.calculate_flat_rate(rate_per_kwh=-0.1)


class TestTieredRate(unittest.TestCase):
    def setUp(self):
        self.calc = EnergyBillCalculator(sample_consumption())

    def test_tiered_rate_valid(self):
        """Test tiered math with clip/diff logic over edges."""
        tariff_tiers = [
            {"limit": 5.0, "rate": 0.10},  # First 5 kWh @ $0.10
            {"limit": float('inf'), "rate": 0.20}  # Remaining 3 kWh @ $0.20
        ]
        res = self.calc.calculate_tiered_rate(tariff_tiers=tariff_tiers, fixed_fee=5.0)

        # 5 * 0.10 + 3 * 0.20 = 0.5 + 0.6 = 1.10
        self.assertAlmostEqual(res["energy_fee"], 1.10)
        self.assertAlmostEqual(res["total_bill"], 6.10)

        self.assertEqual(res["breakdown"]["tier_1"]["kwh"], 5.0)
        self.assertAlmostEqual(res["breakdown"]["tier_1"]["cost"], 0.50)
        self.assertEqual(res["breakdown"]["tier_2"]["kwh"], 3.0)
        self.assertAlmostEqual(res["breakdown"]["tier_2"]["cost"], 0.60)

    def test_tiered_rate_malformed_limits(self):
        """Test that non-increasing limits raise errors."""
        tariff_tiers = [
            {"limit": 10.0, "rate": 0.10},
            {"limit": 5.0, "rate": 0.20}  # Limit dropped (invalid block size)
        ]
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            self.calc.calculate_tiered_rate(tariff_tiers=tariff_tiers)

    def test_tiered_rate_exceeds_bounds(self):
        """Test failure when final tier doesn't cover total usage."""
        tariff_tiers = [
            {"limit": 5.0, "rate": 0.10}  # Total usage is 8.0
        ]
        with self.assertRaisesRegex(ValueError, "usage is 8.0"):
            self.calc.calculate_tiered_rate(tariff_tiers=tariff_tiers)

    def test_tiered_rate_negative_rates(self):
        """Test negative rates in tiers are blocked."""
        tariff_tiers = [{"limit": float('inf'), "rate": -0.10}]
        with self.assertRaisesRegex(ValueError, "non-negative"):
            self.calc.calculate_tiered_rate(tariff_tiers=tariff_tiers)


class TestTouRate(unittest.TestCase):
    def setUp(self):
        self.calc = EnergyBillCalculator(sample_consumption())
        self.period_rates = {"peak": 0.50, "shoulder": 0.30, "off-peak": 0.10}
        self.time_windows = {
            "peak": (time(18, 0), time(22, 0)),
            "off-peak": (time(22, 0), time(7, 0))  # Midnight cross
        }

    def test_tou_rate_valid(self):
        """Test TOU mapping and bincount logic, including midnight crossing."""
        res = self.calc.calculate_tou_rate(
            period_rates=self.period_rates,
            time_windows=self.time_windows
        )

        # Validation against the sample data:
        # 10:00 (1.0) -> Shoulder
        # 18:00 (2.5) -> Peak
        # 19:00 (2.5) -> Peak
        # 23:00 (1.0) -> Off-Peak
        # 01:00 (1.0) -> Off-Peak

        breakdown = res["breakdown"]
        self.assertEqual(breakdown["peak"]["kwh"], 5.0)
        self.assertAlmostEqual(breakdown["peak"]["cost"], 2.50)  # 5 * 0.50

        self.assertEqual(breakdown["off-peak"]["kwh"], 2.0)
        self.assertAlmostEqual(breakdown["off-peak"]["cost"], 0.20)  # 2 * 0.10

        self.assertEqual(breakdown["shoulder"]["kwh"], 1.0)
        self.assertAlmostEqual(breakdown["shoulder"]["cost"], 0.30)  # 1 * 0.30

        self.assertAlmostEqual(res["energy_fee"], 3.00)

    def test_tou_rate_overlap(self):
        """Test that the 1440-LUT catches overlapping windows."""
        self.time_windows["peak"] = (time(18, 0), time(23, 0))
        self.time_windows["off-peak"] = (time(22, 0), time(7, 0))  # Overlaps 22:00-23:00

        with self.assertRaisesRegex(ValueError, "Overlapping time windows"):
            self.calc.calculate_tou_rate(
                period_rates=self.period_rates,
                time_windows=self.time_windows
            )

    def test_tou_rate_missing_rate(self):
        """Test error when a window is defined but no rate is provided."""
        del self.period_rates["peak"]
        with self.assertRaisesRegex(ValueError, "No rate supplied"):
            self.calc.calculate_tou_rate(
                period_rates=self.period_rates,
                time_windows=self.time_windows
            )

    def test_tou_rate_zero_length_window(self):
        """Test error when start and end times are identical."""
        self.time_windows["peak"] = (time(18, 0), time(18, 0))
        with self.assertRaisesRegex(ValueError, "zero length"):
            self.calc.calculate_tou_rate(
                period_rates=self.period_rates,
                time_windows=self.time_windows
            )

    def test_tou_rate_custom_default_period(self):
        """Test that a non-standard default period name works."""
        del self.period_rates["shoulder"]
        self.period_rates["standard"] = 0.30

        res = self.calc.calculate_tou_rate(
            period_rates=self.period_rates,
            time_windows=self.time_windows,
            default_period="standard"
        )

        self.assertIn("standard", res["breakdown"])
        self.assertEqual(res["breakdown"]["standard"]["kwh"], 1.0)
