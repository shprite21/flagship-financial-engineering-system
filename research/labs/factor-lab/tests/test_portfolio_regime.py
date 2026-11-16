import pandas as pd

from data.synthetic import adjusted_close_wide, generate_market_panel
from portfolio.constraints.exposure import beta_neutralize_weights, constrain_turnover
from portfolio.optimization.optimizers import max_sharpe_weights
from regime.engine import classify_regimes


def test_optimizer_respects_gross_exposure():
    expected_returns = pd.Series({"A": 0.05, "B": 0.03, "C": -0.01})
    covariance = pd.DataFrame(
        [[0.04, 0.01, 0.00], [0.01, 0.03, 0.00], [0.00, 0.00, 0.02]],
        index=expected_returns.index,
        columns=expected_returns.index,
    )

    weights = max_sharpe_weights(expected_returns, covariance)

    assert weights.abs().sum() <= 1.0 + 1e-12


def test_regime_classifier_returns_composite_state():
    panel = generate_market_panel(periods=260)
    prices = adjusted_close_wide(panel)
    returns = prices.pct_change(fill_method=None).fillna(0.0).mean(axis=1)

    regimes = classify_regimes(returns, prices.mean(axis=1))

    assert "composite_regime" in regimes.columns
    assert regimes["composite_regime"].notna().all()


def test_turnover_and_beta_constraints():
    target = pd.Series({"A": 0.5, "B": -0.5})
    previous = pd.Series({"A": 0.0, "B": 0.0})
    constrained = constrain_turnover(target, previous, max_turnover=0.4)
    assert constrained.abs().sum() <= 0.4 + 1e-12

    beta_neutral = beta_neutralize_weights(target, pd.Series({"A": 1.2, "B": 0.8}))
    assert abs(beta_neutral.dot(pd.Series({"A": 1.2, "B": 0.8}))) < 1e-12
