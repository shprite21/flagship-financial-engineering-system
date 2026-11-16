"""Dynamic factor weighting engines."""

from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_information_ratio_weights(
    factor_returns: pd.DataFrame,
    window: int = 126,
    floor: float = 0.0,
) -> pd.DataFrame:
    """Allocate more weight to factors with stronger trailing information ratios."""

    mean = factor_returns.rolling(window).mean()
    vol = factor_returns.rolling(window).std().replace(0, np.nan)
    score = mean.div(vol).clip(lower=floor).fillna(0.0)
    total = score.sum(axis=1).replace(0, np.nan)
    return score.div(total, axis=0).fillna(1.0 / max(factor_returns.shape[1], 1))


def regime_weight_overlay(
    base_weights: pd.DataFrame,
    regimes: pd.Series,
    defensive_factor_names: list[str],
    defensive_boost: float = 1.5,
) -> pd.DataFrame:
    adjusted = base_weights.copy()
    crash_dates = regimes.reindex(adjusted.index).ffill().eq("crash")
    adjusted.loc[crash_dates, defensive_factor_names] *= defensive_boost
    return adjusted.div(adjusted.abs().sum(axis=1).replace(0, np.nan), axis=0).fillna(base_weights)

