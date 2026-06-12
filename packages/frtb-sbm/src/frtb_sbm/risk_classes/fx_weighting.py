"""FX delta SBM weighting kernels.

Regulatory traceability:
    Basel MAR21.86-MAR21.89 for FX delta buckets and risk weights.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.batch import SbmSensitivityBatch, sorted_fx_delta_batch_indices
from frtb_sbm.data_models import SbmRiskClass, SbmRiskMeasure, SbmSensitivity, WeightedSensitivity
from frtb_sbm.kernel.weighting import _optional_axis_value
from frtb_sbm.reference_data import fx_bucket_definition, fx_delta_risk_weight
from frtb_sbm.regimes import ensure_profile_supports_risk_class_measure
from frtb_sbm.validation import SbmInputError, sort_sensitivities_deterministic


def weight_fx_delta_sensitivity_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
    reporting_currency: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted FX delta sensitivities from a package-owned batch.
    Parameters
    ----------
    batch : SbmSensitivityBatch
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


def weight_fx_delta_sensitivities(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
    reporting_currency: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted FX delta sensitivities for a supported profile.
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


__all__ = [
    "weight_fx_delta_sensitivities",
    "weight_fx_delta_sensitivity_batch",
]
