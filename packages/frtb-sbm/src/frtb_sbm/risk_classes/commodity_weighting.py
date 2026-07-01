"""Commodity delta SBM weighting kernels.

Regulatory traceability:
    Basel MAR21.76-MAR21.80 for commodity delta buckets and risk weights.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.batch import SbmSensitivityBatch, sorted_commodity_delta_batch_indices
from frtb_sbm.data_models import SbmRiskClass, SbmRiskMeasure, SbmSensitivity, WeightedSensitivity
from frtb_sbm.kernel.weighting import _required_optional_axis_value
from frtb_sbm.org_scope import scope_at
from frtb_sbm.reference_data import commodity_bucket_definition, commodity_delta_risk_weight
from frtb_sbm.regimes import ensure_profile_supports_risk_class_measure
from frtb_sbm.validation import sort_sensitivities_deterministic


def weight_commodity_delta_sensitivity_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted commodity delta sensitivities from a package-owned batch.
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
                org_scope=scope_at(batch.org_scopes, index),
            )
        )
    return tuple(weighted)


def weight_commodity_delta_sensitivities(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted commodity delta sensitivities for a supported profile.
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
                org_scope=sensitivity.org_scope,
            )
        )
    return tuple(weighted)


__all__ = [
    "weight_commodity_delta_sensitivities",
    "weight_commodity_delta_sensitivity_batch",
]
