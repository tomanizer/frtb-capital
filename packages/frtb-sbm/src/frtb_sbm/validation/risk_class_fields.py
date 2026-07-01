"""Risk-class-specific field validation for SBM sensitivities.

Regulatory traceability:
    Basel MAR21 risk-class field requirements and SBM-NFR-004 fail-closed
    unsupported-feature handling for path-specific sensitivity inputs.
"""

from __future__ import annotations

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm._errors import SbmInputError
from frtb_sbm._text import require_text as _require_text
from frtb_sbm.data_models import SbmRegulatoryProfile, SbmRiskClass, SbmRiskMeasure, SbmSensitivity
from frtb_sbm.validation.coercion import (
    _is_blank,
    normalise_currency_code,
    normalise_sensitivity_amount,
    require_positive_int,
)

_TENOR_REQUIRED: frozenset[tuple[SbmRiskClass, SbmRiskMeasure]] = frozenset(
    {
        (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA),
        (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA),
        (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE),
        (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA),
        (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA),
        (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.DELTA),
        (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.DELTA),
    }
)

_OPTION_TENOR_REQUIRED: frozenset[tuple[SbmRiskClass, SbmRiskMeasure]] = frozenset(
    {
        (risk_class, SbmRiskMeasure.VEGA)
        for risk_class in (
            SbmRiskClass.GIRR,
            SbmRiskClass.FX,
            SbmRiskClass.EQUITY,
            SbmRiskClass.COMMODITY,
            SbmRiskClass.CSR_NONSEC,
            SbmRiskClass.CSR_SEC_NONCTP,
            SbmRiskClass.CSR_SEC_CTP,
        )
    }
)

_QUALIFIER_REQUIRED: frozenset[SbmRiskClass] = frozenset(
    {
        SbmRiskClass.CSR_NONSEC,
        SbmRiskClass.CSR_SEC_CTP,
        SbmRiskClass.CSR_SEC_NONCTP,
        SbmRiskClass.EQUITY,
        SbmRiskClass.COMMODITY,
    }
)


def validate_risk_class_fields(
    sensitivity: SbmSensitivity,
    *,
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
) -> None:
    """Validate path-specific fields on one canonical sensitivity.

    Parameters
    ----------
    sensitivity
        Canonical sensitivity row already checked for common identity fields.
    risk_class
        Resolved risk-class enum for the row.
    risk_measure
        Resolved risk-measure enum for the row.
    """

    sensitivity_id = sensitivity.sensitivity_id

    if _qualifier_is_required(risk_class, risk_measure) and _is_blank(sensitivity.qualifier):
        raise SbmInputError(
            "qualifier is required for the selected risk class",
            field="qualifier",
            sensitivity_id=sensitivity_id,
        )

    if (risk_class, risk_measure) in _TENOR_REQUIRED:
        _require_text(sensitivity.tenor, "tenor", sensitivity_id)

    if (risk_class, risk_measure) in _OPTION_TENOR_REQUIRED:
        _require_text(sensitivity.option_tenor, "option_tenor", sensitivity_id)

    if sensitivity.liquidity_horizon_days is not None:
        require_positive_int(
            sensitivity.liquidity_horizon_days,
            "liquidity_horizon_days",
            sensitivity_id,
        )

    for field_name in ("tenor", "option_tenor", "maturity", "qualifier"):
        value = getattr(sensitivity, field_name)
        if value is not None:
            _require_text(value, field_name, sensitivity_id)

    if risk_measure is SbmRiskMeasure.CURVATURE:
        _validate_curvature_amounts(sensitivity)

    if risk_class is SbmRiskClass.FX and risk_measure is SbmRiskMeasure.DELTA:
        _validate_fx_delta_fields(sensitivity)
    if risk_class is SbmRiskClass.FX and risk_measure is SbmRiskMeasure.VEGA:
        _validate_fx_vega_fields(sensitivity)
    if risk_class is SbmRiskClass.EQUITY and risk_measure is SbmRiskMeasure.DELTA:
        _validate_equity_delta_fields(sensitivity)
    if risk_class is SbmRiskClass.EQUITY and risk_measure is SbmRiskMeasure.VEGA:
        _validate_equity_vega_fields(sensitivity)
    if risk_class is SbmRiskClass.COMMODITY and risk_measure is SbmRiskMeasure.DELTA:
        _validate_commodity_delta_fields(sensitivity)
    if risk_class is SbmRiskClass.COMMODITY and risk_measure is SbmRiskMeasure.VEGA:
        _validate_commodity_vega_fields(sensitivity)
    if risk_class is SbmRiskClass.CSR_NONSEC and risk_measure is SbmRiskMeasure.VEGA:
        _validate_csr_nonsec_vega_fields(sensitivity)
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP and risk_measure is SbmRiskMeasure.VEGA:
        _validate_csr_sec_nonctp_vega_fields(sensitivity)
    if risk_class is SbmRiskClass.CSR_SEC_CTP and risk_measure is SbmRiskMeasure.VEGA:
        _validate_csr_sec_ctp_vega_fields(sensitivity)


def _qualifier_is_required(
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
) -> bool:
    if risk_class is SbmRiskClass.COMMODITY and risk_measure is SbmRiskMeasure.VEGA:
        return False
    return risk_class in _QUALIFIER_REQUIRED


def _validate_fx_delta_fields(sensitivity: SbmSensitivity) -> None:
    # Local import: reference_data -> commodity_reference_data -> validation.
    from frtb_sbm.reference_data import normalise_fx_delta_currency_code

    sensitivity_id = sensitivity.sensitivity_id
    bucket = normalise_fx_delta_currency_code(
        normalise_currency_code(
            sensitivity.bucket,
            field="bucket",
            sensitivity_id=sensitivity_id,
        )
    )
    risk_factor = normalise_fx_delta_currency_code(
        normalise_currency_code(
            sensitivity.risk_factor,
            field="risk_factor",
            sensitivity_id=sensitivity_id,
        )
    )
    if bucket != risk_factor:
        raise SbmInputError(
            "FX delta bucket must match risk_factor currency",
            field="bucket",
            sensitivity_id=sensitivity_id,
        )


def _validate_fx_vega_fields(sensitivity: SbmSensitivity) -> None:
    # Local import: reference_data -> commodity_reference_data -> validation.
    from frtb_sbm.reference_data import (
        girr_vega_option_tenor_definition,
        normalise_fx_delta_currency_code,
    )

    sensitivity_id = sensitivity.sensitivity_id
    bucket = normalise_fx_delta_currency_code(
        normalise_currency_code(
            sensitivity.bucket,
            field="bucket",
            sensitivity_id=sensitivity_id,
        )
    )
    risk_factor = normalise_fx_delta_currency_code(
        normalise_currency_code(
            sensitivity.risk_factor,
            field="risk_factor",
            sensitivity_id=sensitivity_id,
        )
    )
    if bucket != risk_factor:
        raise SbmInputError(
            "FX vega bucket must match risk_factor currency",
            field="bucket",
            sensitivity_id=sensitivity_id,
        )
    girr_vega_option_tenor_definition(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        sensitivity.option_tenor or "",
    )


def _validate_equity_delta_fields(sensitivity: SbmSensitivity) -> None:
    from frtb_sbm.equity_reference_data import (
        EQUITY_REPO_RISK_FACTOR,
        EQUITY_SPOT_RISK_FACTOR,
    )

    sensitivity_id = sensitivity.sensitivity_id
    risk_factor = sensitivity.risk_factor.strip().upper()
    if risk_factor not in {EQUITY_SPOT_RISK_FACTOR, EQUITY_REPO_RISK_FACTOR}:
        raise SbmInputError(
            "equity delta risk_factor must be SPOT or REPO",
            field="risk_factor",
            sensitivity_id=sensitivity_id,
        )


def _validate_equity_vega_fields(sensitivity: SbmSensitivity) -> None:
    from frtb_sbm.equity_reference_data import (
        EQUITY_REPO_RISK_FACTOR,
        EQUITY_SPOT_RISK_FACTOR,
    )
    from frtb_sbm.reference_data import girr_vega_option_tenor_definition

    sensitivity_id = sensitivity.sensitivity_id
    risk_factor = sensitivity.risk_factor.strip().upper()
    if risk_factor == EQUITY_REPO_RISK_FACTOR:
        raise UnsupportedRegulatoryFeatureError(
            "equity vega has no capital requirement for equity repo rates (MAR21.12(2)(b))"
        )
    if risk_factor != EQUITY_SPOT_RISK_FACTOR:
        raise SbmInputError(
            "equity vega risk_factor must be SPOT",
            field="risk_factor",
            sensitivity_id=sensitivity_id,
        )
    girr_vega_option_tenor_definition(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        sensitivity.option_tenor or "",
    )


def _validate_commodity_delta_fields(sensitivity: SbmSensitivity) -> None:
    _require_text(sensitivity.bucket, "bucket", sensitivity.sensitivity_id)


def _validate_commodity_vega_fields(sensitivity: SbmSensitivity) -> None:
    from frtb_sbm.reference_data import girr_vega_option_tenor_definition

    _require_text(sensitivity.bucket, "bucket", sensitivity.sensitivity_id)
    girr_vega_option_tenor_definition(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        sensitivity.option_tenor or "",
    )


def _validate_csr_nonsec_vega_fields(sensitivity: SbmSensitivity) -> None:
    from frtb_sbm.csr_nonsec_reference_data import csr_nonsec_validate_vega_inputs
    from frtb_sbm.reference_data import girr_vega_option_tenor_definition

    csr_nonsec_validate_vega_inputs(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        bucket_id=sensitivity.bucket,
        risk_factor=sensitivity.risk_factor,
        qualifier=sensitivity.qualifier or "",
    )
    girr_vega_option_tenor_definition(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        sensitivity.option_tenor or "",
    )


def _validate_csr_sec_nonctp_vega_fields(sensitivity: SbmSensitivity) -> None:
    from frtb_sbm.csr_sec_nonctp_reference_data import csr_sec_nonctp_validate_vega_inputs
    from frtb_sbm.reference_data import girr_vega_option_tenor_definition

    csr_sec_nonctp_validate_vega_inputs(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        bucket_id=sensitivity.bucket,
        risk_factor=sensitivity.risk_factor,
        qualifier=sensitivity.qualifier or "",
    )
    girr_vega_option_tenor_definition(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        sensitivity.option_tenor or "",
    )


def _validate_csr_sec_ctp_vega_fields(sensitivity: SbmSensitivity) -> None:
    from frtb_sbm.csr_sec_ctp_reference_data import csr_sec_ctp_validate_vega_inputs
    from frtb_sbm.reference_data import girr_vega_option_tenor_definition

    csr_sec_ctp_validate_vega_inputs(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        bucket_id=sensitivity.bucket,
        risk_factor=sensitivity.risk_factor,
        qualifier=sensitivity.qualifier or "",
    )
    girr_vega_option_tenor_definition(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        sensitivity.option_tenor or "",
    )


def _validate_curvature_amounts(sensitivity: SbmSensitivity) -> None:
    sensitivity_id = sensitivity.sensitivity_id
    if sensitivity.up_shock_amount is None or sensitivity.down_shock_amount is None:
        raise SbmInputError(
            "curvature inputs require up_shock_amount and down_shock_amount",
            field="up_shock_amount",
            sensitivity_id=sensitivity_id,
        )
    normalise_sensitivity_amount(sensitivity.up_shock_amount, sensitivity_id=sensitivity_id)
    normalise_sensitivity_amount(sensitivity.down_shock_amount, sensitivity_id=sensitivity_id)


__all__ = ["validate_risk_class_fields"]
