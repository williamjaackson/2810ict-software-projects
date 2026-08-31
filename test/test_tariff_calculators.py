"""
Module: test_tariff_calculators.py
Author: Shromm Gaind

AI Assistance Declaration:
I declare that I am the primary author of this module. AI tools
(Codex / GPT-5.3 Sol) were used strictly as an assistive tool for:
-Generating the unit tests within this file
Everything within this file has been readthrough and I hold responsibility for the code.
"""
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, time

from src.tariff_calculators import EnergyBillCalculator


# ==========================================
# FIXTURES (Test Data)
# ==========================================

@pytest.fixture
def sample_consumption():
    """Provides a standard 5-reading usage profile totaling 8.0 kWh."""
    return {
        datetime(2025, 1, 1, 10, 0): 1.0,  # 10:00 - Shoulder
        datetime(2025, 1, 1, 18, 0): 2.5,  # 18:00 - Peak
        datetime(2025, 1, 1, 19, 0): 2.5,  # 19:00 - Peak
        datetime(2025, 1, 1, 23, 0): 1.0,  # 23:00 - Off-Peak
        datetime(2025, 1, 2, 1, 0): 1.0,  # 01:00 - Off-Peak (Next day)
    }


@pytest.fixture
def calc(sample_consumption):
    return EnergyBillCalculator(sample_consumption)


# ==========================================
# INITIALIZATION & VALIDATION TESTS
# ==========================================

def test_init_valid(calc):
    """Test standard initialization and cached total."""
    assert calc.total_kwh == 8.0
    assert len(calc.timestamps) == 5
    assert len(calc.kwh_usage) == 5


def test_init_empty_dict():
    """Test that empty data raises a ValueError."""
    with pytest.raises(ValueError, match="cannot be empty"):
        EnergyBillCalculator({})


def test_init_negative_consumption(sample_consumption):
    """Test that negative consumption raises an error."""
    sample_consumption[datetime(2025, 1, 1, 12, 0)] = -5.0
    with pytest.raises(ValueError, match="Negative consumption"):
        EnergyBillCalculator(sample_consumption)


def test_init_nan_consumption(sample_consumption):
    """Test that NaN values are blocked."""
    sample_consumption[datetime(2025, 1, 1, 12, 0)] = np.nan
    with pytest.raises(ValueError, match="NaN or infinite"):
        EnergyBillCalculator(sample_consumption)


def test_init_out_of_order_sorting():
    """Test that out-of-order timestamps are automatically sorted."""
    unsorted_data = {
        datetime(2025, 1, 2, 0, 0): 2.0,
        datetime(2025, 1, 1, 0, 0): 1.0,
    }
    c = EnergyBillCalculator(unsorted_data, sort=True)
    assert c.timestamps[0] == pd.Timestamp("2025-01-01 00:00:00")
    assert c.kwh_usage[0] == 1.0


def test_minute_of_day_calculation(calc):
    """Test that timestamps are correctly mapped to 0-1439 minutes."""
    mod = calc.minute_of_day
    assert mod[0] == 600   # 10:00 -> 10 * 60 = 600
    assert mod[1] == 1080  # 18:00 -> 18 * 60 = 1080


# ==========================================
# FLAT RATE TESTS
# ==========================================

def test_flat_rate_valid(calc):
    """Test accurate flat rate mathematics."""
    res = calc.calculate_flat_rate(rate_per_kwh=0.20, fixed_fee=10.0)

    assert res["model"] == "Flat Rate"
    assert res["total_kwh"] == 8.0
    assert res["fixed_fee"] == 10.0
    # 8.0 * 0.20 = 1.6
    assert res["energy_fee"] == pytest.approx(1.6)
    assert res["total_bill"] == pytest.approx(11.6)


def test_flat_rate_invalid_rates(calc):
    """Test negative rates raise errors."""
    with pytest.raises(ValueError, match="non-negative"):
        calc.calculate_flat_rate(rate_per_kwh=-0.1)


# ==========================================
# TIERED RATE TESTS
# ==========================================

def test_tiered_rate_valid(calc):
    """Test tiered math with clip/diff logic over edges."""
    tariff_tiers = [
        {"limit": 5.0, "rate": 0.10},  # First 5 kWh @ $0.10
        {"limit": float('inf'), "rate": 0.20}  # Remaining 3 kWh @ $0.20
    ]
    res = calc.calculate_tiered_rate(tariff_tiers=tariff_tiers, fixed_fee=5.0)

    # 5 * 0.10 + 3 * 0.20 = 0.5 + 0.6 = 1.10
    assert res["energy_fee"] == pytest.approx(1.10)
    assert res["total_bill"] == pytest.approx(6.10)

    assert res["breakdown"]["tier_1"]["kwh"] == 5.0
    assert res["breakdown"]["tier_1"]["cost"] == pytest.approx(0.50)
    assert res["breakdown"]["tier_2"]["kwh"] == 3.0
    assert res["breakdown"]["tier_2"]["cost"] == pytest.approx(0.60)


def test_tiered_rate_malformed_limits(calc):
    """Test that non-increasing limits raise errors."""
    tariff_tiers = [
        {"limit": 10.0, "rate": 0.10},
        {"limit": 5.0, "rate": 0.20}  # Limit dropped (invalid block size)
    ]
    with pytest.raises(ValueError, match="strictly increasing"):
        calc.calculate_tiered_rate(tariff_tiers=tariff_tiers)


def test_tiered_rate_exceeds_bounds(calc):
    """Test failure when final tier doesn't cover total usage."""
    tariff_tiers = [
        {"limit": 5.0, "rate": 0.10}  # Total usage is 8.0
    ]
    with pytest.raises(ValueError, match="usage is 8.0"):
        calc.calculate_tiered_rate(tariff_tiers=tariff_tiers)


def test_tiered_rate_negative_rates(calc):
    """Test negative rates in tiers are blocked."""
    tariff_tiers = [{"limit": float('inf'), "rate": -0.10}]
    with pytest.raises(ValueError, match="non-negative"):
        calc.calculate_tiered_rate(tariff_tiers=tariff_tiers)


# ==========================================
# TIME OF USE (TOU) TESTS
# ==========================================

@pytest.fixture
def tou_config():
    return {
        "period_rates": {"peak": 0.50, "shoulder": 0.30, "off-peak": 0.10},
        "time_windows": {
            "peak": (time(18, 0), time(22, 0)),
            "off-peak": (time(22, 0), time(7, 0))  # Midnight cross
        }
    }


def test_tou_rate_valid(calc, tou_config):
    """Test TOU mapping and bincount logic, including midnight crossing."""
    res = calc.calculate_tou_rate(
        period_rates=tou_config["period_rates"],
        time_windows=tou_config["time_windows"]
    )

    # Validation against the fixture data:
    # 10:00 (1.0) -> Shoulder
    # 18:00 (2.5) -> Peak
    # 19:00 (2.5) -> Peak
    # 23:00 (1.0) -> Off-Peak
    # 01:00 (1.0) -> Off-Peak

    breakdown = res["breakdown"]
    assert breakdown["peak"]["kwh"] == 5.0
    assert breakdown["peak"]["cost"] == pytest.approx(2.50)  # 5 * 0.50

    assert breakdown["off-peak"]["kwh"] == 2.0
    assert breakdown["off-peak"]["cost"] == pytest.approx(0.20)  # 2 * 0.10

    assert breakdown["shoulder"]["kwh"] == 1.0
    assert breakdown["shoulder"]["cost"] == pytest.approx(0.30)  # 1 * 0.30

    assert res["energy_fee"] == pytest.approx(3.00)


def test_tou_rate_overlap(calc, tou_config):
    """Test that the 1440-LUT catches overlapping windows."""
    tou_config["time_windows"]["peak"] = (time(18, 0), time(23, 0))
    tou_config["time_windows"]["off-peak"] = (time(22, 0), time(7, 0))  # Overlaps 22:00-23:00

    with pytest.raises(ValueError, match="Overlapping time windows"):
        calc.calculate_tou_rate(
            period_rates=tou_config["period_rates"],
            time_windows=tou_config["time_windows"]
        )


def test_tou_rate_missing_rate(calc, tou_config):
    """Test error when a window is defined but no rate is provided."""
    del tou_config["period_rates"]["peak"]
    with pytest.raises(ValueError, match="No rate supplied"):
        calc.calculate_tou_rate(
            period_rates=tou_config["period_rates"],
            time_windows=tou_config["time_windows"]
        )


def test_tou_rate_zero_length_window(calc, tou_config):
    """Test error when start and end times are identical."""
    tou_config["time_windows"]["peak"] = (time(18, 0), time(18, 0))
    with pytest.raises(ValueError, match="zero length"):
        calc.calculate_tou_rate(
            period_rates=tou_config["period_rates"],
            time_windows=tou_config["time_windows"]
        )


def test_tou_rate_custom_default_period(calc, tou_config):
    """Test that a non-standard default period name works."""
    del tou_config["period_rates"]["shoulder"]
    tou_config["period_rates"]["standard"] = 0.30

    res = calc.calculate_tou_rate(
        period_rates=tou_config["period_rates"],
        time_windows=tou_config["time_windows"],
        default_period="standard"
    )

    assert "standard" in res["breakdown"]
    assert res["breakdown"]["standard"]["kwh"] == 1.0
