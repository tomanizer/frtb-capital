"""Row-level non-GIRR vega weighting validation helpers.

Regulatory traceability:
    Basel MAR21.9-MAR21.14 and MAR21.51-MAR21.86 define the
    supported non-GIRR vega risk-factor identity axes.
"""

from __future__ import annotations

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm._text import require_text as _require_text
from frtb_sbm.data_models import SbmRiskClass, SbmSensitivity
from frtb_sbm.reference_data import (
    commodity_bucket_definition,
    csr_nonsec_validate_vega_inputs,
    equity_bucket_definition,
    fx_bucket_definition,
    girr_vega_option_tenor_definition,
    normalise_fx_delta_currency_code,
)
from frtb_sbm.validation import SbmInputError

VegaFactorValidation = tuple[tuple[str, ...], tuple[str, ...]]


def _validate_non_girr_vega_sensitivity(
    sensitivity: SbmSensitivity,
    *,
    profile_id: str,
) -> VegaFactorValidation:
    option_tenor = girr_vega_option_tenor_definition(
        profile_id,
        sensitivity.option_tenor or "",
    ).tenor
    if sensitivity.risk_class is SbmRiskClass.FX:
        return _validate_fx_vega_sensitivity(sensitivity, profile_id, option_tenor)
    if sensitivity.risk_class is SbmRiskClass.EQUITY:
        return _validate_equity_vega_sensitivity(sensitivity, profile_id, option_tenor)
    if sensitivity.risk_class is SbmRiskClass.COMMODITY:
        return _validate_commodity_vega_sensitivity(sensitivity, profile_id, option_tenor)
    if sensitivity.risk_class is SbmRiskClass.CSR_NONSEC:
        return _validate_csr_nonsec_vega_sensitivity(sensitivity, profile_id, option_tenor)
    if sensitivity.risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        return _validate_csr_sec_nonctp_vega_sensitivity(sensitivity, profile_id, option_tenor)
    if sensitivity.risk_class is SbmRiskClass.CSR_SEC_CTP:
        return _validate_csr_sec_ctp_vega_sensitivity(sensitivity, profile_id, option_tenor)
    raise UnsupportedRegulatoryFeatureError(
        f"non-GIRR vega weighting is unsupported for risk_class={sensitivity.risk_class.value}"
    )


def _validate_fx_vega_sensitivity(
    sensitivity: SbmSensitivity,
    profile_id: str,
    option_tenor: str,
) -> VegaFactorValidation:
    bucket = fx_bucket_definition(profile_id, sensitivity.bucket)
    risk_factor = normalise_fx_delta_currency_code(sensitivity.risk_factor)
    if bucket.currency != risk_factor:
        raise SbmInputError(
            "FX vega bucket must match risk_factor currency",
            field="bucket",
            sensitivity_id=sensitivity.sensitivity_id,
        )
    return (bucket.currency, option_tenor), _fx_vega_factor_citations(bucket.citation_id)


def _fx_vega_factor_citations(bucket_citation_id: str) -> tuple[str, ...]:
    if bucket_citation_id.startswith("us_npr_"):
        return (bucket_citation_id,)
    if bucket_citation_id.startswith("pra_uk_crr_"):
        return ("pra_uk_crr_325q_fx_risk_factors", bucket_citation_id)
    return ("basel_mar21_14", bucket_citation_id)


def _validate_equity_vega_sensitivity(
    sensitivity: SbmSensitivity,
    profile_id: str,
    option_tenor: str,
) -> VegaFactorValidation:
    from frtb_sbm.equity_reference_data import EQUITY_SPOT_RISK_FACTOR

    equity_bucket_definition(profile_id, sensitivity.bucket)
    if sensitivity.risk_factor.strip().upper() != EQUITY_SPOT_RISK_FACTOR:
        raise UnsupportedRegulatoryFeatureError(
            "equity vega has no capital requirement for equity repo rates (MAR21.12(2)(b))"
        )
    qualifier = _require_text(sensitivity.qualifier, "qualifier", sensitivity.sensitivity_id)
    return (
        sensitivity.bucket,
        qualifier,
        EQUITY_SPOT_RISK_FACTOR,
        option_tenor,
    ), ("basel_mar21_12", "basel_mar21_72")


def _validate_commodity_vega_sensitivity(
    sensitivity: SbmSensitivity,
    profile_id: str,
    option_tenor: str,
) -> VegaFactorValidation:
    commodity_bucket_definition(profile_id, sensitivity.bucket)
    commodity = _require_text(
        sensitivity.risk_factor,
        "risk_factor",
        sensitivity.sensitivity_id,
    )
    return (sensitivity.bucket, commodity, option_tenor), ("basel_mar21_13", "basel_mar21_81")


def _validate_csr_nonsec_vega_sensitivity(
    sensitivity: SbmSensitivity,
    profile_id: str,
    option_tenor: str,
) -> VegaFactorValidation:
    qualifier = _require_text(sensitivity.qualifier, "qualifier", sensitivity.sensitivity_id)
    csr_nonsec_validate_vega_inputs(
        profile_id,
        bucket_id=sensitivity.bucket,
        risk_factor=sensitivity.risk_factor,
        qualifier=qualifier,
    )
    return (
        sensitivity.bucket,
        qualifier,
        sensitivity.risk_factor.strip().upper(),
        option_tenor,
    ), ("basel_mar21_9", "basel_mar21_51")


def _validate_csr_sec_nonctp_vega_sensitivity(
    sensitivity: SbmSensitivity,
    profile_id: str,
    option_tenor: str,
) -> VegaFactorValidation:
    from frtb_sbm.csr_sec_nonctp_reference_data import csr_sec_nonctp_validate_vega_inputs

    qualifier = _require_text(sensitivity.qualifier, "qualifier", sensitivity.sensitivity_id)
    csr_sec_nonctp_validate_vega_inputs(
        profile_id,
        bucket_id=sensitivity.bucket,
        risk_factor=sensitivity.risk_factor,
        qualifier=qualifier,
    )
    return (
        sensitivity.bucket,
        qualifier,
        sensitivity.risk_factor.strip().upper(),
        option_tenor,
    ), ("basel_mar21_10", "basel_mar21_61")


def _validate_csr_sec_ctp_vega_sensitivity(
    sensitivity: SbmSensitivity,
    profile_id: str,
    option_tenor: str,
) -> VegaFactorValidation:
    from frtb_sbm.csr_sec_ctp_reference_data import (
        csr_sec_ctp_validate_vega_inputs,
        ensure_csr_sec_ctp_decomposition_evidence,
    )

    ensure_csr_sec_ctp_decomposition_evidence(sensitivity)
    qualifier = _require_text(sensitivity.qualifier, "qualifier", sensitivity.sensitivity_id)
    csr_sec_ctp_validate_vega_inputs(
        profile_id,
        bucket_id=sensitivity.bucket,
        risk_factor=sensitivity.risk_factor,
        qualifier=qualifier,
    )
    return (
        sensitivity.bucket,
        qualifier,
        sensitivity.risk_factor.strip().upper(),
        option_tenor,
    ), ("basel_mar21_11", "basel_mar21_58")
