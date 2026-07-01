"""GIRR delta and vega SBM weighting kernels.

Regulatory traceability:
    Basel MAR21.39-MAR21.40 for GIRR delta risk weights; MAR21.92 for
    GIRR vega liquidity horizon and risk-weight scaling.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.batch import SbmSensitivityBatch, sorted_girr_vega_batch_indices
from frtb_sbm.data_models import SbmRiskClass, SbmRiskMeasure, SbmSensitivity, WeightedSensitivity
from frtb_sbm.kernel.weighting import _liquidity_horizon_at, _required_optional_axis_value
from frtb_sbm.org_scope import scope_at
from frtb_sbm.reference_data import (
    girr_bucket_definition,
    girr_delta_risk_weight,
    girr_vega_liquidity_horizon_days,
    vega_risk_weight,
)
from frtb_sbm.regimes import ensure_profile_supports_risk_class_measure
from frtb_sbm.validation import sort_sensitivities_deterministic


def weight_girr_delta_sensitivities(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
    reporting_currency: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted GIRR delta sensitivities for a supported profile.
    Parameters
    ----------
    sensitivities : Sequence[SbmSensitivity]
        See signature.
    profile_id : str
        See signature.
    reporting_currency : str
        See signature.

    Returns
    -------
    tuple[WeightedSensitivity, ...]
    """

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
                org_scope=sensitivity.org_scope,
            )
        )
    return tuple(weighted)


def weight_girr_vega_sensitivities(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted GIRR vega sensitivities for a supported profile.
    Parameters
    ----------
    sensitivities : Sequence[SbmSensitivity]
        See signature.
    profile_id : str
        See signature.

    Returns
    -------
    tuple[WeightedSensitivity, ...]
    """

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
                org_scope=sensitivity.org_scope,
            )
        )
    return tuple(weighted)


def weight_girr_vega_sensitivity_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted GIRR vega sensitivities from a package-owned batch.
    Parameters
    ----------
    batch : SbmSensitivityBatch
        See signature.
    profile_id : str
        See signature.

    Returns
    -------
    tuple[WeightedSensitivity, ...]
    """

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
                org_scope=scope_at(batch.org_scopes, index),
            )
        )
    return tuple(weighted)


__all__ = [
    "weight_girr_delta_sensitivities",
    "weight_girr_vega_sensitivities",
    "weight_girr_vega_sensitivity_batch",
]
