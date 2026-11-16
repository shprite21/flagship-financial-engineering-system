import numpy as np
import pandas as pd

from market_regime_detection import engineer_features, get_feature_columns, split_data


def test_future_volatility_cannot_change_earlier_features_or_cross_split_labels():
    rng = np.random.default_rng(7)
    close = 100 * np.exp(np.cumsum(rng.normal(0.001, 0.01, 300)))
    index = pd.bdate_range("2020-01-01", periods=len(close))
    bars = pd.DataFrame({key: close for key in ("open", "close", "adj_close", "high", "low")}, index=index)
    bars["volume"] = 10000
    full = engineer_features(bars)
    truncated = engineer_features(bars.iloc[:160])
    features = get_feature_columns()
    pd.testing.assert_frame_equal(full.loc[truncated.index, features], truncated[features])
    train, test, _, _ = split_data(full)
    assert full.index.get_loc(train.index[-1]) + 2 == full.index.get_loc(test.index[0])
