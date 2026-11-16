"""Synthetic market and fundamental data for examples, tests, and dashboards."""

from __future__ import annotations

import numpy as np
import pandas as pd


DEFAULT_TICKERS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "JPM",
    "XOM",
    "UNH",
    "PG",
    "HD",
    "CAT",
]

DEFAULT_SECTORS = {
    "AAPL": "Technology",
    "MSFT": "Technology",
    "NVDA": "Technology",
    "AMZN": "Consumer Discretionary",
    "GOOGL": "Communication Services",
    "META": "Communication Services",
    "JPM": "Financials",
    "XOM": "Energy",
    "UNH": "Health Care",
    "PG": "Consumer Staples",
    "HD": "Consumer Discretionary",
    "CAT": "Industrials",
}


def generate_market_panel(
    tickers: list[str] | None = None,
    periods: int = 756,
    seed: int = 7,
    start: str = "2021-01-01",
) -> pd.DataFrame:
    """Create reproducible OHLCV data with market, sector, and idiosyncratic structure."""

    tickers = tickers or DEFAULT_TICKERS
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range(start=start, periods=periods)
    n_assets = len(tickers)

    market = rng.normal(0.00035, 0.010, periods)
    sector_names = sorted({DEFAULT_SECTORS.get(ticker, "Other") for ticker in tickers})
    sector_shocks = {
        sector: rng.normal(0.0, 0.006, periods).cumsum() * 0.02
        for sector in sector_names
    }
    idio = rng.normal(0.00005, 0.018, (periods, n_assets))
    beta = rng.uniform(0.75, 1.25, n_assets)
    drift = rng.uniform(-0.00005, 0.00025, n_assets)
    returns = np.empty_like(idio)
    for idx, ticker in enumerate(tickers):
        sector = DEFAULT_SECTORS.get(ticker, "Other")
        returns[:, idx] = beta[idx] * market + sector_shocks[sector] + drift[idx] + idio[:, idx]

    prices = 100 * np.exp(np.cumsum(returns, axis=0))
    rows: list[pd.DataFrame] = []
    for idx, ticker in enumerate(tickers):
        close = pd.Series(prices[:, idx], index=dates)
        overnight = pd.Series(rng.normal(0, 0.004, periods), index=dates)
        open_ = close.shift(1).fillna(close.iloc[0]) * (1 + overnight)
        high = pd.concat([open_, close], axis=1).max(axis=1) * (1 + rng.uniform(0.0, 0.015, periods))
        low = pd.concat([open_, close], axis=1).min(axis=1) * (1 - rng.uniform(0.0, 0.015, periods))
        volume = rng.lognormal(mean=15, sigma=0.35, size=periods).astype(int)
        frame = pd.DataFrame(
            {
                "open": open_.to_numpy(),
                "high": high.to_numpy(),
                "low": low.to_numpy(),
                "close": close.to_numpy(),
                "adj_close": close.to_numpy(),
                "volume": volume,
                "sector": DEFAULT_SECTORS.get(ticker, "Other"),
                "market_cap": close.to_numpy() * rng.uniform(2e8, 2e9),
            },
            index=dates,
        )
        frame["ticker"] = ticker
        rows.append(frame)

    panel = pd.concat(rows)
    panel.index.name = "date"
    return panel.reset_index().set_index(["date", "ticker"]).sort_index()


def generate_fundamentals(
    market_panel: pd.DataFrame,
    seed: int = 11,
    quarterly: bool = True,
) -> pd.DataFrame:
    """Create point-in-time style fundamentals indexed by date and ticker."""

    rng = np.random.default_rng(seed)
    dates = market_panel.index.get_level_values("date").unique()
    step = 63 if quarterly else 21
    fundamental_dates = dates[::step]
    tickers = market_panel.index.get_level_values("ticker").unique().tolist()

    records: list[dict[str, object]] = []
    for ticker in tickers:
        price = market_panel.xs(ticker, level="ticker")["adj_close"].reindex(dates).ffill()
        for current_date in fundamental_dates:
            if current_date not in price.index:
                px = float(price.asof(current_date))
            else:
                px = float(price.loc[current_date])
            shares = rng.uniform(3e8, 5e9)
            market_cap = max(px * shares, 1.0)
            book_value = market_cap / rng.uniform(1.2, 8.0)
            earnings = market_cap * rng.uniform(0.015, 0.08)
            ebitda = market_cap * rng.uniform(0.04, 0.14)
            enterprise_value = market_cap * rng.uniform(0.9, 1.4)
            assets = book_value * rng.uniform(1.6, 3.5)
            debt = assets * rng.uniform(0.05, 0.45)
            gross_profit = assets * rng.uniform(0.08, 0.35)
            accruals = assets * rng.uniform(-0.08, 0.08)
            free_cash_flow = market_cap * rng.uniform(-0.005, 0.06)
            records.append(
                {
                    "date": current_date,
                    "ticker": ticker,
                    "book_value": book_value,
                    "earnings": earnings,
                    "ebitda": ebitda,
                    "enterprise_value": enterprise_value,
                    "market_cap": market_cap,
                    "assets": assets,
                    "debt": debt,
                    "gross_profit": gross_profit,
                    "accruals": accruals,
                    "free_cash_flow": free_cash_flow,
                    "roe": earnings / max(book_value, 1.0),
                }
            )
    return pd.DataFrame.from_records(records).set_index(["date", "ticker"]).sort_index()


def adjusted_close_wide(panel: pd.DataFrame) -> pd.DataFrame:
    """Return wide adjusted close prices from a normalized market panel."""

    return panel["adj_close"].unstack("ticker").sort_index()
