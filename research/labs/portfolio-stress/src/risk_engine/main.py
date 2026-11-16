"""Command-line workflow for estimation, simulation, reporting and figure export."""

import argparse
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import platform
from tempfile import TemporaryDirectory

import matplotlib
import numpy as np
import pandas as pd
import scipy

from .covariance import Moments, correlation_matrix, estimate_moments, factor_covariance
from .data_loader import load_history
from .portfolio import equity_paths, resolve_weights
from .risk_metrics import RiskReport, measure_risk
from .simulator import simulate_log_returns
from .stress_testing import Scenario
from .visualization import save_figures


def _section(value: object, name: str, required: set[str], optional: set[str]) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object")
    absent = required.difference(value)
    unknown = set(value).difference(required | optional)
    if absent or unknown:
        raise ValueError(f"Invalid {name} keys: missing {sorted(absent)}, unrecognized {sorted(unknown)}")
    return value


def _read_config(path: Path) -> dict:
    config = _section(json.loads(path.read_text(encoding="utf-8")), "configuration",
                      {"data", "portfolio", "simulation", "scenarios", "confidence_levels", "output_dir"}, set())
    data = _section(config["data"], "data", {"path", "kind", "label"}, {"date_column", "missing", "duplicates"})
    portfolio = _section(config["portfolio"], "portfolio", {"initial_capital", "currency"}, {"weights"})
    _section(config["simulation"], "simulation", {"paths", "horizon_days", "seed"}, set())
    for name, value in (("data.path", data["path"]), ("data.label", data["label"]),
                        ("currency", portfolio["currency"]), ("output_dir", config["output_dir"])):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name} must be a nonempty string")
    capital = portfolio["initial_capital"]
    if isinstance(capital, bool) or not isinstance(capital, (int, float)):
        raise ValueError("initial_capital must be a number")
    if not isinstance(config["scenarios"], list):
        raise ValueError("scenarios must be a list of stress definitions")
    if not isinstance(config["confidence_levels"], list):
        raise ValueError("confidence_levels must be a list of probabilities")
    if any(isinstance(c, bool) or not isinstance(c, (int, float)) for c in config["confidence_levels"]):
        raise ValueError("confidence_levels must contain numeric probabilities")
    return config


def _scenarios(definitions: list) -> list[Scenario]:
    scenarios = [Scenario("Baseline")]
    seen = {"baseline"}
    for definition in definitions:
        scenario = Scenario(**_section(definition, "scenario", {"name"}, {"volatility_multiplier", "correlation_blend"}))
        if not isinstance(scenario.name, str) or scenario.name.strip().casefold() in seen:
            raise ValueError("Scenario names must be distinct strings; Baseline is reserved")
        seen.add(scenario.name.strip().casefold())
        scenarios.append(scenario)
    return scenarios


def _write_tables(directory: Path, reports: dict[str, RiskReport], initial: float) -> None:
    summary = pd.DataFrame({name: r.summary for name, r in reports.items()}).T.rename_axis("scenario")
    for metric in ("mean_terminal_loss", "worst_max_drawdown_pct"):
        summary[f"delta_{metric}"] = summary[metric] - summary.loc["Baseline", metric]
    summary.to_csv(directory / "scenario_summary.csv")
    tails = pd.DataFrame([{"scenario": name, **record}
                          for name, report in reports.items() for record in report.tails])
    base = tails[tails["scenario"] == "Baseline"].set_index("confidence")
    for metric in ("var_currency", "es_currency"):
        tails[f"delta_{metric}"] = tails[metric] - tails["confidence"].map(base[metric])
    tails.to_csv(directory / "tail_risk.csv", index=False)
    outcomes = [pd.DataFrame({
        "scenario": name, "path": np.arange(len(report.terminal_values)),
        "terminal_value": report.terminal_values, "terminal_loss": initial - report.terminal_values,
        "max_drawdown_pct": 100 * report.max_drawdowns,
    }) for name, report in reports.items()]
    pd.concat(outcomes, ignore_index=True).to_csv(directory / "path_outcomes.csv", index=False)


def _simulate_scenarios(config: dict, moments: Moments, weights: np.ndarray, stage: Path) -> dict:
    portfolio = config["portfolio"]
    initial = portfolio["initial_capital"]
    reports = {}
    scenario_models = {}
    tables = stage / "tables"
    tables.mkdir()
    with gzip.GzipFile(tables / "equity_paths.csv.gz", "wb", compresslevel=4, mtime=0) as stream:
        for scenario in _scenarios(config["scenarios"]):
            target = scenario.covariance(moments)
            model = factor_covariance(target)
            draws = simulate_log_returns(moments.mean, model.lower, **config["simulation"])
            wealth = equity_paths(draws, weights, initial)
            del draws
            reports[scenario.name] = measure_risk(wealth, config["confidence_levels"])
            if scenario.name == "Baseline":
                baseline_paths = wealth
            curves = pd.DataFrame(wealth, columns=[f"day_{day}" for day in range(wealth.shape[1])])
            curves.insert(0, "path", np.arange(len(wealth)))
            curves.insert(0, "scenario", scenario.name)
            curves.to_csv(stream, index=False, header=scenario.name == "Baseline", compression=None)
            scenario_models[scenario.name] = {
                "target_covariance": target.tolist(), "effective_covariance": model.effective.tolist(),
                "target_min_eigenvalue": model.min_eigenvalue, "max_asymmetry": model.max_asymmetry,
                "active_diagonal_shift": model.diagonal_shift,
            }
    _write_tables(tables, reports, initial)
    save_figures(stage / "figures", reports, baseline_paths, config["data"]["label"], portfolio["currency"])
    return scenario_models


def run(config_path: Path | str) -> Path:
    """Run all configured scenarios and publish one self-contained output directory."""
    path = Path(config_path).resolve()
    config = _read_config(path)
    data = config["data"]
    input_path = path.parent / data["path"]
    if not input_path.is_file():
        raise ValueError(f"Missing input CSV {input_path}. For the demo run python data/generate_sample_data.py")
    digest = hashlib.sha256(input_path.read_bytes()).hexdigest()
    history = load_history(input_path, data["kind"], data.get("date_column", "date"),
                           data.get("missing", "error"), data.get("duplicates", "error"))
    moments = estimate_moments(history.log_returns)
    weights = resolve_weights(moments.assets, config["portfolio"].get("weights"))
    metadata = {
        "config": config, "input_sha256": digest, "input_rows": history.input_rows,
        "duplicate_rows_removed": history.duplicate_rows_removed,
        "incomplete_return_rows_removed": history.incomplete_return_rows_removed,
        "aligned_return_rows": len(history.log_returns),
        "first_return_date": str(history.log_returns.index[0].date()),
        "last_return_date": str(history.log_returns.index[-1].date()),
        "assets": moments.assets, "weights": weights.tolist(), "daily_log_mean": moments.mean.tolist(),
        "sample_covariance": moments.covariance.tolist(),
        "sample_correlation": correlation_matrix(moments.covariance).tolist(),
        "bit_generator": "PCG64",
        "versions": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
                     "scipy": scipy.__version__, "matplotlib": matplotlib.__version__},
    }
    root = (path.parent / config["output_dir"]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    # Publish only after every output succeeds. Concurrent runs have distinct directories.
    with TemporaryDirectory(dir=root, prefix=".staging-") as temporary:
        stage = Path(temporary) / "report"
        stage.mkdir()
        metadata["scenario_models"] = _simulate_scenarios(config, moments, weights, stage)
        (stage / "run_metadata.json").write_text(json.dumps(metadata, indent=2, allow_nan=False) + "\n",
                                                 encoding="utf-8")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        destination = root / f"run-{stamp}-{Path(temporary).name.removeprefix('.staging-')}"
        stage.rename(destination)
    return destination


def main() -> None:
    """Parse a research configuration and print the completed report location."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config/default_config.json"))
    args = parser.parse_args()
    try:
        destination = run(args.config)
    except (OSError, ValueError, TypeError, FloatingPointError, csv.Error, np.linalg.LinAlgError) as exc:
        parser.exit(2, f"Risk simulation failed: {exc}\n")
    print(f"Completed research run: {destination}")


if __name__ == "__main__":
    main()
