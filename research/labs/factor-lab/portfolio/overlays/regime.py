"""Adaptive exposure overlays driven by market regimes."""

from __future__ import annotations

import pandas as pd


def apply_regime_exposure_scaling(
    weights: pd.DataFrame,
    regimes: pd.Series,
    gross_targets: dict[str, float] | None = None,
) -> pd.DataFrame:
    targets = gross_targets or {"risk_on": 1.2, "normal": 1.0, "crash": 0.35}
    aligned_regimes = regimes.reindex(weights.index).ffill().fillna("normal")
    scaled = weights.copy()
    for date, regime in aligned_regimes.items():
        gross = scaled.loc[date].abs().sum()
        if gross > 0:
            scaled.loc[date] = scaled.loc[date] * targets.get(str(regime), 1.0) / gross
    return scaled

