"""Factor analytics."""

from analytics.factor_analysis.cross_sectional import average_risk_premia, fama_macbeth_regression
from analytics.factor_analysis.fundamental_law import effective_breadth, fundamental_law_ir, transfer_coefficient
from analytics.factor_analysis.ic import decile_forward_returns, information_coefficient

__all__ = [
    "average_risk_premia",
    "decile_forward_returns",
    "effective_breadth",
    "fama_macbeth_regression",
    "fundamental_law_ir",
    "information_coefficient",
    "transfer_coefficient",
]
