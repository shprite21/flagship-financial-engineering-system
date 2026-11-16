"""Catalogue-signal adapters to existing allocators, using completed history only."""
from dataclasses import replace

import numpy as np
import pandas as pd

from .allocation import AllocationConfig, ConstrainedOptimizer, InverseVolatilityAllocator, RiskParityAllocator


def weight_signals(signals: pd.DataFrame, returns: pd.DataFrame, method: str,
                   config: AllocationConfig, lookback: int) -> pd.DataFrame:
    if method == 'signal':
        return signals
    directions = np.sign(signals)
    if config.long_only:
        directions = directions.clip(lower=0)
    if method == 'equal':
        return directions
    positive = replace(config, lookback=lookback, long_only=True, min_weight=0)
    if method == 'inverse_volatility':
        # Base inverse-vol weights are conditioned on the observed signal sign.
        return InverseVolatilityAllocator(positive).allocate(returns).weights * directions
    if method not in ('risk_parity', 'minimum_variance'):
        raise ValueError('Unsupported portfolio weighting method')
    if not config.long_only:
        raise ValueError('Covariance-based project allocations require long-only signals')
    output = pd.DataFrame(0.0, index=signals.index, columns=signals.columns)
    for i in range(lookback, len(returns)):
        active = signals.columns[directions.iloc[i] > 0]
        if active.empty:
            continue
        # Estimation ends at the previous completed bar; current signal selection
        # is known at this close and still has the existing execution lag.
        history = returns.iloc[i - lookback:i + 1].loc[:, active]
        if method == 'risk_parity':
            weights = RiskParityAllocator(positive).allocate(history).weights.iloc[-1]
        else:
            covariance = history.iloc[:-1].cov()
            weights = ConstrainedOptimizer(positive).allocate(pd.Series(0.0, index=active), covariance)
        output.loc[signals.index[i], active] = weights
    return output
