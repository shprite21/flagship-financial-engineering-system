"""Regime detection inspired by momentum crash and volatility state research."""

from __future__ import annotations

import numpy as np
import pandas as pd


def volatility_regimes(returns: pd.Series, window: int = 63) -> pd.Series:
    vol = returns.rolling(window).std() * np.sqrt(252)
    low, high = vol.quantile([0.33, 0.67])
    labels = pd.Series("normal_vol", index=returns.index)
    labels[vol <= low] = "low_vol"
    labels[vol >= high] = "high_vol"
    labels[vol.isna()] = "unknown"
    return labels.rename("volatility_regime")


def bull_bear_states(prices: pd.Series, moving_average_window: int = 200) -> pd.Series:
    moving_average = prices.rolling(moving_average_window).mean()
    state = pd.Series("bear", index=prices.index)
    state[prices >= moving_average] = "bull"
    state[moving_average.isna()] = "unknown"
    return state.rename("trend_state")


def drawdown_states(prices: pd.Series, crash_threshold: float = -0.2, correction_threshold: float = -0.1) -> pd.Series:
    wealth = prices.div(prices.iloc[0])
    drawdown = wealth.div(wealth.cummax()).sub(1.0)
    state = pd.Series("expansion", index=prices.index)
    state[drawdown <= correction_threshold] = "correction"
    state[drawdown <= crash_threshold] = "crash"
    return state.rename("drawdown_state")


def rolling_sharpe_states(returns: pd.Series, window: int = 126) -> pd.Series:
    sharpe = returns.rolling(window).mean().div(returns.rolling(window).std()).mul(np.sqrt(252))
    state = pd.Series("neutral", index=returns.index)
    state[sharpe > 1.0] = "positive"
    state[sharpe < -0.5] = "negative"
    state[sharpe.isna()] = "unknown"
    return state.rename("rolling_sharpe_state")


def hmm_regimes(features: pd.DataFrame, n_states: int = 3) -> pd.Series:
    """Fit a Gaussian HMM when hmmlearn exists; otherwise use volatility quantiles."""

    clean = features.dropna()
    labels = pd.Series("unknown", index=features.index)
    if clean.empty:
        return labels.rename("hmm_state")
    try:
        from hmmlearn.hmm import GaussianHMM
    except ImportError:
        vol_proxy = clean.std(axis=1)
        bins = pd.qcut(vol_proxy.rank(method="first"), q=min(n_states, len(clean)), labels=False)
        labels.loc[clean.index] = [f"state_{int(value)}" for value in bins]
        return labels.rename("hmm_state")
    model = GaussianHMM(n_components=n_states, covariance_type="full", n_iter=200, random_state=42)
    fitted = model.fit(clean.to_numpy())
    states = fitted.predict(clean.to_numpy())
    labels.loc[clean.index] = [f"state_{state}" for state in states]
    return labels.rename("hmm_state")


def classify_regimes(market_returns: pd.Series, market_prices: pd.Series | None = None) -> pd.DataFrame:
    prices = market_prices if market_prices is not None else (1 + market_returns.fillna(0.0)).cumprod()
    realized_vol = market_returns.rolling(63).std() * np.sqrt(252)
    drawdown = prices.div(prices.cummax()).sub(1.0)
    features = pd.DataFrame({"returns": market_returns, "realized_vol": realized_vol, "drawdown": drawdown})
    regimes = pd.concat(
        [
            volatility_regimes(market_returns),
            bull_bear_states(prices),
            drawdown_states(prices),
            rolling_sharpe_states(market_returns),
            hmm_regimes(features),
        ],
        axis=1,
    )
    regimes["composite_regime"] = "normal"
    regimes.loc[regimes["drawdown_state"].eq("crash") | regimes["volatility_regime"].eq("high_vol"), "composite_regime"] = (
        "crash"
    )
    regimes.loc[regimes["trend_state"].eq("bull") & regimes["volatility_regime"].eq("low_vol"), "composite_regime"] = (
        "risk_on"
    )
    return regimes

