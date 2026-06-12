"""Compatibility exports for NMRF SES helpers.

NMRF record types, stress artifact conversion, SES aggregation, and capital
routing physically live in focused ``frtb_ima.nmrf_*`` modules. This module
preserves the historical ``frtb_ima.nmrf`` import path.
"""

from frtb_ima.nmrf_aggregation import (
    aggregate_ses,
    aggregate_ses_breakdown,
    aggregate_ses_breakdown_for_policy,
    aggregate_ses_for_policy,
    aggregate_ses_type_a,
    aggregate_ses_type_b,
    ses_values_from_stress_results,
)
from frtb_ima.nmrf_capital import (
    calculate_nmrf_capital_for_policy,
    route_nmrf_classifications_for_capital,
)
from frtb_ima.nmrf_stress import (
    calculate_nmrf_ses_from_revaluation,
    nmrf_effective_liquidity_horizon,
    nmrf_stress_result_from_external_ses,
    nmrf_stress_result_from_linear_sensitivity,
    require_nmrf_stress_generation_supported,
    ses_for_nmrf_linear,
)
from frtb_ima.nmrf_types import (
    NMRFCapitalResult,
    NMRFCapitalRouting,
    NMRFStressArtifact,
    NMRFStressMethod,
    NMRFStressScenarioResult,
    SESAggregationResult,
)

__all__ = [
    "NMRFCapitalResult",
    "NMRFCapitalRouting",
    "NMRFStressArtifact",
    "NMRFStressMethod",
    "NMRFStressScenarioResult",
    "SESAggregationResult",
    "aggregate_ses",
    "aggregate_ses_breakdown",
    "aggregate_ses_breakdown_for_policy",
    "aggregate_ses_for_policy",
    "aggregate_ses_type_a",
    "aggregate_ses_type_b",
    "calculate_nmrf_capital_for_policy",
    "calculate_nmrf_ses_from_revaluation",
    "nmrf_effective_liquidity_horizon",
    "nmrf_stress_result_from_external_ses",
    "nmrf_stress_result_from_linear_sensitivity",
    "require_nmrf_stress_generation_supported",
    "route_nmrf_classifications_for_capital",
    "ses_for_nmrf_linear",
    "ses_values_from_stress_results",
]
