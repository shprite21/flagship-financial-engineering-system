"""Alternative-data ingestion abstractions."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class AlternativeDataSet:
    name: str
    vendor: str
    frequency: str
    point_in_time: bool = True


def align_alternative_signal(signal: pd.DataFrame, prices_index: pd.DatetimeIndex, lag_days: int = 1) -> pd.DataFrame:
    """Lag and align alternative signals to trading dates to reduce lookahead bias."""

    shifted = signal.sort_index().shift(lag_days)
    return shifted.reindex(prices_index).ffill()

