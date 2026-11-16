"""Rolling walk-forward train/test split utilities."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class WalkForwardWindow:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def rolling_walk_forward_windows(
    index: pd.DatetimeIndex,
    train_size: int = 504,
    test_size: int = 63,
    step_size: int = 63,
) -> list[WalkForwardWindow]:
    windows: list[WalkForwardWindow] = []
    start = 0
    while start + train_size + test_size <= len(index):
        train_start = index[start]
        train_end = index[start + train_size - 1]
        test_start = index[start + train_size]
        test_end = index[start + train_size + test_size - 1]
        windows.append(WalkForwardWindow(train_start, train_end, test_start, test_end))
        start += step_size
    return windows

