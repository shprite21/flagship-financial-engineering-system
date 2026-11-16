"""Cross-sectional expected-return regressions."""

from __future__ import annotations

import numpy as np
import pandas as pd


def fama_macbeth_regression(
    factor_scores: dict[str, pd.DataFrame],
    forward_returns: pd.DataFrame,
    min_assets: int = 5,
) -> pd.DataFrame:
    """Run date-by-date cross-sectional regressions and return risk premia."""

    common_index = forward_returns.index
    common_columns = forward_returns.columns
    for frame in factor_scores.values():
        common_index = common_index.intersection(frame.index)
        common_columns = common_columns.intersection(frame.columns)

    rows = []
    names = list(factor_scores)
    for date in common_index:
        x_frame = pd.concat(
            [factor_scores[name].loc[date, common_columns].rename(name) for name in names],
            axis=1,
        )
        y = forward_returns.loc[date, common_columns].rename("forward_return")
        data = pd.concat([x_frame, y], axis=1).dropna()
        if len(data) < max(min_assets, len(names) + 1):
            continue
        x = np.column_stack([np.ones(len(data)), data[names].to_numpy()])
        beta = np.linalg.lstsq(x, data["forward_return"].to_numpy(), rcond=None)[0]
        rows.append(pd.Series(beta[1:], index=names, name=date))
    return pd.DataFrame(rows)


def average_risk_premia(premia: pd.DataFrame) -> pd.DataFrame:
    mean = premia.mean()
    std_error = premia.std().div(len(premia) ** 0.5)
    t_stat = mean.div(std_error.replace(0, np.nan))
    return pd.DataFrame({"mean_premium": mean, "std_error": std_error, "t_stat": t_stat})

