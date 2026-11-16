"""Reusable portfolio constraint models."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class PortfolioConstraints:
    max_position_weight: float = 0.05
    gross_exposure: float = 1.0
    net_exposure: float | None = 0.0
    long_only: bool = False


def apply_basic_constraints(weights: pd.Series, constraints: PortfolioConstraints) -> pd.Series:
    constrained = weights.copy().fillna(0.0)
    if constraints.long_only:
        constrained = constrained.clip(lower=0.0)
    constrained = constrained.clip(
        lower=0.0 if constraints.long_only else -constraints.max_position_weight,
        upper=constraints.max_position_weight,
    )
    if constraints.net_exposure is not None and not constraints.long_only:
        constrained = constrained - constrained.mean()
    gross = constrained.abs().sum()
    if gross > 0:
        constrained = constrained * constraints.gross_exposure / gross
    return constrained

