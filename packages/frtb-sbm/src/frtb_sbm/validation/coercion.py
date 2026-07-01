"""Common coercion helpers for SBM validation stages.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for validation.py, Basel MAR21.1,
    U.S. NPR 2.0 section V.A.7.a, and SBM-NFR-004.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import TypeVar

from frtb_sbm._errors import SbmInputError
from frtb_sbm._text import require_text as _require_text
from frtb_sbm.data_models import (
    SbmFxRiskFactorBasis,
    SbmPairwiseEvidenceMode,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
)

EnumT = TypeVar(
    "EnumT",
    SbmFxRiskFactorBasis,
    SbmPairwiseEvidenceMode,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSignConvention,
)


def normalise_sensitivity_amount(value: float, *, sensitivity_id: str = "") -> float:
    """Return a finite sensitivity amount.
    Parameters
    ----------
    value : float
        See signature.
    sensitivity_id : str, optional
        See signature.

    Returns
    -------
    float
    """

    return _finite_float(value, field="amount", sensitivity_id=sensitivity_id)


def normalise_currency_code(
    value: str,
    *,
    field: str = "amount_currency",
    sensitivity_id: str = "",
) -> str:
    """Return an upper-case ISO-style currency code.
    Parameters
    ----------
    value : str
        See signature.
    field : str, optional
        See signature.
    sensitivity_id : str, optional
        See signature.

    Returns
    -------
    str
    """

    code = _require_text(value, field, sensitivity_id)
    normalised = code.upper()
    if len(normalised) != 3 or not normalised.isalpha():
        raise SbmInputError(
            "currency code must be a three-letter alphabetic code",
            field=field,
            sensitivity_id=sensitivity_id,
        )
    return normalised


def coerce_risk_class(value: SbmRiskClass | str) -> SbmRiskClass:
    """Normalise a risk-class identifier to the canonical enum.
    Parameters
    ----------
    value : SbmRiskClass | str
        See signature.

    Returns
    -------
    SbmRiskClass
    """

    return _coerce_enum(value, SbmRiskClass, "risk_class")


def coerce_risk_measure(value: SbmRiskMeasure | str) -> SbmRiskMeasure:
    """Normalise a risk-measure identifier to the canonical enum.
    Parameters
    ----------
    value : SbmRiskMeasure | str
        See signature.

    Returns
    -------
    SbmRiskMeasure
    """

    return _coerce_enum(value, SbmRiskMeasure, "risk_measure")


def coerce_sign_convention(value: SbmSignConvention | str) -> SbmSignConvention:
    """Normalise a sign-convention identifier to the canonical enum.
    Parameters
    ----------
    value : SbmSignConvention | str
        See signature.

    Returns
    -------
    SbmSignConvention
    """

    return _coerce_enum(value, SbmSignConvention, "sign_convention")


def coerce_pairwise_evidence_mode(
    value: SbmPairwiseEvidenceMode | str,
) -> SbmPairwiseEvidenceMode:
    """Normalise a pairwise evidence mode to the canonical enum.
    Parameters
    ----------
    value : SbmPairwiseEvidenceMode | str
        See signature.

    Returns
    -------
    SbmPairwiseEvidenceMode
    """

    return _coerce_enum(value, SbmPairwiseEvidenceMode, "pairwise_evidence_mode")


def coerce_fx_risk_factor_basis(
    value: SbmFxRiskFactorBasis | str,
) -> SbmFxRiskFactorBasis:
    """Normalise an FX risk-factor basis to the canonical enum.

    Parameters
    ----------
    value : SbmFxRiskFactorBasis | str
        Candidate FX risk-factor basis.

    Returns
    -------
    SbmFxRiskFactorBasis
    """

    return _coerce_enum(value, SbmFxRiskFactorBasis, "fx_risk_factor_basis")


def sensitivity_sort_key(sensitivity: SbmSensitivity) -> tuple[str, str, str, str, str]:
    """Return a deterministic ordering key for one sensitivity.
    Parameters
    ----------
    sensitivity : SbmSensitivity
        See signature.

    Returns
    -------
    tuple[str, str, str, str, str]
    """

    return (
        sensitivity.risk_class.value,
        sensitivity.risk_measure.value,
        sensitivity.bucket,
        sensitivity.risk_factor,
        sensitivity.sensitivity_id,
    )


def sort_sensitivities_deterministic(
    sensitivities: Sequence[SbmSensitivity],
) -> tuple[SbmSensitivity, ...]:
    """Return sensitivities in stable risk-class, bucket, and id order.
    Parameters
    ----------
    sensitivities : Sequence[SbmSensitivity]
        See signature.

    Returns
    -------
    tuple[SbmSensitivity, ...]
    """

    return tuple(sorted(sensitivities, key=sensitivity_sort_key))


def _coerce_enum(
    value: object,
    enum_type: type[EnumT],
    field: str,
    sensitivity_id: str = "",
) -> EnumT:
    if isinstance(value, enum_type):
        return value
    if not isinstance(value, str):
        raise SbmInputError(f"invalid {field}", field=field, sensitivity_id=sensitivity_id)
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise SbmInputError(
            f"{field} must be one of: {allowed}",
            field=field,
            sensitivity_id=sensitivity_id,
        ) from exc


def _finite_float(value: object, *, field: str, sensitivity_id: str = "") -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SbmInputError("value must be numeric", field=field, sensitivity_id=sensitivity_id)
    number = float(value)
    if not math.isfinite(number):
        raise SbmInputError("value must be finite", field=field, sensitivity_id=sensitivity_id)
    return number


def _is_blank(value: str | None) -> bool:
    return value is None or value.strip() == ""


def require_positive_int(value: object, field: str, sensitivity_id: str = "") -> int:
    """Return a positive integer or raise a structured SBM input error.

    Parameters
    ----------
    value
        Candidate value to validate.
    field
        Field name reported in diagnostics.
    sensitivity_id
        Optional sensitivity identifier reported in diagnostics.

    Returns
    -------
    int
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise SbmInputError(
            "value must be a positive integer",
            field=field,
            sensitivity_id=sensitivity_id,
        )
    if value <= 0:
        raise SbmInputError(
            "value must be a positive integer",
            field=field,
            sensitivity_id=sensitivity_id,
        )
    return value


__all__ = [
    "coerce_fx_risk_factor_basis",
    "coerce_pairwise_evidence_mode",
    "coerce_risk_class",
    "coerce_risk_measure",
    "coerce_sign_convention",
    "normalise_currency_code",
    "normalise_sensitivity_amount",
    "require_positive_int",
    "sensitivity_sort_key",
    "sort_sensitivities_deterministic",
]
