"""Earnings-event data helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd


def generate_earnings_events(
    tickers: list[str],
    dates: pd.DatetimeIndex,
    seed: int = 31,
    observations_per_ticker: int = 12,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    records = []
    candidate_dates = dates[:: max(len(dates) // max(observations_per_ticker, 1), 1)]
    for ticker in tickers:
        for event_date in candidate_dates[:observations_per_ticker]:
            estimate = rng.normal(1.5, 0.35)
            actual = estimate + rng.normal(0.03, 0.20)
            records.append(
                {
                    "ticker": ticker,
                    "event_date": pd.Timestamp(event_date),
                    "estimate_eps": estimate,
                    "actual_eps": actual,
                }
            )
    return pd.DataFrame.from_records(records).sort_values(["ticker", "event_date"])

