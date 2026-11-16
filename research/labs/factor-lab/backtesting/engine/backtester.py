"""Vectorized no-lookahead portfolio backtesting engine."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from backtesting.performance.metrics import performance_summary
from backtesting.slippage.models import VolumeShareSlippage
from backtesting.transaction_costs.costs import TransactionCostModel


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    periods_per_year: int = 252
    transaction_cost_bps: float = 5.0
    slippage_bps: float = 2.0
    shift_weights: bool = True


@dataclass(slots=True)
class BacktestResult:
    returns: pd.Series
    gross_returns: pd.Series
    weights: pd.DataFrame
    turnover: pd.Series
    costs: pd.Series
    equity_curve: pd.Series
    metrics: dict[str, float]


def _turnover(weights: pd.DataFrame) -> pd.Series:
    return weights.diff().abs().sum(axis=1).fillna(weights.abs().sum(axis=1))


def run_backtest(
    returns: pd.DataFrame,
    target_weights: pd.DataFrame,
    benchmark_returns: pd.Series | None = None,
    config: BacktestConfig | None = None,
) -> BacktestResult:
    """Run a vectorized portfolio backtest with execution lag and costs."""

    config = config or BacktestConfig()
    common_index = returns.index.intersection(target_weights.index)
    common_columns = returns.columns.intersection(target_weights.columns)
    asset_returns = returns.loc[common_index, common_columns].fillna(0.0)
    weights = target_weights.loc[common_index, common_columns].fillna(0.0)
    executed_weights = weights.shift(1).fillna(0.0) if config.shift_weights else weights
    gross_returns = executed_weights.mul(asset_returns).sum(axis=1).rename("gross_return")
    turnover = _turnover(weights).rename("turnover")
    tc = TransactionCostModel(bps=config.transaction_cost_bps).from_turnover(turnover)
    slippage = VolumeShareSlippage(bps=config.slippage_bps).estimate(turnover)
    costs = (tc + slippage).rename("costs")
    net_returns = gross_returns.sub(costs, fill_value=0.0).rename("net_return")
    equity_curve = (1 + net_returns).cumprod().rename("equity_curve")
    metrics = performance_summary(net_returns, benchmark_returns, config.periods_per_year)
    metrics["turnover"] = float(turnover.mean() * config.periods_per_year)
    return BacktestResult(
        returns=net_returns,
        gross_returns=gross_returns,
        weights=executed_weights,
        turnover=turnover,
        costs=costs,
        equity_curve=equity_curve,
        metrics=metrics,
    )

