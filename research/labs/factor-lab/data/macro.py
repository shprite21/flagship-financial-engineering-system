"""Macro and regime input helpers."""

from __future__ import annotations

import numpy as np
import pandas as pd


def generate_macro_regime_inputs(index: pd.DatetimeIndex, seed: int = 21) -> pd.DataFrame:
    """Create deterministic macro inputs for local research demos."""

    rng = np.random.default_rng(seed)
    rates = 0.03 + np.cumsum(rng.normal(0.0, 0.00015, len(index)))
    vix = np.clip(18 + np.cumsum(rng.normal(0.0, 0.25, len(index))), 8, 65)
    realized_vol = pd.Series(rng.normal(0.16, 0.035, len(index)), index=index).abs()
    return pd.DataFrame(
        {
            "vix": vix,
            "ten_year_rate": rates,
            "realized_volatility": realized_vol.to_numpy(),
        },
        index=index,
    )


def macro_surprise_zscore(macro: pd.DataFrame, window: int = 252) -> pd.DataFrame:
    mean = macro.rolling(window).mean()
    std = macro.rolling(window).std().replace(0, np.nan)
    return macro.sub(mean).div(std)

