"""Machine-learning alpha blending and cross-sectional ranking utilities."""

from __future__ import annotations

import numpy as np
import pandas as pd


def fit_cross_sectional_ridge(
    features: dict[str, pd.DataFrame],
    forward_returns: pd.DataFrame,
    ridge: float = 1e-3,
) -> pd.Series:
    """Fit a pooled ridge model across date/ticker observations."""

    stacked_features = [frame.stack(future_stack=True).rename(name) for name, frame in features.items()]
    x_frame = pd.concat(stacked_features, axis=1)
    y = forward_returns.stack(future_stack=True).rename("forward_return")
    data = pd.concat([x_frame, y], axis=1).dropna()
    if data.empty:
        return pd.Series(0.0, index=list(features), name="ridge_coefficients")
    x = data[list(features)].to_numpy()
    y_values = data["forward_return"].to_numpy()
    x = (x - x.mean(axis=0)) / np.where(x.std(axis=0) == 0, 1.0, x.std(axis=0))
    penalty = ridge * np.eye(x.shape[1])
    beta = np.linalg.pinv(x.T @ x + penalty) @ x.T @ y_values
    return pd.Series(beta, index=list(features), name="ridge_coefficients")


def predict_ml_alpha(features: dict[str, pd.DataFrame], coefficients: pd.Series) -> pd.DataFrame:
    aligned_index = None
    aligned_columns = None
    for frame in features.values():
        aligned_index = frame.index if aligned_index is None else aligned_index.intersection(frame.index)
        aligned_columns = frame.columns if aligned_columns is None else aligned_columns.intersection(frame.columns)
    prediction = None
    for name, frame in features.items():
        contribution = frame.loc[aligned_index, aligned_columns].fillna(0.0) * coefficients.get(name, 0.0)
        prediction = contribution if prediction is None else prediction + contribution
    return prediction if prediction is not None else pd.DataFrame()

