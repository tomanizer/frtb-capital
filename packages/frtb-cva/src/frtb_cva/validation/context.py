"""CVA calculation context and multiplier validation."""

from __future__ import annotations

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_cva._unsupported import MAR50_9_UNSUPPORTED_MESSAGE
from frtb_cva.data_models import CvaCalculationContext, CvaMethod, CvaRegulatoryProfile
from frtb_cva.validation.common import (
    CvaInputError,
    _finite_float,
    _require_mixed_sensitivity_scope_evidence,
    _require_text,
)


def validate_calculation_context(context: object) -> CvaCalculationContext:
    """Validate a CVA calculation context.

    Parameters
    ----------
    context : object
        Candidate :class:`~frtb_cva.data_models.CvaCalculationContext`.

    Returns
    -------
    CvaCalculationContext
        The same context when all required fields and enums are valid.

    Raises
    ------
    CvaInputError
        If the object is not a context or required text fields are blank.
    UnsupportedRegulatoryFeatureError
        If ``materiality_threshold_elected`` is requested but not implemented.
    """

    if not isinstance(context, CvaCalculationContext):
        raise CvaInputError("context must be a CvaCalculationContext", field="context")
    _require_text(context.run_id, "run_id")
    _require_text(context.base_currency, "base_currency")
    if not isinstance(context.profile, CvaRegulatoryProfile):
        raise CvaInputError("invalid regulatory profile", field="profile")
    if not isinstance(context.method, CvaMethod):
        raise CvaInputError("invalid CVA method", field="method")
    if context.materiality_threshold_elected:
        raise UnsupportedRegulatoryFeatureError(MAR50_9_UNSUPPORTED_MESSAGE)
    for netting_set_id in context.carve_out_netting_set_ids:
        _require_text(netting_set_id, "carve_out_netting_set_ids")
    if context.method is CvaMethod.MIXED_CARVE_OUT:
        _require_mixed_sensitivity_scope_evidence(context.sa_cva_sensitivity_scope_evidence_id)
    elif context.sa_cva_sensitivity_scope_evidence_id is not None:
        _require_text(
            context.sa_cva_sensitivity_scope_evidence_id,
            "sa_cva_sensitivity_scope_evidence_id",
        )
    return context


def validate_m_cva_multiplier(value: object) -> float:
    """Return a finite SA-CVA multiplier satisfying the MAR50.5 floor.

    Parameters
    ----------
    value : object
        Candidate ``m_cva`` multiplier from caller configuration.

    Returns
    -------
    float
        Finite multiplier greater than or equal to ``1.0``.

    Raises
    ------
    CvaInputError
        If the value is non-numeric, non-finite, not positive, or below the MAR50.5 floor.
    """

    m_cva = _finite_float(value, field="m_cva")
    if m_cva <= 0.0:
        raise CvaInputError("m_cva must be positive", field="m_cva")
    if m_cva < 1.0:
        raise CvaInputError("m_cva must be at least 1.0 (MAR50.5)", field="m_cva")
    return m_cva


__all__ = [
    "validate_calculation_context",
    "validate_m_cva_multiplier",
]
