"""Finite-sample terminal loss statistics and path-dependent drawdowns."""

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RiskReport:
    """Scenario summaries, empirical tail estimates and the underlying path outcomes."""

    summary: dict[str, float]
    tails: list[dict[str, float | int]]
    terminal_values: np.ndarray
    max_drawdowns: np.ndarray


def measure_risk(wealth: np.ndarray, confidence_levels: Sequence[float] = (0.95, 0.99)) -> RiskReport:
    """Measure terminal loss relative to day zero and peak-to-trough drawdown magnitudes."""
    wealth = np.asarray(wealth, dtype=float)
    if wealth.ndim != 2 or wealth.shape[0] < 1 or wealth.shape[1] < 2:
        raise ValueError("Wealth must contain at least one path, day zero and one forecast day")
    initial = wealth[0, 0]
    if initial <= 0 or not np.isfinite(wealth).all() or (wealth < 0).any() or (wealth[:, 0] != initial).any():
        raise ValueError("Paths must be finite, nonnegative and share positive initial capital")
    levels = np.asarray(confidence_levels, dtype=float)
    if levels.ndim != 1 or not len(levels) or not np.all((0 < levels) & (levels < 1)):
        raise ValueError("Confidence levels must be a nonempty list of probabilities strictly between 0 and 1")
    if len(np.unique(levels)) != len(levels):
        raise ValueError("Confidence levels must be unique")
    terminal = wealth[:, -1].copy()
    losses = initial - terminal
    peaks = np.maximum.accumulate(wealth, axis=1)
    drawdowns = (1 - wealth / peaks).max(axis=1)
    summary = {
        "mean_terminal_value": float(terminal.mean()),
        "median_terminal_value": float(np.median(terminal)),
        "mean_terminal_pnl": float(-losses.mean()),
        "median_terminal_pnl": float(-np.median(losses)),
        "mean_terminal_loss": float(losses.mean()),
        "probability_of_loss": float(np.mean(losses > 0)),
        "mean_max_drawdown_pct": float(100 * drawdowns.mean()),
        "median_max_drawdown_pct": float(100 * np.median(drawdowns)),
        "worst_max_drawdown_pct": float(100 * drawdowns.max()),
    }
    tails = []
    for level, threshold in zip(levels, np.quantile(losses, levels, method="linear")):
        tail = losses[losses >= threshold]
        es = float(tail.mean())
        tails.append({
            "confidence": float(level), "tail_paths": int(tail.size),
            "var_currency": float(threshold), "es_currency": es,
            "var_pct": float(100 * threshold / initial), "es_pct": float(100 * es / initial),
        })
    return RiskReport(summary, tails, terminal, drawdowns)
