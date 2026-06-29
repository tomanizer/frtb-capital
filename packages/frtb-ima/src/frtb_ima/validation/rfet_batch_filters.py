"""RFET columnar batch exclusion filter helpers."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

from frtb_ima.data_contracts import RFETDataPoolEvidence, RFETRepresentativenessEvidence
from frtb_ima.validation.rfet_batch import RFETObservationBatch, _RFETBatchObservationWindow
from frtb_ima.validation.rfet_quantitative import RFETExclusionReason


def _batch_exclusion_reason(
    observations: RFETObservationBatch,
    index: int,
    *,
    observation_date: np.datetime64,
    as_of64: np.datetime64,
    lookback_start64: np.datetime64,
    lookback_end64: np.datetime64,
    window: _RFETBatchObservationWindow,
    require_source: bool,
    bucket_representative: bool,
    representative_items: Sequence[RFETRepresentativenessEvidence],
    seen_lineage_keys: set[tuple[object, ...]],
    seen_dates: set[np.datetime64],
    data_pools: Sequence[RFETDataPoolEvidence],
) -> RFETExclusionReason | None:
    reason = _batch_pre_representativeness_exclusion_reason(
        observations,
        index,
        observation_date=observation_date,
        as_of64=as_of64,
        lookback_start64=lookback_start64,
        lookback_end64=lookback_end64,
        window=window,
        require_source=require_source,
        data_pools=data_pools,
    )
    if reason is not None:
        return reason
    if not bucket_representative:
        if representative_items:
            return RFETExclusionReason.NON_REPRESENTATIVE_EVIDENCE
        return RFETExclusionReason.NON_REPRESENTATIVE_BUCKET
    lineage_key = _lineage_key_from_batch(observations, index)
    if lineage_key in seen_lineage_keys:
        return RFETExclusionReason.DUPLICATE_SOURCE_VENDOR
    if observation_date in seen_dates:
        return RFETExclusionReason.DUPLICATE_DATE
    return None


def _batch_pre_representativeness_exclusion_reason(
    observations: RFETObservationBatch,
    index: int,
    *,
    observation_date: np.datetime64,
    as_of64: np.datetime64,
    lookback_start64: np.datetime64,
    lookback_end64: np.datetime64,
    window: _RFETBatchObservationWindow,
    require_source: bool,
    data_pools: Sequence[RFETDataPoolEvidence],
) -> RFETExclusionReason | None:
    if observation_date > as_of64:
        return RFETExclusionReason.FUTURE_OBSERVATION
    if observation_date < lookback_start64 or observation_date > lookback_end64:
        return RFETExclusionReason.OUTSIDE_LOOKBACK
    if observation_date in window.official_holidays:
        return RFETExclusionReason.OFFICIAL_HOLIDAY
    if window.business_dates is not None and observation_date not in window.business_dates:
        return RFETExclusionReason.NON_BUSINESS_DATE
    if require_source and not observations.sources[index]:
        return RFETExclusionReason.MISSING_SOURCE
    if not bool(observations.verifiable[index]):
        return RFETExclusionReason.UNVERIFIABLE_PRICE
    if _requires_date_normalization_evidence_batch(observations, index):
        return RFETExclusionReason.MISSING_DATE_NORMALIZATION_EVIDENCE
    if not _has_vendor_audit_evidence_batch(observations, index, data_pools):
        return RFETExclusionReason.MISSING_VENDOR_AUDIT_EVIDENCE
    return None


def _lineage_key_from_batch(batch: RFETObservationBatch, index: int) -> tuple[object, ...]:
    return (
        batch.observation_dates[index],
        str(batch.sources[index]),
        str(batch.vendor_ids[index]),
        str(batch.venues[index]),
        str(batch.feeds[index]),
        str(batch.data_pool_ids[index]),
    )


def _requires_date_normalization_evidence_batch(
    batch: RFETObservationBatch,
    index: int,
) -> bool:
    timestamp = batch.observation_timestamps[index]
    return (
        not np.isnat(timestamp)
        and timestamp.astype("datetime64[D]") != batch.observation_dates[index]
        and not str(batch.date_normalization_evidence[index])
    )


def _has_vendor_audit_evidence_batch(
    batch: RFETObservationBatch,
    index: int,
    data_pools: Sequence[RFETDataPoolEvidence],
) -> bool:
    vendor_id = str(batch.vendor_ids[index])
    if not vendor_id:
        return True
    if str(batch.vendor_audit_evidence_ids[index]):
        return True
    data_pool_id = str(batch.data_pool_ids[index])
    for pool in data_pools:
        if data_pool_id and pool.pool_id == data_pool_id:
            return True
        if pool.vendor_id == vendor_id:
            return True
    return False


def _batch_vendor_audit_evidence_count(
    observations: RFETObservationBatch,
    ordered_indices: npt.NDArray[np.int_],
    data_pools: Sequence[RFETDataPoolEvidence],
) -> int:
    return len(
        {
            item
            for item in (
                *(pool.independent_audit_evidence_id for pool in data_pools),
                *(str(observations.vendor_audit_evidence_ids[index]) for index in ordered_indices),
            )
            if item
        }
    )
