"""
Module: tariff_calculators.py
Author: Shromm Gaind

AI Assistance Declaration:
I declare that I am the primary author of this module. AI tools
(Codex / GPT-5.3 Sol) were used strictly as an assistive tool for:
- Renaming variables to fit project specific names.
- Generating exceptions and raising errors
- Generating structural comments and docstrings.
"""
from __future__ import annotations

from datetime import time
from functools import cached_property
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

MINUTES_PER_DAY = 1440


class EnergyBillCalculator:
    def __init__(self, consumption_data: Mapping[Any, float], *, sort: bool = True):
        if not consumption_data:
            raise ValueError("Consumption dictionary cannot be empty.")

        # Convert dict to 1D arrays
        kwh = np.fromiter(consumption_data.values(), np.float64, len(consumption_data))
        stamps = pd.DatetimeIndex(list(consumption_data.keys()))

        # Validate data integrity
        if not np.isfinite(kwh).all():
            raise ValueError("NaN or infinite consumption values detected.")
        if (kwh < 0.0).any():
            raise ValueError("Negative consumption values detected.")
        if stamps.hasnans:
            raise ValueError("Invalid timestamps in consumption dictionary.")

        # Ensure chronological order for safe cumulative tier/TOU logic
        if sort and not stamps.is_monotonic_increasing:
            order = np.argsort(stamps.asi8, kind="stable")
            stamps, kwh = stamps.take(order), kwh[order]

        self.timestamps, self.kwh_usage = stamps, kwh
        self.total_kwh = float(kwh.sum())

    @cached_property
    def minute_of_day(self) -> np.ndarray:
        """Minute of day (0..1439) for each reading. Assumes tz-naive timestamps."""
        # Use epoch integers (bypasses slow Pandas accessors)
        epoch_minutes = self.timestamps.values.astype("datetime64[m]").view(np.int64)
        return (epoch_minutes % MINUTES_PER_DAY).astype(np.int16)

    def _bill(self, model: str, energy_fee: float, fixed_fee: float, breakdown=None) -> dict:
        """Standardize output format across all billing models."""
        if fixed_fee < 0:
            raise ValueError("Fixed fee must be non-negative.")
        bill = {
            "model": model,
            "total_kwh": self.total_kwh,
            "fixed_fee": float(fixed_fee),
            "energy_fee": energy_fee,
            "total_bill": energy_fee + fixed_fee,
        }
        if breakdown is not None:
            bill["breakdown"] = breakdown
        return bill

    def calculate_flat_rate(self, rate_per_kwh: float, fixed_fee: float = 0.0) -> dict:
        if rate_per_kwh < 0:
            raise ValueError("Rate must be non-negative.")
        return self._bill("Flat Rate", self.total_kwh * rate_per_kwh, fixed_fee)

    def calculate_tiered_rate(
            self, tariff_tiers: Sequence[Mapping[str, float]], fixed_fee: float = 0.0
    ) -> dict:
        """tariff_tiers: [{'limit': 100, 'rate': 0.50}, ..., {'limit': inf, 'rate': 0.70}]"""
        if not tariff_tiers:
            raise ValueError("At least one tier is required.")

        rates = np.array([t["rate"] for t in tariff_tiers], np.float64)
        # Build tier boundaries, inserting 0.0 as the starting edge
        edges = np.array([0.0, *(t["limit"] for t in tariff_tiers)], np.float64)
        sizes = np.diff(edges)  # Max capacity of each tier block

        if (rates < 0).any():
            raise ValueError("Rates must be non-negative.")
        if not (sizes > 0).all():
            raise ValueError("Malformed tiers: limits must be strictly increasing.")
        if self.total_kwh > edges[-1]:
            raise ValueError(
                f"Tiers cover only {edges[-1]} kWh but usage is {self.total_kwh} kWh; "
                "the final tier limit should be float('inf')."
            )

        # Cap usage within each tier's limits (0 to tier max size)
        kwh = np.clip(self.total_kwh - edges[:-1], 0.0, sizes)
        cost = kwh * rates

        return self._bill(
            "Tiered Rate",
            float(cost.sum()),
            fixed_fee,
            {
                f"tier_{i}": {"kwh": float(k), "cost": float(c)}
                for i, (k, c) in enumerate(zip(kwh, cost), 1)
            },
        )

    def calculate_tou_rate(
            self,
            period_rates: Mapping[str, float],
            time_windows: Mapping[str, tuple[time, time]],
            fixed_fee: float = 0.0,
            default_period: str = "shoulder",
    ) -> dict:
        """Time-of-use billing. Intervals outside every window fall to default_period."""
        # Ensure default period maps to index 0
        names = [default_period, *(p for p in time_windows if p != default_period)]

        missing = [p for p in names if p not in period_rates]
        if missing:
            raise ValueError(f"No rate supplied for period(s): {', '.join(missing)}")
        rates = np.array([period_rates[p] for p in names], np.float64)

        if (rates < 0).any():
            raise ValueError("Rates must be non-negative.")

        # Map each reading to a period code, then group and sum usage via bincount
        codes = _build_period_lut(time_windows, names[1:])[self.minute_of_day]
        kwh = np.bincount(codes, weights=self.kwh_usage, minlength=len(names))
        cost = kwh * rates

        return self._bill(
            "Time of Use",
            float(cost.sum()),
            fixed_fee,
            {n: {"kwh": float(k), "cost": float(c)} for n, k, c in zip(names, kwh, cost)},
        )


def _build_period_lut(
        time_windows: Mapping[str, tuple[time, time]], period_names: Sequence[str]
) -> np.ndarray:
    """Minute-of-day -> period code (0 = default). Overlap is a tariff property,
    so it is checked over 1440 slots rather than over the meter readings."""
    lut = np.zeros(MINUTES_PER_DAY, np.int8)

    for code, name in enumerate(period_names, 1):
        start, end = (t.hour * 60 + t.minute for t in time_windows[name])
        if start == end:
            raise ValueError(f"Window '{name}' has zero length.")

        # Windows crossing midnight wrap to two runs of minutes. Slices are
        # views, so this neither allocates memory nor scans the table twice.
        runs = ((start, end),) if start < end else ((start, MINUTES_PER_DAY), (0, end))

        for lo, hi in runs:
            if lut[lo:hi].any():
                raise ValueError(f"Overlapping time windows detected involving '{name}'.")
            lut[lo:hi] = code

    return lut