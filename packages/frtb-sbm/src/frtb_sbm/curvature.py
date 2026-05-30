"""
Curvature contract parsing and fail-closed capital gates.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for curvature.py, Basel MAR21.5,
    U.S. NPR 2.0 section V.A.7.a footnote 328, and SBM-CURV-001.
"""

from __future__ import annotations

from collections.abc import Sequence

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.data_models import (
    CurvatureInput,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmUnsupportedFeature,
)
from frtb_sbm.reference_data import curvature_citation_ids
from frtb_sbm.validation import (
    SbmInputError,
    ensure_sbm_profile_known,
    normalise_sensitivity_amount,
    sensitivity_sort_key,
    validate_sbm_sensitivities,
)

CURVATURE_CAPITAL_REQUIREMENT_ID = "SBM-CURV-001"


def parse_curvature_input(
    sensitivity: SbmSensitivity,
    *,
    profile_id: str,
) -> CurvatureInput:
    """Build a canonical curvature input from one validated CURVATURE sensitivity."""

    ensure_sbm_profile_known(profile_id)
    if sensitivity.risk_measure is not SbmRiskMeasure.CURVATURE:
        raise SbmInputError(
            "parse_curvature_input requires risk_measure=CURVATURE",
            field="risk_measure",
            sensitivity_id=sensitivity.sensitivity_id,
        )
    up_shock_amount = sensitivity.up_shock_amount
    down_shock_amount = sensitivity.down_shock_amount
    if up_shock_amount is None or down_shock_amount is None:
        raise SbmInputError(
            "curvature inputs require up_shock_amount and down_shock_amount",
            field="up_shock_amount",
            sensitivity_id=sensitivity.sensitivity_id,
        )
    return CurvatureInput(
        sensitivity_id=sensitivity.sensitivity_id,
        risk_class=sensitivity.risk_class,
        bucket=sensitivity.bucket,
        risk_factor=sensitivity.risk_factor,
        amount_currency=sensitivity.amount_currency,
        up_shock_amount=normalise_sensitivity_amount(
            up_shock_amount,
            sensitivity_id=sensitivity.sensitivity_id,
        ),
        down_shock_amount=normalise_sensitivity_amount(
            down_shock_amount,
            sensitivity_id=sensitivity.sensitivity_id,
        ),
        citation_ids=curvature_citation_ids(profile_id),
    )


def validate_curvature_sensitivities(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
) -> tuple[CurvatureInput, ...]:
    """Validate curvature-only sensitivities and return canonical curvature inputs."""

    ensure_sbm_profile_known(profile_id)
    if not sensitivities:
        raise SbmInputError("sensitivities must not be empty", field="sensitivities")
    for sensitivity in sensitivities:
        if sensitivity.risk_measure is not SbmRiskMeasure.CURVATURE:
            raise SbmInputError(
                "validate_curvature_sensitivities accepts only CURVATURE rows",
                field="risk_measure",
                sensitivity_id=sensitivity.sensitivity_id,
            )
    validated = validate_sbm_sensitivities(sensitivities)
    ordered = sorted(validated, key=sensitivity_sort_key)
    return tuple(
        parse_curvature_input(sensitivity, profile_id=profile_id) for sensitivity in ordered
    )


def curvature_worst_branch(up_shock_amount: float, down_shock_amount: float) -> str:
    """Return the profile-prescribed worst-side branch label for up/down shocks."""

    up = normalise_sensitivity_amount(up_shock_amount)
    down = normalise_sensitivity_amount(down_shock_amount)
    if down < up:
        return "down"
    return "up"


def curvature_capital_unsupported_feature(profile_id: str) -> SbmUnsupportedFeature:
    """Return structured metadata for the unsupported curvature capital path."""

    ensure_sbm_profile_known(profile_id)
    return SbmUnsupportedFeature(
        feature_key="sbm_curvature_capital",
        dimension="risk_measure",
        reason=(
            "Curvature capital is unsupported until the cited aggregation path "
            "is implemented (SBM-CURV-001)."
        ),
        requirement_id=CURVATURE_CAPITAL_REQUIREMENT_ID,
    )


def ensure_sbm_curvature_capital_unsupported(
    profile_id: str,
    sensitivities: Sequence[SbmSensitivity] | None = None,
) -> None:
    """Fail closed until the curvature capital aggregation path is implemented."""

    ensure_sbm_profile_known(profile_id)
    if sensitivities is not None:
        validate_curvature_sensitivities(sensitivities, profile_id=profile_id)
    raise UnsupportedRegulatoryFeatureError(
        "frtb-sbm curvature capital is unsupported until the cited curvature "
        f"aggregation path is implemented ({CURVATURE_CAPITAL_REQUIREMENT_ID}); "
        "use validate_curvature_sensitivities to validate up/down shock inputs"
    )


__all__ = [
    "CURVATURE_CAPITAL_REQUIREMENT_ID",
    "curvature_capital_unsupported_feature",
    "curvature_worst_branch",
    "ensure_sbm_curvature_capital_unsupported",
    "parse_curvature_input",
    "validate_curvature_sensitivities",
]
