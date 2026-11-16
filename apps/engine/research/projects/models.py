"""Versioned orchestration contracts; executable rules remain ResearchRequest."""
from typing import Literal

from pydantic import Field, model_validator

from research.workspace import ResearchRequest
from research.survival.models import Strict as SurvivalStrict, SurvivalConfig


class Strict(SurvivalStrict):
    model_config = {**SurvivalStrict.model_config, 'str_strip_whitespace': True}


class Thesis(Strict):
    title: str = Field(min_length=3, max_length=100)
    research_question: str = Field(min_length=10, max_length=3000)
    economic_hypothesis: str = Field(min_length=10, max_length=3000)
    mechanism: str = Field(min_length=10, max_length=3000)
    holding_period: str = Field(min_length=2, max_length=300)
    alpha_source: str = Field(min_length=3, max_length=1000)
    failure_conditions: str = Field(min_length=10, max_length=3000)
    primary_metrics: list[str] = Field(default_factory=lambda: ['sharpe', 'max_drawdown'], min_length=1, max_length=20)
    secondary_metrics: list[str] = Field(default_factory=lambda: ['turnover', 'volatility'], max_length=20)
    acceptance_criteria: str = Field(min_length=10, max_length=3000)
    rejection_criteria: str = Field(min_length=10, max_length=3000)
    limitations: str = Field(min_length=10, max_length=3000)
    notes: str = Field('', max_length=5000)


class Specification(Strict):
    thesis: Thesis
    research: ResearchRequest
    market: Literal['US', 'IN'] = 'US'
    frequency: Literal['1d'] = '1d'
    signal_notes: str = Field('', max_length=5000)
    portfolio_notes: str = Field('', max_length=3000)
    validation: SurvivalConfig = Field(default_factory=SurvivalConfig)
    holdout_fraction: float = Field(.2, ge=.1, le=.3)
    prior_exposure: Literal['unknown', 'previously_inspected'] = 'unknown'
    prior_exposure_note: str = Field('Historical exposure outside Q is not independently verified.', min_length=10, max_length=2000)

    @model_validator(mode='after')
    def one_strategy(self):
        if len(self.research.sleeves) != 1:
            raise ValueError('A research project investigates exactly one catalogue strategy')
        if self.research.snapshot_run_id:
            raise ValueError('Select a project dataset snapshot instead of a mutable run pointer')
        if any(s.endswith('.NS') != (self.market == 'IN') for s in self.research.symbols):
            raise ValueError('Project market must match every universe instrument')
        if self.market == 'IN' and self.research.data_mode == 'demo':
            raise ValueError('The seeded demo dataset uses US instrument labels')
        if self.research.hypothesis != self.thesis.economic_hypothesis:
            raise ValueError('Executable mandate hypothesis must match the versioned thesis')
        return self


class CreateProject(Strict):
    spec: Specification


class Revision(CreateProject):
    parent_revision: str = Field(pattern=r'^[a-f0-9]{64}$')
    reason: str = Field(min_length=10, max_length=3000)


class Reason(Strict):
    reason: str = Field(min_length=10, max_length=3000)


class DatasetRequest(Reason):
    prior_run_id: str | None = Field(None, pattern=r'^\d{8}T\d{6}Z-[a-f0-9]{8}$')


class TrialRequest(Reason):
    revision_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    dataset_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    lookbacks: list[int] = Field(default_factory=list, max_length=9)
    rebalance: Literal['daily', 'weekly', 'monthly'] | None = None
    commission_bps: float | None = Field(None, ge=0, le=100)
    slippage_bps: float | None = Field(None, ge=0, le=100)


class Reference(Strict):
    citation: str = Field(min_length=3, max_length=2000)
    authors: str = Field('', max_length=1000)
    year: int | None = Field(None, ge=1500, le=2100)
    url: str = Field('', max_length=2000)
    doi: str = Field('', max_length=500)
    finding: str = Field('', max_length=3000)
    relevance: str = Field(min_length=10, max_length=3000)
    assumptions: str = Field('', max_length=3000)
    replication_status: Literal['not_attempted', 'planned', 'attempted', 'supported', 'not_supported'] = 'not_attempted'
    related_trial: str | None = Field(None, pattern=r'^[a-f0-9]{64}$')

    @model_validator(mode='after')
    def safe_link(self):
        if self.url and not self.url.startswith(('https://', 'http://')):
            raise ValueError('Reference URL must use HTTP or HTTPS')
        return self


class KillCriteria(Strict):
    max_drawdown: float = Field(.15, gt=0, le=1)
    max_gross: float = Field(1, gt=0, le=3)
    max_volatility: float | None = Field(None, gt=0, le=5)
    max_cost_drift_bps: float | None = Field(None, ge=0, le=1000)
    max_stale_days: int = Field(7, ge=1, le=365)
    minimum_observations: int = Field(60, ge=20, le=1000)


class FreezeRequest(Reason):
    trial_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    validation_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    expected_metrics: dict[str, float] = Field(default_factory=dict)
    expectation_basis: str = Field(min_length=10, max_length=3000)
    kill: KillCriteria = Field(default_factory=KillCriteria)


class ForwardRequest(Reason):
    strategy_version_id: str = Field(pattern=r'^[a-f0-9]{64}$')
    mode: Literal['manual', 'automated'] = 'manual'
    provider: str = Field('unconfigured', pattern=r'^[a-zA-Z0-9_-]{1,64}$')
