"""Independently check the published figures using only Python's standard library."""
import argparse
import csv
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent


def check_equal(a, b, label):
    if a is None or b is None:
        matches = a is None and b is None
    else:
        matches = math.isclose(a, b, abs_tol=1e-10, rel_tol=1e-10)
    if not matches:
        raise ValueError(f"{label}: recalculated {a}, recorded {b}")


def verify(results):
    report = json.loads((results / "summary.json").read_text())
    for root, key in ((results, "output_sha256"), (HERE, "study_source_sha256"),
                      (HERE.parents[1] / "apps/engine", "engine_source_sha256")):
        for name, expected in report[key].items():
            if hashlib.sha256((root / name).read_bytes()).hexdigest() != expected:
                raise ValueError(f"Fingerprint mismatch: {name}")
    with (results / "daily.csv").open(newline="") as file:
        groups = defaultdict(list)
        for row in csv.DictReader(file):
            groups[row["study"], row["policy"]].append(row)
    expected_groups = {(s, p) for s in ("regime", "cointegration") for p in ("baseline", "candidate")}
    if groups.keys() != expected_groups:
        raise ValueError("Missing or unexpected study ledger.")
    calendar = [r["date"] for r in groups["regime", "baseline"]]
    if calendar != sorted(set(calendar)) or (calendar[0], calendar[-1], len(calendar)) != (
        report["input"]["oos_first"], report["input"]["oos_last"], report["sessions"]
    ):
        raise ValueError("Invalid OOS calendar.")
    fields = {
        "net": "net_return",
        "zero_bps_fixed_fills": "return_without_execution_cost",
        "ten_bps_fixed_fills": "return_double_execution_cost",
        "zero_bps_reexecuted": "reexecuted_zero_bps_return",
        "ten_bps_reexecuted": "reexecuted_ten_bps_return",
    }
    for (study, policy), rows in groups.items():
        if [r["date"] for r in rows] != calendar:
            raise ValueError(f"Mismatched OOS dates for {study}/{policy}")
        result = report[study][policy]
        for name, field in fields.items():
            r = [float(row[field]) for row in rows]
            equity = peak = 1.
            drawdown = 0.
            for change in r:
                equity *= 1 + change
                peak = max(equity, peak)
                drawdown = min(drawdown, equity / peak - 1)
            std = statistics.stdev(r)
            sharpe = statistics.mean(r) / std * math.sqrt(252) if std > 1e-12 else None
            measured = dict(sharpe=sharpe, cagr=equity ** (252 / len(r)) - 1,
                            total_return=equity - 1, max_drawdown=drawdown)
            for metric, value in measured.items():
                check_equal(value, result[name][metric], f"{study}/{policy}/{name}/{metric}")
        for field, metric in (("turnover", "annual_traded_notional_over_equity"),
                              ("execution_cost_fraction", "annual_mean_execution_cost_fraction"),
                              ("borrow_cost_fraction", "annual_mean_borrow_cost_fraction")):
            check_equal(252 * statistics.mean(float(row[field]) for row in rows), result[metric], metric)
        check_equal(sum(float(row["turnover"]) > 0 for row in rows), result["sessions_with_fills"], "fill days")
    folds = json.loads((results / "folds.json").read_text())
    for fit in folds["regime"]:
        if fit["last_training_close"] >= fit["next_eligible_fill"]:
            raise ValueError("HMM calibration overlaps its first eligible fill.")
    for fold in folds["cointegration"]:
        if not (fold["calibration_first"] <= fold["calibration_last"] < fold["validation_first"]
                <= fold["validation_last"] < fold["test_first"] <= fold["test_last"]):
            raise ValueError("A basket training, validation or test window overlaps.")
    print(f"Verified {len(groups)} matched ledgers, {len(calendar)} OOS sessions, "
          f"{len(fields)} cost scenarios, source hashes and fold boundaries.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", type=Path, default=HERE / "results")
    verify(parser.parse_args().results)
