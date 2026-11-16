"""Analyze recorded scaling studies; no synthetic benchmark data."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd


def bootstrap_median(values, seed=42, repetitions=10000):
    a = np.asarray(values, dtype=float)
    if a.size < 2:
        raise ValueError("At least two measured repetitions are required")
    rng = np.random.default_rng(seed)
    medians = np.median(rng.choice(a, (repetitions, a.size), replace=True), axis=1)
    return np.quantile(medians, [.025, .975])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("benchmark", type=Path)
    parser.add_argument("--output", type=Path, default=Path("scaling-analysis.csv"))
    args = parser.parse_args()
    study = json.loads(args.benchmark.read_text())
    rows = []
    for point in study["points"]:
        for device, samples in point["samples"].items():
            times = [s["total_ms"] for s in samples]
            low, high = bootstrap_median(times)
            rows.append(dict(agents=point["agents"], device=device, repeats=len(times),
                             median_ms=np.median(times), ci95_low_ms=low, ci95_high_ms=high,
                             min_ms=min(times), max_ms=max(times)))
    frame = pd.DataFrame(rows)
    frame.to_csv(args.output, index=False)
    print(frame.to_string(index=False))
    print("Intervals describe timing variability on this hardware, not economic uncertainty.")


if __name__ == "__main__":
    main()
