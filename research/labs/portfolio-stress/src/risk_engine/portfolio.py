"""Long-only fixed-weight portfolios rebalanced at each daily boundary."""

from collections.abc import Mapping, Sequence

import numpy as np


def _validate_weights(weights: np.ndarray) -> None:
    if weights.ndim != 1 or not np.isfinite(weights).all() or (weights < 0).any():
        raise ValueError("Weights must be a finite nonnegative vector")
    if not np.isclose(weights.sum(), 1.0, rtol=0, atol=1e-10):
        raise ValueError("Portfolio weights must sum to one")


def resolve_weights(assets: Sequence[str], weights: Mapping[str, float] | None = None) -> np.ndarray:
    """Align named weights to historical columns. Omitted weights allocate equal capital."""
    if not len(assets) or len(set(assets)) != len(assets):
        raise ValueError("Expected at least one constituent and unique names")
    if weights is None:
        return np.full(len(assets), 1.0 / len(assets))
    if not isinstance(weights, Mapping) or set(weights) != set(assets):
        raise ValueError(f"Weight names must match the constituents {list(assets)}")
    if any(isinstance(w, bool) or not isinstance(w, (int, float, np.number)) for w in weights.values()):
        raise ValueError("Portfolio weights must be numeric")
    result = np.array([weights[asset] for asset in assets], dtype=float)
    _validate_weights(result)
    return result


def equity_paths(log_returns: np.ndarray, weights: np.ndarray, initial_capital: float) -> np.ndarray:
    """Compound weighted daily simple returns and prepend initial capital on every path."""
    x = np.asarray(log_returns, dtype=float)
    weights = np.asarray(weights, dtype=float)
    _validate_weights(weights)
    if x.ndim != 3 or 0 in x.shape or x.shape[2] != weights.size or not np.isfinite(x).all():
        raise ValueError("Expected finite nonempty log returns with shape (paths, days, constituents)")
    if isinstance(initial_capital, bool) or not np.isfinite(initial_capital) or initial_capital <= 0:
        raise ValueError("Initial capital must be finite and positive")
    with np.errstate(over="raise", invalid="raise"):
        if (weights == 0).any():
            held = weights > 0
            x, weights = x[:, :, held], weights[held]
        daily_returns = np.expm1(x) @ weights
        wealth = np.empty((x.shape[0], x.shape[1] + 1))
        wealth[:, 0] = initial_capital
        gross = 1.0 + daily_returns
        # Near total loss, 1 + a rounded simple return can erase positive wealth.
        near_zero = gross < np.sqrt(np.finfo(float).eps)
        if near_zero.any():
            gross[near_zero] = np.exp(x[near_zero]) @ weights
        if (gross <= 0).any():
            raise ValueError("Daily portfolio gross return is outside positive floating-point range")
        wealth[:, 1:] = initial_capital * np.cumprod(gross, axis=1)
    if (wealth[:, 1:] == 0).any():
        raise ValueError("Simulated wealth underflowed, check input units and stress assumptions")
    return wealth
