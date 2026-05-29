"""
Cited risk-weight lookup and weighted sensitivity records.

Regulatory traceability:
    Basel MAR21.39-MAR21.40 — GIRR delta risk weights.
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
from frtb_sbm.reference_data import girr_bucket_definition, girr_delta_risk_weight
from frtb_sbm.regimes import ensure_profile_supports_risk_class_measure
from frtb_sbm.validation import sort_sensitivities_deterministic


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
    if risk_classes == {SbmRiskClass.GIRR} and risk_measures == {SbmRiskMeasure.DELTA}:
        return weight_girr_delta_sensitivities(
            sensitivities,
            profile_id=profile_id,
            reporting_currency=reporting_currency,
        )
    raise UnsupportedRegulatoryFeatureError(
        "frtb-sbm weighted sensitivity lookup supports only GIRR delta inputs in phase 1"
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


__all__ = [
    "compute_weighted_sensitivities",
    "sort_weighted_sensitivities_deterministic",
    "weight_girr_delta_sensitivities",
    "weighted_sensitivity_sort_key",
]
