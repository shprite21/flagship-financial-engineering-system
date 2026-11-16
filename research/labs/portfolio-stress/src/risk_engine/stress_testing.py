"""Volatility scaling and PSD-preserving correlation stresses."""

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from .covariance import Moments, correlation_matrix


@dataclass(frozen=True)
class Scenario:
    """Stress inputs. Unspecified named volatility multipliers default to one."""

    name: str
    volatility_multiplier: float | Mapping[str, float] = 1.0
    correlation_blend: float = 0.0

    def covariance(self, historical: Moments) -> np.ndarray:
        """Construct a target covariance while leaving the historical log mean unchanged."""
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Scenario name must be a nonempty string")
        blend = self.correlation_blend
        if isinstance(blend, bool) or not isinstance(blend, (float, int)) or not 0 <= blend <= 1:
            raise ValueError("correlation_blend must be between zero and one inclusive")
        scale = self.volatility_multiplier
        if isinstance(scale, Mapping):
            unknown = set(scale).difference(historical.assets)
            if unknown:
                raise ValueError(f"Unknown volatility multiplier constituents: {sorted(unknown)}")
            scales = [scale.get(asset, 1.0) for asset in historical.assets]
        else:
            scales = [scale] * len(historical.assets)
        if any(isinstance(s, bool) or not isinstance(s, (int, float)) or not np.isfinite(s) or s <= 0
               for s in scales):
            raise ValueError("Volatility multipliers must be finite positive numbers")
        corr = correlation_matrix(historical.covariance)
        if blend == 0:
            return historical.covariance * np.outer(scales, scales)
        stressed_corr = (1 - blend) * corr + blend * np.ones_like(corr)
        vol = np.sqrt(historical.covariance.diagonal()) * scales
        return np.outer(vol, vol) * stressed_corr
