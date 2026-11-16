"""Transaction cost models for turnover-aware backtests."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class TransactionCostModel:
    bps: float = 5.0
    commission_per_share: float = 0.0

    def from_turnover(self, turnover: pd.Series) -> pd.Series:
        return turnover.fillna(0.0) * self.bps / 10_000.0

