"""Fundamental Law of Active Management diagnostics."""

from __future__ import annotations

import numpy as np
import pandas as pd


def effective_breadth(signal_returns: pd.DataFrame, autocorrelation_lag: int = 1) -> float:
    """Estimate independent bets after penalizing for average factor autocorrelation."""

    raw_breadth = signal_returns.count(axis=1).mean()
    autocorr = signal_returns.apply(lambda series: series.autocorr(autocorrelation_lag)).mean()
    penalty = max(1.0 + 2.0 * max(float(autocorr), 0.0), 1e-8)
    return float(raw_breadth / penalty)


def fundamental_law_ir(
    information_coefficient: float,
    breadth: float,
    transfer_coefficient: float = 1.0,
) -> float:
    return float(information_coefficient * np.sqrt(max(breadth, 0.0)) * transfer_coefficient)


def transfer_coefficient(raw_alpha: pd.Series, constrained_weights: pd.Series) -> float:
    aligned = pd.concat([raw_alpha, constrained_weights], axis=1).dropna()
    if len(aligned) < 3:
        return 0.0
    return float(aligned.iloc[:, 0].corr(aligned.iloc[:, 1], method="spearman"))

