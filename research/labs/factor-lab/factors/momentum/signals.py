"""Momentum factor variants.

Canonical 12-1 momentum is measured from t-12 months through t-2 months:
MOM_i = product(1 + r_i) - 1.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from factors.base import FactorResult, sector_neutralize, zscore_cross_section


@dataclass(frozen=True, slots=True)
class MomentumConfig:
    lookback_days: int = 252
    skip_days: int = 21
    volatility_window: int = 63
    sector_neutral: bool = False


def simple_returns(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.pct_change(fill_method=None)


def cumulative_return(prices: pd.DataFrame, lookback_days: int, skip_days: int = 0) -> pd.DataFrame:
    start = prices.shift(lookback_days + skip_days)
    end = prices.shift(skip_days)
    return end.div(start).sub(1.0)


def twelve_minus_one_momentum(prices: pd.DataFrame) -> FactorResult:
    raw = cumulative_return(prices, lookback_days=252, skip_days=21)
    return FactorResult(
        name="momentum_12_1",
        scores=zscore_cross_section(raw),
        metadata={"paper": "Jegadeesh & Titman (1993)", "lookback_days": 252, "skip_days": 21},
    )


def six_month_momentum(prices: pd.DataFrame, skip_days: int = 21) -> FactorResult:
    raw = cumulative_return(prices, lookback_days=126, skip_days=skip_days)
    return FactorResult(
        name="momentum_6m",
        scores=zscore_cross_section(raw),
        metadata={"lookback_days": 126, "skip_days": skip_days},
    )


def volatility_adjusted_momentum(
    prices: pd.DataFrame,
    lookback_days: int = 252,
    skip_days: int = 21,
    volatility_window: int = 63,
) -> FactorResult:
    raw = cumulative_return(prices, lookback_days=lookback_days, skip_days=skip_days)
    realized_vol = simple_returns(prices).rolling(volatility_window).std()
    adjusted = raw.div(realized_vol.replace(0, pd.NA))
    return FactorResult(
        name="vol_adjusted_momentum",
        scores=zscore_cross_section(adjusted),
        metadata={"lookback_days": lookback_days, "skip_days": skip_days, "volatility_window": volatility_window},
    )


def sector_neutral_momentum(prices: pd.DataFrame, sectors: pd.Series | dict[str, str]) -> FactorResult:
    raw = cumulative_return(prices, lookback_days=252, skip_days=21)
    neutral = sector_neutralize(raw, sectors)
    return FactorResult(
        name="sector_neutral_momentum",
        scores=zscore_cross_section(neutral),
        metadata={"lookback_days": 252, "skip_days": 21, "neutralization": "sector_demean"},
    )


def generate_momentum_suite(
    prices: pd.DataFrame,
    sectors: pd.Series | dict[str, str] | None = None,
) -> dict[str, FactorResult]:
    suite = {
        "momentum_12_1": twelve_minus_one_momentum(prices),
        "momentum_6m": six_month_momentum(prices),
        "vol_adjusted_momentum": volatility_adjusted_momentum(prices),
    }
    if sectors is not None:
        suite["sector_neutral_momentum"] = sector_neutral_momentum(prices, sectors)
    return suite

