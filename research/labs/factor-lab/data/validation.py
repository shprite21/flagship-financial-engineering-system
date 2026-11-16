"""Data validation checks that keep research inputs honest."""

from __future__ import annotations

import pandas as pd

from data.schemas import DataQualityReport


REQUIRED_OHLCV_COLUMNS = {"open", "high", "low", "close", "adj_close", "volume"}


def validate_market_data(frame: pd.DataFrame) -> DataQualityReport:
    issues: list[str] = []
    missing_columns = REQUIRED_OHLCV_COLUMNS.difference(frame.columns)
    if missing_columns:
        issues.append(f"Missing OHLCV columns: {sorted(missing_columns)}")

    duplicate_rows = int(frame.index.duplicated().sum())
    if duplicate_rows:
        issues.append(f"Duplicate date/ticker rows: {duplicate_rows}")

    numeric = frame[[column for column in REQUIRED_OHLCV_COLUMNS if column in frame.columns]]
    missing_ratio = float(numeric.isna().sum().sum() / max(numeric.size, 1))
    if missing_ratio > 0.02:
        issues.append(f"Missing numeric data ratio exceeds 2%: {missing_ratio:.2%}")

    if {"high", "low"}.issubset(frame.columns) and (frame["high"] < frame["low"]).any():
        issues.append("High price below low price for at least one row.")

    if "volume" in frame.columns and (frame["volume"] < 0).any():
        issues.append("Negative volume detected.")

    return DataQualityReport(
        passed=not issues,
        rows=len(frame),
        missing_ratio=missing_ratio,
        duplicate_rows=duplicate_rows,
        issues=issues,
    )

