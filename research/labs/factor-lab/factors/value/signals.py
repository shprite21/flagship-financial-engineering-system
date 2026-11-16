"""Value signals: book-to-market, earnings yield, EV/EBITDA, and FCF yield."""

from __future__ import annotations

import pandas as pd

from factors.base import FactorResult, sector_neutralize, zscore_cross_section


def _ratio_wide(fundamentals: pd.DataFrame, numerator: str, denominator: str) -> pd.DataFrame:
    ratio = fundamentals[numerator].div(fundamentals[denominator].replace(0, pd.NA))
    return ratio.unstack("ticker").sort_index()


def book_to_market(fundamentals: pd.DataFrame) -> pd.DataFrame:
    return _ratio_wide(fundamentals, "book_value", "market_cap")


def earnings_yield(fundamentals: pd.DataFrame) -> pd.DataFrame:
    return _ratio_wide(fundamentals, "earnings", "market_cap")


def ev_to_ebitda_value(fundamentals: pd.DataFrame) -> pd.DataFrame:
    # Lower EV/EBITDA is cheaper, so invert the ratio for an alpha score.
    ratio = fundamentals["enterprise_value"].div(fundamentals["ebitda"].replace(0, pd.NA))
    return (-ratio).unstack("ticker").sort_index()


def free_cash_flow_yield(fundamentals: pd.DataFrame) -> pd.DataFrame:
    return _ratio_wide(fundamentals, "free_cash_flow", "market_cap")


def value_composite(
    fundamentals: pd.DataFrame,
    sectors: pd.Series | dict[str, str] | None = None,
) -> FactorResult:
    components = {
        "book_to_market": book_to_market(fundamentals),
        "earnings_yield": earnings_yield(fundamentals),
        "ev_to_ebitda": ev_to_ebitda_value(fundamentals),
        "free_cash_flow_yield": free_cash_flow_yield(fundamentals),
    }
    scored = [zscore_cross_section(component) for component in components.values()]
    composite = sum(scored) / len(scored)
    if sectors is not None:
        composite = sector_neutralize(composite, sectors)
    return FactorResult(
        name="value_composite",
        scores=zscore_cross_section(composite),
        metadata={"components": list(components), "paper_family": "Fama-French value / cross-section"},
    )

