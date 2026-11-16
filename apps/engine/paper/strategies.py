"""Trusted signal adapters. Custom code never executes inside the service."""
import math
import numpy as np
import pandas as pd
from .models import utc


def terminal(spec, history, actions, holding):
    p = spec.parameters
    symbol = p['symbol']
    bars = history[symbol]
    lookback, slow = int(p['lookback']), int(p['slow'])
    if len(bars) <= max(lookback, slow if p['kind'] == 'SMA crossover' else lookback):
        raise ValueError('Insufficient causal warmup for strategy')
    closes = [b.close for b in bars]
    for action in actions:
        if action.symbol == symbol and action.kind == 'split' and utc(action.effective_at) <= utc(bars[-1].end):
            closes = [c / action.amount if utc(b.end) < utc(action.effective_at) else c for b, c in zip(bars, closes)]
    last, window = closes[-1], closes[-lookback:]
    average = sum(window) / len(window)
    kind = p['kind']
    if kind == 'SMA crossover':
        signal = average > sum(closes[-slow:]) / slow
    elif kind == 'RSI mean reversion':
        delta = np.diff(closes[-lookback-1:])
        up, down = np.maximum(delta, 0).mean(), np.maximum(-delta, 0).mean()
        rsi = (50 if up == 0 else 100) if down == 0 else 100 - 100 / (1 + up / down)
        signal = rsi < (55 if holding else 30)
    elif kind == 'Bollinger mean reversion':
        signal = last < (average if holding else average - 2 * float(np.std(window)))
    elif kind == 'Breakout':
        signal = last > (average if holding else max(closes[-lookback-1:-1]))
    elif kind == 'Time-series momentum':
        signal = last > closes[-lookback-1]
    else:
        raise ValueError('Unknown terminal strategy')
    return {symbol: float(p['allocation']) if signal else 0}


def targets(spec, history, actions, account):
    if spec.adapter.startswith('custom_'):
        raise ValueError('Custom execution blocked: verified isolated worker is not configured')
    if spec.adapter == 'terminal':
        return terminal(spec, history, actions, account['positions'].get(spec.parameters['symbol'], {}).get('quantity', 0) > 0)
    if spec.adapter == 'allocation':
        return spec.parameters['weights']
    from research.workspace import ResearchRequest, pipeline_for
    from data.models import MarketDataBundle
    from strategies.library import StrategyPipeline
    from portfolio import RegimeConditionedAllocator
    from risk import ExposureConstraint, VolatilityTargeter
    request = ResearchRequest.model_validate(spec.parameters)
    frames = {}
    for symbol, bars in history.items():
        rows = []
        for b in bars:
            factor = math.prod(a.amount for a in actions if a.symbol == symbol and a.kind == 'split'
                               and utc(b.end) < utc(a.effective_at) <= utc(bars[-1].end))
            rows.append({'date': pd.Timestamp(b.end).tz_localize(None),
                         **{k.title(): getattr(b, k) / factor for k in ('open', 'high', 'low', 'close')},
                         'Volume': b.volume * factor})
        frames[symbol] = pd.DataFrame(rows).set_index('date')
    if min(map(len, frames.values())) < max(126, max(s.lookback for s in request.sleeves) + 2):
        raise ValueError('Insufficient portfolio warmup')
    if any(not f.index.equals(next(iter(frames.values())).index) for f in frames.values()):
        raise ValueError('Portfolio history must have aligned complete sessions')
    bundle = MarketDataBundle(ohlcv=frames)
    pipeline = pipeline_for(request)
    prices = bundle.close()
    returns = prices.pct_change().fillna(0)
    regimes = pipeline._detect_regimes(prices, returns) if request.regime_enabled else pd.Series(1, index=prices.index)
    signals = pipeline.strategy_pipeline.generate(bundle)
    blended = StrategyPipeline.weighted_blend(signals, pipeline.strategy_budgets)
    from portfolio.weighting import weight_signals
    weighted = weight_signals(blended.weights, returns, request.portfolio_method,
                              pipeline.allocation_config, request.portfolio_lookback)
    allocated = RegimeConditionedAllocator(pipeline.allocation_config).allocate(weighted, regimes)
    constrained = ExposureConstraint(pipeline.risk_config).apply(allocated.weights)
    scaled = VolatilityTargeter(pipeline.risk_config).scale_weights(constrained, returns)
    return ExposureConstraint(pipeline.risk_config).apply(scaled).iloc[-1].to_dict()
