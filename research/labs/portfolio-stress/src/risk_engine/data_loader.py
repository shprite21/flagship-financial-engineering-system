"""Read a common daily observation grid from a wide CSV."""

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class ReturnHistory:
    """Aligned daily log returns and counts describing preprocessing."""

    log_returns: pd.DataFrame
    input_rows: int
    duplicate_rows_removed: int
    incomplete_return_rows_removed: int


def load_history(
    path: Path | str,
    kind: str,
    date_column: str = "date",
    missing: str = "error",
    duplicates: str = "error",
) -> ReturnHistory:
    """Load prices or decimal simple returns, preserving the price observation grid."""
    if kind not in ("prices", "simple_returns"):
        raise ValueError("kind must be 'prices' or 'simple_returns'")
    if missing not in ("error", "drop") or duplicates not in ("error", "last"):
        raise ValueError("missing must be 'error' or 'drop', duplicates 'error' or 'last'")
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.reader(stream, strict=True)
        header = next(reader, [])
        if date_column not in header or len(header) < 2:
            raise ValueError(f"CSV requires '{date_column}' and at least one constituent")
        if len(set(header)) != len(header) or any(not name.strip() for name in header):
            raise ValueError("CSV column names must be unique and nonempty")
        rows = []
        for row in reader:
            if len(row) != len(header):
                raise ValueError(f"CSV row ending on line {reader.line_num} has the wrong width")
            rows.append(row)
    if not rows:
        raise ValueError("CSV contains a header but no observations")
    raw = pd.DataFrame(rows, columns=header, dtype=str)
    date_text = raw.pop(date_column)
    dates = pd.to_datetime(date_text, format="%Y-%m-%d", errors="coerce")
    bad_dates = dates.isna() | ~date_text.str.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", na=False)
    if bad_dates.any():
        raise ValueError(f"Expected YYYY-MM-DD, found {date_text[bad_dates].iloc[0]!r}")
    raw.index = pd.DatetimeIndex(dates, name=date_column)
    values = pd.DataFrame(index=raw.index)
    for name, column in raw.items():
        tokens = column.str.strip()
        absent = tokens.isin(["", "NA", "NaN", "null"])
        numeric = pd.to_numeric(tokens.mask(absent), errors="coerce").astype(float)
        invalid = ~absent & ~np.isfinite(numeric)
        if invalid.any():
            raise ValueError(f"Invalid numeric value for {name} on {invalid[invalid].index[0].date()}")
        invalid = numeric.le(0 if kind == "prices" else -1)
        if invalid.any():
            rule = "prices must be positive" if kind == "prices" else "simple returns must exceed -100%"
            raise ValueError(f"{name} on {invalid[invalid].index[0].date()}: {rule}")
        values[name] = numeric

    repeats = values.index.duplicated(keep="last")
    if repeats.any() and duplicates == "error":
        raise ValueError(f"Duplicate date {values.index[repeats][0].date()}")
    values = values.loc[~repeats].sort_index()
    if missing == "error" and values.isna().any().any():
        row, col = np.argwhere(values.isna().to_numpy())[0]
        raise ValueError(f"Missing {values.columns[col]} on {values.index[row].date()}")
    if kind == "prices":
        # Differencing first prevents a missing intermediate quote becoming a daily return.
        returns = np.log(values).diff().iloc[1:]
    else:
        returns = np.log1p(values)
    aligned = returns.dropna(how="any")
    if len(aligned) < 2:
        raise ValueError("At least two complete daily return observations are required")
    return ReturnHistory(aligned, len(raw), int(repeats.sum()), len(returns) - len(aligned))
