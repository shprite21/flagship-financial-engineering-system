"""Configurable equity universes."""

from __future__ import annotations

from data.schemas import UniverseConfig
from data.synthetic import DEFAULT_SECTORS, DEFAULT_TICKERS


def demo_large_cap_universe() -> UniverseConfig:
    return UniverseConfig(
        name="demo_large_cap",
        tickers=DEFAULT_TICKERS,
        benchmark="SPY",
        sector_map={ticker: DEFAULT_SECTORS.get(ticker, "Other") for ticker in DEFAULT_TICKERS},
    )


def from_tickers(name: str, tickers: list[str], benchmark: str = "SPY") -> UniverseConfig:
    return UniverseConfig(name=name, tickers=tickers, benchmark=benchmark)

