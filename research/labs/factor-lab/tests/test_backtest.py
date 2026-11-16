from backtesting.engine.backtester import run_backtest
from data.synthetic import adjusted_close_wide, generate_market_panel
from factors.base import long_short_weights
from factors.momentum.signals import twelve_minus_one_momentum


def test_backtest_shifts_weights_and_produces_metrics():
    panel = generate_market_panel(periods=320)
    prices = adjusted_close_wide(panel)
    returns = prices.pct_change(fill_method=None).fillna(0.0)
    scores = twelve_minus_one_momentum(prices).scores
    weights = long_short_weights(scores).reindex(returns.index).ffill().fillna(0.0)

    result = run_backtest(returns, weights)

    assert len(result.returns) == len(returns)
    assert result.equity_curve.iloc[-1] > 0
    assert {"cagr", "sharpe", "max_drawdown", "turnover"}.issubset(result.metrics)

