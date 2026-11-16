"""Independent regressions for archive identity and benchmark completeness."""
import hashlib

import numpy as np
import pandas as pd
import pytest

from apps.research_api import ResearchWorkspace, atomic_json
from portfolio.custom import MarketDataError
from research.workspace import ResearchRequest, run_research
from scripts.run_research import make_synthetic_bundle


def mandate(**changes):
    return ResearchRequest(**{
        "name": "Provenance regression", "hypothesis": "Verify fixed inputs before research.",
        "data_mode": "demo", "symbols": ["AAA"], "train_window": 126,
        "test_window": 63, "sleeves": [{"strategy": "time_series_momentum", "budget": 100, "lookback": 20}],
        **changes,
    })


@pytest.mark.parametrize("tampered", [None, "prices.csv", "benchmark.csv"])
def test_snapshot_reuse_verifies_exact_bytes_before_invoking_runner(tmp_path, tampered):
    calls = []

    def runner(request, directory, progress, bundle):
        calls.append(bundle)
        raise MarketDataError("verified input reached runner")

    ws = ResearchWorkspace(tmp_path / "experiments", runner=runner)
    try:
        req = mandate()
        parent = ws.tracker.start_run(req.name, req.model_dump())
        directory = ws.root / parent.experiment_id
        dates = pd.date_range("2024-01-01", periods=3)
        frame = pd.DataFrame({"Close": [10., 11., 12.]}, index=dates)
        pd.concat({"AAA": frame}, names=["symbol", "date"]).to_csv(directory / "prices.csv")
        frame.to_csv(directory / "benchmark.csv")
        fingerprint = hashlib.sha256((directory / "prices.csv").read_bytes() + (directory / "benchmark.csv").read_bytes()).hexdigest()
        atomic_json(directory / "job.json", {"status": "completed", "request": req.model_dump()})
        atomic_json(directory / "result.json", {"data": {"snapshot_sha256": fingerprint}})
        if tampered:
            with (directory / tampered).open("ab") as stream:
                stream.write(b"\n")  # Semantically equivalent CSV still differs from the archived bytes.
        job = ws.submit(mandate(snapshot_run_id=parent.experiment_id))
        ws.executor.shutdown(wait=True)
        result = ws.get(job["run_id"])
        assert result["status"] == "failed"
        if tampered:
            assert not calls
            assert "fingerprint mismatch" in result["error"]
        else:
            assert len(calls) == 1
            assert calls[0].close()["AAA"].tolist() == [10., 11., 12.]
            assert result["error"] == "verified input reached runner"
    finally:
        ws.executor.shutdown(wait=True)


@pytest.mark.parametrize("problem", ["missing", "nan", "zero", "infinite", "duplicate"])
def test_benchmark_cannot_silently_create_zero_returns(synthetic_bundle, tmp_path, problem):
    benchmark = synthetic_bundle.close().mean(axis=1).to_frame("Close")
    if problem == "missing":
        benchmark = benchmark.drop(benchmark.index[180])
    elif problem == "duplicate":
        benchmark = pd.concat([benchmark, benchmark.iloc[-1:]])
    else:
        benchmark.iloc[180, 0] = {"nan": np.nan, "zero": 0, "infinite": np.inf}[problem]
    synthetic_bundle.benchmark = benchmark
    with pytest.raises(MarketDataError, match="Benchmark must contain"):
        run_research(mandate(), tmp_path, bundle=synthetic_bundle)
    assert not (tmp_path / "result.json").exists()


def test_seeded_demo_bars_respect_open_close_range():
    bundle = make_synthetic_bundle(seed=7)
    for frame in bundle.ohlcv.values():
        assert (frame.High >= frame[["Open", "Close"]].max(axis=1)).all()
        assert (frame.Low <= frame[["Open", "Close"]].min(axis=1)).all()
