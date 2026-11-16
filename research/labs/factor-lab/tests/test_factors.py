from data.synthetic import adjusted_close_wide, generate_fundamentals, generate_market_panel
from factors.base import long_short_weights
from factors.momentum.signals import twelve_minus_one_momentum
from factors.multifactor import blend_factors
from factors.quality.signals import quality_composite
from factors.value.signals import value_composite


def test_momentum_and_multifactor_scores_have_expected_shape():
    panel = generate_market_panel(periods=300)
    prices = adjusted_close_wide(panel)
    fundamentals = generate_fundamentals(panel)

    momentum = twelve_minus_one_momentum(prices).scores
    value = value_composite(fundamentals).scores.reindex(prices.index).ffill()
    quality = quality_composite(fundamentals).scores.reindex(prices.index).ffill()
    composite = blend_factors({"momentum": momentum, "value": value, "quality": quality})

    assert composite.shape == prices.shape
    assert composite.dropna(how="all").shape[0] > 0


def test_long_short_weights_are_dollar_neutral():
    panel = generate_market_panel(periods=300)
    prices = adjusted_close_wide(panel)
    scores = twelve_minus_one_momentum(prices).scores

    weights = long_short_weights(scores).dropna(how="all")
    latest = weights.iloc[-1]

    assert abs(latest.sum()) < 1e-12
    assert latest.abs().sum() <= 1.0 + 1e-12

