import pandas as pd
import pytest

from backtesting import BacktestConfig, VectorizedBacktester
from research.sleeves import sleeve_diagnostics


@pytest.mark.parametrize("position", [0.0, 0.5, -0.5])
@pytest.mark.parametrize("frequency", [None, "W-FRI", "ME"])
def test_trade_ledger_reconciles_actual_turnover_and_costs(position, frequency):
    index = pd.bdate_range("2024-01-01", periods=45)
    prices = pd.DataFrame({"AAA": [100 * 1.002 ** i for i in range(45)],
                           "BBB": [100 * 0.999 ** i for i in range(45)]}, index=index)
    targets = pd.DataFrame({"AAA": position, "BBB": -position / 2}, index=index)
    targets.iloc[25:] = 0
    config = BacktestConfig(initial_capital=10000, rebalance_frequency=frequency,
                            execution_lag=1, drift_between_rebalances=True,
                            annual_borrow_bps=200, transaction_cost_bps=5, slippage_bps=3)
    backtest = VectorizedBacktester(config).run(prices, targets)
    evaluation = index[10:]
    detail = sleeve_diagnostics(prices, targets, backtest, evaluation, config)
    nav_before = backtest.equity_curve.shift(1).fillna(10000)
    rebased = nav_before * 10000 / nav_before.loc[evaluation[0]]
    for date in evaluation:
        trades = [t for t in detail["trades"] if t["date"] == date.strftime("%Y-%m-%d")]
        assert sum(abs(t["weight_change"]) for t in trades) == pytest.approx(backtest.turnover.loc[date], abs=1e-12)
        assert sum(abs(t["notional"]) for t in trades) == pytest.approx(backtest.turnover.loc[date] * rebased.loc[date], abs=1e-8)
        assert sum(t["trading_cost"] for t in trades) == pytest.approx(backtest.turnover.loc[date] * 8 / 10000 * rebased.loc[date], abs=1e-8)
    assert detail["ending_nav"] == pytest.approx(10000 * (1 + backtest.returns.loc[evaluation]).prod())
    if position == 0:
        assert detail["trades"] == []
        assert detail["cash_value"] == 10000
        assert detail["cost_contribution"] == 0


def test_first_loss_drawdown_and_lagged_trade():
    index = pd.bdate_range("2024-01-01", periods=4)
    prices = pd.DataFrame({"AAA": [100, 90, 99, 99]}, index=index)
    targets = pd.DataFrame({"AAA": [0.5, 0.5, 0, 1]}, index=index)
    config = BacktestConfig(initial_capital=1000, rebalance_frequency=None,
                            drift_between_rebalances=True, transaction_cost_bps=0, slippage_bps=0)
    backtest = VectorizedBacktester(config).run(prices, targets)
    detail = sleeve_diagnostics(prices, targets, backtest, index[1:], config)
    assert detail["trades"][0]["date"] == "2024-01-02"
    assert detail["trades"][0]["notional"] == 500
    assert detail["equity_curve"][1]["drawdown"] == pytest.approx(-0.05)
    assert detail["holdings"][0]["current_weight"] == 0
    assert detail["holdings"][0]["target_weight"] == 1
