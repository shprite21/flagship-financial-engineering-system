"""Statistical arbitrage: pairs, cointegration, and PCA residuals."""

from factors.stat_arb.pairs import estimate_hedge_ratio, pair_spread, spread_zscore
from factors.stat_arb.pca import pca_residuals

__all__ = ["estimate_hedge_ratio", "pair_spread", "pca_residuals", "spread_zscore"]

