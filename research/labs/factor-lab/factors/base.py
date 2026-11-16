"""Shared utilities for cross-sectional equity factor research."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd


@dataclass(slots=True)
class FactorResult:
    name: str
    scores: pd.DataFrame
    metadata: dict[str, Any] = field(default_factory=dict)

    def latest(self) -> pd.Series:
        return self.scores.dropna(how="all").iloc[-1].sort_values(ascending=False)


def winsorize_cross_section(frame: pd.DataFrame, limit: float = 3.0) -> pd.DataFrame:
    """Clip each cross-section to robust median/MAD bounds."""

    median = frame.median(axis=1)
    mad = (frame.sub(median, axis=0).abs()).median(axis=1).replace(0, np.nan)
    lower = median - limit * 1.4826 * mad
    upper = median + limit * 1.4826 * mad
    return frame.clip(lower=lower, upper=upper, axis=0)


def zscore_cross_section(frame: pd.DataFrame, winsorize: bool = True) -> pd.DataFrame:
    """Cross-sectional z-score by date."""

    clean = winsorize_cross_section(frame) if winsorize else frame.copy()
    mean = clean.mean(axis=1)
    std = clean.std(axis=1).replace(0, np.nan)
    return clean.sub(mean, axis=0).div(std, axis=0)


def rank_to_deciles(scores: pd.DataFrame, ascending: bool = False, buckets: int = 10) -> pd.DataFrame:
    """Convert factor scores into 1..N cross-sectional buckets by date."""

    def assign(row: pd.Series) -> pd.Series:
        valid = row.dropna()
        output = pd.Series(np.nan, index=row.index)
        if len(valid) < buckets:
            output.loc[valid.index] = valid.rank(ascending=ascending, method="first")
            return output
        output.loc[valid.index] = pd.qcut(
            valid.rank(ascending=ascending, method="first"),
            q=buckets,
            labels=False,
            duplicates="drop",
        ) + 1
        return output

    return scores.apply(assign, axis=1)


def long_short_weights(
    scores: pd.DataFrame,
    long_quantile: float = 0.8,
    short_quantile: float = 0.2,
    gross_exposure: float = 1.0,
) -> pd.DataFrame:
    """Construct dollar-neutral long-short weights from cross-sectional scores."""

    def weights_for_row(row: pd.Series) -> pd.Series:
        valid = row.dropna()
        weights = pd.Series(0.0, index=row.index)
        if len(valid) < 2:
            return weights
        long_cutoff = valid.quantile(long_quantile)
        short_cutoff = valid.quantile(short_quantile)
        longs = valid[valid >= long_cutoff].index
        shorts = valid[valid <= short_cutoff].index
        if len(longs) == 0 or len(shorts) == 0:
            return weights
        weights.loc[longs] = gross_exposure / 2 / len(longs)
        weights.loc[shorts] = -gross_exposure / 2 / len(shorts)
        return weights

    return scores.apply(weights_for_row, axis=1)


def sector_neutralize(scores: pd.DataFrame, sectors: pd.Series | dict[str, str]) -> pd.DataFrame:
    """Demean scores inside each sector for every date."""

    sector_series = pd.Series(sectors)
    aligned = sector_series.reindex(scores.columns).fillna("Unknown")
    neutral = scores.copy()
    for sector in aligned.unique():
        tickers = aligned[aligned == sector].index
        neutral.loc[:, tickers] = scores.loc[:, tickers].sub(scores.loc[:, tickers].mean(axis=1), axis=0)
    return neutral


def forward_returns(prices: pd.DataFrame, horizon: int = 21) -> pd.DataFrame:
    """Forward total returns used for IC and event analyses."""

    return prices.shift(-horizon).div(prices).sub(1.0)

