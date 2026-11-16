import numpy as np
import pytest
from scipy.stats import norm

from risk_engine.portfolio import equity_paths
from risk_engine.risk_metrics import measure_risk
from risk_engine.simulator import simulate_log_returns


def test_known_terminal_losses_and_drawdowns():
    wealth = [[100, 110, 120], [100, 120, 100], [100, 80, 90], [100, 105, 70], [100, 50, 50]]
    report = measure_risk(wealth, [0.75, 0.95, 0.99])
    # Sorted losses [-20, 0, 10, 30, 50]. Linear ranks are 3, 3.8 and 3.96.
    np.testing.assert_allclose([r["var_currency"] for r in report.tails], [30, 46, 49.2])
    np.testing.assert_allclose([r["es_currency"] for r in report.tails], [40, 50, 50])
    assert [r["tail_paths"] for r in report.tails] == [2, 1, 1]
    np.testing.assert_allclose(report.max_drawdowns, [0, 1/6, 0.2, 1/3, 0.5])
    assert report.summary["worst_max_drawdown_pct"] == 50
    assert report.summary["probability_of_loss"] == 0.6
    assert report.summary["mean_terminal_pnl"] == -14
    assert report.summary["median_terminal_pnl"] == -10
    assert report.summary["mean_terminal_value"] == 86
    assert report.summary["median_terminal_value"] == 90


def test_loss_scale_ties_and_all_gains():
    report = measure_risk([[200, 180], [200, 180], [200, 120]], [0.50])
    assert report.tails[0]["tail_paths"] == 3
    assert report.tails[0]["var_pct"] == 10
    assert report.tails[0]["es_pct"] == 20
    gains = measure_risk([[100, 105], [100, 110]], [0.95])
    assert gains.tails[0]["var_currency"] < 0
    assert gains.tails[0]["es_currency"] == -5
    assert gains.summary["probability_of_loss"] == 0


def test_gaussian_single_asset_matches_analytic_tail():
    mu, sigma, horizon, capital, confidence = 0.0002, 0.012, 5, 250_000, 0.95
    x = simulate_log_returns([mu], [[sigma]], 100_000, horizon, 141)
    empirical = measure_risk(equity_paths(x, [1], capital), [confidence]).tails[0]
    m, s = mu * horizon, sigma * np.sqrt(horizon)
    z = norm.ppf(1 - confidence)
    var = capital * (1 - np.exp(m + s * z))
    es = capital * (1 - np.exp(m + s*s/2) * norm.cdf(z - s) / (1 - confidence))
    assert empirical["var_currency"] == pytest.approx(var, rel=0.02)
    assert empirical["es_currency"] == pytest.approx(es, rel=0.02)


@pytest.mark.parametrize("levels", [[], [1.0], [0], [0.95, 0.95], [np.nan]])
def test_invalid_levels(levels):
    with pytest.raises(ValueError, match="Confidence levels"):
        measure_risk([[100, 101]], levels)
