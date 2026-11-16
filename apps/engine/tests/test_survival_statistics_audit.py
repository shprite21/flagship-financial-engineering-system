"""Independent numerical oracles and research-gate regressions for the V2 audit."""
from itertools import permutations
import json
import math
from statistics import NormalDist, mean, stdev

import numpy as np
import pytest

from research.survival import statistics
from research.survival.methods import method
from research.survival.models import Gate, LayerResult, SurvivalConfig, apply_gates, summarize


def test_cscv_tied_selection_is_column_invariant_and_has_equal_partition_mass():
    # Six partitions: four losses, one success, and one two-way IS tie whose
    # complementary ranks straddle the median. Expected PBO = (4 + 1/2) / 6.
    # The old first-column argmax returned 5/6 or 2/3 for this same search family.
    offsets = np.array([[0, 1, 0], [0, 0, 0], [-2, 2, 2], [-1, -1, 1]]) / 256
    panel = np.repeat(offsets, 4, axis=0) + np.tile([-1., 1.], 8)[:, None] / 128
    expected = statistics.pbo(panel, blocks=4, minimum_per_half=8)
    assert expected['pbo'] == pytest.approx(.75)
    assert expected['partitions'] == 6
    assert expected['tied_training_winners'] == 1
    assert len(expected['logits']) == 7
    assert math.fsum(expected['logit_weights']) == pytest.approx(1)
    for partition in range(6):
        mass = math.fsum(weight for key, weight in zip(expected['logit_partitions'], expected['logit_weights'])
                         if key == partition)
        assert mass == pytest.approx(1 / 6)
    assert math.fsum(weight for logit, weight in zip(expected['logits'], expected['logit_weights'])
                     if logit <= 0) == pytest.approx(expected['pbo'])
    for ordering in permutations(range(3)):
        assert statistics.pbo(panel[:, ordering], 4, 8) == expected
    # The disclosed trailing observations are excluded rather than used by one half.
    extended = statistics.pbo(np.vstack([panel, [.4, -.2, .1]]), 4, 8)
    assert extended['discarded_tail_observations'] == 1
    assert extended['pbo'] == expected['pbo']
    assert extended['logits'] == expected['logits']


@pytest.mark.parametrize('lags', [0, 1, 5])
def test_hac_matches_explicit_bartlett_covariance(lags):
    # Serial dependence is deliberate. Compute the covariance sum directly,
    # without calling statsmodels or its HAC helpers as the reference oracle.
    shocks = np.random.default_rng(831).normal(0, .004, 240)
    values = []
    for shock in shocks:
        values.append(.0002 + .65 * (values[-1] if values else 0) + float(shock))
    center, n = mean(values), len(values)
    residual = [value - center for value in values]
    covariance_sum = math.fsum(value * value for value in residual)
    for lag in range(1, lags + 1):
        products = math.fsum(residual[i] * residual[i - lag] for i in range(lag, n))
        covariance_sum += 2 * (1 - lag / (lags + 1)) * products
    standard_error = math.sqrt(covariance_sum) / n
    result = statistics.hac_mean(values, lags=lags)
    assert result['daily_mean'] == pytest.approx(center, abs=1e-15)
    assert result['standard_error'] == pytest.approx(standard_error, abs=1e-15)
    assert result['z'] == pytest.approx(center / standard_error)
    assert result['p_one_sided'] == pytest.approx(NormalDist().cdf(-center / standard_error))
    assert result['ci_low'] == pytest.approx(center - NormalDist().inv_cdf(.975) * standard_error)
    assert result['ci_high'] == pytest.approx(center + NormalDist().inv_cdf(.975) * standard_error)


def test_dsr_uses_daily_sample_sharpe_and_pearson_moments():
    values = [float(value) for value in np.random.default_rng(221).normal(.0008, .012, 180)]
    values[13], values[91] = -.07, -.05  # Exercise asymmetric, heavy-tailed moments.
    trials = [-.07, .02, .06, .11]
    center, scale = mean(values), stdev(values)
    centered = [value - center for value in values]
    variance = mean([value ** 2 for value in centered])
    third = mean([value ** 3 for value in centered]) / variance ** 1.5
    fourth = mean([value ** 4 for value in centered]) / variance ** 2
    sr = center / scale
    normal, gamma = NormalDist(), .5772156649015329
    hurdle = stdev(trials) * ((1 - gamma) * normal.inv_cdf(.75)
                              + gamma * normal.inv_cdf(1 - 1 / (4 * math.e)))
    denominator = math.sqrt(1 - third * sr + (fourth - 1) * sr * sr / 4)
    expected = normal.cdf((sr - hurdle) * math.sqrt(len(values) - 1) / denominator)
    result = statistics.deflated_sharpe(values, trials, 4)
    assert result['daily_sharpe'] == pytest.approx(sr)
    assert result['expected_max_daily_sharpe'] == pytest.approx(hurdle)
    assert result['dsr'] == pytest.approx(expected, abs=1e-14)
    assert statistics.deflated_sharpe(values, trials, 2)['dsr'] >= result['dsr']


def test_by_harmonic_adjustment_preserves_input_order():
    # m=4 and H_m=25/12. Apply the sorted step-up lower envelope manually:
    # sorted p=(.001,.003,.02,.7), q=(1/120,1/80,1/18,1).
    assert statistics.fdr([.02, .001, .7, .003]) == pytest.approx([1 / 18, 1 / 120, 1., 1 / 80])
    with pytest.raises(statistics.NeedData):
        statistics.fdr([.2, float('nan')])


def test_circular_bootstrap_preserves_blocks_wraps_and_truncates(monkeypatch):
    class FixedStarts:
        def integers(self, high, size):
            assert high == 7
            assert size == (2, 4)
            return np.array([[6, 2, 4, 0], [1, 5, 3, 6]])

    monkeypatch.setattr(statistics.np.random, 'default_rng', lambda seed: FixedStarts())
    values = np.array([.01, -.02, .015, -.005, .03, -.01, .005])
    result = statistics.block_bootstrap(values, samples=2, block_length=2, minimum=6)
    explicit_paths = [values[[6, 0, 2, 3, 4, 5, 0]], values[[1, 2, 5, 6, 3, 4, 6]]]
    expected_returns, expected_drawdowns = [], []
    for i, path in enumerate(explicit_paths):
        nav, peak, drawdown = 1., 1., 0.
        for daily in path:
            nav *= 1 + daily
            peak = max(peak, nav)
            drawdown = min(drawdown, nav / peak - 1)
        expected_returns.append(nav - 1)
        expected_drawdowns.append(drawdown)
        assert result['distributions']['sharpe'][i] == pytest.approx(mean(path) / stdev(path) * math.sqrt(252))
        assert result['distributions']['cagr'][i] == pytest.approx(nav ** (252 / 7) - 1)
    assert result['distributions']['total_return'] == pytest.approx(expected_returns)
    assert result['distributions']['max_drawdown'] == pytest.approx(expected_drawdowns)
    assert result['loss_probability'] == sum(value < 0 for value in expected_returns) / 2


@pytest.mark.parametrize('value', [float('inf'), -float('inf'), float('nan'), True, '0.1', None])
@pytest.mark.parametrize('operator', ['<=', '>='])
def test_gate_invalid_metrics_are_unavailable_and_json_safe(value, operator):
    config = SurvivalConfig(gates=[Gate(layer=8, metric='nested.p', operator=operator, threshold=.05, severity='FAIL')])
    result = apply_gates(LayerResult(**method(8), status='PASS', metrics={'nested': {'p': value}}), config)
    assert result.gate_results[0]['status'] == 'N-A'
    assert result.gate_results[0]['value'] is None
    json.dumps(result.gate_results, allow_nan=False)
    summary = summarize([LayerResult(**method(1), status='PASS'), result], config)
    assert summary['status'] == 'WARN'
    assert not summary['research_gates_satisfied']


def test_summary_missing_required_layer_and_missing_failure_gate_are_unresolved():
    integrity = LayerResult(**method(1), status='PASS')
    summary = summarize([integrity], SurvivalConfig(required_layers=[1, 8]))
    assert summary['unresolved_required_layers'] == [8]
    assert summary['status'] == 'WARN'
    assert not summary['research_gates_satisfied']
    gate = Gate(layer=8, metric='p', operator='<=', threshold=.05, severity='FAIL')
    config = SurvivalConfig(gates=[gate])
    for layers in ([integrity], [integrity, LayerResult(**method(8), status='PASS', metrics={'p': .01})]):
        # A requested gate must actually have been evaluated; presence of a
        # layer alone cannot substitute for the saved decision evidence.
        summary = summarize(layers, config)
        assert summary['unresolved_failure_gates'] == [{'layer': 8, 'metric': 'p'}]
        assert not summary['research_gates_satisfied']


def test_summary_mandatory_integrity_and_hard_failure_cannot_be_waived():
    empty = summarize([], SurvivalConfig(required_layers=[]))
    assert empty['unresolved_required_layers'] == [1]
    assert not empty['research_gates_satisfied']
    inconsistent = LayerResult(**method(1), status='PASS', hard_failure=True)
    summary = summarize([inconsistent], SurvivalConfig())
    assert summary['status'] == 'FAIL'
    assert summary['hard_failures'] == [1]
    assert not summary['research_gates_satisfied']
