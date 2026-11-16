"""Lightweight reinforcement-learning style factor allocation sandbox."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(slots=True)
class ExponentialWeightsAllocator:
    learning_rate: float = 5.0

    def allocate(self, factor_returns: pd.DataFrame) -> pd.DataFrame:
        cumulative_reward = factor_returns.fillna(0.0).cumsum()
        scores = np.exp(self.learning_rate * cumulative_reward.clip(-1, 1))
        return scores.div(scores.sum(axis=1), axis=0)

