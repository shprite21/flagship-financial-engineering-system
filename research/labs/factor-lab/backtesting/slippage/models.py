"""Execution slippage approximations."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class VolumeShareSlippage:
    bps: float = 2.0
    volume_impact_coefficient: float = 0.1

    def estimate(self, turnover: pd.Series, participation_rate: pd.Series | None = None) -> pd.Series:
        base = turnover.fillna(0.0) * self.bps / 10_000.0
        if participation_rate is None:
            return base
        return base + self.volume_impact_coefficient * participation_rate.fillna(0.0) ** 2

