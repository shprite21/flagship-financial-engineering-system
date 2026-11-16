import numpy as np
import pytest

from risk_engine.simulator import simulate_log_returns


def test_seed_shape_and_empirical_moments():
    mu = np.array([0.0003, 0.0001])
    lower = np.array([[0.02, 0], [-0.003, 0.01]])
    x = simulate_log_returns(mu, lower, 12_000, 9, 38)
    assert x.shape == (12_000, 9, 2)
    np.testing.assert_array_equal(x, simulate_log_returns(mu, lower, 12_000, 9, 38))
    assert not np.array_equal(x, simulate_log_returns(mu, lower, 12_000, 9, 39))
    flat = x.reshape(-1, 2)
    sigma = lower @ lower.T
    # Gaussian sample mean and covariance standard errors, six-sigma tolerance.
    mean_se = np.sqrt(sigma.diagonal() / len(flat))
    cov_se = np.sqrt((np.outer(sigma.diagonal(), sigma.diagonal()) + sigma**2) / (len(flat) - 1))
    assert np.all(np.abs(flat.mean(axis=0) - mu) < 6 * mean_se)
    assert np.all(np.abs(np.cov(flat.T) - sigma) < 6 * cov_se)


@pytest.mark.parametrize(("paths", "horizon", "seed"), [(0, 1, 1), (1, 0, 1), (3, 2, -1), (True, 2, 0)])
def test_invalid_simulation_dimensions(paths, horizon, seed):
    with pytest.raises(ValueError):
        simulate_log_returns([0], [[1]], paths, horizon, seed)
