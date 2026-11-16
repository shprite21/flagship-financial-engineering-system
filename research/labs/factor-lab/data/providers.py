"""External data provider adapters.

The adapters intentionally expose a small normalized contract so users can swap
vendor-specific details without touching research logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd


@dataclass(slots=True)
class YFinanceProvider:
    name: str = "yfinance"

    def get_ohlcv(self, tickers: list[str], start: date | str, end: date | str | None) -> pd.DataFrame:
        try:
            import yfinance as yf
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("Install yfinance to use YFinanceProvider.") from exc

        raw = yf.download(
            tickers=tickers,
            start=str(start),
            end=None if end is None else str(end),
            auto_adjust=False,
            progress=False,
            group_by="ticker",
        )
        records: list[pd.DataFrame] = []
        for ticker in tickers:
            if len(tickers) == 1:
                sub = raw.copy()
            else:
                sub = raw[ticker].copy()
            sub = sub.rename(
                columns={
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Adj Close": "adj_close",
                    "Volume": "volume",
                }
            )
            sub["ticker"] = ticker
            records.append(sub)
        frame = pd.concat(records)
        frame.index.name = "date"
        return frame.reset_index().set_index(["date", "ticker"]).sort_index()


@dataclass(slots=True)
class PolygonProvider:
    api_key: str
    name: str = "polygon"

    def get_ohlcv(self, tickers: list[str], start: date | str, end: date | str | None) -> pd.DataFrame:
        raise NotImplementedError(
            "PolygonProvider defines the abstraction layer; add authenticated REST calls here."
        )


@dataclass(slots=True)
class AlphaVantageProvider:
    api_key: str
    name: str = "alpha_vantage"

    def get_ohlcv(self, tickers: list[str], start: date | str, end: date | str | None) -> pd.DataFrame:
        raise NotImplementedError(
            "AlphaVantageProvider defines the abstraction layer; add authenticated REST calls here."
        )

