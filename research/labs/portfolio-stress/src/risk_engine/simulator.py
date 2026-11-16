"""IID multivariate Gaussian daily log returns."""

import numpy as np


def simulate_log_returns(
    mean: np.ndarray,
    lower: np.ndarray,
    paths: int = 10_000,
    horizon_days: int = 21,
    seed: int = 1729,
) -> np.ndarray:
    """Draw (path, trading day, constituent) log returns from a lower covariance factor."""
    for name, value in (("paths", paths), ("horizon_days", horizon_days), ("seed", seed)):
        minimum = 0 if name == "seed" else 1
        if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value < minimum:
            raise ValueError(f"{name} must be an integer >= {minimum}")
    mean = np.asarray(mean, dtype=float)
    lower = np.asarray(lower, dtype=float)
    if mean.ndim != 1 or not mean.size or lower.shape != (mean.size, mean.size):
        raise ValueError("Mean vector and square covariance factor must have matching dimensions")
    if not np.isfinite(mean).all() or not np.isfinite(lower).all() or np.triu(lower, 1).any():
        raise ValueError("Expected finite moments and a lower triangular covariance factor")
    rng = np.random.Generator(np.random.PCG64(seed))
    normals = rng.standard_normal((paths, horizon_days, mean.size))
    return normals @ lower.T + mean
