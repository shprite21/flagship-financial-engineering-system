"""Provider-agnostic ingestion orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Protocol

import pandas as pd

from data.cache import ParquetCache
from data.schemas import UniverseConfig
from data.validation import validate_market_data

LOGGER = logging.getLogger(__name__)


class EquityDataProvider(Protocol):
    """Interface implemented by yfinance, Polygon, Alpha Vantage, or internal loaders."""

    name: str

    def get_ohlcv(self, tickers: list[str], start: date | str, end: date | str | None) -> pd.DataFrame:
        """Return a MultiIndex frame indexed by date, ticker."""


@dataclass(slots=True)
class IngestionPipeline:
    provider: EquityDataProvider
    cache: ParquetCache
    universe: UniverseConfig

    def load_prices(
        self,
        start: date | str,
        end: date | str | None = None,
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        cache_key = f"{self.universe.name}_{start}_{end or 'latest'}"
        if not force_refresh and self.cache.exists("ohlcv", cache_key):
            frame = self.cache.read("ohlcv", cache_key)
        else:
            LOGGER.info("Fetching %s tickers from %s", len(self.universe.tickers), self.provider.name)
            frame = self.provider.get_ohlcv(self.universe.tickers, start=start, end=end)
            report = validate_market_data(frame)
            if not report.passed:
                LOGGER.warning("Market data validation warnings: %s", report.issues)
            self.cache.write(frame, "ohlcv", cache_key)
        return frame

