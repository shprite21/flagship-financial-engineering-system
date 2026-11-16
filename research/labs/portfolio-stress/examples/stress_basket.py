"""Stress the held-out basket returns exported by project 02."""

import argparse
import json
from pathlib import Path

import pandas as pd

from risk_engine.main import run


def stress_basket(export: Path, workspace: Path) -> Path:
    # The basket export writes its trading date as the first CSV column.
    basket = pd.read_csv(export, index_col=0, parse_dates=[0])
    returns = basket[["strategy_return"]].rename(columns={"strategy_return": "Basket"})
    if not isinstance(returns.index, pd.DatetimeIndex) or returns.index.hasnans:
        raise ValueError("Expected dated rows from the basket equity_curve.csv export")

    defaults = Path(__file__).resolve().parents[1] / "config" / "default_config.json"
    config = json.loads(defaults.read_text(encoding="utf-8"))
    config["data"].update(path="basket_returns.csv", label="Held-out ETF basket net returns")
    config["portfolio"]["weights"] = {"Basket": 1.0}
    config["scenarios"] = [{"name": "50% higher volatility", "volatility_multiplier": 1.5}]
    config["output_dir"] = "outputs"

    workspace.mkdir(parents=True, exist_ok=False)
    returns.to_csv(workspace / "basket_returns.csv", index_label="date", date_format="%Y-%m-%d")
    config_path = workspace / "basket_risk.json"
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return run(config_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path, help="Project 02 performance_reports/equity_curve.csv")
    parser.add_argument("workspace", type=Path, help="New directory for risk inputs and results")
    args = parser.parse_args()
    print(stress_basket(args.export, args.workspace))
