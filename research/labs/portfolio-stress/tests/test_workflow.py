import json
from pathlib import Path
import subprocess
import sys

import matplotlib.image as mpimg
import numpy as np
import pandas as pd
import pytest

from risk_engine.main import run


PROJECT = Path(__file__).resolve().parents[1]


def test_generated_data_and_full_cli(tmp_path):
    data = tmp_path / "sample.csv"
    command = [sys.executable, str(PROJECT / "data/generate_sample_data.py"),
               "--output", str(data), "--observations", "120"]
    subprocess.run(command, check=True)
    first = data.read_bytes()
    subprocess.run(command, check=True)
    assert data.read_bytes() == first

    config = json.loads((PROJECT / "config/default_config.json").read_text())
    config["simulation"].update(paths=200, horizon_days=3)
    config["data"]["path"] = "sample.csv"
    config["output_dir"] = "reports"
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps(config))
    subprocess.run([sys.executable, "-m", "risk_engine.main", "--config", str(settings)], cwd=tmp_path, check=True)
    report, = (tmp_path / "reports").iterdir()
    curves = pd.read_csv(report / "tables/equity_paths.csv.gz").set_index(["scenario", "path"])
    outcomes = pd.read_csv(report / "tables/path_outcomes.csv").set_index(["scenario", "path"])
    assert curves.shape == (800, 4)
    pd.testing.assert_index_equal(curves.index, outcomes.index)
    np.testing.assert_allclose(curves["day_3"], outcomes["terminal_value"])
    np.testing.assert_allclose(100 * (1 - curves / curves.cummax(axis=1)).max(axis=1), outcomes["max_drawdown_pct"])
    summary = pd.read_csv(report / "tables/scenario_summary.csv").set_index("scenario")
    tails = pd.read_csv(report / "tables/tail_risk.csv")
    for row in tails.itertuples():
        losses = outcomes.loc[row.scenario, "terminal_loss"]
        np.testing.assert_allclose(losses.quantile(row.confidence), row.var_currency)
        np.testing.assert_allclose(losses[losses >= losses.quantile(row.confidence)].mean(), row.es_currency)
        assert summary.loc[row.scenario, "worst_max_drawdown_pct"] == pytest.approx(
            outcomes.loc[row.scenario, "max_drawdown_pct"].max())
    assert len(tails) == 8
    metadata = json.loads((report / "run_metadata.json").read_text())
    assert metadata["aligned_return_rows"] == 120
    assert metadata["config"] == config
    assert len(metadata["scenario_models"]) == 4
    assert set(p.stem for p in (report / "figures").glob("*.png")) == {
        "equity_paths", "terminal_value", "terminal_losses", "maximum_drawdowns", "tail_risk",
    }
    for image in (report / "figures").glob("*.png"):
        pixels = mpimg.imread(image)
        assert pixels.shape[0] >= 600 and pixels.std() > 0.02

    # A failure in a later scenario must leave the previously published run intact.
    config["scenarios"][-1]["volatility_multiplier"] = 0
    settings.write_text(json.dumps(config))
    with pytest.raises(ValueError, match="Volatility multipliers"):
        run(settings)
    assert list((tmp_path / "reports").iterdir()) == [report]
