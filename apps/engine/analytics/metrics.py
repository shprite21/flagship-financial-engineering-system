"""Performance analytics for systematic trading research."""

from __future__ import annotations

import numpy as np
import pandas as pd


def sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    annualization_factor: int = 252,
) -> float:
    """Annualized Sharpe ratio."""

    excess = returns.dropna() - risk_free_rate / annualization_factor
    volatility = excess.std()
    if volatility == 0 or np.isnan(volatility):
        return float("nan")
    return float(excess.mean() / volatility * np.sqrt(annualization_factor))


def sortino_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    annualization_factor: int = 252,
) -> float:
    """Annualized Sortino ratio using lower-partial second moment.

    Downside deviation includes all observations, with positive excess returns
    contributing zero. It is not the standard deviation conditional on a loss.
    No observed downside makes this ratio undefined (NaN).
    """

    excess = returns.dropna() - risk_free_rate / annualization_factor
    downside = np.sqrt(np.square(excess.clip(upper=0.0)).mean())
    if downside == 0 or np.isnan(downside):
        return float("nan")
    return float(excess.mean() / downside * np.sqrt(annualization_factor))


def drawdown_series(equity_curve: pd.Series, initial_equity: float | None = None) -> pd.Series:
    """Return drawdown series from an equity curve."""

    running_max = equity_curve.cummax()
    if initial_equity is not None:
        running_max = running_max.clip(lower=initial_equity)
    return (equity_curve / running_max - 1.0).rename("drawdown")


def max_drawdown(equity_curve: pd.Series, initial_equity: float | None = None) -> float:
    """Maximum drawdown."""

    if equity_curve.empty:
        return 0.0
    return float(drawdown_series(equity_curve, initial_equity).min())


def calmar_ratio(
    returns: pd.Series,
    equity_curve: pd.Series | None = None,
    annualization_factor: int = 252,
) -> float:
    """Calmar ratio: annualized return divided by absolute max drawdown."""

    clean = returns.dropna()
    if clean.empty:
        return float("nan")
    annualized_return = (1.0 + clean).prod() ** (annualization_factor / len(clean)) - 1.0
    if equity_curve is None:
        equity_curve = (1.0 + clean).cumprod()
    initial_equity = _initial_equity(clean, equity_curve)
    drawdown = abs(max_drawdown(equity_curve, initial_equity))
    if drawdown == 0:
        return float("nan")
    return float(annualized_return / drawdown)


def rolling_sharpe(
    returns: pd.Series,
    window: int = 63,
    annualization_factor: int = 252,
) -> pd.Series:
    """Rolling annualized Sharpe ratio."""

    mean = returns.rolling(window).mean()
    volatility = returns.rolling(window).std().replace(0.0, np.nan)
    return (mean / volatility * np.sqrt(annualization_factor)).rename("rolling_sharpe")


def rolling_returns(returns: pd.Series, window: int = 63) -> pd.Series:
    """Rolling compounded returns."""

    return ((1.0 + returns).rolling(window).apply(np.prod, raw=True) - 1.0).rename(
        "rolling_returns"
    )


def turnover(weights: pd.DataFrame) -> pd.Series:
    """Portfolio turnover from target weights."""

    changes = weights.diff().abs().sum(axis=1)
    if not weights.empty:
        changes.iloc[0] = weights.iloc[0].abs().sum()
    return changes.rename("turnover")


def exposure_analysis(weights: pd.DataFrame, sector_map: dict[str, str] | None = None) -> pd.DataFrame:
    """Compute long, short, gross, net, and optional sector exposures."""

    analysis = pd.DataFrame(
        {
            "long_exposure": weights.clip(lower=0.0).sum(axis=1),
            "short_exposure": weights.clip(upper=0.0).sum(axis=1),
            "gross_exposure": weights.abs().sum(axis=1),
            "net_exposure": weights.sum(axis=1),
        },
        index=weights.index,
    )
    if sector_map:
        sectors = sorted(set(sector_map.values()))
        for sector in sectors:
            members = [symbol for symbol, mapped_sector in sector_map.items() if mapped_sector == sector]
            members = [symbol for symbol in members if symbol in weights.columns]
            if members:
                analysis[f"sector_{sector}_net"] = weights[members].sum(axis=1)
                analysis[f"sector_{sector}_gross"] = weights[members].abs().sum(axis=1)
    return analysis


def rolling_correlations(returns: pd.DataFrame, window: int = 63) -> pd.DataFrame:
    """Average rolling pairwise correlation across a return panel."""

    rows = []
    for index_position in range(window, len(returns) + 1):
        window_returns = returns.iloc[index_position - window : index_position]
        correlation = window_returns.corr()
        upper_triangle = correlation.where(np.triu(np.ones(correlation.shape), k=1).astype(bool))
        rows.append(
            {
                "date": returns.index[index_position - 1],
                "average_pairwise_correlation": float(upper_triangle.stack().mean()),
            }
        )
    if not rows:
        return pd.DataFrame(index=returns.index, columns=["average_pairwise_correlation"])
    return pd.DataFrame(rows).set_index("date")


def factor_decomposition(
    portfolio_returns: pd.Series,
    factor_returns: pd.DataFrame,
) -> pd.Series:
    """Estimate static factor exposures via linear regression."""

    aligned = pd.concat(
        [portfolio_returns.rename("portfolio"), factor_returns],
        axis=1,
        join="inner",
    ).dropna()
    if aligned.empty:
        return pd.Series(dtype=float)
    y = aligned["portfolio"].to_numpy()
    x = aligned.drop(columns="portfolio").to_numpy()
    x = np.column_stack([np.ones(len(x)), x])
    coefficients = np.linalg.lstsq(x, y, rcond=None)[0]
    return pd.Series(coefficients, index=["alpha", *aligned.drop(columns="portfolio").columns])


def aggregate_metrics(
    returns: pd.Series,
    equity_curve: pd.Series | None = None,
    annualization_factor: int = 252,
) -> dict[str, float]:
    """Generate a compact performance metric dictionary."""

    clean = returns.dropna()
    if equity_curve is None:
        equity_curve = (1.0 + clean).cumprod()
    if clean.empty:
        return {
            "total_return": 0.0,
            "annualized_return": 0.0,
            "annualized_volatility": 0.0,
            "sharpe": float("nan"),
            "sortino": float("nan"),
            "calmar": float("nan"),
            "max_drawdown": 0.0,
            "hit_rate": 0.0,
        }

    total_return = float((1.0 + clean).prod() - 1.0)
    annualized_return = float((1.0 + clean).prod() ** (annualization_factor / len(clean)) - 1.0)
    annualized_volatility = float(clean.std() * np.sqrt(annualization_factor))
    return {
        "total_return": total_return,
        "annualized_return": annualized_return,
        "annualized_volatility": annualized_volatility,
        "sharpe": sharpe_ratio(clean, annualization_factor=annualization_factor),
        "sortino": sortino_ratio(clean, annualization_factor=annualization_factor),
        "calmar": calmar_ratio(clean, equity_curve, annualization_factor),
        "max_drawdown": max_drawdown(equity_curve, _initial_equity(clean, equity_curve)),
        "hit_rate": float((clean > 0).mean()),
        "skew": float(clean.skew()),
        "kurtosis": float(clean.kurtosis()),
    }


def _initial_equity(returns: pd.Series, equity_curve: pd.Series) -> float | None:
    """Recover pre-return NAV when the supplied curve starts after return zero."""
    if returns.empty or equity_curve.empty:
        return None
    # A caller may explicitly include the initial NAV as an additional point.
    if len(equity_curve) == len(returns) + 1:
        return float(equity_curve.iloc[0])
    denominator = 1.0 + float(returns.iloc[0])
    if denominator <= 0 or not np.isfinite(denominator):
        return None
    return float(equity_curve.iloc[0]) / denominator


def regime_performance(
    returns: pd.Series,
    regimes: pd.Series,
    annualization_factor: int = 252,
) -> pd.DataFrame:
    """Break performance metrics down by market regime."""

    aligned = pd.DataFrame(
        {
            "returns": returns,
            "regime": regimes.reindex(returns.index).ffill(),
        }
    ).dropna()
    rows = []
    for regime, group in aligned.groupby("regime"):
        equity = (1.0 + group["returns"]).cumprod()
        metrics = aggregate_metrics(group["returns"], equity, annualization_factor)
        metrics["regime"] = regime
        metrics["observations"] = float(len(group))
        rows.append(metrics)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index("regime").sort_index()
