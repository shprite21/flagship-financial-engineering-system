"""Versioned contracts shared by the paper runner, feed adapters and API."""
from datetime import date, datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)


def utc(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timezone-aware timestamps are required')
    return result.astimezone(timezone.utc)


class StrategySpec(Strict):
    name: str = Field(min_length=1, max_length=100)
    adapter: Literal['terminal', 'research', 'allocation', 'custom_python', 'custom_javascript']
    reference: str = Field(min_length=1, max_length=200)
    parameters: dict = Field(default_factory=dict)
    output: Literal['targets', 'orders'] = 'targets'
    budget: float = Field(default=1, gt=0, le=1)
    research_sleeve: str | None = None


class Deployment(Strict):
    name: str = Field(min_length=1, max_length=100)
    market: Literal['US', 'IN']
    currency: Literal['USD', 'INR']
    provider: str = Field(default='unconfigured', pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    universe: list[str] = Field(min_length=1, max_length=30)
    capital: float = Field(default=100000, ge=1, le=1e9)
    mode: Literal['strategy', 'combined', 'funded'] = 'strategy'
    interval: Literal['1d', '1m'] = '1d'
    rebalance: Literal['daily', 'weekly', 'monthly', 'every_bar'] = 'daily'
    strategies: list[StrategySpec] = Field(min_length=1, max_length=30)
    commission_bps: float = Field(default=10, ge=0, le=500)
    slippage_bps: float = Field(default=5, ge=0, le=500)
    participation: float = Field(default=.01, gt=0, le=1)
    max_asset_weight: float = Field(default=1, gt=0, le=1)
    max_gross: float = Field(default=1, gt=0, le=1)
    max_order_notional: float = Field(default=20000, gt=0, le=1e9)
    drawdown_limit: float = Field(default=.2, gt=0, le=1)

    @model_validator(mode='after')
    def consistent(self):
        if self.currency != {'US': 'USD', 'IN': 'INR'}[self.market]:
            raise ValueError('Use separate USD and INR accounts')
        if len(set(self.universe)) != len(self.universe):
            raise ValueError('Universe contains duplicate instruments')
        import re
        if any(not re.fullmatch(r'[A-Z0-9^][A-Z0-9.^&_-]{0,39}', s) for s in self.universe):
            raise ValueError('Invalid instrument identifier')
        if any(s.endswith('.NS') != (self.market == 'IN') for s in self.universe):
            raise ValueError('US and NSE instruments need separate accounts')
        if self.mode == 'strategy' and len(self.strategies) != 1:
            raise ValueError('A standalone account needs one strategy')
        if abs(sum(s.budget for s in self.strategies) - 1) > 1e-9:
            raise ValueError('Strategy budgets must sum to one')
        if self.interval == '1d' and self.rebalance == 'every_bar':
            raise ValueError('Every-bar scheduling requires one-minute data')
        return self


class Session(Strict):
    date: str
    open: str
    close: str
    settlement: str

    @model_validator(mode='after')
    def times(self):
        if not utc(self.open) < utc(self.close) < utc(self.settlement):
            raise ValueError('Session open, close and settlement must be ordered')
        if date.fromisoformat(self.date).isoformat() != self.date:
            raise ValueError('Session dates must use YYYY-MM-DD')
        self.open, self.close, self.settlement = (utc(v).isoformat() for v in (self.open, self.close, self.settlement))
        return self


class Bar(Strict):
    symbol: str
    start: str
    end: str
    received_at: str
    session: str
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)

    @model_validator(mode='after')
    def valid(self):
        if not utc(self.start) < utc(self.end) <= utc(self.received_at):
            raise ValueError('Only completed bars with ordered receipt timestamps are accepted')
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close) or self.low > self.high:
            raise ValueError('Invalid OHLC range')
        self.start, self.end, self.received_at = (utc(v).isoformat() for v in (self.start, self.end, self.received_at))
        return self


class Action(Strict):
    id: str
    symbol: str
    effective_at: str
    kind: Literal['split', 'dividend']
    amount: float = Field(gt=0)
    pay_at: str | None = None

    @model_validator(mode='after')
    def times(self):
        utc(self.effective_at)
        if self.pay_at and utc(self.pay_at) < utc(self.effective_at):
            raise ValueError('Dividend payment cannot precede entitlement')
        self.effective_at = utc(self.effective_at).isoformat()
        if self.pay_at: self.pay_at = utc(self.pay_at).isoformat()
        return self


class Feed(Strict):
    schema_version: Literal[1] = 1
    provider: str
    market: Literal['US', 'IN']
    interval: Literal['1d', '1m']
    price_basis: Literal['raw']
    source: str = Field(min_length=1)
    generated_at: str
    calendar_version: str = Field(min_length=1)
    rules_version: str = Field(min_length=1)
    actions_complete_through: str
    sessions: list[Session] = Field(min_length=2)
    bars: list[Bar] = Field(default_factory=list, max_length=500000)
    actions: list[Action] = Field(default_factory=list)

    @model_validator(mode='after')
    def consistency(self):
        self.generated_at = utc(self.generated_at).isoformat()
        self.actions_complete_through = utc(self.actions_complete_through).isoformat()
        sessions = {s.date: s for s in self.sessions}
        if len(sessions) != len(self.sessions) or len({a.id for a in self.actions}) != len(self.actions):
            raise ValueError('Duplicate sessions or corporate actions')
        ordered = sorted(self.sessions, key=lambda s: utc(s.open))
        if any(utc(a.close) >= utc(b.open) for a, b in zip(ordered, ordered[1:])):
            raise ValueError('Overlapping exchange sessions')
        seen = set()
        for b in self.bars:
            key = (b.symbol, b.start)
            s = sessions.get(b.session)
            if key in seen or not s or not utc(s.open) <= utc(b.start) < utc(b.end) <= utc(s.close):
                raise ValueError('Duplicate bar or bar outside its exchange session')
            if self.interval == '1d' and (b.start != s.open or b.end != s.close):
                raise ValueError('Daily bars must cover the complete exchange session')
            if self.interval == '1m' and (utc(b.end) - utc(b.start)).total_seconds() != 60:
                raise ValueError('Intraday bars must be one minute')
            seen.add(key)
        return self


class OrderIntent(Strict):
    symbol: str
    side: Literal['BUY', 'SELL']
    quantity: int = Field(gt=0, strict=True)
    type: Literal['market', 'limit', 'stop', 'stop_limit'] = 'market'
    tif: Literal['DAY', 'GTC'] = 'DAY'
    limit: float | None = Field(default=None, gt=0)
    stop: float | None = Field(default=None, gt=0)

    @model_validator(mode='after')
    def prices(self):
        if (self.type in ('limit', 'stop_limit')) != (self.limit is not None):
            raise ValueError('Limit orders require a limit price, other orders prohibit it')
        if (self.type in ('stop', 'stop_limit')) != (self.stop is not None):
            raise ValueError('Stop orders require a stop price, other orders prohibit it')
        return self
