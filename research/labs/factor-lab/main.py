"""Command-line research runner for the Systematic Equities Research Lab."""

from __future__ import annotations

import argparse
import json
import logging

from backtesting.engine.backtester import run_backtest
from data.synthetic import DEFAULT_SECTORS, adjusted_close_wide, generate_fundamentals, generate_market_panel
from factors.base import long_short_weights
from factors.low_vol.signals import low_volatility_score
from factors.momentum.signals import sector_neutral_momentum, twelve_minus_one_momentum
from factors.multifactor import blend_factors, factor_correlation_matrix
from factors.quality.signals import quality_composite
from factors.value.signals import value_composite
from regime.engine import classify_regimes


def run_demo(periods: int = 756) -> dict[str, object]:
    panel = generate_market_panel(periods=periods)
    prices = adjusted_close_wide(panel)
    returns = prices.pct_change(fill_method=None).fillna(0.0)
    fundamentals = generate_fundamentals(panel)
    sectors = {ticker: DEFAULT_SECTORS.get(ticker, "Other") for ticker in prices.columns}

    momentum = twelve_minus_one_momentum(prices).scores
    sector_momentum = sector_neutral_momentum(prices, sectors).scores
    value = value_composite(fundamentals, sectors=sectors).scores.reindex(prices.index).ffill()
    quality = quality_composite(fundamentals).scores.reindex(prices.index).ffill()
    low_vol = low_volatility_score(returns).scores
    composite = blend_factors(
        {
            "momentum": momentum,
            "sector_momentum": sector_momentum,
            "value": value,
            "quality": quality,
            "low_vol": low_vol,
        },
        weights={"momentum": 0.25, "sector_momentum": 0.15, "value": 0.2, "quality": 0.25, "low_vol": 0.15},
    )

    weights = long_short_weights(composite).reindex(returns.index).ffill().fillna(0.0)
    backtest = run_backtest(returns, weights, benchmark_returns=returns.mean(axis=1))
    regimes = classify_regimes(returns.mean(axis=1), prices.mean(axis=1))
    corr = factor_correlation_matrix(
        {"momentum": momentum, "value": value, "quality": quality, "low_vol": low_vol}
    ).round(3)

    return {
        "metrics": backtest.metrics,
        "latest_regime": regimes.iloc[-1].to_dict(),
        "latest_alpha": composite.iloc[-1].sort_values(ascending=False).round(4).to_dict(),
        "factor_correlations": corr.to_dict(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a reproducible demo research pipeline.")
    parser.add_argument("--periods", type=int, default=756, help="Business days of synthetic history.")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    result = run_demo(periods=args.periods)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()

