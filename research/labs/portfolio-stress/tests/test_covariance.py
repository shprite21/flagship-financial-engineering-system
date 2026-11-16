import numpy as np
import pandas as pd
import pytest

from risk_engine.covariance import correlation_matrix, estimate_moments, factor_covariance


def test_unbiased_sample_estimates_and_orientation():
    panel = pd.DataFrame({"A": [0.01, -0.02, 0.03], "B": [0.0, 0.04, -0.01]})
    moments = estimate_moments(panel)
    np.testing.assert_allclose(moments.mean, panel.mean())
    np.testing.assert_allclose(moments.covariance, np.cov(panel.T, ddof=1))
    np.testing.assert_allclose(moments.covariance, moments.covariance.T)
    np.testing.assert_allclose(correlation_matrix(moments.covariance), np.corrcoef(panel.T))
    model = factor_covariance(moments.covariance)
    np.testing.assert_allclose(model.lower @ model.lower.T, moments.covariance)
    assert model.diagonal_shift == 0 and model.min_eigenvalue > 0


def test_roundoff_regularization_is_auditable():
    matrix = np.array([[1.0, 1.0 + 2e-16], [1.0 + 2e-16, 1.0]])
    original = matrix.copy()
    model = factor_covariance(matrix)
    assert 0 < model.diagonal_shift < 1e-12
    np.testing.assert_array_equal(matrix, original)
    np.testing.assert_allclose(model.effective, matrix + np.eye(2) * model.diagonal_shift)
    np.testing.assert_allclose(model.lower @ model.lower.T, model.effective)


def test_rank_deficient_and_constant_assets():
    matrix = np.array([[1, 0, 1], [0, 0, 0], [1, 0, 1]], dtype=float)
    model = factor_covariance(matrix)
    assert model.diagonal_shift > 0
    np.testing.assert_array_equal(model.lower[1], 0)
    np.testing.assert_allclose(model.lower @ model.lower.T, model.effective)
    np.testing.assert_array_equal(correlation_matrix(matrix)[1], [0, 1, 0])
    flat = estimate_moments(pd.DataFrame({"Flat": [0.0031] * 47}))
    np.testing.assert_array_equal(factor_covariance(flat.covariance).lower, [[0]])


def test_roundoff_asymmetry_is_reported():
    matrix = np.array([[1, 0.5], [0.5 + 1e-16, 1]])
    model = factor_covariance(matrix)
    assert model.max_asymmetry > 0
    np.testing.assert_array_equal(model.effective, model.effective.T)


@pytest.mark.parametrize("matrix", [
    [[1, 0.2], [0.3, 1]], [[1, 2], [2, 1]], [[-1]], [[np.nan]], [[1, 0]], [[0, 0.1], [0.1, 1]]
])
def test_rejects_invalid_covariances(matrix):
    with pytest.raises(ValueError):
        factor_covariance(matrix)
