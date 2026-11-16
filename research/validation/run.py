"""Run the terminal's historical strategy experiments on an authenticated local panel."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd
import optuna
from threadpoolctl import threadpool_limits

HERE = Path(__file__).resolve().parent
ENGINE = HERE.parents[1] / "apps" / "engine"
sys.path.insert(0, str(ENGINE))

from qresearch.basket import BasketConfig, basket
from qresearch.regimes import RegimeConfig, regimes


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def load_snapshot(path, manifest_path, protocol):
    source = json.loads(manifest_path.read_text(encoding="utf-8"))
    observed = digest(path)
    if observed != protocol["snapshot_sha256"] or observed != source["processed_hashes"][protocol["snapshot_file"]]:
        raise ValueError("The panel SHA-256 differs from this protocol or the source manifest.")
    panel = pd.read_csv(path)
    dates = pd.to_datetime(panel.date, format="%Y-%m-%d", errors="raise")
    if not dates.is_monotonic_increasing or dates.duplicated().any() or len(panel) != source["common_sessions"]:
        raise ValueError("Unordered, duplicate or missing dates in the historical snapshot.")
    assets = sorted(set(protocol["regime"]["assets"]) | set(protocol["cointegration"]["assets"]))
    prices = panel[assets].to_numpy(dtype=float)
    if not np.isfinite(prices).all() or (prices <= 0).any():
        raise ValueError("Positive finite prices required on every session.")
    source_assets = {item["symbol"]: item for item in source["symbols"]}
    relevant = []
    for symbol in assets:
        item = source_assets[symbol]
        if item["currency"] != "USD" or item["missing_benchmark_sessions"]:
            raise ValueError(f"Unusable historical coverage for {symbol}.")
        relevant.append({key: item[key] for key in ("symbol", "url", "params", "sha256")})
    test_dates = dates.between(protocol["oos_start"], protocol["oos_end"])
    selected = np.flatnonzero(test_dates)
    training = protocol["training_sessions"]
    if not len(selected) or selected[0] < training or panel.date.iloc[selected[-1]] != protocol["oos_end"]:
        raise ValueError("The snapshot does not cover the stipulated training and test dates.")
    window = panel.iloc[selected[0] - training:selected[-1] + 1].reset_index(drop=True)
    provenance = dict(source=source["source"], retrieved_utc=source["retrieved_utc"],
                      is_point_in_time=source["source_is_point_in_time"], panel_sha256=observed,
                      manifest_sha256=digest(manifest_path), symbols=relevant,
                      oos_first=window.date.iloc[training], oos_last=window.date.iloc[-1],
                      formation_first=window.date.iloc[0], formation_last=window.date.iloc[training - 1])
    return window, provenance


def ledger(account, fold, expected_bps):
    """Extract daily realized two-sided traded notional and fixed-fill cost sensitivity."""
    fills = defaultdict(float)
    for trade in account["trades"]:
        if trade["accepted"]:
            # Remove signed fill slippage to express notional at the reference mark.
            mid = trade["price"] / (1 + np.sign(trade["quantity"]) * expected_bps / 10000)
            fills[trade["date"]] += abs(trade["quantity"]) * mid
    bills = pd.DataFrame(account["equity"]).set_index("date")
    net = bills.equity
    execution_cost = bills.commission + bills.slippage
    previous = net.shift(1)
    daily = pd.DataFrame({
        "net_return": net.pct_change(),
        "return_without_execution_cost": (net + execution_cost).pct_change(),
        "return_double_execution_cost": (net - execution_cost).pct_change(),
        "turnover": pd.Series(dict(fills), dtype=float).reindex(net.index, fill_value=0) / previous,
        "execution_cost_fraction": execution_cost.diff() / previous,
        "borrow_cost_fraction": bills.borrow.diff() / previous,
        "fold": fold,
    }).iloc[1:]
    if not np.isfinite(daily.to_numpy()).all() or (daily.turnover < 0).any():
        raise ValueError("Invalid account ledger.")
    return daily


def sharpe(returns):
    volatility = returns.std(ddof=1)
    return float(np.sqrt(252) * returns.mean() / volatility) if volatility > 1e-12 else None


def statistics(returns):
    returns = np.asarray(returns, dtype=float)
    nav = np.r_[1., (1. + returns).cumprod()]
    return dict(sharpe=sharpe(returns), cagr=float(nav[-1] ** (252 / len(returns)) - 1),
                max_drawdown=float((nav / np.maximum.accumulate(nav) - 1).min()),
                total_return=float(nav[-1] - 1))


def paired_inference(baseline, candidate, config):
    """Paired circular blocks preserve both timing and synchronous strategy exposures."""
    base = np.asarray(baseline)
    alt = np.asarray(candidate)
    rng = np.random.default_rng(config["seed"])
    width = config["block_sessions"]
    blocks = (len(base) + width - 1) // width
    samples = []
    for _ in range(config["replications"]):
        starts = rng.integers(0, len(base), blocks)
        indices = ((starts[:, None] + np.arange(width)) % len(base)).ravel()[:len(base)]
        b, a = sharpe(base[indices]), sharpe(alt[indices])
        if b is not None and a is not None:
            samples.append(a - b)
    observed = None if sharpe(base) is None or sharpe(alt) is None else sharpe(alt) - sharpe(base)
    # 97.5% each yields >=95% nominal simultaneous coverage for the two comparisons.
    interval = None
    if len(samples) == config["replications"]:
        interval = np.quantile(samples, [.0125, .9875]).tolist()
    return dict(candidate_minus_baseline_sharpe=observed,
                bonferroni_97_5_percent_interval=interval,
                defined_replicates=len(samples), **config)


def compare(baseline, candidate, config):
    if not baseline.index.equals(candidate.index) or baseline.index.has_duplicates:
        raise ValueError("Baseline and candidate calendars diverge.")
    results = {}
    for name, daily in (("baseline", baseline), ("candidate", candidate)):
        results[name] = dict(
            net=statistics(daily.net_return),
            zero_bps_reexecuted=statistics(daily.reexecuted_zero_bps_return),
            ten_bps_reexecuted=statistics(daily.reexecuted_ten_bps_return),
            zero_bps_fixed_fills=statistics(daily.return_without_execution_cost),
            ten_bps_fixed_fills=statistics(daily.return_double_execution_cost),
            annual_traded_notional_over_equity=float(daily.turnover.mean() * 252),
            sessions_with_fills=int((daily.turnover > 0).sum()),
            annual_mean_execution_cost_fraction=float(daily.execution_cost_fraction.mean() * 252),
            annual_mean_borrow_cost_fraction=float(daily.borrow_cost_fraction.mean() * 252))
        results[name]["calendar_year_returns"] = {
            year: statistics(part.net_return)["total_return"]
            for year, part in daily.groupby(daily.index.str[:4])
        }
    results["paired_inference"] = paired_inference(baseline.net_return, candidate.net_return, config)
    results["block_length_sensitivity"] = [
        paired_inference(baseline.net_return, candidate.net_return, dict(config, block_sessions=width))
        for width in (5, 60)
    ]
    return results


def evaluate(p, frame, account):
    fixed = dict(**account, seed=p["seed"])
    slip = account["slippage_bps"]
    reg = p["regime"]
    regime_config = RegimeConfig(**fixed, initial_train=p["training_sessions"],
                                 refit_every=reg["refit_every"], iterations=reg["iterations"])
    history = dict(assets=reg["assets"], currency="USD", synthetic=False)
    result = regimes(regime_config, history, frame)
    rb = ledger(result["baseline_account"], 0, slip)
    rc = ledger(result["results"]["HMM allocation"], 0, slip)
    fit_rows = [{
        "last_training_close": fit["last_date"], "next_eligible_fill": fit["first_eligible_fill"],
        "observations": fit["observations"], "converged": fit["converged"],
        "last_log_likelihood_change": fit["log_likelihood"][-1] - fit["log_likelihood"][-2],
        "cointegration_eligible": fit["cointegration"]["eligible"]
    } for fit in result["fits"]]

    pair = p["cointegration"]
    basket_config = BasketConfig(**fixed, train_window=p["training_sessions"],
                                 **{key: pair[key] for key in ("method", "validation_window", "test_window", "trials")})
    result = basket(basket_config, dict(history, assets=pair["assets"]), frame)
    folds = result["folds"]
    def chain(name):
        return pd.concat([ledger(f["accounts"][name], f["fold"], slip) for f in folds])
    pb, pc = chain("baseline"), chain("optimized")
    # Cross-check saved study equity against the actual module output.
    for totals, daily in zip(result["results"]["Basket comparison"]["aggregate"], (pb, pc)):
        if not np.isclose(totals["total_return"], statistics(daily.net_return)["total_return"]):
            raise ValueError("Chained daily ledger does not match basket module equity.")
    if not rb.index.equals(pb.index):
        raise ValueError("The two experiments must cover the same OOS calendar.")

    fold_rows = []
    for fold in folds:
        keep = ("fold", "calibration_first", "calibration_last", "validation_first", "validation_last",
                "test_first", "test_last", "selected", "evaluation_status")
        fold_rows.append({**{k: fold[k] for k in keep},
                          "outer_eg_p": fold["outer_cointegration"].get("p_value"),
                          "inner_eg_p": fold["inner_cointegration"].get("p_value"),
                          "trial_count": sum(row["fold"] == fold["fold"]
                                             for row in result["results"]["Basket comparison"]["trials"])})
    ledgers = {("regime", "baseline"): rb, ("regime", "candidate"): rc,
               ("cointegration", "baseline"): pb, ("cointegration", "candidate"): pc}
    return ledgers, dict(regime=fit_rows, cointegration=fold_rows)


def run(snapshot, manifest, output):
    protocol_path = HERE / "protocol.json"
    p = json.loads(protocol_path.read_text(encoding="utf-8"))
    frame, provenance = load_snapshot(snapshot, manifest, p)
    ledgers, folds = evaluate(p, frame, p["account"])
    for cost_scale, column in ((0, "reexecuted_zero_bps_return"), (2, "reexecuted_ten_bps_return")):
        cost_account = dict(p["account"])
        for field in ("commission_bps", "slippage_bps"):
            cost_account[field] *= cost_scale
        sensitivity, _ = evaluate(p, frame, cost_account)
        for key, daily in ledgers.items():
            daily[column] = sensitivity[key].net_return
    output.mkdir(parents=True, exist_ok=True)
    logs = [daily.assign(study=study, policy=name).reset_index() for (study, name), daily in ledgers.items()]
    daily_path = output / "daily.csv"
    pd.concat(logs).to_csv(daily_path, index=False, float_format="%.15g", lineterminator="\n")
    diagnostics = output / "folds.json"
    write_json(diagnostics, folds)
    source_paths = [
        "basket.py", "regimes.py", "cointegration.py", "equity_account.py",
        "origins/arbitrage/signals.py", "origins/arbitrage/spread_builder.py",
        "origins/regime/strategies/base.py", "origins/regime/strategies/momentum.py",
        "origins/regime/strategies/mean_reversion.py",
    ]
    import qresearch.regimes
    engine = Path(qresearch.regimes.__file__).parent
    summary = dict(
        study=p["study"], input=provenance, sessions=len(ledgers["regime", "candidate"]),
        **{study: compare(ledgers[study, "baseline"], ledgers[study, "candidate"], p["bootstrap"])
           for study in ("regime", "cointegration")},
        python=platform.python_version(),
        libraries={k: version(k) for k in ("numpy", "pandas", "scipy", "statsmodels", "hmmlearn",
                                           "optuna", "pydantic", "scikit-learn")},
        engine_source_sha256={f"qresearch/{path}": digest(engine / path) for path in source_paths},
        study_source_sha256={"run.py": digest(Path(__file__)), "protocol.json": digest(protocol_path)},
        output_sha256={f.name: digest(f) for f in (daily_path, diagnostics)})
    write_json(output / "summary.json", summary)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=HERE / "results")
    args = parser.parse_args()
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    with threadpool_limits(limits=1):
        result = run(args.snapshot, args.manifest, args.output)
    for module in ("regime", "cointegration"):
        print(module, json.dumps(result[module]))
