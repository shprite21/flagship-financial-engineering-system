"""Hidden Markov Model regime detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

try:  # pragma: no cover - depends on installed research stack
    from sklearn.mixture import GaussianMixture
    from sklearn.preprocessing import StandardScaler
except ImportError:  # pragma: no cover - lean runtime fallback
    GaussianMixture = None
    StandardScaler = None

from regime_detection.base import BaseRegimeDetector, RegimeResult


@dataclass
class HMMRegimeDetector(BaseRegimeDetector):
    """Gaussian HMM detector for latent market regimes.

    If ``hmmlearn`` is unavailable, the detector falls back to a Gaussian
    mixture model with the same standardized feature interface. This keeps the
    research pipeline usable in lean environments while preserving the HMM path
    for full installations. Prediction uses forward-filtered state probabilities;
    callers must fit on a separate training prefix for out-of-sample evidence.
    """

    n_states: int = 3
    covariance_type: str = "diag"
    random_state: int = 42
    n_iter: int = 250

    name: str = "hmm"

    def __post_init__(self) -> None:
        self.scaler_: Any | None = None
        self.model_: Any | None = None
        self.feature_columns_: list[str] | None = None
        self.state_order_: dict[int, int] | None = None
        self.backend_: str | None = None
        self.training_start_: object | None = None
        self.training_end_: object | None = None

    def fit(self, features: pd.DataFrame) -> HMMRegimeDetector:
        matrix = self._prepare_features(features)
        self.training_start_ = matrix.index[0]
        self.training_end_ = matrix.index[-1]
        self.feature_columns_ = list(matrix.columns)
        self.scaler_ = StandardScaler() if StandardScaler is not None else _SimpleStandardScaler()
        scaled = self.scaler_.fit_transform(matrix)

        try:
            from hmmlearn.hmm import GaussianHMM

            model = GaussianHMM(
                n_components=self.n_states,
                covariance_type=self.covariance_type,
                n_iter=self.n_iter,
                random_state=self.random_state,
            )
            self.backend_ = "hmmlearn.GaussianHMM"
        except ImportError:  # pragma: no cover - depends on optional environment
            if GaussianMixture is not None:
                model = GaussianMixture(
                    n_components=self.n_states,
                    covariance_type="diag",
                    random_state=self.random_state,
                    max_iter=self.n_iter,
                )
                self.backend_ = "sklearn.GaussianMixture"
            else:
                model = _QuantileStateModel(n_states=self.n_states)
                self.backend_ = "quantile_fallback"

        model.fit(scaled)
        self.model_ = model
        raw_labels = self._predict_raw(scaled)
        self.state_order_ = self._order_states_by_volatility(matrix, raw_labels)
        return self

    def predict(self, features: pd.DataFrame) -> RegimeResult:
        if (
            self.model_ is None
            or self.scaler_ is None
            or self.feature_columns_ is None
            or self.state_order_ is None
        ):
            raise RuntimeError("HMMRegimeDetector must be fit before predict")

        matrix = self._prepare_features(features)[self.feature_columns_]
        scaled = self.scaler_.transform(matrix)
        raw_labels = self._predict_raw(scaled)
        labels = pd.Series(
            [self.state_order_.get(int(label), int(label)) for label in raw_labels],
            index=matrix.index,
            name="hmm_regime",
        )
        probabilities = self._predict_probabilities(scaled, matrix.index)
        if probabilities is not None and self.state_order_ is not None:
            probabilities = probabilities.rename(columns=self.state_order_)
            probabilities = probabilities.reindex(sorted(probabilities.columns), axis=1)
        return RegimeResult(
            labels=labels,
            probabilities=probabilities,
            diagnostics={
                "backend": self.backend_,
                "n_states": self.n_states,
                "state_order": self.state_order_,
                "probability_method": "forward_filter" if self.backend_ == "hmmlearn.GaussianHMM" else "independent_observation",
                "training_start": str(self.training_start_),
                "training_end": str(self.training_end_),
                "prediction_overlaps_training": bool(matrix.index[0] <= self.training_end_),
                "out_of_sample_contract": "Fit scaler, states, and state ordering only on a prior training prefix; each predict call starts at the fitted initial distribution.",
            },
        )

    @staticmethod
    def _prepare_features(features: pd.DataFrame) -> pd.DataFrame:
        if features.index.has_duplicates or not features.index.is_monotonic_increasing:
            raise ValueError("Regime features must have unique chronological observations")
        matrix = features.select_dtypes(include=[np.number]).replace([np.inf, -np.inf], np.nan)
        matrix = matrix.dropna(how="any")
        if matrix.empty:
            raise ValueError("Regime features are empty after dropping missing values")
        return matrix

    def _predict_raw(self, scaled: np.ndarray) -> np.ndarray:
        model = self.model_
        if self.backend_ == "hmmlearn.GaussianHMM":
            return self._filtered_probabilities(scaled).argmax(axis=1)
        if model is not None and hasattr(model, "predict"):
            return model.predict(scaled)
        raise RuntimeError("Underlying regime model does not support predict")

    def _predict_probabilities(self, scaled: np.ndarray, index: pd.Index) -> pd.DataFrame | None:
        model = self.model_
        if self.backend_ == "hmmlearn.GaussianHMM":
            return pd.DataFrame(self._filtered_probabilities(scaled), index=index, columns=range(self.n_states))
        if model is not None and hasattr(model, "predict_proba"):
            probabilities = model.predict_proba(scaled)
            return pd.DataFrame(probabilities, index=index, columns=range(probabilities.shape[1]))
        if model is not None and hasattr(model, "score_samples"):
            result = model.score_samples(scaled)
            if isinstance(result, tuple) and len(result) == 2:
                probabilities = result[1]
                return pd.DataFrame(probabilities, index=index, columns=range(probabilities.shape[1]))
        return None

    def _filtered_probabilities(self, scaled: np.ndarray) -> np.ndarray:
        """P(state_t | observations_0:t), never Viterbi or backward smoothing.

        Log-space forward recursion avoids underflow for extreme observations.
        The fitted hmmlearn model supplies emission likelihoods only.
        """
        model = self.model_
        log_emissions = model._compute_log_likelihood(scaled)
        with np.errstate(divide="ignore"):
            log_transition = np.log(model.transmat_)
            log_prior = np.log(model.startprob_)
        filtered = np.empty_like(log_emissions)
        for position, emission in enumerate(log_emissions):
            if position:
                log_prior = np.logaddexp.reduce(log_posterior[:, None] + log_transition, axis=0)
            log_posterior = log_prior + emission
            normalizer = np.logaddexp.reduce(log_posterior)
            if not np.isfinite(normalizer):
                raise ValueError("HMM observations have no finite state likelihood")
            log_posterior -= normalizer
            filtered[position] = np.exp(log_posterior)
        return filtered

    def _order_states_by_volatility(self, matrix: pd.DataFrame, raw_labels: np.ndarray) -> dict[int, int]:
        volatility_proxy = matrix.abs().mean(axis=1)
        state_volatility = (
            pd.DataFrame({"state": raw_labels, "volatility": volatility_proxy})
            .groupby("state")["volatility"]
            .mean()
            .sort_values()
        )
        # Include unobserved states so probability-column remapping is bijective.
        ordered = list(state_volatility.index)
        ordered.extend(state for state in range(self.n_states) if state not in ordered)
        return {int(raw_state): rank for rank, raw_state in enumerate(ordered)}


class _SimpleStandardScaler:
    """Small fallback compatible with the scikit-learn scaler API used here."""

    def fit_transform(self, matrix: pd.DataFrame) -> np.ndarray:
        values = matrix.to_numpy(dtype=float)
        self.mean_ = np.nanmean(values, axis=0)
        self.scale_ = np.nanstd(values, axis=0)
        self.scale_ = np.where(self.scale_ == 0, 1.0, self.scale_)
        return self.transform(matrix)

    def transform(self, matrix: pd.DataFrame) -> np.ndarray:
        values = matrix.to_numpy(dtype=float)
        return (values - self.mean_) / self.scale_


class _QuantileStateModel:
    """Deterministic fallback that buckets observations by feature magnitude."""

    def __init__(self, n_states: int) -> None:
        self.n_states = n_states
        self.thresholds_: np.ndarray | None = None

    def fit(self, values: np.ndarray) -> _QuantileStateModel:
        score = np.nanmean(np.abs(values), axis=1)
        quantiles = np.linspace(0, 1, self.n_states + 1)[1:-1]
        self.thresholds_ = np.quantile(score, quantiles)
        return self

    def predict(self, values: np.ndarray) -> np.ndarray:
        if self.thresholds_ is None:
            raise RuntimeError("Quantile fallback model must be fit before predict")
        score = np.nanmean(np.abs(values), axis=1)
        return np.digitize(score, self.thresholds_)

    def predict_proba(self, values: np.ndarray) -> np.ndarray:
        labels = self.predict(values)
        probabilities = np.zeros((len(labels), self.n_states))
        probabilities[np.arange(len(labels)), labels] = 1.0
        return probabilities
