"""Independent allocation invariants and research/paper adapter equivalence."""
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from portfolio.allocation import AllocationConfig
from portfolio.weighting import weight_signals
from research.workspace import ResearchRequest, make_demo_bundle, pipeline_for, subset_bundle
from scripts.single_strategy_example import example_spec


@pytest.mark.parametrize('method', ['signal', 'equal', 'inverse_volatility', 'risk_parity', 'minimum_variance'])
def test_all_weighting_methods_are_causal_and_respect_inactive_signals(method):
    rng = np.random.default_rng(12)
    returns = pd.DataFrame(rng.normal(0, .01, (55, 3)), columns=['A', 'B', 'C'])
    signals = pd.DataFrame({'A': [2.] * 55, 'B': [1.] * 55, 'C': [0.] * 55})
    cfg = AllocationConfig(long_only=True, min_weight=0, max_weight=.6)
    before = weight_signals(signals, returns, method, cfg, 20)
    changed = returns.copy()
    changed.iloc[40:] = rng.normal(0, .5, (15, 3))
    after = weight_signals(signals, changed, method, cfg, 20)
    pd.testing.assert_frame_equal(before.iloc[:40], after.iloc[:40])
    assert before['C'].eq(0).all()
    assert np.isfinite(before.to_numpy()).all()
    if method not in ('signal', 'equal'):
        assert before.max().max() <= .6 + 1e-7
        assert before.sum(axis=1).max() <= 1 + 1e-7


def test_equal_weighting_uses_only_signal_direction_and_preserves_cash():
    signal = pd.DataFrame([[10., 1., -4., 0.], [0., 0., 0., 0.]])
    cfg = AllocationConfig(long_only=True, min_weight=0)
    actual = weight_signals(signal, signal * 0, 'equal', cfg, 20)
    np.testing.assert_array_equal(actual, [[1, 1, 0, 0], [0, 0, 0, 0]])


@pytest.mark.parametrize('method,expected', [('inverse_volatility', [2/3, 1/3]), ('risk_parity', [2/3, 1/3]), ('minimum_variance', [.8, .2])])
def test_two_uncorrelated_assets_have_known_inverse_risk_allocations(method, expected):
    # Orthogonal, zero-mean observations: variance(B) = 4 * variance(A).
    returns = pd.DataFrame({'A': [.1, -.1, .1, -.1] * 6, 'B': [.2, .2, -.2, -.2] * 6})
    signals = returns * 0 + 1
    result = weight_signals(signals, returns, method, AllocationConfig(long_only=True, min_weight=0, max_weight=1), 20)
    np.testing.assert_allclose(result.iloc[20].to_numpy(), expected, atol=.002)


@pytest.mark.parametrize('method', ['equal', 'inverse_volatility', 'risk_parity', 'minimum_variance'])
def test_paper_targets_match_research_for_the_frozen_weighting_method(method):
    from paper.models import StrategySpec
    from paper.strategies import targets
    bundle = make_demo_bundle()
    bundle = subset_bundle(bundle, bundle.close().index[:140])
    request = example_spec().research.model_copy(update={'portfolio_method': method, 'portfolio_lookback': 20})
    expected = pipeline_for(request).run(bundle).weights.iloc[-1]
    history = {symbol: [SimpleNamespace(end=date.tz_localize('UTC').isoformat(), open=row.Open, high=row.High,
                  low=row.Low, close=row.Close, volume=row.Volume) for date, row in frame.iterrows()]
               for symbol, frame in bundle.ohlcv.items()}
    spec = StrategySpec(name='Allocation contract fixture', adapter='research', reference='fixture', parameters=request.model_dump())
    actual = targets(spec, history, [], {})
    np.testing.assert_allclose([actual[s] for s in expected.index], expected, atol=1e-12)
    assert min(actual.values()) >= 0
    assert max(actual.values()) <= request.max_asset_weight + 1e-12
    assert sum(actual.values()) <= request.max_gross_exposure + 1e-12


def test_old_research_requests_keep_the_original_allocation_default():
    values = example_spec().research.model_dump()
    values.pop('portfolio_method')
    values.pop('portfolio_lookback')
    request = ResearchRequest.model_validate(values)
    assert request.portfolio_method == 'signal'
    assert request.portfolio_lookback == 63
    with pytest.raises(ValueError, match='long-only'):
        ResearchRequest.model_validate({**values, 'portfolio_method': 'minimum_variance', 'long_only': False})
