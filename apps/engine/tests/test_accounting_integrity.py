"""Independent numerical regressions for the V2 research-integrity audit."""

from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from analytics.metrics import aggregate_metrics, calmar_ratio, sharpe_ratio, sortino_ratio
from analytics.tearsheet import PerformanceReport
from backtesting.engine import BacktestConfig, VectorizedBacktester
from data.models import MarketDataBundle, align_frames
from portfolio.allocation import (
    AllocationConfig, ConstrainedOptimizer, InverseVolatilityAllocator,
    RegimeConditionedAllocator, RiskParityAllocator, RollingSharpeAllocator,
)
from regime_detection.hmm import HMMRegimeDetector


def test_sortino_uses_all_observations_in_lower_partial_moment():
    returns = pd.Series([-0.02, 0.01, 0.03, 0.04])
    expected = 0.015 / np.sqrt(0.02**2 / 4) * np.sqrt(252)
    assert sortino_ratio(returns) == pytest.approx(expected)
    assert np.isnan(sortino_ratio(pd.Series([0.01, 0.02])))
    assert np.isnan(sharpe_ratio(pd.Series([0.0, 0.0])))
    assert np.isnan(calmar_ratio(pd.Series([0.01, 0.02])))


def test_first_loss_is_counted_against_initial_nav():
    returns = pd.Series([-0.1, 0.2])
    metrics = aggregate_metrics(returns, pd.Series([90.0, 108.0]))
    assert metrics["total_return"] == pytest.approx(0.08)
    assert metrics["max_drawdown"] == pytest.approx(-0.1)
    assert aggregate_metrics(returns, pd.Series([100.0, 90.0, 108.0]))["max_drawdown"] == pytest.approx(-0.1)


def test_drifting_holdings_reconcile_to_shares_and_report_executed_turnover():
    dates = pd.bdate_range("2024-01-04", periods=7)
    prices = pd.DataFrame({"A": [100, 100, 110, 121, 133.1, 146.41, 161.051]}, index=dates)
    result = VectorizedBacktester(BacktestConfig(
        initial_capital=1000, rebalance_frequency="W-FRI", drift_between_rebalances=True,
        transaction_cost_bps=0, slippage_bps=0,
    )).run(prices, prices * 0 + 0.5)
    # Friday decision buys five modeled shares at Friday's close for Monday's
    # close-to-close interval. The remaining 500 cash stays constant.
    np.testing.assert_allclose(result.equity_curve.iloc[2:], 500 + 5 * prices["A"].iloc[2:])
    np.testing.assert_allclose(result.turnover, [0, 0, 0.5, 0, 0, 0, 0])
    report = PerformanceReport.from_backtest(result)
    pd.testing.assert_series_equal(report.turnover, result.turnover)
    assert result.weights.iloc[3, 0] > result.weights.iloc[2, 0]
    assert report.turnover.iloc[3] == 0


@pytest.mark.parametrize("target", [(0.4, 0.3), (0.4, -0.3)])
@pytest.mark.parametrize("frequency", [None, "W-FRI"])
def test_constant_weight_costs_reconcile_to_independent_cash_and_shares(target, frequency):
    dates = pd.bdate_range("2024-01-04", periods=8)
    prices = pd.DataFrame({
        "A": [100, 110, 99, 103, 111, 101, 91, 102],
        "B": [80, 81, 84, 78, 75, 80, 83, 85],
    }, index=dates)
    targets = pd.DataFrame([target] * len(dates), index=dates, columns=prices.columns)
    result = VectorizedBacktester(BacktestConfig(
        initial_capital=1000, rebalance_frequency=frequency,
        transaction_cost_bps=20, slippage_bps=10, annual_borrow_bps=252,
    )).run(prices, targets)
    # Independent dollar ledger. The return proxy trades at the previous close,
    # restores target fractions of PRE-COST NAV every day, then marks today's
    # close. Constant weights require trades even between weekly target updates.
    cash, shares = 1000.0, np.zeros(2)
    navs, turnovers, costs, slippages = [cash], [0.0], [0.0], [0.0]
    for i in range(1, len(prices)):
        prior_prices = prices.iloc[i - 1].to_numpy()
        nav_before = cash + shares @ prior_prices
        active = frequency is None or i >= 2  # Friday's first decision is lagged.
        desired_shares = (np.array(target) if active else np.zeros(2)) * nav_before / prior_prices
        trade = desired_shares - shares
        notional = np.abs(trade) @ prior_prices
        commission, slip = notional * 0.002, notional * 0.001
        borrow = np.abs(desired_shares.clip(max=0)) @ prior_prices * 0.0252 / 252
        cash -= trade @ prior_prices + commission + slip + borrow
        shares = desired_shares
        navs.append(cash + shares @ prices.iloc[i].to_numpy())
        turnovers.append(notional / nav_before)
        costs.append((commission + borrow) / nav_before)
        slippages.append(slip / nav_before)
    np.testing.assert_allclose(result.equity_curve, navs, rtol=1e-12)
    np.testing.assert_allclose(result.turnover, turnovers, atol=1e-14)
    np.testing.assert_allclose(result.costs, costs, atol=1e-14)
    np.testing.assert_allclose(result.slippage, slippages, atol=1e-14)
    assert result.turnover.iloc[3] > 0


def test_constant_fully_invested_single_asset_without_costs_needs_no_restoration():
    prices = pd.DataFrame({"A": [100, 110, 99, 105]}, index=pd.bdate_range("2024-01-01", periods=4))
    result = VectorizedBacktester(BacktestConfig(
        rebalance_frequency=None, transaction_cost_bps=0, slippage_bps=0,
    )).run(prices, prices * 0 + 1)
    np.testing.assert_allclose(result.turnover, [0, 1, 0, 0], atol=1e-14)
    np.testing.assert_allclose(result.equity_curve, prices["A"] / 100 * 1_000_000)


@pytest.mark.parametrize("drift", [False, True])
def test_backtest_lag_cost_and_future_perturbation(drift):
    dates = pd.bdate_range("2024-01-01", periods=8)
    prices = pd.DataFrame({"A": [100, 110, 99, 99, 105, 110, 115, 120]}, index=dates)
    targets = pd.DataFrame({"A": [0.5, 0, 0.5, 0.5, 0, 0.5, 0, 0]}, index=dates)
    engine = VectorizedBacktester(BacktestConfig(
        rebalance_frequency=None, transaction_cost_bps=10, slippage_bps=0,
        drift_between_rebalances=drift,
    ))
    result = engine.run(prices, targets)
    assert result.returns.iloc[0] == 0
    assert result.returns.iloc[1] == pytest.approx(0.5 * 0.1 - 0.5 * 0.001)
    altered_prices, altered_targets = prices.copy(), targets.copy()
    altered_prices.iloc[5:] *= 7
    altered_targets.iloc[5:] = -2
    altered = engine.run(altered_prices, altered_targets)
    pd.testing.assert_series_equal(result.returns.iloc[:5], altered.returns.iloc[:5])


@pytest.mark.parametrize("lag", [0, -1, True, 0.5])
def test_same_bar_and_invalid_execution_lags_are_rejected(lag):
    with pytest.raises(ValueError, match="execution_lag"):
        BacktestConfig(execution_lag=lag)


@pytest.mark.parametrize("bad_price", [0, -1, np.nan, np.inf])
def test_missing_or_invalid_prices_are_not_imputed_by_backtest(bad_price):
    prices = pd.DataFrame({"A": [100, bad_price, 105]})
    with pytest.raises(ValueError, match="finite and positive"):
        VectorizedBacktester().run(prices, prices * 0 + 1)


@pytest.mark.parametrize("drift", [False, True])
def test_bankruptcy_rejected_before_equity_can_recover(drift):
    prices = pd.DataFrame({"A": [100, 10, 100]}, index=pd.bdate_range("2024-01-01", periods=3))
    with pytest.raises(ValueError, match="exhausted"):
        VectorizedBacktester(BacktestConfig(
            rebalance_frequency=None, drift_between_rebalances=drift,
        )).run(prices, prices * 0 + 2)


def test_alignment_and_returns_preserve_missing_observations_and_volume():
    dates = pd.bdate_range("2024-01-01", periods=3)
    frames = {
        "A": pd.DataFrame({"Close": [100, 110], "Volume": [1000, 2000]}, index=dates[[0, 2]]),
        "B": pd.DataFrame({"Close": [10, 11, 12], "Volume": [1, 2, 3]}, index=dates),
    }
    aligned = align_frames(frames)
    assert aligned["A"].loc[dates[1]].isna().all()
    returns = MarketDataBundle(aligned).returns()
    assert returns["A"].isna().all()
    filled = align_frames(frames, method="ffill")
    assert filled["A"].loc[dates[1], "Close"] == 100
    assert np.isnan(filled["A"].loc[dates[1], "Volume"])
    with pytest.raises(ValueError, match="future"):
        align_frames(frames, method="bfill")


@pytest.mark.parametrize("allocator", [InverseVolatilityAllocator, RollingSharpeAllocator, RiskParityAllocator])
def test_one_asset_allocators_keep_caps_and_cash(allocator):
    returns = pd.DataFrame({"A": [0.01, 0.02, 0.015, 0.025, 0.01, 0.02]})
    config = AllocationConfig(lookback=3, long_only=True, min_weight=0, max_weight=0.15)
    weights = allocator(config).allocate(returns).weights
    assert weights.iloc[-1, 0] == pytest.approx(0.15)
    assert (weights.abs().sum(axis=1) <= 0.15 + 1e-10).all()


def test_regime_scaling_cannot_undo_asset_cap():
    config = AllocationConfig(gross_leverage=1, min_weight=-0.2, max_weight=0.2)
    weights = RegimeConditionedAllocator(config).allocate(
        pd.DataFrame({"A": [1.0], "B": [-1.0]}), pd.Series([2])
    ).weights
    np.testing.assert_allclose(weights.iloc[0], [0.2, -0.2])


@pytest.mark.parametrize("solver_failure", [False, True])
def test_optimizer_fallback_respects_bounds_budget_and_cash(monkeypatch, solver_failure):
    import portfolio.allocation as module
    optimizer = ConstrainedOptimizer(AllocationConfig(long_only=True, min_weight=0, max_weight=0.15))
    monkeypatch.setattr(optimizer, "_allocate_cvxpy", lambda *args: (_ for _ in ()).throw(RuntimeError("unavailable")))
    monkeypatch.setattr(module, "minimize", (lambda *args, **kwargs: SimpleNamespace(success=False, x=np.array([1.0]))) if solver_failure else None)
    result = optimizer.allocate(pd.Series({"A": 0.1}), pd.DataFrame([[0.04]], index=["A"], columns=["A"]))
    assert result["A"] == pytest.approx(0.15)


def test_long_only_negative_lower_bound_does_not_permit_shorts():
    assets = ["A", "B", "C"]
    optimizer = ConstrainedOptimizer(AllocationConfig(long_only=True, min_weight=-0.5, max_weight=0.5))
    weights = optimizer.allocate(pd.Series([-1, 0.1, 0.2], index=assets), pd.DataFrame(np.eye(3), index=assets, columns=assets))
    assert (weights >= -1e-8).all()
    assert weights.sum() == pytest.approx(1)


def test_hmm_filter_matches_independent_bayes_recursion_and_ignores_future():
    class EmissionModel:
        startprob_ = np.array([0.6, 0.4])
        transmat_ = np.array([[0.9, 0.1], [0.2, 0.8]])

        def _compute_log_likelihood(self, values):
            return np.log(np.column_stack([values[:, 0], 1 - values[:, 0]]))

        def predict(self, values):
            raise AssertionError("Viterbi prediction must never be used")

        def predict_proba(self, values):
            raise AssertionError("Backward-smoothed probabilities must never be used")

    detector = HMMRegimeDetector(n_states=2)
    detector.model_ = EmissionModel()
    detector.backend_ = "hmmlearn.GaussianHMM"
    values = np.array([[0.8], [0.3], [0.9], [0.1]])
    filtered = detector._filtered_probabilities(values)
    first = np.array([0.6 * 0.8, 0.4 * 0.2]); first /= first.sum()
    second_prior = np.array([first[0] * 0.9 + first[1] * 0.2, first[0] * 0.1 + first[1] * 0.8])
    second = second_prior * [0.3, 0.7]; second /= second.sum()
    np.testing.assert_allclose(filtered[:2], [first, second])
    altered = values.copy(); altered[2:] = 1 - altered[2:]
    np.testing.assert_allclose(filtered[:2], detector._filtered_probabilities(altered)[:2])
    np.testing.assert_allclose(filtered[:2], detector._filtered_probabilities(values[:2]))
    np.testing.assert_array_equal(detector._predict_raw(values), filtered.argmax(axis=1))
    assert set(detector._order_states_by_volatility(pd.DataFrame(values), np.zeros(4, dtype=int)).values()) == {0, 1}
