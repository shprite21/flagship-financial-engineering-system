"""Post-Earnings Announcement Drift (PEAD) event study framework."""

from __future__ import annotations

import pandas as pd


def standardized_unexpected_earnings(events: pd.DataFrame, rolling_window: int = 8) -> pd.Series:
    """Compute SUE = surprise / rolling std(surprise) by ticker."""

    required = {"ticker", "event_date", "actual_eps", "estimate_eps"}
    missing = required.difference(events.columns)
    if missing:
        raise ValueError(f"Missing PEAD event columns: {sorted(missing)}")
    ordered = events.sort_values(["ticker", "event_date"]).copy()
    ordered["surprise"] = ordered["actual_eps"] - ordered["estimate_eps"]
    sigma = ordered.groupby("ticker")["surprise"].transform(
        lambda values: values.rolling(rolling_window, min_periods=3).std()
    )
    return ordered["surprise"].div(sigma.replace(0, pd.NA)).rename("sue")


def event_study(
    returns: pd.DataFrame,
    events: pd.DataFrame,
    benchmark_returns: pd.Series | None = None,
    pre_window: int = 5,
    post_window: int = 20,
) -> pd.DataFrame:
    """Calculate event-window abnormal returns and CAR for each announcement."""

    output: list[dict[str, object]] = []
    returns = returns.sort_index()
    benchmark = benchmark_returns.reindex(returns.index).fillna(0.0) if benchmark_returns is not None else None

    for row in events.itertuples(index=False):
        event_date = pd.Timestamp(getattr(row, "event_date"))
        ticker = getattr(row, "ticker")
        if ticker not in returns.columns:
            continue
        if event_date not in returns.index:
            event_pos = returns.index.searchsorted(event_date)
            if event_pos >= len(returns.index):
                continue
        else:
            event_pos = returns.index.get_loc(event_date)
        start = max(0, event_pos - pre_window)
        stop = min(len(returns.index), event_pos + post_window + 1)
        window = returns.iloc[start:stop][ticker].copy()
        if benchmark is not None:
            window = window.sub(benchmark.iloc[start:stop], fill_value=0.0)
        car = window.cumsum()
        for offset, value in zip(range(start - event_pos, stop - event_pos), car, strict=False):
            output.append(
                {
                    "event_date": event_date,
                    "ticker": ticker,
                    "relative_day": offset,
                    "cumulative_abnormal_return": value,
                }
            )
    return pd.DataFrame(output)

