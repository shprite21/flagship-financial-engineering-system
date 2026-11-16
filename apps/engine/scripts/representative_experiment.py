"""Run Q's fixed, offline research protocol through its API and verify its export.

From apps/engine: python -m scripts.representative_experiment
All prices are seeded synthetic observations. This demonstrates mechanics, not alpha.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from fastapi import FastAPI
from fastapi.testclient import TestClient
import numpy as np

from apps import research_api
from apps.research_api import ResearchWorkspace
from research.survival.models import SurvivalConfig
from research.survival.replay import replay
from research.workspace import PROJECT_ROOT, ResearchRequest, strategy_catalog


def wait_for(client, route, timeout=300):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(route)
        response.raise_for_status()
        job = response.json()
        if job["status"] == "failed":
            raise RuntimeError(f"Research job failed: {job.get('error')}")
        if job["status"] == "completed":
            return job
        time.sleep(.1)
    raise TimeoutError(f"Research job exceeded {timeout} seconds")


def run(output: Path):
    if output.exists() and any(output.iterdir()):
        raise ValueError("Choose an empty output directory; previous experiments are preserved")
    output.mkdir(parents=True, exist_ok=True)
    workspace = ResearchWorkspace(output / "experiments")
    previous_workspace = research_api.workspace
    research_api.workspace = lambda: workspace
    app = FastAPI(title="Q reproducible offline experiment")
    app.include_router(research_api.router)
    request = ResearchRequest(
        name="Fixed momentum and reversal mechanics study",
        hypothesis="Test a fixed 60/40 momentum/reversal allocation under risk limits and trading costs; no parameter selection.",
        data_mode="demo", symbols=strategy_catalog()["demo_symbols"],
        sleeves=[{"strategy": "time_series_momentum", "budget": 60, "lookback": 63},
                 {"strategy": "mean_reversion", "budget": 40, "lookback": 20}],
        train_window=252, test_window=63, commission_bps=2, slippage_bps=3,
    )
    config = SurvivalConfig()  # DSR remains unavailable without defensible effective-trial assumptions.
    try:
        with TestClient(app) as client:
            submitted = client.post("/api/research/runs", json=request.model_dump())
            submitted.raise_for_status()
            experiment_id = submitted.json()["run_id"]
            job = wait_for(client, f"/api/research/runs/{experiment_id}")
            result = job["result"]
            payload = {"experiment_id": experiment_id, "config": config.model_dump()}
            submitted = client.post("/api/research/survival/runs", json=payload)
            submitted.raise_for_status()
            run_id = submitted.json()["id"]
            survival = wait_for(client, f"/api/research/survival/runs/{run_id}")
            cached = client.post("/api/research/survival/runs", json=payload)
            cached.raise_for_status()
            exported = client.get(f"/api/research/survival/runs/{run_id}/export")
            exported.raise_for_status()
            export_path = output / "survival-export.zip"
            export_path.write_bytes(exported.content)
            verified = replay(export_path)
            decision = client.post(f"/api/research/runs/{experiment_id}/decision", json={
                "status": "rejected",
                "rationale": "Synthetic data validates mechanics only; no empirical investment evidence or paper promotion.",
            })
            decision.raise_for_status()
            # Register a frozen forward protocol without inventing any future observations.
            paper = client.post("/api/research/survival/paper", json={
                "experiment_id": experiment_id, "initial_nav": request.initial_capital})
            paper.raise_for_status()
            paper_id = paper.json()["id"]
            forward = client.get(f"/api/research/survival/paper/{paper_id}")
            forward.raise_for_status()
            # Verify the same saved JSON and artifact routes used by the web interface.
            artifact = client.get(f"/api/research/runs/{experiment_id}/artifacts/result")
            artifact.raise_for_status()
            stored = artifact.json()
            layers = survival["result"]["layers"]
            by_id = {layer["id"]: layer for layer in layers}
            cost_scenarios = by_id[5]["diagnostics"]["scenarios"]
            checks = {
                "api_artifact_matches_result": stored == result,
                "all_18_layers_reported": len(layers) == 18,
                "no_layer_calculation_errors": not any(reason.startswith("Calculation failed") for layer in layers for reason in layer["reasons"]),
                "no_hard_integrity_failure": not by_id[1]["hard_failure"],
                "attribution_reconciles": bool(np.isclose(result["attribution"]["asset_contribution"] + result["attribution"]["cost_contribution"], result["metrics"]["total_return"], atol=1e-10)),
                "cost_stress_monotone": all(a["total_return"] >= b["total_return"] for a, b in zip(cost_scenarios, cost_scenarios[1:])),
                "cache_reuses_identical_submission": cached.json().get("cached") is True and cached.json()["id"] == run_id,
                "export_exact_replay": verified["verified"],
                "synthetic_promotion_blocked": result["paper_candidate_eligible"] is False,
                "negative_decision_preserved": decision.json()["decision"]["status"] == "rejected",
                "forward_has_no_invented_observations": forward.json()["observations"] == 0,
                "live_execution_disabled": survival["result"]["summary"]["live_eligible"] is False,
            }
            summary = {
                "label": "SYNTHETIC MECHANICS DEMONSTRATION — NOT MARKET PERFORMANCE",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "experiment_id": experiment_id, "survival_id": run_id,
                "request": request.model_dump(), "survival_config": config.model_dump(),
                "data": result["data"], "source_sha256": result["provenance"]["source_sha256"],
                "dependencies": result["provenance"]["dependencies"],
                "export_sha256": hashlib.sha256(exported.content).hexdigest(),
                "catalogue_strategies": len(strategy_catalog()["strategies"]),
                "research_walk_forward_windows": result["validation"]["complete_windows"],
                "research_metrics": result["metrics"], "validation_metrics": result["validation"]["metrics"],
                "survival_summary": survival["result"]["summary"],
                "layers": [{"id": layer["id"], "name": layer["name"], "status": layer["status"],
                            "metrics": layer["metrics"], "reasons": layer["reasons"]} for layer in layers],
                "cost_scenarios": cost_scenarios,
                "forward": {"id": paper_id, "observations": 0, "broker_verified": False},
                "checks": checks,
                "limitations": ["Fixed seeded synthetic prices, not observed markets or exchange sessions.",
                    "No parameter optimization or strategy selected from these results.",
                    "Main portfolio accounting is fractional; whole-share liquidity stress is a separate account.",
                    "Historical splits are retrospective; no untouched holdout is claimed.",
                    "DSR is unavailable without effective independent trial assumptions.",
                    "No broker, external feed, frontend browser, or prospective performance verified by this script."],
            }
            (output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
            failed = [key for key, value in checks.items() if not value]
            if failed:
                raise AssertionError(f"Experiment invariants failed: {failed}; see {output / 'summary.json'}")
            print(json.dumps({"summary": str(output / "summary.json"), "checks": checks,
                              "survival": summary["survival_summary"]}, indent=2))
            return summary
    finally:
        workspace.executor.shutdown(wait=True)
        research_api.workspace = previous_workspace


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT.parents[1] / "outputs" / "research-demo" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    args = parser.parse_args()
    run(args.output.resolve())
