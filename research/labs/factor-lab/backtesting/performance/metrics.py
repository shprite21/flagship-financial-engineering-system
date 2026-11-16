"""Institutional performance metrics."""

from __future__ import annotations

import numpy as np
import pandas as pd


def annualized_return(returns: pd.Series, periods_per_year: int = 252) -> float:
    clean = returns.dropna()
    if clean.empty:
        return 0.0
    total = float((1 + clean).prod())
    years = len(clean) / periods_per_year
    return total ** (1 / years) - 1 if years > 0 else 0.0


def annualized_volatility(returns: pd.Series, periods_per_year: int = 252) -> float:
    return float(returns.dropna().std() * np.sqrt(periods_per_year))


def sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.0, periods_per_year: int = 252) -> float:
    excess = returns.dropna() - risk_free_rate / periods_per_year
    vol = excess.std()
    return float(excess.mean() / vol * np.sqrt(periods_per_year)) if vol and not np.isnan(vol) else 0.0


def sortino_ratio(returns: pd.Series, periods_per_year: int = 252) -> float:
    downside = returns[returns < 0].std()
    return float(returns.mean() / downside * np.sqrt(periods_per_year)) if downside and not np.isnan(downside) else 0.0


def max_drawdown(returns: pd.Series) -> float:
    wealth = (1 + returns.fillna(0.0)).cumprod()
    drawdown = wealth.div(wealth.cummax()).sub(1.0)
    return float(drawdown.min())


def calmar_ratio(returns: pd.Series, periods_per_year: int = 252) -> float:
    mdd = abs(max_drawdown(returns))
    return annualized_return(returns, periods_per_year) / mdd if mdd else 0.0


def alpha_beta(
    returns: pd.Series,
    benchmark_returns: pd.Series,
    periods_per_year: int = 252,
) -> tuple[float, float]:
    aligned = pd.concat([returns, benchmark_returns], axis=1).dropna()
    if len(aligned) < 3:
        return 0.0, 0.0
    y = aligned.iloc[:, 0].to_numpy()
    x = np.column_stack([np.ones(len(aligned)), aligned.iloc[:, 1].to_numpy()])
    intercept, beta = np.linalg.lstsq(x, y, rcond=None)[0]
    return float(intercept * periods_per_year), float(beta)


def information_ratio(active_returns: pd.Series, periods_per_year: int = 252) -> float:
    tracking_error = active_returns.dropna().std()
    if not tracking_error or np.isnan(tracking_error):
        return 0.0
    return float(active_returns.mean() / tracking_error * np.sqrt(periods_per_year))


def hit_ratio(returns: pd.Series) -> float:
    clean = returns.dropna()
    return float((clean > 0).mean()) if len(clean) else 0.0


def performance_summary(
    returns: pd.Series,
    benchmark_returns: pd.Series | None = None,
    periods_per_year: int = 252,
) -> dict[str, float]:
    summary = {
        "cagr": annualized_return(returns, periods_per_year),
        "volatility": annualized_volatility(returns, periods_per_year),
        "sharpe": sharpe_ratio(returns, periods_per_year=periods_per_year),
        "sortino": sortino_ratio(returns, periods_per_year),
        "calmar": calmar_ratio(returns, periods_per_year),
        "max_drawdown": max_drawdown(returns),
        "hit_ratio": hit_ratio(returns),
    }
    if benchmark_returns is not None:
        alpha, beta = alpha_beta(returns, benchmark_returns, periods_per_year)
        active = returns.sub(benchmark_returns, fill_value=0.0)
        summary.update({"alpha": alpha, "beta": beta, "information_ratio": information_ratio(active, periods_per_year)})
    return summary

