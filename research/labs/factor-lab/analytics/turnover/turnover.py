"""Turnover diagnostics."""

from __future__ import annotations

import pandas as pd


def portfolio_turnover(weights: pd.DataFrame) -> pd.Series:
    return weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1)).rename("turnover")

