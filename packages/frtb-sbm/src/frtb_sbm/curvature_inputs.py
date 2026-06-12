"""Row-wise curvature input parsing and validation helpers.

Regulatory traceability:
    Basel MAR21.5, MAR21.8-MAR21.14, MAR21.96-MAR21.99, and SBM-CURV-001.
"""

from __future__ import annotations

from collections.abc import Sequence

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.commodity_reference_data import commodity_bucket_definition
from frtb_sbm.csr_nonsec_reference_data import (
    CSR_BOND_RISK_FACTOR,
    CSR_CDS_RISK_FACTOR,
    csr_nonsec_bucket_definition,
)
from frtb_sbm.csr_sec_ctp_reference_data import csr_sec_ctp_bucket_definition
from frtb_sbm.csr_sec_nonctp_reference_data import (
    CSR_SEC_BOND_RISK_FACTOR,
    CSR_SEC_CDS_RISK_FACTOR,
    csr_sec_nonctp_bucket_definition,
)
from frtb_sbm.curvature_factors import (
    _required_curvature_shock,
    _validate_fx_curvature_scalar_flag,
)
from frtb_sbm.data_models import (
    CurvatureBranchRecord,
    CurvatureInput,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
)
from frtb_sbm.equity_reference_data import EQUITY_SPOT_RISK_FACTOR, equity_bucket_definition
from frtb_sbm.reference_data import (
    curvature_citation_ids,
    curvature_risk_weight,
    girr_bucket_definition,
    normalise_fx_delta_currency_code,
)
from frtb_sbm.regimes import ensure_profile_supports_risk_class_measure
from frtb_sbm.validation import (
    SbmInputError,
    ensure_sbm_profile_known,
    normalise_sensitivity_amount,
    sensitivity_sort_key,
    validate_sbm_sensitivities,
)


def parse_curvature_input(
    sensitivity: SbmSensitivity,
    *,
    profile_id: str,
) -> CurvatureInput:
    """Build a canonical curvature input from one validated CURVATURE sensitivity.
    Parameters
    ----------
    sensitivity : SbmSensitivity
        See signature.
    profile_id : str
        See signature.

    Returns
    -------
    CurvatureInput
    """

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
    """Validate curvature-only sensitivities and return canonical curvature inputs.
    Parameters
    ----------
    sensitivities : Sequence[SbmSensitivity]
        See signature.
    profile_id : str
        See signature.

    Returns
    -------
    tuple[CurvatureInput, ...]
    """

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
    """Return the profile-prescribed worst-side branch label for up/down shocks.
    Parameters
    ----------
    up_shock_amount : float
        See signature.
    down_shock_amount : float
        See signature.

    Returns
    -------
    str
    """

    up = normalise_sensitivity_amount(up_shock_amount)
    down = normalise_sensitivity_amount(down_shock_amount)
    if down < up:
        return "down"
    return "up"


def selected_curvature_shock_amount(up_shock_amount: float, down_shock_amount: float) -> float:
    """Return the more negative up/down shock amount for curvature weighting.
    Parameters
    ----------
    up_shock_amount : float
        See signature.
    down_shock_amount : float
        See signature.

    Returns
    -------
    float
    """

    up = normalise_sensitivity_amount(up_shock_amount)
    down = normalise_sensitivity_amount(down_shock_amount)
    branch = curvature_worst_branch(up, down)
    return down if branch == "down" else up


def _validate_curvature_capital_sensitivities(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
    reporting_currency: str,
) -> tuple[SbmSensitivity, ...]:
    ensure_sbm_profile_known(profile_id)
    if not sensitivities:
        raise SbmInputError("sensitivities must not be empty", field="sensitivities")
    validated = tuple(sorted(validate_sbm_sensitivities(sensitivities), key=sensitivity_sort_key))
    risk_classes = {item.risk_class for item in validated}
    if len(risk_classes) != 1:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm curvature capital requires a homogeneous risk class"
        )
    risk_class = next(iter(risk_classes))
    ensure_profile_supports_risk_class_measure(
        profile_id,
        risk_class,
        SbmRiskMeasure.CURVATURE,
    )
    for sensitivity in validated:
        if sensitivity.risk_measure is not SbmRiskMeasure.CURVATURE:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm curvature capital does not support "
                f"risk_measure={sensitivity.risk_measure.value}"
            )
        if sensitivity.up_shock_amount is None or sensitivity.down_shock_amount is None:
            raise SbmInputError(
                "curvature inputs require up_shock_amount and down_shock_amount",
                field="up_shock_amount",
                sensitivity_id=sensitivity.sensitivity_id,
            )
        _validate_curvature_mapping(
            sensitivity,
            profile_id=profile_id,
            reporting_currency=reporting_currency,
        )
    return validated


def _curvature_input_branch_records(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
) -> tuple[CurvatureBranchRecord, ...]:
    citations = curvature_citation_ids(profile_id)
    records: list[CurvatureBranchRecord] = []
    for sensitivity in sensitivities:
        up_shock = _required_curvature_shock(sensitivity, field="up_shock_amount")
        down_shock = _required_curvature_shock(sensitivity, field="down_shock_amount")
        records.append(
            CurvatureBranchRecord(
                sensitivity_id=sensitivity.sensitivity_id,
                selected_branch=curvature_worst_branch(up_shock, down_shock),
                up_shock_amount=up_shock,
                down_shock_amount=down_shock,
                citation_ids=citations,
            )
        )
    return tuple(records)


def _validate_curvature_mapping(
    sensitivity: SbmSensitivity,
    *,
    profile_id: str,
    reporting_currency: str,
) -> None:
    risk_class = sensitivity.risk_class
    if risk_class is SbmRiskClass.GIRR:
        girr_bucket_definition(profile_id, sensitivity.bucket)
        if sensitivity.risk_factor.strip().upper() in {"INFL", "XCCY"}:
            raise UnsupportedRegulatoryFeatureError(
                "GIRR curvature has no capital requirement for inflation or "
                "cross-currency basis risk factors (MAR21.8(5)(b))"
            )
        return
    if risk_class is SbmRiskClass.FX:
        bucket = normalise_fx_delta_currency_code(sensitivity.bucket)
        risk_factor = normalise_fx_delta_currency_code(sensitivity.risk_factor)
        reporting = normalise_fx_delta_currency_code(reporting_currency)
        if bucket != risk_factor:
            raise SbmInputError(
                "FX curvature bucket must match risk_factor currency",
                field="bucket",
                sensitivity_id=sensitivity.sensitivity_id,
            )
        curvature_risk_weight(
            profile_id,
            risk_class=risk_class,
            currency=risk_factor,
            reporting_currency=reporting,
        )
        _validate_fx_curvature_scalar_flag(sensitivity, reporting_currency=reporting)
        return
    if risk_class is SbmRiskClass.EQUITY:
        equity_bucket_definition(profile_id, sensitivity.bucket)
        if sensitivity.risk_factor.strip().upper() != EQUITY_SPOT_RISK_FACTOR:
            raise UnsupportedRegulatoryFeatureError(
                "equity curvature has no capital requirement for equity repo rates (MAR21.12(3))"
            )
        return
    if risk_class is SbmRiskClass.COMMODITY:
        commodity_bucket_definition(profile_id, sensitivity.bucket)
        return
    if risk_class is SbmRiskClass.CSR_NONSEC:
        csr_nonsec_bucket_definition(profile_id, sensitivity.bucket)
        _normalise_csr_basis(sensitivity.risk_factor)
        return
    if risk_class is SbmRiskClass.CSR_SEC_CTP:
        csr_sec_ctp_bucket_definition(profile_id, sensitivity.bucket)
        _normalise_csr_basis(sensitivity.risk_factor)
        return
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        csr_sec_nonctp_bucket_definition(profile_id, sensitivity.bucket)
        _normalise_csr_sec_basis(sensitivity.risk_factor)
        return
    raise UnsupportedRegulatoryFeatureError(
        f"frtb-sbm curvature capital is unsupported for risk_class={risk_class.value}"
    )


def _normalise_csr_basis(risk_factor: str) -> str:
    normalised = risk_factor.strip().upper()
    if normalised not in {CSR_BOND_RISK_FACTOR, CSR_CDS_RISK_FACTOR}:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm CSR non-securitisation curvature supports BOND and CDS "
            f"risk factors only; received risk_factor={normalised!r}"
        )
    return normalised


def _normalise_csr_sec_basis(risk_factor: str) -> str:
    normalised = risk_factor.strip().upper()
    if normalised not in {CSR_SEC_BOND_RISK_FACTOR, CSR_SEC_CDS_RISK_FACTOR}:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm CSR securitisation curvature supports BOND and CDS risk factors only; "
            f"received risk_factor={normalised!r}"
        )
    return normalised


__all__ = [
    "_curvature_input_branch_records",
    "_normalise_csr_basis",
    "_normalise_csr_sec_basis",
    "_validate_curvature_capital_sensitivities",
    "_validate_curvature_mapping",
    "curvature_worst_branch",
    "parse_curvature_input",
    "selected_curvature_shock_amount",
    "validate_curvature_sensitivities",
]
