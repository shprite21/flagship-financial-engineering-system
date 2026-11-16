import numpy as np
import pytest

from risk_engine.covariance import Moments, correlation_matrix, factor_covariance
from risk_engine.portfolio import equity_paths
from risk_engine.risk_metrics import measure_risk
from risk_engine.simulator import simulate_log_returns
from risk_engine.stress_testing import Scenario


@pytest.fixture
def historical():
    return Moments(("A", "B"), np.array([0.0002, 0.0001]),
                   np.array([[0.0004, -0.00008], [-0.00008, 0.0001]]))


def test_volatility_stress_increases_dispersion(historical):
    base = Scenario("Baseline").covariance(historical)
    stress = Scenario("Volatility", 1.5).covariance(historical)
    np.testing.assert_array_equal(base, historical.covariance)
    np.testing.assert_allclose(stress, 2.25 * base)
    def paths(matrix):
        x = simulate_log_returns(historical.mean, factor_covariance(matrix).lower, 5000, 8, 12)
        return x, equity_paths(x, [0.6, 0.4], 1000)

    x, wealth = paths(base)
    stressed_x, stressed_wealth = paths(stress)
    np.testing.assert_allclose(stressed_x.std(axis=0), 1.5 * x.std(axis=0))
    assert stressed_wealth[:, -1].std() > wealth[:, -1].std()
    assert measure_risk(stressed_wealth).tails[0]["es_currency"] > measure_risk(wealth).tails[0]["es_currency"]


@pytest.mark.parametrize("blend", [0.0, 0.3, 1.0])
def test_combined_stress_preserves_psd_and_target_volatility(historical, blend):
    target = Scenario("Combined", {"A": 1.25}, blend).covariance(historical)
    original = correlation_matrix(historical.covariance)
    np.testing.assert_allclose(correlation_matrix(target), (1 - blend) * original + blend)
    np.testing.assert_allclose(np.sqrt(target.diagonal()), [0.025, 0.01])
    assert np.linalg.eigvalsh(target).min() >= -1e-18
    model = factor_covariance(target)
    np.testing.assert_allclose(model.lower @ model.lower.T, model.effective)


@pytest.mark.parametrize(("scale", "blend"), [({"X": 2}, 0), (-1.0, 0), (np.inf, 0), (1.0, 1.1), (1, -0.1)])
def test_invalid_stress_parameters(historical, scale, blend):
    with pytest.raises(ValueError):
        Scenario("Invalid", scale, blend).covariance(historical)
