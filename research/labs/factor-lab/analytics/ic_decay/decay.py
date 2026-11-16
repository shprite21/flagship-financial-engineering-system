"""Factor IC decay curves."""

from __future__ import annotations

import pandas as pd

from analytics.factor_analysis.ic import information_coefficient
from factors.base import forward_returns


def ic_decay_curve(scores: pd.DataFrame, prices: pd.DataFrame, horizons: list[int] | None = None) -> pd.Series:
    horizons = horizons or [1, 5, 10, 21, 63]
    values = {}
    for horizon in horizons:
        fwd = forward_returns(prices, horizon=horizon)
        values[horizon] = information_coefficient(scores, fwd).mean()
    return pd.Series(values, name="mean_rank_ic")

