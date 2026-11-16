"""Fama-French style proxy portfolio construction."""

from __future__ import annotations

import pandas as pd

from factors.value.signals import book_to_market


def _top_bottom_spread(scores: pd.DataFrame, returns: pd.DataFrame, top: float = 0.7, bottom: float = 0.3) -> pd.Series:
    common_index = scores.index.intersection(returns.index)
    spreads = []
    for date in common_index:
        row = scores.loc[date].dropna()
        if len(row) < 4:
            spreads.append(float("nan"))
            continue
        high = row[row >= row.quantile(top)].index
        low = row[row <= row.quantile(bottom)].index
        spreads.append(returns.loc[date, high].mean() - returns.loc[date, low].mean())
    return pd.Series(spreads, index=common_index)


def construct_ff3_proxies(fundamentals: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
    """Build SMB and HML proxy returns from available fundamentals."""

    market_cap = fundamentals["market_cap"].unstack("ticker").sort_index().reindex(returns.index).ffill()
    value = book_to_market(fundamentals).reindex(returns.index).ffill()
    smb = _top_bottom_spread(-market_cap, returns).rename("SMB")
    hml = _top_bottom_spread(value, returns).rename("HML")
    market = returns.mean(axis=1).rename("MKT")
    return pd.concat([market, smb, hml], axis=1)


def construct_ff5_proxies(fundamentals: pd.DataFrame, returns: pd.DataFrame) -> pd.DataFrame:
    """Build MKT, SMB, HML, RMW, and CMA proxy returns.

    Investment data is proxied by negative asset growth when point-in-time assets
    are available, so higher scores represent conservative investment.
    """

    ff3 = construct_ff3_proxies(fundamentals, returns)
    profitability = (
        fundamentals["earnings"].div(fundamentals["book_value"].replace(0, pd.NA)).unstack("ticker").sort_index()
    )
    assets = fundamentals["assets"].unstack("ticker").sort_index()
    conservative_investment = -assets.pct_change(fill_method=None)
    rmw = _top_bottom_spread(profitability.reindex(returns.index).ffill(), returns).rename("RMW")
    cma = _top_bottom_spread(conservative_investment.reindex(returns.index).ffill(), returns).rename("CMA")
    return pd.concat([ff3, rmw, cma], axis=1)

