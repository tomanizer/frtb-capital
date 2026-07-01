"""Non-GIRR vega SBM weighting kernels.

Regulatory traceability:
    Basel MAR21.90-MAR21.92 for vega weighted sensitivity construction,
    with risk-class factor axes validated against MAR21.9-MAR21.14.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm._citations import merge_citation_ids as _merge_citation_ids
from frtb_sbm.batch import SbmSensitivityBatch, sorted_sbm_batch_indices
from frtb_sbm.data_models import (
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    WeightedSensitivity,
)
from frtb_sbm.kernel.weighting import _liquidity_horizon_at, _optional_axis_value
from frtb_sbm.reference_data import vega_liquidity_horizon_days, vega_risk_weight
from frtb_sbm.reference_profiles import _resolve_supported_profile
from frtb_sbm.regimes import ensure_profile_supports_risk_class_measure
from frtb_sbm.risk_classes.vega_validation import (
    _validate_non_girr_vega_batch_row,
    _validate_non_girr_vega_sensitivity,
)
from frtb_sbm.validation import sort_sensitivities_deterministic


def weight_non_girr_vega_sensitivities(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted non-GIRR vega sensitivities for a supported profile.
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
            risk_class=sensitivity.risk_class,
        )
        citation_ids = _merge_citation_ids(
            _weighted_sensitivity_citation_ids(profile_id, sensitivity.risk_class),
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
    """Return cited weighted non-GIRR vega sensitivities from a package-owned batch.
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
            risk_class=risk_class,
        )
        citation_ids = _merge_citation_ids(
            _weighted_sensitivity_citation_ids(profile_id, risk_class),
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


def _weighted_sensitivity_citation_ids(
    profile_id: str,
    risk_class: SbmRiskClass,
) -> tuple[str, ...]:
    profile = _resolve_supported_profile(profile_id)
    if profile is SbmRegulatoryProfile.US_NPR_2_0 and risk_class is SbmRiskClass.FX:
        return (
            "us_npr_91_fr_14952_va7a_sbm_scope",
            "us_npr_91_fr_14952_va7a_fx_vega_lh_rw",
        )
    return ("basel_mar21_90", "basel_mar21_91")


__all__ = [
    "weight_non_girr_vega_sensitivities",
    "weight_non_girr_vega_sensitivity_batch",
]
