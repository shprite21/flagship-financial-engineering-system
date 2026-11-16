"""Pairs trading and residual mean reversion utilities."""

from __future__ import annotations

import numpy as np
import pandas as pd


def estimate_hedge_ratio(y: pd.Series, x: pd.Series) -> float:
    aligned = pd.concat([y, x], axis=1).dropna()
    if len(aligned) < 3:
        raise ValueError("Need at least three aligned observations to estimate hedge ratio.")
    design = np.column_stack([np.ones(len(aligned)), aligned.iloc[:, 1].to_numpy()])
    _, beta = np.linalg.lstsq(design, aligned.iloc[:, 0].to_numpy(), rcond=None)[0]
    return float(beta)


def pair_spread(y: pd.Series, x: pd.Series, hedge_ratio: float | None = None) -> pd.Series:
    beta = estimate_hedge_ratio(y, x) if hedge_ratio is None else hedge_ratio
    return y.sub(beta * x, fill_value=np.nan).rename("spread")


def spread_zscore(spread: pd.Series, window: int = 60) -> pd.Series:
    mean = spread.rolling(window).mean()
    std = spread.rolling(window).std().replace(0, np.nan)
    return spread.sub(mean).div(std).rename("zscore")


def cointegration_diagnostics(y: pd.Series, x: pd.Series) -> dict[str, float | str]:
    """Run Engle-Granger diagnostics when statsmodels is installed."""

    aligned = pd.concat([y, x], axis=1).dropna()
    if len(aligned) < 30:
        return {"status": "insufficient_observations", "observations": float(len(aligned))}
    try:
        from statsmodels.tsa.stattools import coint
    except ImportError:
        correlation = aligned.iloc[:, 0].corr(aligned.iloc[:, 1])
        return {"status": "statsmodels_missing", "correlation": float(correlation)}
    statistic, pvalue, _ = coint(aligned.iloc[:, 0], aligned.iloc[:, 1])
    return {"status": "ok", "coint_t": float(statistic), "pvalue": float(pvalue)}


def pairs_trading_signals(
    prices: pd.DataFrame,
    left: str,
    right: str,
    entry_z: float = 2.0,
    exit_z: float = 0.5,
    window: int = 60,
) -> pd.DataFrame:
    spread = pair_spread(np.log(prices[left]), np.log(prices[right]))
    z = spread_zscore(spread, window=window)
    signal = pd.Series(0.0, index=z.index)
    signal[z > entry_z] = -1.0
    signal[z < -entry_z] = 1.0
    signal[z.abs() < exit_z] = 0.0
    return pd.DataFrame({"spread": spread, "zscore": z, "signal": signal})

