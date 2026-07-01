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
from typing import cast

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.batch import (
    SbmSensitivityBatch,
    sorted_csr_nonsec_delta_batch_indices,
    sorted_csr_sec_ctp_delta_batch_indices,
    sorted_csr_sec_nonctp_delta_batch_indices,
)
from frtb_sbm.data_models import (
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    WeightedSensitivity,
)
from frtb_sbm.kernel.weighting import (
    _required_optional_axis_value,
    sort_weighted_sensitivities_deterministic,
    weighted_sensitivity_sort_key,
)
from frtb_sbm.org_scope import scope_at
from frtb_sbm.reference_data import (
    csr_nonsec_delta_risk_weight,
    csr_nonsec_validate_delta_inputs,
)
from frtb_sbm.regimes import ensure_profile_supports_risk_class_measure
from frtb_sbm.risk_classes.commodity_weighting import (
    weight_commodity_delta_sensitivities,
    weight_commodity_delta_sensitivity_batch,
)
from frtb_sbm.risk_classes.csr_sec_ctp_weighting import (
    _ensure_csr_sec_ctp_decomposition_evidence_for_batch,
)
from frtb_sbm.risk_classes.equity_weighting import (
    weight_equity_delta_sensitivities,
    weight_equity_delta_sensitivity_batch,
)
from frtb_sbm.risk_classes.fx_weighting import (
    weight_fx_delta_sensitivities,
    weight_fx_delta_sensitivity_batch,
)
from frtb_sbm.risk_classes.girr_weighting import (
    weight_girr_delta_sensitivities,
    weight_girr_vega_sensitivities,
    weight_girr_vega_sensitivity_batch,
)
from frtb_sbm.risk_classes.vega_weighting import (
    weight_non_girr_vega_sensitivities,
    weight_non_girr_vega_sensitivity_batch,
)
from frtb_sbm.validation import sort_sensitivities_deterministic


def compute_weighted_sensitivities(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
    reporting_currency: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted sensitivities for supported profile paths.
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


def weight_csr_nonsec_delta_sensitivity_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted CSR non-securitisation delta sensitivities from a batch.
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
                org_scope=scope_at(batch.org_scopes, index),
            )
        )
    return tuple(weighted)


def weight_csr_sec_nonctp_delta_sensitivity_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted CSR securitisation non-CTP delta sensitivities from a batch.
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
                org_scope=scope_at(batch.org_scopes, index),
            )
        )
    return tuple(weighted)


def weight_csr_sec_ctp_delta_sensitivity_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted CSR securitisation CTP delta sensitivities from a batch.
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
                org_scope=scope_at(batch.org_scopes, index),
            )
        )
    return tuple(weighted)


def weight_csr_nonsec_delta_sensitivities(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted CSR non-securitisation delta sensitivities.
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
                org_scope=sensitivity.org_scope,
            )
        )
    return tuple(weighted)


def weight_csr_sec_nonctp_delta_sensitivities(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted CSR securitisation non-CTP delta sensitivities.
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
                org_scope=sensitivity.org_scope,
            )
        )
    return tuple(weighted)


def weight_csr_sec_ctp_delta_sensitivities(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
) -> tuple[WeightedSensitivity, ...]:
    """Return cited weighted CSR securitisation CTP delta sensitivities.
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
                org_scope=sensitivity.org_scope,
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
