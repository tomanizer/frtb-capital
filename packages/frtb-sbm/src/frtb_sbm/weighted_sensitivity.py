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
from numbers import Integral
from typing import cast

import numpy as np
import numpy.typing as npt
from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm._citations import merge_citation_ids as _merge_citation_ids
from frtb_sbm._text import require_text as _require_text
from frtb_sbm.batch import (
    SbmSensitivityBatch,
    sorted_commodity_delta_batch_indices,
    sorted_csr_nonsec_delta_batch_indices,
    sorted_csr_sec_ctp_delta_batch_indices,
    sorted_csr_sec_nonctp_delta_batch_indices,
    sorted_equity_delta_batch_indices,
    sorted_fx_delta_batch_indices,
    sorted_girr_vega_batch_indices,
    sorted_sbm_batch_indices,
)
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
    csr_nonsec_validate_vega_inputs,
    equity_bucket_definition,
    equity_delta_risk_weight,
    fx_bucket_definition,
    fx_delta_risk_weight,
    girr_bucket_definition,
    girr_delta_risk_weight,
    girr_vega_liquidity_horizon_days,
    girr_vega_option_tenor_definition,
    normalise_fx_delta_currency_code,
    vega_liquidity_horizon_days,
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
    if risk_measure is SbmRiskMeasure.VEGA:
        return weight_non_girr_vega_sensitivities(
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


def weight_girr_vega_sensitivity_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted GIRR vega sensitivities from a package-owned batch."""

    ensure_profile_supports_risk_class_measure(
        profile_id,
        SbmRiskClass.GIRR,
        SbmRiskMeasure.VEGA,
    )
    if batch.risk_class is not SbmRiskClass.GIRR:
        raise UnsupportedRegulatoryFeatureError(
            f"frtb-sbm GIRR vega weighting does not support risk_class={batch.risk_class.value}"
        )
    if batch.risk_measure is not SbmRiskMeasure.VEGA:
        raise UnsupportedRegulatoryFeatureError(
            f"frtb-sbm GIRR vega weighting does not support risk_measure={batch.risk_measure.value}"
        )
    default_horizon = girr_vega_liquidity_horizon_days(profile_id)
    weighted: list[WeightedSensitivity] = []
    for row_index in sorted_girr_vega_batch_indices(batch):
        index = int(row_index)
        horizon = _liquidity_horizon_at(
            batch,
            index,
            default_horizon=default_horizon,
        )
        risk_weight, citation_ids = vega_risk_weight(
            profile_id,
            liquidity_horizon_days=horizon,
        )
        amount = float(batch.amounts[index])
        weighted.append(
            WeightedSensitivity(
                sensitivity_id=cast(str, batch.sensitivity_ids[index]),
                risk_class=SbmRiskClass.GIRR,
                risk_measure=SbmRiskMeasure.VEGA,
                bucket=cast(str, batch.buckets[index]),
                raw_amount=amount,
                risk_weight=risk_weight,
                scaled_amount=amount * risk_weight,
                citation_ids=citation_ids,
                qualifier=_required_optional_axis_value(batch.option_tenors, index, "option_tenor"),
                liquidity_horizon_days=horizon,
            )
        )
    return tuple(weighted)


def weight_non_girr_vega_sensitivities(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted non-GIRR vega sensitivities for a supported profile."""

    if not sensitivities:
        return ()
    risk_classes = {item.risk_class for item in sensitivities}
    if len(risk_classes) != 1:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm non-GIRR vega weighting requires homogeneous risk class"
        )
    risk_class = next(iter(risk_classes))
    if risk_class is SbmRiskClass.GIRR:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm non-GIRR vega weighting does not support GIRR; "
            "use weight_girr_vega_sensitivities"
        )
    ensure_profile_supports_risk_class_measure(
        profile_id,
        risk_class,
        SbmRiskMeasure.VEGA,
    )
    weighted: list[WeightedSensitivity] = []
    for sensitivity in sort_sensitivities_deterministic(sensitivities):
        if sensitivity.risk_class is not risk_class:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm non-GIRR vega weighting requires homogeneous risk class"
            )
        if sensitivity.risk_measure is not SbmRiskMeasure.VEGA:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm non-GIRR vega weighting does not support "
                f"risk_measure={sensitivity.risk_measure.value}"
            )
        factor_key, risk_factor_citations = _validate_non_girr_vega_sensitivity(
            sensitivity,
            profile_id=profile_id,
        )
        horizon = (
            sensitivity.liquidity_horizon_days
            if sensitivity.liquidity_horizon_days is not None
            else vega_liquidity_horizon_days(
                profile_id,
                risk_class=sensitivity.risk_class,
                bucket_id=sensitivity.bucket,
            )
        )
        risk_weight, weight_citations = vega_risk_weight(
            profile_id,
            liquidity_horizon_days=horizon,
        )
        citation_ids = _merge_citation_ids(
            ("basel_mar21_90", "basel_mar21_91"),
            risk_factor_citations,
            weight_citations,
        )
        scaled_amount = sensitivity.amount * risk_weight
        weighted.append(
            WeightedSensitivity(
                sensitivity_id=sensitivity.sensitivity_id,
                risk_class=sensitivity.risk_class,
                risk_measure=SbmRiskMeasure.VEGA,
                bucket=sensitivity.bucket,
                raw_amount=sensitivity.amount,
                risk_weight=risk_weight,
                scaled_amount=scaled_amount,
                citation_ids=citation_ids,
                qualifier=sensitivity.qualifier,
                liquidity_horizon_days=horizon,
                factor_key=factor_key,
            )
        )
    return tuple(weighted)


def weight_non_girr_vega_sensitivity_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted non-GIRR vega sensitivities from a package-owned batch."""

    risk_class = batch.risk_class
    if risk_class is SbmRiskClass.GIRR:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm non-GIRR vega weighting does not support GIRR; "
            "use weight_girr_vega_sensitivity_batch"
        )
    if batch.risk_measure is not SbmRiskMeasure.VEGA:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm non-GIRR vega weighting does not support "
            f"risk_measure={batch.risk_measure.value}"
        )
    ensure_profile_supports_risk_class_measure(
        profile_id,
        risk_class,
        SbmRiskMeasure.VEGA,
    )
    weighted: list[WeightedSensitivity] = []
    for row_index in sorted_sbm_batch_indices(batch):
        index = int(row_index)
        factor_key, risk_factor_citations = _validate_non_girr_vega_batch_row(
            batch,
            index,
            profile_id=profile_id,
        )
        bucket_id = cast(str, batch.buckets[index])
        horizon = _liquidity_horizon_at(
            batch,
            index,
            default_horizon=vega_liquidity_horizon_days(
                profile_id,
                risk_class=risk_class,
                bucket_id=bucket_id,
            ),
        )
        risk_weight, weight_citations = vega_risk_weight(
            profile_id,
            liquidity_horizon_days=horizon,
        )
        citation_ids = _merge_citation_ids(
            ("basel_mar21_90", "basel_mar21_91"),
            risk_factor_citations,
            weight_citations,
        )
        amount = float(batch.amounts[index])
        weighted.append(
            WeightedSensitivity(
                sensitivity_id=cast(str, batch.sensitivity_ids[index]),
                risk_class=risk_class,
                risk_measure=SbmRiskMeasure.VEGA,
                bucket=bucket_id,
                raw_amount=amount,
                risk_weight=risk_weight,
                scaled_amount=amount * risk_weight,
                citation_ids=citation_ids,
                qualifier=_optional_axis_value(batch.qualifiers, index),
                liquidity_horizon_days=horizon,
                factor_key=factor_key,
            )
        )
    return tuple(weighted)


def _validate_non_girr_vega_sensitivity(
    sensitivity: SbmSensitivity,
    *,
    profile_id: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    option_tenor = girr_vega_option_tenor_definition(
        profile_id,
        sensitivity.option_tenor or "",
    ).tenor
    if sensitivity.risk_class is SbmRiskClass.FX:
        bucket = fx_bucket_definition(profile_id, sensitivity.bucket)
        risk_factor = normalise_fx_delta_currency_code(sensitivity.risk_factor)
        if bucket.currency != risk_factor:
            raise SbmInputError(
                "FX vega bucket must match risk_factor currency",
                field="bucket",
                sensitivity_id=sensitivity.sensitivity_id,
            )
        return (bucket.currency, option_tenor), ("basel_mar21_14", "basel_mar21_86")
    if sensitivity.risk_class is SbmRiskClass.EQUITY:
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
    if sensitivity.risk_class is SbmRiskClass.COMMODITY:
        commodity_bucket_definition(profile_id, sensitivity.bucket)
        commodity = _require_text(
            sensitivity.risk_factor,
            "risk_factor",
            sensitivity.sensitivity_id,
        )
        return (sensitivity.bucket, commodity, option_tenor), ("basel_mar21_13", "basel_mar21_81")
    if sensitivity.risk_class is SbmRiskClass.CSR_NONSEC:
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
    if sensitivity.risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        from frtb_sbm.csr_sec_nonctp_reference_data import (
            csr_sec_nonctp_validate_vega_inputs,
        )

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
    if sensitivity.risk_class is SbmRiskClass.CSR_SEC_CTP:
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
    raise UnsupportedRegulatoryFeatureError(
        f"non-GIRR vega weighting is unsupported for risk_class={sensitivity.risk_class.value}"
    )


def _validate_non_girr_vega_batch_row(
    batch: SbmSensitivityBatch,
    row_index: int,
    *,
    profile_id: str,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    sensitivity_id = cast(str, batch.sensitivity_ids[row_index])
    risk_class = batch.risk_class
    bucket_id = cast(str, batch.buckets[row_index])
    risk_factor = cast(str, batch.risk_factors[row_index])
    option_tenor = girr_vega_option_tenor_definition(
        profile_id,
        _required_optional_axis_value(batch.option_tenors, row_index, "option_tenor"),
    ).tenor

    if risk_class is SbmRiskClass.FX:
        bucket = fx_bucket_definition(profile_id, bucket_id)
        normalized_risk_factor = normalise_fx_delta_currency_code(risk_factor)
        if bucket.currency != normalized_risk_factor:
            raise SbmInputError(
                "FX vega bucket must match risk_factor currency",
                field="bucket",
                sensitivity_id=sensitivity_id,
            )
        return (bucket.currency, option_tenor), ("basel_mar21_14", "basel_mar21_86")
    if risk_class is SbmRiskClass.EQUITY:
        from frtb_sbm.equity_reference_data import EQUITY_SPOT_RISK_FACTOR

        equity_bucket_definition(profile_id, bucket_id)
        if risk_factor.strip().upper() != EQUITY_SPOT_RISK_FACTOR:
            raise UnsupportedRegulatoryFeatureError(
                "equity vega has no capital requirement for equity repo rates (MAR21.12(2)(b))"
            )
        qualifier = _require_text(
            _optional_axis_value(batch.qualifiers, row_index),
            "qualifier",
            sensitivity_id,
        )
        return (
            bucket_id,
            qualifier,
            EQUITY_SPOT_RISK_FACTOR,
            option_tenor,
        ), ("basel_mar21_12", "basel_mar21_72")
    if risk_class is SbmRiskClass.COMMODITY:
        commodity_bucket_definition(profile_id, bucket_id)
        commodity = _require_text(risk_factor, "risk_factor", sensitivity_id)
        return (bucket_id, commodity, option_tenor), ("basel_mar21_13", "basel_mar21_81")
    if risk_class is SbmRiskClass.CSR_NONSEC:
        qualifier = _require_text(
            _optional_axis_value(batch.qualifiers, row_index),
            "qualifier",
            sensitivity_id,
        )
        csr_nonsec_validate_vega_inputs(
            profile_id,
            bucket_id=bucket_id,
            risk_factor=risk_factor,
            qualifier=qualifier,
        )
        return (
            bucket_id,
            qualifier,
            risk_factor.strip().upper(),
            option_tenor,
        ), ("basel_mar21_9", "basel_mar21_51")
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        from frtb_sbm.csr_sec_nonctp_reference_data import (
            csr_sec_nonctp_validate_vega_inputs,
        )

        qualifier = _require_text(
            _optional_axis_value(batch.qualifiers, row_index),
            "qualifier",
            sensitivity_id,
        )
        csr_sec_nonctp_validate_vega_inputs(
            profile_id,
            bucket_id=bucket_id,
            risk_factor=risk_factor,
            qualifier=qualifier,
        )
        return (
            bucket_id,
            qualifier,
            risk_factor.strip().upper(),
            option_tenor,
        ), ("basel_mar21_10", "basel_mar21_61")
    if risk_class is SbmRiskClass.CSR_SEC_CTP:
        from frtb_sbm.csr_sec_ctp_reference_data import (
            csr_sec_ctp_validate_vega_inputs,
        )

        _ensure_csr_sec_ctp_decomposition_evidence_for_batch(batch, row_index)
        qualifier = _require_text(
            _optional_axis_value(batch.qualifiers, row_index),
            "qualifier",
            sensitivity_id,
        )
        csr_sec_ctp_validate_vega_inputs(
            profile_id,
            bucket_id=bucket_id,
            risk_factor=risk_factor,
            qualifier=qualifier,
        )
        return (
            bucket_id,
            qualifier,
            risk_factor.strip().upper(),
            option_tenor,
        ), ("basel_mar21_11", "basel_mar21_58")
    raise UnsupportedRegulatoryFeatureError(
        f"non-GIRR vega weighting is unsupported for risk_class={risk_class.value}"
    )


def weight_fx_delta_sensitivity_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
    reporting_currency: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted FX delta sensitivities from a package-owned batch."""

    ensure_profile_supports_risk_class_measure(
        profile_id,
        SbmRiskClass.FX,
        SbmRiskMeasure.DELTA,
    )
    if batch.risk_class is not SbmRiskClass.FX:
        raise UnsupportedRegulatoryFeatureError(
            f"frtb-sbm FX delta weighting does not support risk_class={batch.risk_class.value}"
        )
    if batch.risk_measure is not SbmRiskMeasure.DELTA:
        raise UnsupportedRegulatoryFeatureError(
            f"frtb-sbm FX delta weighting does not support risk_measure={batch.risk_measure.value}"
        )
    weighted: list[WeightedSensitivity] = []
    for row_index in sorted_fx_delta_batch_indices(batch):
        index = int(row_index)
        bucket = fx_bucket_definition(profile_id, cast(str, batch.buckets[index]))
        risk_factor = cast(str, batch.risk_factors[index]).strip().upper()
        if bucket.currency != risk_factor:
            raise SbmInputError(
                "FX bucket must match risk_factor currency",
                field="bucket",
                sensitivity_id=cast(str, batch.sensitivity_ids[index]),
            )
        risk_weight, citation_ids = fx_delta_risk_weight(
            profile_id,
            currency=bucket.currency,
            reporting_currency=reporting_currency,
        )
        amount = float(batch.amounts[index])
        weighted.append(
            WeightedSensitivity(
                sensitivity_id=cast(str, batch.sensitivity_ids[index]),
                risk_class=SbmRiskClass.FX,
                risk_measure=SbmRiskMeasure.DELTA,
                bucket=cast(str, batch.buckets[index]),
                raw_amount=amount,
                risk_weight=risk_weight,
                scaled_amount=amount * risk_weight,
                citation_ids=citation_ids,
                qualifier=_optional_axis_value(batch.qualifiers, index),
            )
        )
    return tuple(weighted)


def weight_equity_delta_sensitivity_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted equity delta sensitivities from a package-owned batch."""

    ensure_profile_supports_risk_class_measure(
        profile_id,
        SbmRiskClass.EQUITY,
        SbmRiskMeasure.DELTA,
    )
    if batch.risk_class is not SbmRiskClass.EQUITY:
        raise UnsupportedRegulatoryFeatureError(
            f"frtb-sbm equity delta weighting does not support risk_class={batch.risk_class.value}"
        )
    if batch.risk_measure is not SbmRiskMeasure.DELTA:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm equity delta weighting does not support "
            f"risk_measure={batch.risk_measure.value}"
        )
    weighted: list[WeightedSensitivity] = []
    for row_index in sorted_equity_delta_batch_indices(batch):
        index = int(row_index)
        bucket_id = cast(str, batch.buckets[index])
        risk_factor = cast(str, batch.risk_factors[index])
        equity_bucket_definition(profile_id, bucket_id)
        risk_weight, citation_ids = equity_delta_risk_weight(
            profile_id,
            bucket_id=bucket_id,
            risk_factor=risk_factor,
        )
        amount = float(batch.amounts[index])
        weighted.append(
            WeightedSensitivity(
                sensitivity_id=cast(str, batch.sensitivity_ids[index]),
                risk_class=SbmRiskClass.EQUITY,
                risk_measure=SbmRiskMeasure.DELTA,
                bucket=bucket_id,
                raw_amount=amount,
                risk_weight=risk_weight,
                scaled_amount=amount * risk_weight,
                citation_ids=citation_ids,
                qualifier=_required_optional_axis_value(batch.qualifiers, index, "qualifier"),
            )
        )
    return tuple(weighted)


def weight_commodity_delta_sensitivity_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted commodity delta sensitivities from a package-owned batch."""

    ensure_profile_supports_risk_class_measure(
        profile_id,
        SbmRiskClass.COMMODITY,
        SbmRiskMeasure.DELTA,
    )
    if batch.risk_class is not SbmRiskClass.COMMODITY:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm commodity delta weighting does not support "
            f"risk_class={batch.risk_class.value}"
        )
    if batch.risk_measure is not SbmRiskMeasure.DELTA:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm commodity delta weighting does not support "
            f"risk_measure={batch.risk_measure.value}"
        )
    weighted: list[WeightedSensitivity] = []
    for row_index in sorted_commodity_delta_batch_indices(batch):
        index = int(row_index)
        bucket_id = cast(str, batch.buckets[index])
        commodity_bucket_definition(profile_id, bucket_id)
        risk_weight, citation_ids = commodity_delta_risk_weight(
            profile_id,
            bucket_id=bucket_id,
        )
        amount = float(batch.amounts[index])
        weighted.append(
            WeightedSensitivity(
                sensitivity_id=cast(str, batch.sensitivity_ids[index]),
                risk_class=SbmRiskClass.COMMODITY,
                risk_measure=SbmRiskMeasure.DELTA,
                bucket=bucket_id,
                raw_amount=amount,
                risk_weight=risk_weight,
                scaled_amount=amount * risk_weight,
                citation_ids=citation_ids,
                qualifier=_required_optional_axis_value(batch.qualifiers, index, "qualifier"),
            )
        )
    return tuple(weighted)


def weight_csr_nonsec_delta_sensitivity_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted CSR non-securitisation delta sensitivities from a batch."""

    ensure_profile_supports_risk_class_measure(
        profile_id,
        SbmRiskClass.CSR_NONSEC,
        SbmRiskMeasure.DELTA,
    )
    if batch.risk_class is not SbmRiskClass.CSR_NONSEC:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm CSR non-securitisation delta weighting does not support "
            f"risk_class={batch.risk_class.value}"
        )
    if batch.risk_measure is not SbmRiskMeasure.DELTA:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm CSR non-securitisation delta weighting does not support "
            f"risk_measure={batch.risk_measure.value}"
        )
    weighted: list[WeightedSensitivity] = []
    for row_index in sorted_csr_nonsec_delta_batch_indices(batch):
        index = int(row_index)
        bucket_id = cast(str, batch.buckets[index])
        risk_factor = cast(str, batch.risk_factors[index])
        tenor = cast(str, batch.tenors[index])
        qualifier = _required_optional_axis_value(batch.qualifiers, index, "qualifier")
        csr_nonsec_validate_delta_inputs(
            profile_id,
            bucket_id=bucket_id,
            risk_factor=risk_factor,
            tenor=tenor,
            qualifier=qualifier,
        )
        risk_weight, citation_ids = csr_nonsec_delta_risk_weight(
            profile_id,
            bucket_id=bucket_id,
        )
        amount = float(batch.amounts[index])
        weighted.append(
            WeightedSensitivity(
                sensitivity_id=cast(str, batch.sensitivity_ids[index]),
                risk_class=SbmRiskClass.CSR_NONSEC,
                risk_measure=SbmRiskMeasure.DELTA,
                bucket=bucket_id,
                raw_amount=amount,
                risk_weight=risk_weight,
                scaled_amount=amount * risk_weight,
                citation_ids=citation_ids,
                qualifier=qualifier,
            )
        )
    return tuple(weighted)


def weight_csr_sec_nonctp_delta_sensitivity_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted CSR securitisation non-CTP delta sensitivities from a batch."""

    from frtb_sbm.csr_sec_nonctp_reference_data import (
        csr_sec_nonctp_delta_risk_weight,
        csr_sec_nonctp_validate_delta_inputs,
    )

    ensure_profile_supports_risk_class_measure(
        profile_id,
        SbmRiskClass.CSR_SEC_NONCTP,
        SbmRiskMeasure.DELTA,
    )
    if batch.risk_class is not SbmRiskClass.CSR_SEC_NONCTP:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm CSR securitisation non-CTP delta weighting does not support "
            f"risk_class={batch.risk_class.value}"
        )
    if batch.risk_measure is not SbmRiskMeasure.DELTA:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm CSR securitisation non-CTP delta weighting does not support "
            f"risk_measure={batch.risk_measure.value}"
        )
    weighted: list[WeightedSensitivity] = []
    for row_index in sorted_csr_sec_nonctp_delta_batch_indices(batch):
        index = int(row_index)
        bucket_id = cast(str, batch.buckets[index])
        risk_factor = cast(str, batch.risk_factors[index])
        tenor = cast(str, batch.tenors[index])
        qualifier = _required_optional_axis_value(batch.qualifiers, index, "qualifier")
        csr_sec_nonctp_validate_delta_inputs(
            profile_id,
            bucket_id=bucket_id,
            risk_factor=risk_factor,
            tenor=tenor,
            qualifier=qualifier,
        )
        risk_weight, citation_ids = csr_sec_nonctp_delta_risk_weight(
            profile_id,
            bucket_id=bucket_id,
        )
        amount = float(batch.amounts[index])
        weighted.append(
            WeightedSensitivity(
                sensitivity_id=cast(str, batch.sensitivity_ids[index]),
                risk_class=SbmRiskClass.CSR_SEC_NONCTP,
                risk_measure=SbmRiskMeasure.DELTA,
                bucket=bucket_id,
                raw_amount=amount,
                risk_weight=risk_weight,
                scaled_amount=amount * risk_weight,
                citation_ids=citation_ids,
                qualifier=qualifier,
            )
        )
    return tuple(weighted)


def weight_csr_sec_ctp_delta_sensitivity_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted CSR securitisation CTP delta sensitivities from a batch."""

    from frtb_sbm.csr_sec_ctp_reference_data import (
        csr_sec_ctp_delta_risk_weight,
        csr_sec_ctp_validate_delta_inputs,
    )

    ensure_profile_supports_risk_class_measure(
        profile_id,
        SbmRiskClass.CSR_SEC_CTP,
        SbmRiskMeasure.DELTA,
    )
    if batch.risk_class is not SbmRiskClass.CSR_SEC_CTP:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm CSR securitisation CTP delta weighting does not support "
            f"risk_class={batch.risk_class.value}"
        )
    if batch.risk_measure is not SbmRiskMeasure.DELTA:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm CSR securitisation CTP delta weighting does not support "
            f"risk_measure={batch.risk_measure.value}"
        )
    weighted: list[WeightedSensitivity] = []
    for row_index in sorted_csr_sec_ctp_delta_batch_indices(batch):
        index = int(row_index)
        _ensure_csr_sec_ctp_decomposition_evidence_for_batch(batch, index)
        bucket_id = cast(str, batch.buckets[index])
        risk_factor = cast(str, batch.risk_factors[index])
        tenor = cast(str, batch.tenors[index])
        qualifier = _required_optional_axis_value(batch.qualifiers, index, "qualifier")
        csr_sec_ctp_validate_delta_inputs(
            profile_id,
            bucket_id=bucket_id,
            risk_factor=risk_factor,
            tenor=tenor,
            qualifier=qualifier,
        )
        risk_weight, citation_ids = csr_sec_ctp_delta_risk_weight(
            profile_id,
            bucket_id=bucket_id,
        )
        amount = float(batch.amounts[index])
        weighted.append(
            WeightedSensitivity(
                sensitivity_id=cast(str, batch.sensitivity_ids[index]),
                risk_class=SbmRiskClass.CSR_SEC_CTP,
                risk_measure=SbmRiskMeasure.DELTA,
                bucket=bucket_id,
                raw_amount=amount,
                risk_weight=risk_weight,
                scaled_amount=amount * risk_weight,
                citation_ids=citation_ids,
                qualifier=qualifier,
            )
        )
    return tuple(weighted)


def _ensure_csr_sec_ctp_decomposition_evidence_for_batch(
    batch: SbmSensitivityBatch,
    row_index: int,
) -> None:
    from frtb_sbm.csr_sec_ctp_reference_data import (
        CSR_SEC_CTP_DECOMPOSITION_EVIDENCE_FLAG,
        CSR_SEC_CTP_DECOMPOSITION_REQUIRED_FLAG,
    )

    if batch.mapping_citation_ids is None:
        return
    flags = set(batch.mapping_citation_ids[row_index])
    if CSR_SEC_CTP_DECOMPOSITION_REQUIRED_FLAG not in flags:
        return
    if CSR_SEC_CTP_DECOMPOSITION_EVIDENCE_FLAG in flags:
        return
    raise UnsupportedRegulatoryFeatureError(
        "frtb-sbm CSR securitisation CTP requires decomposition evidence when "
        "index constituent decomposition is requested; "
        f"sensitivity_id={cast(str, batch.sensitivity_ids[row_index])!r}"
    )


def _liquidity_horizon_at(
    batch: SbmSensitivityBatch,
    row_index: int,
    *,
    default_horizon: int,
) -> int:
    if batch.liquidity_horizon_days is None:
        return default_horizon
    value = batch.liquidity_horizon_days[row_index]
    if value is None:
        return default_horizon
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise SbmInputError(
            "value must be a positive integer",
            field="liquidity_horizon_days",
            sensitivity_id=cast(str, batch.sensitivity_ids[row_index]),
        )
    horizon = int(value)
    if horizon <= 0:
        raise SbmInputError(
            "value must be a positive integer",
            field="liquidity_horizon_days",
            sensitivity_id=cast(str, batch.sensitivity_ids[row_index]),
        )
    return horizon


def _required_optional_axis_value(
    values: npt.NDArray[np.object_] | None,
    row_index: int,
    field: str,
) -> str:
    if values is None:
        raise SbmInputError(f"{field} is required", field=field)
    value = values[row_index]
    if not isinstance(value, str) or not value.strip():
        raise SbmInputError("non-empty text is required", field=field)
    return value


def _optional_axis_value(
    values: npt.NDArray[np.object_] | None,
    row_index: int,
) -> str | None:
    if values is None:
        return None
    value = values[row_index]
    if value is None:
        return None
    return cast(str, value)


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
    "weight_commodity_delta_sensitivity_batch",
    "weight_csr_nonsec_delta_sensitivities",
    "weight_csr_nonsec_delta_sensitivity_batch",
    "weight_csr_sec_ctp_delta_sensitivities",
    "weight_csr_sec_ctp_delta_sensitivity_batch",
    "weight_csr_sec_nonctp_delta_sensitivities",
    "weight_csr_sec_nonctp_delta_sensitivity_batch",
    "weight_equity_delta_sensitivities",
    "weight_equity_delta_sensitivity_batch",
    "weight_fx_delta_sensitivities",
    "weight_fx_delta_sensitivity_batch",
    "weight_girr_delta_sensitivities",
    "weight_girr_vega_sensitivities",
    "weight_girr_vega_sensitivity_batch",
    "weight_non_girr_vega_sensitivities",
    "weight_non_girr_vega_sensitivity_batch",
    "weighted_sensitivity_sort_key",
]
