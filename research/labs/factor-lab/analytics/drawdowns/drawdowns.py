"""Drawdown calculations."""

from __future__ import annotations

import pandas as pd


def drawdown_series(returns: pd.Series) -> pd.Series:
    wealth = (1 + returns.fillna(0.0)).cumprod()
    return wealth.div(wealth.cummax()).sub(1.0).rename("drawdown")


def top_drawdowns(returns: pd.Series, n: int = 5) -> pd.DataFrame:
    drawdown = drawdown_series(returns)
    troughs = drawdown.nsmallest(n)
    rows = []
    wealth = (1 + returns.fillna(0.0)).cumprod()
    running_max = wealth.cummax()
    for trough_date, depth in troughs.items():
        start_candidates = running_max.loc[:trough_date]
        start = start_candidates[start_candidates == start_candidates.max()].index[-1]
        recovery_candidates = drawdown.loc[trough_date:]
        recovered = recovery_candidates[recovery_candidates >= 0]
        end = recovered.index[0] if not recovered.empty else pd.NaT
        rows.append({"start": start, "trough": trough_date, "recovery": end, "depth": depth})
    return pd.DataFrame(rows)

