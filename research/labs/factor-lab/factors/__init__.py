"""Canonical factor implementations and multi-factor blending."""

from factors.base import FactorResult, long_short_weights, rank_to_deciles, zscore_cross_section
from factors.fama_french import construct_ff3_proxies, construct_ff5_proxies
from factors.multifactor import blend_factors, factor_correlation_matrix

__all__ = [
    "FactorResult",
    "blend_factors",
    "construct_ff3_proxies",
    "construct_ff5_proxies",
    "factor_correlation_matrix",
    "long_short_weights",
    "rank_to_deciles",
    "zscore_cross_section",
]
