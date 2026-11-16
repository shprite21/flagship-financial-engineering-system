"""Profitability factor used by Fama-French 5-factor style models."""

from __future__ import annotations

import pandas as pd

from factors.base import FactorResult, zscore_cross_section


def profitability_score(fundamentals: pd.DataFrame) -> FactorResult:
    operating_profitability = fundamentals["earnings"].div(fundamentals["book_value"].replace(0, pd.NA))
    wide = operating_profitability.unstack("ticker").sort_index()
    return FactorResult(
        name="profitability",
        scores=zscore_cross_section(wide),
        metadata={"paper": "Fama-French 5-Factor Model", "definition": "earnings/book equity"},
    )

