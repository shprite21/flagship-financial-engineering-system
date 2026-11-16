"""Deterministic portfolio weighting schemes."""

from __future__ import annotations

import pandas as pd


def equal_weight(universe: list[str], gross_exposure: float = 1.0, long_only: bool = True) -> pd.Series:
    if not universe:
        raise ValueError("Universe cannot be empty.")
    if long_only:
        return pd.Series(gross_exposure / len(universe), index=universe)
    half = len(universe) // 2
    weights = pd.Series(0.0, index=universe)
    weights.iloc[:half] = gross_exposure / 2 / max(half, 1)
    weights.iloc[half:] = -gross_exposure / 2 / max(len(universe) - half, 1)
    return weights


def inverse_volatility_weights(volatility: pd.Series, gross_exposure: float = 1.0) -> pd.Series:
    inv = 1.0 / volatility.replace(0, pd.NA)
    weights = inv.div(inv.sum())
    return weights.fillna(0.0) * gross_exposure


def signal_weight(scores: pd.Series, gross_exposure: float = 1.0, dollar_neutral: bool = True) -> pd.Series:
    score = scores.dropna()
    if score.empty:
        return pd.Series(0.0, index=scores.index)
    if dollar_neutral:
        score = score - score.mean()
    denom = score.abs().sum()
    if denom == 0:
        return pd.Series(0.0, index=scores.index)
    return score.div(denom).mul(gross_exposure).reindex(scores.index).fillna(0.0)

