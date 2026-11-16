"""Config-driven settings for research pipelines."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class DataSettings(BaseModel):
    raw_dir: Path = Path("data/raw")
    processed_dir: Path = Path("data/processed")
    cache_dir: Path = Path("data/cached")
    fundamentals_dir: Path = Path("data/fundamentals")
    provider: str = "yfinance"
    universe: str = "demo_large_cap"
    incremental_update: bool = True


class BacktestSettings(BaseModel):
    trading_days: int = 252
    rebalance_frequency: str = "M"
    transaction_cost_bps: float = 5.0
    slippage_bps: float = 2.0
    target_gross_exposure: float = 1.0
    max_position_weight: float = 0.05


class PortfolioSettings(BaseModel):
    optimizer: str = "max_sharpe"
    long_short: bool = True
    sector_neutral: bool = False
    beta_neutral: bool = False


class RegimeSettings(BaseModel):
    volatility_window: int = 63
    drawdown_window: int = 252
    hmm_states: int = 3


class ProjectSettings(BaseModel):
    name: str = "Systematic Equities Research Lab"
    subtitle: str = (
        "Institutional-Style Multi-Factor Quantitative Research & Portfolio Construction Framework"
    )


class LabSettings(BaseModel):
    project: ProjectSettings = Field(default_factory=ProjectSettings)
    data: DataSettings = Field(default_factory=DataSettings)
    backtest: BacktestSettings = Field(default_factory=BacktestSettings)
    portfolio: PortfolioSettings = Field(default_factory=PortfolioSettings)
    regime: RegimeSettings = Field(default_factory=RegimeSettings)


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - exercised only without PyYAML installed
        raise RuntimeError("Install pyyaml to load YAML configuration files.") from exc
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping at root of config file: {path}")
    return data


def load_settings(path: str | Path = "configs/default.yaml") -> LabSettings:
    """Load platform settings from YAML, falling back to typed defaults."""

    config_path = Path(path)
    if not config_path.exists():
        return LabSettings()
    return LabSettings.model_validate(_read_yaml(config_path))

