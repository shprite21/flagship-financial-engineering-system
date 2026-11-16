"""Historical moment estimation and audited Cholesky factorization."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.linalg import cholesky


@dataclass(frozen=True)
class Moments:
    """Constituent order and daily historical log-return moments."""

    assets: tuple[str, ...]
    mean: np.ndarray
    covariance: np.ndarray


@dataclass(frozen=True)
class Factorization:
    """Effective covariance, lower factor and numerical diagnostics in variance units."""

    effective: np.ndarray
    lower: np.ndarray
    min_eigenvalue: float
    max_asymmetry: float
    diagonal_shift: float


def estimate_moments(log_returns: pd.DataFrame) -> Moments:
    """Estimate arithmetic mean and unbiased sample covariance of aligned log returns."""
    x = log_returns.to_numpy(dtype=float)
    if x.shape[0] < 2 or x.shape[1] < 1 or not np.isfinite(x).all():
        raise ValueError("Moment estimation requires at least two finite rows and one column")
    if not log_returns.columns.is_unique:
        raise ValueError("Constituent names must be unique")
    # Shift the origin first so even a nonzero constant column has exactly zero variance.
    centered = x - x[0]
    centered -= centered.mean(axis=0)
    covariance = centered.T @ centered / (len(x) - 1)
    return Moments(tuple(log_returns.columns), x.mean(axis=0), covariance)


def _checked_matrix(covariance: np.ndarray) -> tuple[np.ndarray, float, float]:
    matrix = np.asarray(covariance, dtype=float)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1] or not matrix.size:
        raise ValueError("Covariance must be a nonempty square matrix")
    if not np.isfinite(matrix).all() or (matrix.diagonal() < 0).any():
        raise ValueError("Covariance must be finite with nonnegative variances")
    tolerance = (np.finfo(float).eps * len(matrix) * 16) * np.max(np.abs(matrix))
    asymmetry = float(np.max(np.abs(matrix - matrix.T)))
    if asymmetry > tolerance:
        raise ValueError("Covariance must be symmetric")
    matrix = matrix + 0.5 * (matrix.T - matrix)
    if np.any(matrix[matrix.diagonal() == 0] != 0):
        raise ValueError("Zero-variance constituents must have zero cross-covariance")
    return matrix, asymmetry, tolerance


def correlation_matrix(covariance: np.ndarray) -> np.ndarray:
    """Standardize a PSD covariance, using zero cross-correlations for constant assets."""
    matrix, _, tolerance = _checked_matrix(covariance)
    if np.linalg.eigvalsh(matrix)[0] < -tolerance:
        raise ValueError("Covariance must be positive semidefinite")
    vol = np.sqrt(matrix.diagonal())
    denominator = np.outer(vol, vol)
    result = np.divide(matrix, denominator, out=np.zeros_like(matrix), where=denominator > 0)
    np.fill_diagonal(result, 1.0)
    return result


def factor_covariance(covariance: np.ndarray) -> Factorization:
    """Factor a PSD matrix, adding roundoff-scale variance only if Cholesky fails."""
    matrix, asymmetry, tolerance = _checked_matrix(covariance)
    min_eigenvalue = float(np.linalg.eigvalsh(matrix)[0])
    if min_eigenvalue < -tolerance:
        raise ValueError(f"Covariance must be positive semidefinite (min eigenvalue {min_eigenvalue:g})")
    active = matrix.diagonal() > 0
    indices = np.ix_(active, active)
    lower = np.zeros_like(matrix)
    shift = 0.0
    if active.any():
        block = matrix[indices]
        try:
            factor = cholesky(block, lower=True)
        except np.linalg.LinAlgError:
            shift = float(tolerance + max(0.0, -min_eigenvalue))
            block = block + shift * np.eye(len(block))
            factor = cholesky(block, lower=True)
            matrix[indices] = block
        lower[indices] = factor
    return Factorization(matrix, lower, min_eigenvalue, asymmetry, shift)
