"""Compatibility exports for SBM validation helpers.

ADR 0045 validation code now lives in stage-specific modules under this package.
Importing from ``frtb_sbm.validation`` remains the public compatibility surface.
"""

from frtb_sbm._errors import SbmInputError
from frtb_sbm.validation.coercion import (
    coerce_fx_risk_factor_basis,
    coerce_pairwise_evidence_mode,
    coerce_risk_class,
    coerce_risk_measure,
    coerce_sign_convention,
    normalise_currency_code,
    normalise_sensitivity_amount,
    require_positive_int,
    sensitivity_sort_key,
    sort_sensitivities_deterministic,
)
from frtb_sbm.validation.context import (
    ensure_sbm_capital_paths_supported,
    ensure_sbm_profile_known,
    ensure_sbm_risk_class_measure_supported,
    ensure_sbm_run_supported,
    phase1_capital_supported_paths,
    validate_sbm_calculation_context,
)
from frtb_sbm.validation.sensitivity import validate_sbm_sensitivities

__all__ = [
    "SbmInputError",
    "coerce_fx_risk_factor_basis",
    "coerce_pairwise_evidence_mode",
    "coerce_risk_class",
    "coerce_risk_measure",
    "coerce_sign_convention",
    "ensure_sbm_capital_paths_supported",
    "ensure_sbm_profile_known",
    "ensure_sbm_risk_class_measure_supported",
    "ensure_sbm_run_supported",
    "normalise_currency_code",
    "normalise_sensitivity_amount",
    "phase1_capital_supported_paths",
    "require_positive_int",
    "sensitivity_sort_key",
    "sort_sensitivities_deterministic",
    "validate_sbm_calculation_context",
    "validate_sbm_sensitivities",
]
