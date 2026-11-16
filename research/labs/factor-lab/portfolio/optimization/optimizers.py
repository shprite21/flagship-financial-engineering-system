"""Mean-variance, maximum Sharpe, and risk-parity optimizers."""

from __future__ import annotations

import numpy as np
import pandas as pd

from portfolio.constraints.models import PortfolioConstraints, apply_basic_constraints


def _regularized_inverse(covariance: pd.DataFrame, ridge: float = 1e-5) -> np.ndarray:
    cov = covariance.fillna(0.0).to_numpy()
    cov = cov + np.eye(cov.shape[0]) * ridge
    return np.linalg.pinv(cov)


def mean_variance_weights(
    expected_returns: pd.Series,
    covariance: pd.DataFrame,
    risk_aversion: float = 5.0,
    constraints: PortfolioConstraints | None = None,
) -> pd.Series:
    aligned_cov = covariance.loc[expected_returns.index, expected_returns.index]
    inv = _regularized_inverse(aligned_cov)
    raw = inv @ expected_returns.fillna(0.0).to_numpy() / max(risk_aversion, 1e-8)
    weights = pd.Series(raw, index=expected_returns.index)
    return apply_basic_constraints(weights, constraints or PortfolioConstraints())


def max_sharpe_weights(
    expected_returns: pd.Series,
    covariance: pd.DataFrame,
    constraints: PortfolioConstraints | None = None,
) -> pd.Series:
    aligned_cov = covariance.loc[expected_returns.index, expected_returns.index]
    inv = _regularized_inverse(aligned_cov)
    raw = inv @ expected_returns.fillna(0.0).to_numpy()
    weights = pd.Series(raw, index=expected_returns.index)
    return apply_basic_constraints(weights, constraints or PortfolioConstraints())


def risk_parity_weights(covariance: pd.DataFrame, gross_exposure: float = 1.0) -> pd.Series:
    vol = pd.Series(np.sqrt(np.diag(covariance)), index=covariance.index)
    inv = 1.0 / vol.replace(0, np.nan)
    weights = inv / inv.sum()
    return weights.fillna(0.0) * gross_exposure


def cvxpy_mean_variance(
    expected_returns: pd.Series,
    covariance: pd.DataFrame,
    risk_aversion: float = 5.0,
    max_weight: float = 0.05,
) -> pd.Series:
    """Optional convex optimizer for richer institutional constraints."""

    try:
        import cvxpy as cp
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Install cvxpy to use cvxpy_mean_variance.") from exc

    n_assets = len(expected_returns)
    weights = cp.Variable(n_assets)
    cov = covariance.loc[expected_returns.index, expected_returns.index].fillna(0.0).to_numpy()
    mu = expected_returns.fillna(0.0).to_numpy()
    objective = cp.Maximize(mu @ weights - risk_aversion * cp.quad_form(weights, cov))
    constraints = [cp.norm1(weights) <= 1.0, cp.sum(weights) == 0.0, weights <= max_weight, weights >= -max_weight]
    problem = cp.Problem(objective, constraints)
    problem.solve(solver=cp.CLARABEL)
    return pd.Series(np.asarray(weights.value).reshape(-1), index=expected_returns.index)

