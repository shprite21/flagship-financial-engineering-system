"""Risk and exposure diagnostics."""

from __future__ import annotations

import numpy as np
import pandas as pd


def rolling_sharpe(returns: pd.Series, window: int = 126) -> pd.Series:
    return returns.rolling(window).mean().div(returns.rolling(window).std()).mul(np.sqrt(252)).rename("rolling_sharpe")


def rolling_beta(returns: pd.Series, benchmark: pd.Series, window: int = 252) -> pd.Series:
    covariance = returns.rolling(window).cov(benchmark)
    variance = benchmark.rolling(window).var().replace(0, pd.NA)
    return covariance.div(variance).rename("rolling_beta")


def factor_exposure(asset_weights: pd.Series, factor_loadings: pd.DataFrame) -> pd.Series:
    aligned = factor_loadings.reindex(asset_weights.index).fillna(0.0)
    return aligned.mul(asset_weights, axis=0).sum(axis=0).rename("factor_exposure")

