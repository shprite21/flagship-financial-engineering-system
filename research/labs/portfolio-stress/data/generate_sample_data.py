"""Generate synthetic daily simple returns for four fictional investment sleeves."""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


ASSETS = ("Equity", "Rates", "Commodities", "Trend")
DAILY_LOG_MEANS = np.array([0.00025, 0.00008, 0.00012, 0.00015])
DAILY_VOLATILITIES = np.array([0.012, 0.004, 0.014, 0.007])
CORRELATION = np.array([
    [1.00, -0.25, 0.35, -0.10],
    [-0.25, 1.00, -0.10, 0.15],
    [0.35, -0.10, 1.00, 0.05],
    [-0.10, 0.15, 0.05, 1.00],
])


def generate_sample(observations: int = 1260, seed: int = 771) -> pd.DataFrame:
    """Return a synthetic weekday-indexed panel of decimal simple returns."""
    if observations < 2 or seed < 0:
        raise ValueError("Supply at least two observations and a nonnegative seed")
    rng = np.random.Generator(np.random.PCG64(seed))
    independent = rng.standard_normal((observations, len(ASSETS)))
    correlated = independent @ np.linalg.cholesky(CORRELATION).T
    simple = np.expm1(DAILY_LOG_MEANS + correlated * DAILY_VOLATILITIES)
    dates = pd.bdate_range("2018-01-02", periods=observations, name="date")
    return pd.DataFrame(simple, index=dates, columns=ASSETS)


def main() -> None:
    """Write the synthetic sample to a selectable CSV path."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("synthetic_returns.csv"))
    parser.add_argument("--observations", type=int, default=1260)
    parser.add_argument("--seed", type=int, default=771)
    args = parser.parse_args()
    try:
        sample = generate_sample(args.observations, args.seed)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        sample.to_csv(args.output, float_format="%.17g", lineterminator="\n")
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Sample generation failed: {exc}\n")
    print(f"Wrote {len(sample)} synthetic daily observations to {args.output}")


if __name__ == "__main__":
    main()
