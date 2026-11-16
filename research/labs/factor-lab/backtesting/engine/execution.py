"""Execution simulation utilities."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class ExecutionSimulationConfig:
    max_participation_rate: float = 0.1
    delay_days: int = 1
    spread_bps: float = 1.0


def simulate_rebalance_orders(
    target_weights: pd.DataFrame,
    portfolio_value: float,
    prices: pd.DataFrame,
    config: ExecutionSimulationConfig | None = None,
) -> pd.DataFrame:
    """Translate target-weight changes into delayed notional order estimates."""

    config = config or ExecutionSimulationConfig()
    trades = target_weights.diff().fillna(target_weights).shift(config.delay_days).fillna(0.0)
    notional = trades * portfolio_value
    shares = notional.div(prices.reindex_like(target_weights).replace(0, pd.NA))
    return shares.stack(future_stack=True).rename("shares").reset_index()

