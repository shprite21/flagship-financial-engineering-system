"""FastAPI endpoints for factors, backtests, portfolios, signals, and regimes."""

from __future__ import annotations

import pandas as pd
from fastapi import FastAPI

from app.models import BacktestResponse, FactorResponse, RegimeResponse
from backtesting.engine.backtester import run_backtest
from data.synthetic import adjusted_close_wide, generate_fundamentals, generate_market_panel
from factors.base import long_short_weights
from factors.momentum.signals import twelve_minus_one_momentum
from factors.multifactor import blend_factors
from factors.quality.signals import quality_composite
from factors.value.signals import value_composite
from portfolio.weighting.schemes import signal_weight
from regime.engine import classify_regimes

app = FastAPI(
    title="Systematic Equities Research Lab",
    description="Institutional-style systematic equities research API.",
    version="0.1.0",
)


def _demo_context() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    panel = generate_market_panel(periods=756)
    prices = adjusted_close_wide(panel)
    fundamentals = generate_fundamentals(panel)
    returns = prices.pct_change(fill_method=None).fillna(0.0)
    return prices, returns, fundamentals


@app.get("/factors/momentum", response_model=FactorResponse)
def get_momentum_factor() -> FactorResponse:
    prices, _, _ = _demo_context()
    result = twelve_minus_one_momentum(prices)
    return FactorResponse(name=result.name, latest_scores=result.latest().round(4).to_dict())


@app.get("/portfolio/weights")
def get_portfolio_weights() -> dict[str, float]:
    prices, _, fundamentals = _demo_context()
    momentum = twelve_minus_one_momentum(prices).scores
    value = value_composite(fundamentals).scores.reindex(prices.index).ffill()
    quality = quality_composite(fundamentals).scores.reindex(prices.index).ffill()
    alpha = blend_factors({"momentum": momentum, "value": value, "quality": quality})
    return signal_weight(alpha.iloc[-1], gross_exposure=1.0, dollar_neutral=True).round(4).to_dict()


@app.get("/backtest/results", response_model=BacktestResponse)
def get_backtest_results() -> BacktestResponse:
    prices, returns, _ = _demo_context()
    scores = twelve_minus_one_momentum(prices).scores
    weights = long_short_weights(scores).reindex(returns.index).ffill().fillna(0.0)
    result = run_backtest(returns, weights)
    return BacktestResponse(metrics=result.metrics, latest_equity=float(result.equity_curve.iloc[-1]))


@app.get("/regime/current", response_model=RegimeResponse)
def get_current_regime() -> RegimeResponse:
    prices, returns, _ = _demo_context()
    market_returns = returns.mean(axis=1)
    regimes = classify_regimes(market_returns, prices.mean(axis=1))
    latest = regimes.iloc[-1]
    return RegimeResponse(
        date=str(regimes.index[-1].date()),
        composite_regime=str(latest["composite_regime"]),
        details={column: str(latest[column]) for column in regimes.columns},
    )


@app.get("/signals/latest")
def get_latest_signals() -> dict[str, dict[str, float]]:
    prices, _, fundamentals = _demo_context()
    return {
        "momentum": twelve_minus_one_momentum(prices).latest().round(4).to_dict(),
        "value": value_composite(fundamentals).latest().round(4).to_dict(),
        "quality": quality_composite(fundamentals).latest().round(4).to_dict(),
    }
