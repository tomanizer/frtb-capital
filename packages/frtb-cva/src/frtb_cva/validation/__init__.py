"""Deterministic validation and sign normalisation for canonical CVA inputs.

This package guards public CVA entrypoints: it validates dataclass rows,
enforces unique identifiers, normalises exposure and sensitivity signs, and
raises explicit errors for unsupported MAR50.9 elections.
"""

from frtb_cva.validation.common import (
    VALID_AMOUNT_SIGN_CONVENTIONS,
    VALID_EAD_SIGN_CONVENTIONS,
    AmountSignConvention,
    AmountSignConventionEnum,
    CvaInputError,
    EADSignConvention,
    EadSignConvention,
    _finite_float,
    _require_mixed_sensitivity_scope_evidence,
    _validate_effective_maturity,
    normalise_cva_amount,
    normalise_ead_amount,
    normalise_sensitivity_amount,
)
from frtb_cva.validation.context import (
    validate_calculation_context,
    validate_m_cva_multiplier,
)
from frtb_cva.validation.counterparties import (
    validate_cva_counterparties,
    validate_cva_netting_sets,
)
from frtb_cva.validation.hedges import validate_cva_hedges
from frtb_cva.validation.sensitivities import validate_sa_cva_sensitivities

__all__ = [
    "VALID_AMOUNT_SIGN_CONVENTIONS",
    "VALID_EAD_SIGN_CONVENTIONS",
    "AmountSignConvention",
    "AmountSignConventionEnum",
    "CvaInputError",
    "EADSignConvention",
    "EadSignConvention",
    "_finite_float",
    "_require_mixed_sensitivity_scope_evidence",
    "_validate_effective_maturity",
    "normalise_cva_amount",
    "normalise_ead_amount",
    "normalise_sensitivity_amount",
    "validate_calculation_context",
    "validate_cva_counterparties",
    "validate_cva_hedges",
    "validate_cva_netting_sets",
    "validate_m_cva_multiplier",
    "validate_sa_cva_sensitivities",
]
