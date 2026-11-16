"""Sector, beta, turnover, and leverage constraint helpers."""

from __future__ import annotations

import pandas as pd


def constrain_turnover(
    target_weights: pd.Series,
    previous_weights: pd.Series,
    max_turnover: float,
) -> pd.Series:
    """Scale trades when the one-way turnover budget is exceeded."""

    previous = previous_weights.reindex(target_weights.index).fillna(0.0)
    trades = target_weights.fillna(0.0) - previous
    turnover = trades.abs().sum()
    if turnover <= max_turnover or turnover == 0:
        return target_weights.fillna(0.0)
    return previous + trades * (max_turnover / turnover)


def enforce_leverage_limit(weights: pd.Series, gross_limit: float = 1.0) -> pd.Series:
    gross = weights.abs().sum()
    return weights if gross <= gross_limit or gross == 0 else weights * gross_limit / gross


def sector_neutralize_weights(weights: pd.Series, sectors: pd.Series | dict[str, str]) -> pd.Series:
    """Demean active weights inside each sector and preserve original gross exposure."""

    sector_series = pd.Series(sectors).reindex(weights.index).fillna("Unknown")
    neutral = weights.copy().fillna(0.0)
    original_gross = neutral.abs().sum()
    for sector in sector_series.unique():
        tickers = sector_series[sector_series == sector].index
        neutral.loc[tickers] = neutral.loc[tickers] - neutral.loc[tickers].mean()
    new_gross = neutral.abs().sum()
    return neutral * original_gross / new_gross if new_gross else neutral


def beta_neutralize_weights(weights: pd.Series, betas: pd.Series) -> pd.Series:
    """Remove aggregate beta exposure by projecting weights off the beta vector."""

    aligned_betas = betas.reindex(weights.index).fillna(1.0)
    beta_exposure = float(weights.fillna(0.0).dot(aligned_betas))
    beta_norm = float(aligned_betas.dot(aligned_betas))
    if beta_norm == 0:
        return weights.fillna(0.0)
    adjusted = weights.fillna(0.0) - beta_exposure * aligned_betas / beta_norm
    gross = adjusted.abs().sum()
    original_gross = weights.abs().sum()
    return adjusted * original_gross / gross if gross else adjusted
