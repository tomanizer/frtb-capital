"""
Cited risk-weight lookup and weighted sensitivity records.

Regulatory traceability:
    Basel MAR21.39-MAR21.40 — GIRR delta risk weights.
    Basel MAR21.92 — GIRR vega liquidity horizon and risk-weight scaling.
    U.S. NPR 2.0 section V.A.7.a step three.
    SBM-WS-001.
"""

from __future__ import annotations

from collections.abc import Sequence

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.data_models import (
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    WeightedSensitivity,
)
from frtb_sbm.reference_data import (
    commodity_bucket_definition,
    commodity_delta_risk_weight,
    csr_nonsec_delta_risk_weight,
    csr_nonsec_validate_delta_inputs,
    equity_bucket_definition,
    equity_delta_risk_weight,
    fx_bucket_definition,
    fx_delta_risk_weight,
    girr_bucket_definition,
    girr_delta_risk_weight,
    girr_vega_liquidity_horizon_days,
    vega_risk_weight,
)
from frtb_sbm.regimes import ensure_profile_supports_risk_class_measure
from frtb_sbm.validation import SbmInputError, sort_sensitivities_deterministic


def weighted_sensitivity_sort_key(item: WeightedSensitivity) -> tuple[str, str, str, str]:
    """Return a deterministic ordering key for one weighted sensitivity."""

    return (
        item.risk_class.value,
        item.risk_measure.value,
        item.bucket,
        item.sensitivity_id,
    )


def sort_weighted_sensitivities_deterministic(
    weighted_sensitivities: Sequence[WeightedSensitivity],
) -> tuple[WeightedSensitivity, ...]:
    """Return weighted sensitivities in stable risk-class, bucket, and id order."""

    return tuple(sorted(weighted_sensitivities, key=weighted_sensitivity_sort_key))


def compute_weighted_sensitivities(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
    reporting_currency: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted sensitivities for supported profile paths."""

    if not sensitivities:
        return ()
    risk_classes = {item.risk_class for item in sensitivities}
    risk_measures = {item.risk_measure for item in sensitivities}
    if len(risk_classes) != 1 or len(risk_measures) != 1:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm weighted sensitivity lookup requires homogeneous risk class and measure"
        )
    risk_class = next(iter(risk_classes))
    risk_measure = next(iter(risk_measures))
    if risk_class is SbmRiskClass.GIRR and risk_measure is SbmRiskMeasure.DELTA:
        return weight_girr_delta_sensitivities(
            sensitivities,
            profile_id=profile_id,
            reporting_currency=reporting_currency,
        )
    if risk_class is SbmRiskClass.GIRR and risk_measure is SbmRiskMeasure.VEGA:
        return weight_girr_vega_sensitivities(
            sensitivities,
            profile_id=profile_id,
        )
    if risk_class is SbmRiskClass.FX and risk_measure is SbmRiskMeasure.DELTA:
        return weight_fx_delta_sensitivities(
            sensitivities,
            profile_id=profile_id,
            reporting_currency=reporting_currency,
        )
    if risk_class is SbmRiskClass.EQUITY and risk_measure is SbmRiskMeasure.DELTA:
        return weight_equity_delta_sensitivities(
            sensitivities,
            profile_id=profile_id,
        )
    if risk_class is SbmRiskClass.COMMODITY and risk_measure is SbmRiskMeasure.DELTA:
        return weight_commodity_delta_sensitivities(
            sensitivities,
            profile_id=profile_id,
        )
    if risk_class is SbmRiskClass.CSR_NONSEC and risk_measure is SbmRiskMeasure.DELTA:
        return weight_csr_nonsec_delta_sensitivities(
            sensitivities,
            profile_id=profile_id,
        )
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP and risk_measure is SbmRiskMeasure.DELTA:
        return weight_csr_sec_nonctp_delta_sensitivities(
            sensitivities,
            profile_id=profile_id,
        )
    if risk_class is SbmRiskClass.CSR_SEC_CTP and risk_measure is SbmRiskMeasure.DELTA:
        return weight_csr_sec_ctp_delta_sensitivities(
            sensitivities,
            profile_id=profile_id,
        )
    raise UnsupportedRegulatoryFeatureError(
        "frtb-sbm weighted sensitivity lookup does not support "
        f"risk_class={risk_class.value}, risk_measure={risk_measure.value}"
    )


def weight_girr_delta_sensitivities(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
    reporting_currency: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted GIRR delta sensitivities for a supported profile."""

    ensure_profile_supports_risk_class_measure(
        profile_id,
        SbmRiskClass.GIRR,
        SbmRiskMeasure.DELTA,
    )
    weighted: list[WeightedSensitivity] = []
    for sensitivity in sort_sensitivities_deterministic(sensitivities):
        if sensitivity.risk_class is not SbmRiskClass.GIRR:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm GIRR delta weighting does not support "
                f"risk_class={sensitivity.risk_class.value}"
            )
        if sensitivity.risk_measure is not SbmRiskMeasure.DELTA:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm GIRR delta weighting does not support "
                f"risk_measure={sensitivity.risk_measure.value}"
            )
        bucket = girr_bucket_definition(profile_id, sensitivity.bucket)
        risk_weight, citation_ids = girr_delta_risk_weight(
            profile_id,
            tenor=sensitivity.tenor or "",
            currency=bucket.currency,
            reporting_currency=reporting_currency,
        )
        scaled_amount = sensitivity.amount * risk_weight
        weighted.append(
            WeightedSensitivity(
                sensitivity_id=sensitivity.sensitivity_id,
                risk_class=SbmRiskClass.GIRR,
                risk_measure=SbmRiskMeasure.DELTA,
                bucket=sensitivity.bucket,
                raw_amount=sensitivity.amount,
                risk_weight=risk_weight,
                scaled_amount=scaled_amount,
                citation_ids=citation_ids,
                qualifier=sensitivity.tenor,
            )
        )
    return tuple(weighted)


def weight_girr_vega_sensitivities(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted GIRR vega sensitivities for a supported profile."""

    ensure_profile_supports_risk_class_measure(
        profile_id,
        SbmRiskClass.GIRR,
        SbmRiskMeasure.VEGA,
    )
    default_horizon = girr_vega_liquidity_horizon_days(profile_id)
    weighted: list[WeightedSensitivity] = []
    for sensitivity in sort_sensitivities_deterministic(sensitivities):
        if sensitivity.risk_class is not SbmRiskClass.GIRR:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm GIRR vega weighting does not support "
                f"risk_class={sensitivity.risk_class.value}"
            )
        if sensitivity.risk_measure is not SbmRiskMeasure.VEGA:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm GIRR vega weighting does not support "
                f"risk_measure={sensitivity.risk_measure.value}"
            )
        girr_bucket_definition(profile_id, sensitivity.bucket)
        horizon = (
            sensitivity.liquidity_horizon_days
            if sensitivity.liquidity_horizon_days is not None
            else default_horizon
        )
        risk_weight, citation_ids = vega_risk_weight(
            profile_id,
            liquidity_horizon_days=horizon,
        )
        scaled_amount = sensitivity.amount * risk_weight
        weighted.append(
            WeightedSensitivity(
                sensitivity_id=sensitivity.sensitivity_id,
                risk_class=SbmRiskClass.GIRR,
                risk_measure=SbmRiskMeasure.VEGA,
                bucket=sensitivity.bucket,
                raw_amount=sensitivity.amount,
                risk_weight=risk_weight,
                scaled_amount=scaled_amount,
                citation_ids=citation_ids,
                qualifier=sensitivity.option_tenor,
                liquidity_horizon_days=horizon,
            )
        )
    return tuple(weighted)


def weight_fx_delta_sensitivities(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
    reporting_currency: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted FX delta sensitivities for a supported profile."""

    ensure_profile_supports_risk_class_measure(
        profile_id,
        SbmRiskClass.FX,
        SbmRiskMeasure.DELTA,
    )
    weighted: list[WeightedSensitivity] = []
    for sensitivity in sort_sensitivities_deterministic(sensitivities):
        if sensitivity.risk_class is not SbmRiskClass.FX:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm FX delta weighting does not support "
                f"risk_class={sensitivity.risk_class.value}"
            )
        if sensitivity.risk_measure is not SbmRiskMeasure.DELTA:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm FX delta weighting does not support "
                f"risk_measure={sensitivity.risk_measure.value}"
            )
        bucket = fx_bucket_definition(profile_id, sensitivity.bucket)
        if bucket.currency != sensitivity.risk_factor.strip().upper():
            raise SbmInputError(
                "FX bucket must match risk_factor currency",
                field="bucket",
                sensitivity_id=sensitivity.sensitivity_id,
            )
        risk_weight, citation_ids = fx_delta_risk_weight(
            profile_id,
            currency=bucket.currency,
            reporting_currency=reporting_currency,
        )
        scaled_amount = sensitivity.amount * risk_weight
        weighted.append(
            WeightedSensitivity(
                sensitivity_id=sensitivity.sensitivity_id,
                risk_class=SbmRiskClass.FX,
                risk_measure=SbmRiskMeasure.DELTA,
                bucket=sensitivity.bucket,
                raw_amount=sensitivity.amount,
                risk_weight=risk_weight,
                scaled_amount=scaled_amount,
                citation_ids=citation_ids,
                qualifier=sensitivity.qualifier,
            )
        )
    return tuple(weighted)


def weight_equity_delta_sensitivities(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted equity delta sensitivities for a supported profile."""

    ensure_profile_supports_risk_class_measure(
        profile_id,
        SbmRiskClass.EQUITY,
        SbmRiskMeasure.DELTA,
    )
    weighted: list[WeightedSensitivity] = []
    for sensitivity in sort_sensitivities_deterministic(sensitivities):
        if sensitivity.risk_class is not SbmRiskClass.EQUITY:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm equity delta weighting does not support "
                f"risk_class={sensitivity.risk_class.value}"
            )
        if sensitivity.risk_measure is not SbmRiskMeasure.DELTA:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm equity delta weighting does not support "
                f"risk_measure={sensitivity.risk_measure.value}"
            )
        equity_bucket_definition(profile_id, sensitivity.bucket)
        risk_weight, citation_ids = equity_delta_risk_weight(
            profile_id,
            bucket_id=sensitivity.bucket,
            risk_factor=sensitivity.risk_factor,
        )
        scaled_amount = sensitivity.amount * risk_weight
        weighted.append(
            WeightedSensitivity(
                sensitivity_id=sensitivity.sensitivity_id,
                risk_class=SbmRiskClass.EQUITY,
                risk_measure=SbmRiskMeasure.DELTA,
                bucket=sensitivity.bucket,
                raw_amount=sensitivity.amount,
                risk_weight=risk_weight,
                scaled_amount=scaled_amount,
                citation_ids=citation_ids,
                qualifier=sensitivity.qualifier,
            )
        )
    return tuple(weighted)


def weight_commodity_delta_sensitivities(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted commodity delta sensitivities for a supported profile."""

    ensure_profile_supports_risk_class_measure(
        profile_id,
        SbmRiskClass.COMMODITY,
        SbmRiskMeasure.DELTA,
    )
    weighted: list[WeightedSensitivity] = []
    for sensitivity in sort_sensitivities_deterministic(sensitivities):
        if sensitivity.risk_class is not SbmRiskClass.COMMODITY:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm commodity delta weighting does not support "
                f"risk_class={sensitivity.risk_class.value}"
            )
        if sensitivity.risk_measure is not SbmRiskMeasure.DELTA:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm commodity delta weighting does not support "
                f"risk_measure={sensitivity.risk_measure.value}"
            )
        commodity_bucket_definition(profile_id, sensitivity.bucket)
        risk_weight, citation_ids = commodity_delta_risk_weight(
            profile_id,
            bucket_id=sensitivity.bucket,
        )
        scaled_amount = sensitivity.amount * risk_weight
        weighted.append(
            WeightedSensitivity(
                sensitivity_id=sensitivity.sensitivity_id,
                risk_class=SbmRiskClass.COMMODITY,
                risk_measure=SbmRiskMeasure.DELTA,
                bucket=sensitivity.bucket,
                raw_amount=sensitivity.amount,
                risk_weight=risk_weight,
                scaled_amount=scaled_amount,
                citation_ids=citation_ids,
                qualifier=sensitivity.qualifier,
            )
        )
    return tuple(weighted)


def weight_csr_nonsec_delta_sensitivities(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted CSR non-securitisation delta sensitivities."""

    ensure_profile_supports_risk_class_measure(
        profile_id,
        SbmRiskClass.CSR_NONSEC,
        SbmRiskMeasure.DELTA,
    )
    weighted: list[WeightedSensitivity] = []
    for sensitivity in sort_sensitivities_deterministic(sensitivities):
        if sensitivity.risk_class is not SbmRiskClass.CSR_NONSEC:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm CSR non-securitisation delta weighting does not support "
                f"risk_class={sensitivity.risk_class.value}"
            )
        if sensitivity.risk_measure is not SbmRiskMeasure.DELTA:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm CSR non-securitisation delta weighting does not support "
                f"risk_measure={sensitivity.risk_measure.value}"
            )
        csr_nonsec_validate_delta_inputs(
            profile_id,
            bucket_id=sensitivity.bucket,
            risk_factor=sensitivity.risk_factor,
            tenor=sensitivity.tenor or "",
            qualifier=sensitivity.qualifier or "",
        )
        risk_weight, citation_ids = csr_nonsec_delta_risk_weight(
            profile_id,
            bucket_id=sensitivity.bucket,
        )
        scaled_amount = sensitivity.amount * risk_weight
        weighted.append(
            WeightedSensitivity(
                sensitivity_id=sensitivity.sensitivity_id,
                risk_class=SbmRiskClass.CSR_NONSEC,
                risk_measure=SbmRiskMeasure.DELTA,
                bucket=sensitivity.bucket,
                raw_amount=sensitivity.amount,
                risk_weight=risk_weight,
                scaled_amount=scaled_amount,
                citation_ids=citation_ids,
                qualifier=sensitivity.qualifier,
            )
        )
    return tuple(weighted)


def weight_csr_sec_nonctp_delta_sensitivities(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted CSR securitisation non-CTP delta sensitivities."""

    from frtb_sbm.csr_sec_nonctp_reference_data import (
        csr_sec_nonctp_delta_risk_weight,
        csr_sec_nonctp_validate_delta_inputs,
    )

    ensure_profile_supports_risk_class_measure(
        profile_id,
        SbmRiskClass.CSR_SEC_NONCTP,
        SbmRiskMeasure.DELTA,
    )
    weighted: list[WeightedSensitivity] = []
    for sensitivity in sort_sensitivities_deterministic(sensitivities):
        if sensitivity.risk_class is not SbmRiskClass.CSR_SEC_NONCTP:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm CSR securitisation non-CTP delta weighting does not support "
                f"risk_class={sensitivity.risk_class.value}"
            )
        if sensitivity.risk_measure is not SbmRiskMeasure.DELTA:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm CSR securitisation non-CTP delta weighting does not support "
                f"risk_measure={sensitivity.risk_measure.value}"
            )
        csr_sec_nonctp_validate_delta_inputs(
            profile_id,
            bucket_id=sensitivity.bucket,
            risk_factor=sensitivity.risk_factor,
            tenor=sensitivity.tenor or "",
            qualifier=sensitivity.qualifier or "",
        )
        risk_weight, citation_ids = csr_sec_nonctp_delta_risk_weight(
            profile_id,
            bucket_id=sensitivity.bucket,
        )
        scaled_amount = sensitivity.amount * risk_weight
        weighted.append(
            WeightedSensitivity(
                sensitivity_id=sensitivity.sensitivity_id,
                risk_class=SbmRiskClass.CSR_SEC_NONCTP,
                risk_measure=SbmRiskMeasure.DELTA,
                bucket=sensitivity.bucket,
                raw_amount=sensitivity.amount,
                risk_weight=risk_weight,
                scaled_amount=scaled_amount,
                citation_ids=citation_ids,
                qualifier=sensitivity.qualifier,
            )
        )
    return tuple(weighted)


def weight_csr_sec_ctp_delta_sensitivities(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted CSR securitisation CTP delta sensitivities."""

    from frtb_sbm.csr_sec_ctp_reference_data import (
        csr_sec_ctp_delta_risk_weight,
        csr_sec_ctp_validate_delta_inputs,
        ensure_csr_sec_ctp_decomposition_evidence,
    )

    ensure_profile_supports_risk_class_measure(
        profile_id,
        SbmRiskClass.CSR_SEC_CTP,
        SbmRiskMeasure.DELTA,
    )
    weighted: list[WeightedSensitivity] = []
    for sensitivity in sort_sensitivities_deterministic(sensitivities):
        if sensitivity.risk_class is not SbmRiskClass.CSR_SEC_CTP:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm CSR securitisation CTP delta weighting does not support "
                f"risk_class={sensitivity.risk_class.value}"
            )
        if sensitivity.risk_measure is not SbmRiskMeasure.DELTA:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm CSR securitisation CTP delta weighting does not support "
                f"risk_measure={sensitivity.risk_measure.value}"
            )
        ensure_csr_sec_ctp_decomposition_evidence(sensitivity)
        csr_sec_ctp_validate_delta_inputs(
            profile_id,
            bucket_id=sensitivity.bucket,
            risk_factor=sensitivity.risk_factor,
            tenor=sensitivity.tenor or "",
            qualifier=sensitivity.qualifier or "",
        )
        risk_weight, citation_ids = csr_sec_ctp_delta_risk_weight(
            profile_id,
            bucket_id=sensitivity.bucket,
        )
        scaled_amount = sensitivity.amount * risk_weight
        weighted.append(
            WeightedSensitivity(
                sensitivity_id=sensitivity.sensitivity_id,
                risk_class=SbmRiskClass.CSR_SEC_CTP,
                risk_measure=SbmRiskMeasure.DELTA,
                bucket=sensitivity.bucket,
                raw_amount=sensitivity.amount,
                risk_weight=risk_weight,
                scaled_amount=scaled_amount,
                citation_ids=citation_ids,
                qualifier=sensitivity.qualifier,
            )
        )
    return tuple(weighted)


__all__ = [
    "compute_weighted_sensitivities",
    "sort_weighted_sensitivities_deterministic",
    "weight_commodity_delta_sensitivities",
    "weight_csr_nonsec_delta_sensitivities",
    "weight_csr_sec_ctp_delta_sensitivities",
    "weight_csr_sec_nonctp_delta_sensitivities",
    "weight_equity_delta_sensitivities",
    "weight_fx_delta_sensitivities",
    "weight_girr_delta_sensitivities",
    "weight_girr_vega_sensitivities",
    "weighted_sensitivity_sort_key",
]
