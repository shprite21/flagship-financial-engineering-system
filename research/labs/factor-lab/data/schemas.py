"""Typed data contracts used across ingestion and research pipelines."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class UniverseConfig(BaseModel):
    name: str
    tickers: list[str] = Field(min_length=1)
    benchmark: str = "SPY"
    sector_map: dict[str, str] = Field(default_factory=dict)

    @field_validator("tickers")
    @classmethod
    def normalize_tickers(cls, values: list[str]) -> list[str]:
        cleaned = sorted({ticker.upper().strip() for ticker in values if ticker.strip()})
        if not cleaned:
            raise ValueError("Universe must include at least one ticker.")
        return cleaned


class DataQualityReport(BaseModel):
    passed: bool
    rows: int
    missing_ratio: float
    duplicate_rows: int = 0
    issues: list[str] = Field(default_factory=list)

