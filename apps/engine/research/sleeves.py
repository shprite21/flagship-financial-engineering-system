"""Standalone sleeve diagnostics from fractional-weight replay, not share fills."""
from __future__ import annotations

import pandas as pd

from backtesting import BacktestConfig
from backtesting.engine import BacktestResult


def sleeve_diagnostics(prices: pd.DataFrame, targets: pd.DataFrame,
                       result: BacktestResult, evaluation: pd.Index,
                       config: BacktestConfig) -> dict:
    asset_returns = prices.pct_change(fill_method=None).fillna(0)
    held = result.weights
    # Drift is not a trade: compare with the previous close's holdings,
    # including the effect of costs on NAV.
    ending = held.mul(1 + asset_returns).div(1 + result.returns, axis=0)
    before = ending.shift(1).fillna(0)
    changes = held - before
    nav_before = result.equity_curve.shift(1).fillna(config.initial_capital)
    baseline = float(nav_before.loc[evaluation[0]])
    nav_before = nav_before * config.initial_capital / baseline
    net = result.returns.loc[evaluation]
    curve = pd.DataFrame({"net": (1 + net).cumprod() * config.initial_capital,
                          "gross": (1 + result.gross_returns.loc[evaluation]).cumprod() * config.initial_capital})
    start = prices.index[prices.index.get_loc(evaluation[0]) - 1]
    curve.loc[start] = config.initial_capital
    curve = curve.sort_index()
    curve["drawdown"] = curve.net / curve.net.cummax() - 1
    curve["date"] = curve.index.strftime("%Y-%m-%d")
    contributions = result.attribution.loc[evaluation].mul(nav_before.loc[evaluation], axis=0).sum() / config.initial_capital
    costs = float(((result.costs + result.slippage).loc[evaluation] * nav_before.loc[evaluation]).sum())
    final_nav = float(curve.net.iloc[-1])
    final_weights = ending.iloc[-1]
    holdings = [{"symbol": symbol, "current_weight": float(final_weights[symbol]),
                 "target_weight": float(targets.iloc[-1][symbol]),
                 "ending_value": float(final_weights[symbol] * final_nav),
                 "return_contribution": float(contributions[symbol]),
                 "average_gross_weight": float(held.loc[evaluation, symbol].abs().mean())}
                for symbol in prices.columns]
    trades = []
    for date in evaluation:
        turnover = float(result.turnover.loc[date])
        borrow = float(held.loc[date].clip(upper=0).abs().sum()) * config.annual_borrow_bps / 10000 / 252
        trading_drag = float(result.costs.loc[date] + result.slippage.loc[date]) - borrow
        for symbol in prices.columns:
            delta = float(changes.loc[date, symbol])
            if abs(delta) <= 1e-12:
                continue
            trades.append({"date": date.strftime("%Y-%m-%d"), "symbol": symbol,
                           "side": "Buy" if delta > 0 else "Sell",
                           "before_weight": float(before.loc[date, symbol]),
                           "after_weight": float(held.loc[date, symbol]),
                           "weight_change": delta, "notional": delta * float(nav_before.loc[date]),
                           "trading_cost": trading_drag * abs(delta) / turnover * float(nav_before.loc[date]) if turnover else 0.0})
    # Nested weights prevent ticker names colliding with date/cash fields.
    history = [{"date": date.strftime("%Y-%m-%d"),
                "weights": {s: float(held.loc[date, s]) for s in prices.columns},
                "cash": float(1 - held.loc[date].sum())} for date in evaluation]
    return {"basis": "Standalone fractional-weight simulation before blending and portfolio constraints; not allocated portfolio attribution or share fills.",
            "equity_curve": curve.to_dict(orient="records"), "holdings": holdings,
            "allocation_history": history, "trades": trades,
            "ending_nav": final_nav, "cash_weight": float(1 - final_weights.sum()),
            "cash_value": float((1 - final_weights.sum()) * final_nav),
            "cost_contribution": -costs / config.initial_capital,
            "annual_turnover": float(result.turnover.loc[evaluation].mean() * 252)}
