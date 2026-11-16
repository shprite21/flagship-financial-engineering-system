"""Information coefficient, rank IC, and decile spread analysis."""

from __future__ import annotations

import pandas as pd

from factors.base import rank_to_deciles


def information_coefficient(
    scores: pd.DataFrame,
    forward_returns: pd.DataFrame,
    method: str = "spearman",
) -> pd.Series:
    common_index = scores.index.intersection(forward_returns.index)
    common_columns = scores.columns.intersection(forward_returns.columns)
    factor = scores.loc[common_index, common_columns]
    fwd = forward_returns.loc[common_index, common_columns]
    values = []
    for date in common_index:
        aligned = pd.concat([factor.loc[date], fwd.loc[date]], axis=1).dropna()
        if len(aligned) < 3:
            values.append(float("nan"))
        else:
            values.append(aligned.iloc[:, 0].corr(aligned.iloc[:, 1], method=method))
    return pd.Series(values, index=common_index, name=f"{method}_ic")


def decile_forward_returns(
    scores: pd.DataFrame,
    forward_returns: pd.DataFrame,
    buckets: int = 10,
) -> pd.DataFrame:
    deciles = rank_to_deciles(scores, buckets=buckets)
    common_index = deciles.index.intersection(forward_returns.index)
    output = []
    for date in common_index:
        groups = deciles.loc[date]
        returns = forward_returns.loc[date]
        grouped = returns.groupby(groups).mean()
        grouped.name = date
        output.append(grouped)
    return pd.DataFrame(output).sort_index()

