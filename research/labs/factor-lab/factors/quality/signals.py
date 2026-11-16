"""Quality signals inspired by Quality Minus Junk."""

from __future__ import annotations

import pandas as pd

from factors.base import FactorResult, zscore_cross_section


def _wide(fundamentals: pd.DataFrame, column: str) -> pd.DataFrame:
    return fundamentals[column].unstack("ticker").sort_index()


def gross_profitability(fundamentals: pd.DataFrame) -> pd.DataFrame:
    ratio = fundamentals["gross_profit"].div(fundamentals["assets"].replace(0, pd.NA))
    return ratio.unstack("ticker").sort_index()


def accrual_quality(fundamentals: pd.DataFrame) -> pd.DataFrame:
    ratio = fundamentals["accruals"].div(fundamentals["assets"].replace(0, pd.NA))
    return (-ratio.abs()).unstack("ticker").sort_index()


def debt_stability(fundamentals: pd.DataFrame, window: int = 4) -> pd.DataFrame:
    debt_to_assets = fundamentals["debt"].div(fundamentals["assets"].replace(0, pd.NA))
    wide = debt_to_assets.unstack("ticker").sort_index()
    return -wide.diff().abs().rolling(window).mean()


def earnings_consistency(fundamentals: pd.DataFrame, window: int = 4) -> pd.DataFrame:
    wide = _wide(fundamentals, "earnings")
    rolling_std = wide.pct_change(fill_method=None).rolling(window).std()
    return -rolling_std


def quality_composite(fundamentals: pd.DataFrame) -> FactorResult:
    roe = _wide(fundamentals, "roe")
    components = {
        "roe": roe,
        "gross_profitability": gross_profitability(fundamentals),
        "accrual_quality": accrual_quality(fundamentals),
        "debt_stability": debt_stability(fundamentals),
        "earnings_consistency": earnings_consistency(fundamentals),
    }
    scored = [zscore_cross_section(component) for component in components.values()]
    composite = sum(scored) / len(scored)
    return FactorResult(
        name="quality_composite",
        scores=zscore_cross_section(composite),
        metadata={"components": list(components), "paper": "Quality Minus Junk"},
    )

