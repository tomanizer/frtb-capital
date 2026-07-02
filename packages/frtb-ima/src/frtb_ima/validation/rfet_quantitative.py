"""RFET quantitative observation-count validation stage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from typing import Protocol

from frtb_ima.data_contracts import RFETEvidence
from frtb_ima.data_models import RealPriceObservation
from frtb_ima.validation.rfet_qualitative import _RFETQualitativeStage


class RFETExclusionReason(StrEnum):
    """Why a real-price observation did not count for RFET."""

    DUPLICATE_DATE = "DUPLICATE_DATE"
    DUPLICATE_SOURCE_VENDOR = "DUPLICATE_SOURCE_VENDOR"
    FUTURE_OBSERVATION = "FUTURE_OBSERVATION"
    MISSING_DATE_NORMALIZATION_EVIDENCE = "MISSING_DATE_NORMALIZATION_EVIDENCE"
    MISSING_SOURCE = "MISSING_SOURCE"
    MISSING_VENDOR_AUDIT_EVIDENCE = "MISSING_VENDOR_AUDIT_EVIDENCE"
    NON_BUSINESS_DATE = "NON_BUSINESS_DATE"
    NON_REPRESENTATIVE_BUCKET = "NON_REPRESENTATIVE_BUCKET"
    NON_REPRESENTATIVE_EVIDENCE = "NON_REPRESENTATIVE_EVIDENCE"
    OFFICIAL_HOLIDAY = "OFFICIAL_HOLIDAY"
    OUTSIDE_LOOKBACK = "OUTSIDE_LOOKBACK"
    UNVERIFIABLE_PRICE = "UNVERIFIABLE_PRICE"


@dataclass(frozen=True)
class RFETObservationExclusion:
    """One excluded observation with reason for audit review."""

    observation: RealPriceObservation
    reason: RFETExclusionReason

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails.
        Returns
        -------
        dict[str, object]
            Result of the operation.
        """
        return {
            "observation": {
                "risk_factor_name": self.observation.risk_factor_name,
                "observation_date": self.observation.observation_date.isoformat(),
                "source": self.observation.source,
                "vendor_id": self.observation.vendor_id,
                "venue": self.observation.venue,
                "feed": self.observation.feed,
                "data_pool_id": self.observation.data_pool_id,
                "vendor_audit_evidence_id": self.observation.vendor_audit_evidence_id,
                "source_row_id": self.observation.source_row_id,
            },
            "reason": self.reason.value,
        }


@dataclass(frozen=True)
class _RFETQuantitativeStage:
    eligible_dates: tuple[date, ...]
    eligible_sources: frozenset[str]
    eligible_vendors: tuple[str, ...]
    exclusions: tuple[RFETObservationExclusion, ...]
    raw_duplicate_date_count: int
    raw_duplicate_lineage_count: int


class _RFETObservationWindowLike(Protocol):
    @property
    def lookback_start(self) -> date: ...

    @property
    def lookback_end(self) -> date: ...

    @property
    def business_dates(self) -> frozenset[date] | None: ...

    @property
    def official_holidays(self) -> frozenset[date]: ...


def _lineage_key(observation: RealPriceObservation) -> tuple[object, ...]:
    return (
        observation.observation_date,
        observation.source,
        observation.vendor_id,
        observation.venue,
        observation.feed,
        observation.data_pool_id,
    )


def _has_vendor_audit_evidence(
    observation: RealPriceObservation,
    evidence: RFETEvidence,
) -> bool:
    if not observation.vendor_id:
        return True
    if observation.vendor_audit_evidence_id:
        return True
    for pool in evidence.data_pools:
        if observation.data_pool_id and pool.pool_id == observation.data_pool_id:
            return True
        if pool.vendor_id == observation.vendor_id:
            return True
    return False


def _requires_date_normalization_evidence(observation: RealPriceObservation) -> bool:
    timestamp = observation.observation_timestamp
    return (
        timestamp is not None
        and timestamp.date() != observation.observation_date
        and not observation.date_normalization_evidence
    )


def _pre_representativeness_exclusion_reason(
    observation: RealPriceObservation,
    evidence: RFETEvidence,
    window: _RFETObservationWindowLike,
    *,
    require_source: bool,
) -> RFETExclusionReason | None:
    if observation.observation_date > evidence.as_of_date:
        return RFETExclusionReason.FUTURE_OBSERVATION
    if (
        observation.observation_date < window.lookback_start
        or observation.observation_date > window.lookback_end
    ):
        return RFETExclusionReason.OUTSIDE_LOOKBACK
    if observation.observation_date in window.official_holidays:
        return RFETExclusionReason.OFFICIAL_HOLIDAY
    if (
        window.business_dates is not None
        and observation.observation_date not in window.business_dates
    ):
        return RFETExclusionReason.NON_BUSINESS_DATE
    if require_source and not observation.source:
        return RFETExclusionReason.MISSING_SOURCE
    if not observation.verifiable:
        return RFETExclusionReason.UNVERIFIABLE_PRICE
    if _requires_date_normalization_evidence(observation):
        return RFETExclusionReason.MISSING_DATE_NORMALIZATION_EVIDENCE
    if not _has_vendor_audit_evidence(observation, evidence):
        return RFETExclusionReason.MISSING_VENDOR_AUDIT_EVIDENCE
    return None


def _raw_duplicate_counts(
    observations: tuple[RealPriceObservation, ...],
    evidence: RFETEvidence,
    window: _RFETObservationWindowLike,
    *,
    require_source: bool,
) -> tuple[int, int]:
    seen_dates: set[date] = set()
    seen_lineage_keys: set[tuple[object, ...]] = set()
    duplicate_dates = 0
    duplicate_lineage = 0

    for observation in observations:
        if (
            _pre_representativeness_exclusion_reason(
                observation,
                evidence,
                window,
                require_source=require_source,
            )
            is not None
        ):
            continue
        lineage_key = _lineage_key(observation)
        if lineage_key in seen_lineage_keys:
            duplicate_lineage += 1
        elif observation.observation_date in seen_dates:
            duplicate_dates += 1
        seen_lineage_keys.add(lineage_key)
        seen_dates.add(observation.observation_date)

    return duplicate_dates, duplicate_lineage


def _rfet_quantitative_stage(
    evidence: RFETEvidence,
    window: _RFETObservationWindowLike,
    qualitative: _RFETQualitativeStage,
    *,
    require_source: bool = True,
) -> _RFETQuantitativeStage:
    seen_dates: set[date] = set()
    seen_lineage_keys: set[tuple[object, ...]] = set()
    eligible_dates: list[date] = []
    eligible_sources: set[str] = set()
    eligible_vendors: list[str] = []
    exclusions: list[RFETObservationExclusion] = []
    sorted_observations = tuple(sorted(evidence.observations, key=lambda obs: obs.observation_date))
    raw_duplicate_date_count, raw_duplicate_lineage_count = _raw_duplicate_counts(
        sorted_observations,
        evidence,
        window,
        require_source=require_source,
    )

    for observation in sorted_observations:
        lineage_key = _lineage_key(observation)
        reason = _pre_representativeness_exclusion_reason(
            observation,
            evidence,
            window,
            require_source=require_source,
        )
        if reason is None and not qualitative.bucket_representative:
            reason = (
                RFETExclusionReason.NON_REPRESENTATIVE_EVIDENCE
                if qualitative.representativeness
                else RFETExclusionReason.NON_REPRESENTATIVE_BUCKET
            )
        elif reason is None and lineage_key in seen_lineage_keys:
            reason = RFETExclusionReason.DUPLICATE_SOURCE_VENDOR
        elif reason is None and observation.observation_date in seen_dates:
            reason = RFETExclusionReason.DUPLICATE_DATE

        if reason is not None:
            exclusions.append(RFETObservationExclusion(observation, reason))
            continue

        seen_lineage_keys.add(lineage_key)
        seen_dates.add(observation.observation_date)
        eligible_dates.append(observation.observation_date)
        if observation.source:
            eligible_sources.add(observation.source)
        if observation.vendor_id:
            eligible_vendors.append(observation.vendor_id)

    return _RFETQuantitativeStage(
        eligible_dates=tuple(eligible_dates),
        eligible_sources=frozenset(eligible_sources),
        eligible_vendors=tuple(eligible_vendors),
        exclusions=tuple(exclusions),
        raw_duplicate_date_count=raw_duplicate_date_count,
        raw_duplicate_lineage_count=raw_duplicate_lineage_count,
    )
