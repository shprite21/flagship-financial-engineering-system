"""Interactive Streamlit dashboard for the research lab."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from analytics.factor_analysis.ic import information_coefficient
from analytics.ic_decay.decay import ic_decay_curve
from backtesting.engine.backtester import run_backtest
from data.synthetic import DEFAULT_SECTORS, adjusted_close_wide, generate_fundamentals, generate_market_panel
from factors.base import forward_returns, long_short_weights
from factors.low_vol.signals import low_volatility_score
from factors.momentum.signals import twelve_minus_one_momentum, volatility_adjusted_momentum
from factors.multifactor import blend_factors, factor_correlation_matrix
from factors.quality.signals import quality_composite
from factors.stat_arb.pca import residual_zscores
from factors.value.signals import value_composite
from regime.engine import classify_regimes


@st.cache_data(show_spinner=False)
def load_demo() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    panel = generate_market_panel(periods=756)
    prices = adjusted_close_wide(panel)
    fundamentals = generate_fundamentals(panel)
    returns = prices.pct_change(fill_method=None).fillna(0.0)
    return prices, returns, fundamentals


def metric_row(metrics: dict[str, float]) -> None:
    cols = st.columns(5)
    for col, key in zip(cols, ["cagr", "sharpe", "max_drawdown", "hit_ratio", "turnover"], strict=False):
        col.metric(key.replace("_", " ").title(), f"{metrics.get(key, 0):.2%}" if key != "sharpe" else f"{metrics.get(key, 0):.2f}")


def main() -> None:
    st.set_page_config(page_title="Systematic Equities Research Lab", layout="wide")
    prices, returns, fundamentals = load_demo()
    momentum = twelve_minus_one_momentum(prices).scores
    value = value_composite(fundamentals).scores.reindex(prices.index).ffill()
    quality = quality_composite(fundamentals).scores.reindex(prices.index).ffill()
    low_vol = low_volatility_score(returns).scores
    composite = blend_factors({"momentum": momentum, "value": value, "quality": quality, "low_vol": low_vol})
    weights = long_short_weights(composite).reindex(returns.index).ffill().fillna(0.0)
    result = run_backtest(returns, weights)
    regimes = classify_regimes(returns.mean(axis=1), prices.mean(axis=1))

    st.title("Systematic Equities Research Lab")
    page = st.sidebar.radio(
        "Research Console",
        [
            "Overview",
            "Factor Explorer",
            "Portfolio Analytics",
            "Regime Dashboard",
            "Backtest Results",
            "Risk Analytics",
            "Statistical Arbitrage Monitor",
        ],
    )

    if page == "Overview":
        metric_row(result.metrics)
        st.line_chart(result.equity_curve, height=320)
        st.dataframe(composite.iloc[-1].sort_values(ascending=False).to_frame("Composite Alpha"))
    elif page == "Factor Explorer":
        selected = st.selectbox("Factor", ["momentum", "value", "quality", "low_vol"])
        factor_map = {"momentum": momentum, "value": value, "quality": quality, "low_vol": low_vol}
        factor = factor_map[selected]
        st.dataframe(factor.iloc[-1].sort_values(ascending=False).to_frame("Latest Score"))
        fwd = forward_returns(prices, horizon=21)
        st.line_chart(information_coefficient(factor, fwd).rolling(21).mean(), height=260)
        st.bar_chart(ic_decay_curve(factor, prices), height=260)
    elif page == "Portfolio Analytics":
        st.area_chart(weights, height=320)
        st.dataframe(weights.tail(10))
    elif page == "Regime Dashboard":
        st.dataframe(regimes.tail(20))
        st.line_chart(prices.mean(axis=1), height=260)
    elif page == "Backtest Results":
        metric_row(result.metrics)
        st.line_chart(pd.concat([result.gross_returns, result.returns, result.costs], axis=1), height=320)
        st.dataframe(pd.Series(result.metrics, name="Metric"))
    elif page == "Risk Analytics":
        factors = {"momentum": momentum, "value": value, "quality": quality, "low_vol": low_vol}
        st.dataframe(factor_correlation_matrix(factors).round(3))
        st.dataframe(pd.Series(DEFAULT_SECTORS, name="Sector").to_frame())
    elif page == "Statistical Arbitrage Monitor":
        z = residual_zscores(returns, n_components=3).tail(120)
        st.line_chart(z, height=320)
        st.dataframe(z.iloc[-1].sort_values().to_frame("Residual Z-Score"))


if __name__ == "__main__":
    main()

