import math

import numpy as np
import pandas as pd
import pytest

from research.workspace import research_metrics


def test_sample_skewness_independent_moments_and_invariances():
    values = [-0.03, -0.01, 0.0, 0.01, 0.08]
    n = len(values)
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    expected = n / ((n - 1) * (n - 2)) * sum(((x - mean) / math.sqrt(variance)) ** 3 for x in values)
    for scale in (1, 1e-9, 2):
        actual = research_metrics(pd.Series(values) * scale)
        assert actual['skew'] == pytest.approx(expected)
        assert actual['skew_observations'] == n
    assert research_metrics(-pd.Series(values))['skew'] == pytest.approx(-expected)
    assert research_metrics(pd.Series(values) + .02)['skew'] == pytest.approx(expected)


@pytest.mark.parametrize('values', [[], [0.1], [-0.1, 0.2], [0, 0, 0], [0.01] * 5, [0, 1, np.inf]])
def test_undefined_skewness_is_unavailable(values):
    assert research_metrics(pd.Series(values, dtype=float))['skew'] is None


def test_symmetric_and_missing_returns():
    metrics = research_metrics(pd.Series([-.02, -.01, 0, .01, .02, np.nan]))
    assert metrics['skew'] == pytest.approx(0, abs=1e-12)
    assert metrics['skew_observations'] == 5
