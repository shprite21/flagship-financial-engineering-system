"""PCA residual statistical arbitrage."""

from __future__ import annotations

import numpy as np
import pandas as pd


def pca_residuals(returns: pd.DataFrame, n_components: int = 3) -> pd.DataFrame:
    """Remove common PCA components and return residual returns."""

    clean = returns.dropna(how="all").fillna(0.0)
    centered = clean - clean.mean(axis=0)
    u, s, vt = np.linalg.svd(centered.to_numpy(), full_matrices=False)
    k = min(n_components, vt.shape[0])
    common = (u[:, :k] * s[:k]) @ vt[:k, :]
    residual = centered.to_numpy() - common
    return pd.DataFrame(residual, index=clean.index, columns=clean.columns)


def residual_zscores(returns: pd.DataFrame, n_components: int = 3, window: int = 60) -> pd.DataFrame:
    residuals = pca_residuals(returns, n_components=n_components)
    mean = residuals.rolling(window).mean()
    std = residuals.rolling(window).std().replace(0, np.nan)
    return residuals.sub(mean).div(std)

