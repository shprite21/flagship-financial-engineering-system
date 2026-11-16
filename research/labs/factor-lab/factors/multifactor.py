"""Multi-factor alpha blending and factor exposure diagnostics."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from factors.base import zscore_cross_section


@dataclass(slots=True)
class FactorBlendConfig:
    weights: dict[str, float] = field(default_factory=dict)
    orthogonalize: bool = False
    winsorize: bool = True


def _align_factors(factors: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    if not factors:
        raise ValueError("At least one factor is required.")
    common_index = None
    common_columns = None
    for frame in factors.values():
        common_index = frame.index if common_index is None else common_index.intersection(frame.index)
        common_columns = frame.columns if common_columns is None else common_columns.intersection(frame.columns)
    return {name: frame.loc[common_index, common_columns].sort_index() for name, frame in factors.items()}


def _orthogonalize(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    names = list(frames)
    output: dict[str, pd.DataFrame] = {}
    for idx, name in enumerate(names):
        target = frames[name].stack(future_stack=True).rename("target")
        if idx == 0:
            output[name] = frames[name]
            continue
        regressors = [output[prior].stack(future_stack=True).rename(prior) for prior in names[:idx]]
        design = pd.concat(regressors, axis=1).reindex(target.index).fillna(0.0)
        aligned = pd.concat([target, design], axis=1).dropna()
        if aligned.empty:
            output[name] = frames[name]
            continue
        x = np.column_stack([np.ones(len(aligned)), aligned.iloc[:, 1:].to_numpy()])
        y = aligned.iloc[:, 0].to_numpy()
        beta = np.linalg.lstsq(x, y, rcond=None)[0]
        residual = pd.Series(y - x @ beta, index=aligned.index)
        output[name] = residual.unstack().reindex_like(frames[name])
    return output


def blend_factors(
    factors: dict[str, pd.DataFrame],
    weights: dict[str, float] | None = None,
    orthogonalize: bool = False,
) -> pd.DataFrame:
    """Blend z-scored cross-sectional factors into a composite alpha."""

    aligned = _align_factors(factors)
    standardized = {name: zscore_cross_section(frame) for name, frame in aligned.items()}
    if orthogonalize:
        standardized = _orthogonalize(standardized)
    if weights is None:
        weights = {name: 1.0 / len(standardized) for name in standardized}
    total_weight = sum(abs(weights.get(name, 0.0)) for name in standardized) or 1.0
    composite = sum(standardized[name] * weights.get(name, 0.0) for name in standardized) / total_weight
    return zscore_cross_section(composite)


def factor_correlation_matrix(factors: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Correlation matrix across stacked factor scores."""

    aligned = _align_factors(factors)
    stacked = {
        name: frame.stack(future_stack=True).rename(name)
        for name, frame in aligned.items()
    }
    return pd.concat(stacked.values(), axis=1).corr()


def dynamic_regime_weights(
    regimes: pd.Series,
    base_weights: dict[str, float],
    defensive_weights: dict[str, float],
    crash_regime_label: str = "crash",
) -> pd.DataFrame:
    """Return a daily factor-weight schedule conditioned on regime labels."""

    rows = []
    for date, regime in regimes.items():
        row = defensive_weights if regime == crash_regime_label else base_weights
        rows.append(pd.Series(row, name=date))
    return pd.DataFrame(rows).fillna(0.0)

