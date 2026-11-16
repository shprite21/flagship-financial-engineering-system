"""Reproduce the derivatives experiment and historical portfolio-risk forecasts."""

import argparse
import hashlib
import json
import sys
from math import exp
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest


HERE = Path(__file__).resolve().parent
ASSETS = ["MSFT", "JPM", "XOM", "JNJ", "PG"]
SEED = 53021


def read_panel(path):
    data = pd.read_csv(path, usecols=["date", *ASSETS], parse_dates=["date"])
    if data.date.isna().any() or data.date.duplicated().any() or not data.date.is_monotonic_increasing:
        raise ValueError("Dates must be complete, unique and chronological")
    prices = data[ASSETS].to_numpy(float)
    if not np.isfinite(prices).all() or (prices <= 0).any():
        raise ValueError("All five assets require finite, positive adjusted closes on every date")
    return data.set_index("date").loc[:"2025-12-31", ASSETS]


def risk_study(prices):
    from qresearch.risk_simulation import RiskConfig, covariance_factor, simulate_risk, tail_losses

    nav = 100_000
    window = 252
    paths = 10_000
    confidence = .95
    frame = prices.iloc[-(window + 1):].reset_index()
    frame["date"] = frame.date.dt.strftime("%Y-%m-%d")
    history = {"assets": ASSETS, "synthetic": False, "currency": "USD"}
    cfg = RiskConfig(initial_value=nav, paths=paths, horizon=21, confidence=confidence, seed=SEED)
    output = simulate_risk(cfg, history, frame)

    # Each prediction uses exactly 252 completed close-to-close observations.
    # No re-estimation occurs on the evaluation date. Common variates keep
    # forecast changes driven by calibration, rather than by a changing seed.
    returns = np.log(prices).diff().dropna()
    innovations = np.random.default_rng(SEED).standard_normal((paths, len(ASSETS)))
    realized, forecast_var, forecast_es = [], [], []
    dates = returns.loc["2020-01-01":"2025-12-31"].index
    if not len(dates) or dates[0].strftime("%Y-%m-%d") != "2020-01-02" or dates[-1] != pd.Timestamp("2025-12-31"):
        raise ValueError("The reference holdout requires prices spanning 2020-01-02 through 2025-12-31")
    for date in dates:
        day = returns.index.get_loc(date)
        if day < window:
            raise ValueError("At least 252 return observations before the holdout are required")
        train = returns.iloc[day-window:day].to_numpy()
        _, factor, _ = covariance_factor(np.cov(train, rowvar=False, ddof=1))
        sims = np.expm1(train.mean(axis=0) + innovations @ factor.T)
        var, es = tail_losses(-nav * sims.mean(axis=1), confidence)
        if date in (dates[0], dates[-1]):
            train_frame = prices.loc[prices.index < date].tail(window+1).reset_index()
            one_day = cfg.model_copy(update={"horizon": 1})
            check = simulate_risk(one_day, history, train_frame)["results"]["Baseline"]["metrics"]
            if not np.allclose([var, es], [check["var_loss"], check["expected_shortfall_loss"]], atol=1e-8, rtol=0):
                raise RuntimeError("Fast rolling forecast disagrees with integrated one-day risk engine")
        forecast_var.append(var)
        forecast_es.append(es)
        realized.append(-nav * np.expm1(returns.iloc[day].to_numpy()).mean())
    losses = np.array(realized)
    breaches = losses > forecast_var
    n, k = len(losses), int(breaches.sum())
    coverage = binomtest(k, n, 1-confidence)
    interval = coverage.proportion_ci(confidence_level=.95)
    summary = output["results"]["Stress comparison"]["summary"]
    return {
        "assets_equal_dollar": ASSETS, "portfolio_usd": nav, "paths_per_scenario": paths,
        "confidence": confidence, "seed": SEED, "trailing_calibration_returns": window,
        "holdout_one_session": {
            "first": dates[0].date().isoformat(), "last": dates[-1].date().isoformat(),
            "observations": n, "var_exceedances": k, "exceedance_rate": k/n,
            "nominal_exceedance_rate": 1-confidence,
            "adjacent_breach_pairs": int((breaches[1:] & breaches[:-1]).sum()),
            "subsequent_sessions_after_breach": int(breaches[:-1].sum()),
            "binomial_exact_two_sided_p_iid_null": float(coverage.pvalue),
            "exceedance_rate_exact_95pct_interval_iid": [float(interval.low), float(interval.high)],
            "mean_var_usd": float(np.mean(forecast_var)), "mean_es_usd": float(np.mean(forecast_es)),
            "mean_loss_on_var_breaches_usd": float(losses[breaches].mean()) if k else None,
            "mean_forecast_es_on_var_breaches_usd": float(np.asarray(forecast_es)[breaches].mean()) if k else None,
        },
        "terminal_21_session_stress": {
            "calibration_first_price": frame.date.iloc[0], "as_of": frame.date.iloc[-1],
            "config": cfg.model_dump(), "scenarios": [
                {key: row[key] for key in ("scenario", "var_loss", "expected_shortfall_loss",
                                           "median_drawdown_percent", "loss_probability")} for row in summary
            ],
        },
    }


def pricing_checks():
    from qresearch.options import values

    # Dimensioned errors per underlying unit, evaluated away from payoff kinks.
    residual, delta_error, gamma_error = [], [], []
    h = .01
    for spot in (70., 90., 100., 110., 130.):
        for time in (21/252, .5, 1.):
            for sigma in (.15, .35):
                def quote(s, option="call"):
                    return values(s, 100., time, .02, sigma, option)

                center = quote(spot)
                parity = center["price"] - quote(spot, "put")["price"] - (spot - 100*exp(-.02*time))
                up, down = quote(spot+h)["price"], quote(spot-h)["price"]
                residual.append(abs(parity))
                delta_error.append(abs((up-down)/(2*h)-center["delta"]))
                gamma_error.append(abs((up-2*center["price"]+down)/(h*h)-center["gamma"]))
    return {"parameter_sets": len(residual), "spot_step": h,
            "max_put_call_parity_error": max(residual), "max_delta_finite_difference_error": max(delta_error),
            "max_gamma_finite_difference_error": max(gamma_error)}


def derivatives_study():
    from qresearch.option_simulation import SimulationConfig, simulate

    config = SimulationConfig(seed=0)
    seeds = range(64)
    rows = []
    for seed in seeds:
        pair = {}
        for label, threshold in [("unhedged", 100_000.), ("delta_hedged", config.hedge_threshold_shares)]:
            cfg = SimulationConfig(seed=seed, hedge_threshold_shares=threshold)
            report = simulate(cfg)["results"]["Options simulation"]
            if label == "unhedged" and any(t["asset"] == "stock" for t in report["trades"]):
                raise RuntimeError("Unhedged control traded the underlying")
            pair[label] = report["metrics"]
        rows.append(pair)
    keys = ["delta_rmse_shares", "hedging_error_rmse", "net_pnl", "max_drawdown_percent",
            "accepted_trades", "rejected_trades", "option_fees", "hedge_fees", "hedge_slippage"]
    headline = {}
    for label in ("unhedged", "delta_hedged"):
        headline[label] = {key: float(np.mean([row[label][key] for row in rows])) for key in keys}
    difference = np.array([row["delta_hedged"]["delta_rmse_shares"] - row["unhedged"]["delta_rmse_shares"]
                           for row in rows])
    rng = np.random.default_rng(SEED)
    bootstrap = rng.choice(difference, (10_000, len(difference)), replace=True).mean(axis=1)
    return {
        "pricing": pricing_checks(), "market_making": {
            "source": "seeded GBM and simulated customer order arrivals",
            "common_seed_first": seeds.start, "common_seed_last": seeds.stop-1, "seed_pairs": len(seeds),
            "hedged_configuration_first_seed": config.model_dump(), "unhedged_threshold_shares": 100_000,
            "mean_across_paths": headline, "mean_paired_delta_rmse_change_shares": float(difference.mean()),
            "mean_paired_delta_rmse_change_bootstrap_95pct": np.quantile(bootstrap, [.025, .975]).tolist(),
            "bootstrap_seed": SEED, "bootstrap_repetitions": 10_000,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prices", required=True, type=Path, help="Private adjusted-close CSV")
    parser.add_argument("--engine", type=Path, default=HERE.parents[1] / "apps" / "engine")
    parser.add_argument("--out", type=Path, default=HERE / "model-results.json")
    args = parser.parse_args()
    sys.path.insert(0, str(args.engine.resolve()))
    prices = read_panel(args.prices)
    result = {
        "schema": 1, "input_sha256": hashlib.sha256(args.prices.read_bytes()).hexdigest(),
        "risk": risk_study(prices), "derivatives": derivatives_study(),
    }
    args.out.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
