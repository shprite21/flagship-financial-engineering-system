import numpy as np
import pytest

from risk_engine.portfolio import equity_paths, resolve_weights


def test_daily_rebalancing_and_asset_order():
    weights = resolve_weights(["B", "A"], {"A": 0.75, "B": 0.25})
    np.testing.assert_array_equal(weights, [0.25, 0.75])
    x = np.log([[[2, 1], [0.5, 1]], [[1, 1], [1, 1]]])
    values = equity_paths(x, weights, 100)
    np.testing.assert_allclose(values, [[100, 125, 109.375], [100, 100, 100]])
    np.testing.assert_array_equal(resolve_weights(["A", "B"]), [0.5, 0.5])


@pytest.mark.parametrize("weights", [
    {"A": 0.2, "B": 0.5}, {"A": 2, "B": -1}, {"A": np.nan, "B": 0.5},
    {"X": 1, "B": 0}, {"A": 1}, {"A": True, "B": False},
])
def test_invalid_weights(weights):
    with pytest.raises(ValueError):
        resolve_weights(["A", "B"], weights)


@pytest.mark.parametrize("capital", [0, -10, np.inf])
def test_invalid_capital(capital):
    with pytest.raises(ValueError):
        equity_paths(np.zeros((1, 1, 1)), [1], capital)


def test_near_total_loss_and_zero_weight_asset():
    wealth = equity_paths([[[-40, 800], [0, -800]]], [1, 0], 100)
    np.testing.assert_allclose(wealth[0, 1:], 100 * np.exp(-40), rtol=1e-14, atol=0)
