"""Low volatility and beta-aware defensive equity signals."""

from __future__ import annotations

import pandas as pd

from factors.base import FactorResult, zscore_cross_section


def rolling_realized_volatility(returns: pd.DataFrame, window: int = 63, annualization: int = 252) -> pd.DataFrame:
    return returns.rolling(window).std() * annualization**0.5


def beta_to_market(returns: pd.DataFrame, market_returns: pd.Series, window: int = 252) -> pd.DataFrame:
    market = market_returns.reindex(returns.index)
    covariance = returns.rolling(window).cov(market)
    variance = market.rolling(window).var().replace(0, pd.NA)
    return covariance.div(variance, axis=0)


def low_volatility_score(returns: pd.DataFrame, window: int = 63) -> FactorResult:
    vol = rolling_realized_volatility(returns, window=window)
    return FactorResult(
        name="low_volatility",
        scores=zscore_cross_section(-vol),
        metadata={"window": window, "definition": "negative realized volatility"},
    )

