"""API request and response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BacktestResponse(BaseModel):
    metrics: dict[str, float]
    latest_equity: float


class FactorResponse(BaseModel):
    name: str
    latest_scores: dict[str, float] = Field(default_factory=dict)


class RegimeResponse(BaseModel):
    date: str
    composite_regime: str
    details: dict[str, str]

