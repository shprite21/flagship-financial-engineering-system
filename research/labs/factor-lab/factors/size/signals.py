"""Size factor implementation from market capitalization."""

from __future__ import annotations

import numpy as np
import pandas as pd

from factors.base import FactorResult, zscore_cross_section


def size_score(fundamentals: pd.DataFrame) -> FactorResult:
    market_cap = fundamentals["market_cap"].unstack("ticker").sort_index()
    score = -np.log(market_cap.replace(0, np.nan))
    return FactorResult(name="size", scores=zscore_cross_section(score), metadata={"orientation": "small_minus_big"})

