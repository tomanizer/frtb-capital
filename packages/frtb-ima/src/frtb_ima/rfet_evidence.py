"""
RFET evidence assessment.

This module evaluates real-price evidence packages before the simpler RFET
classification functions in ``rfet.py`` are used. It keeps an audit trail of
which observations counted, which were excluded, and why.

Regulatory traceability:
    Supports NPR-MR-RFET-001 through NPR-MR-RFET-003 in
    docs/requirements/NPR_2_0_MARKET_RISK.yml.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from frtb_ima.calendar import BusinessCalendar, ObservationWindowBasis
from frtb_ima.data_contracts import (
    RFETEvidence,
    RFETNewIssuanceEvidence,
    RFETRepresentativenessEvidence,
    RiskFactorDefinition,
)
from frtb_ima.data_models import ModellabilityStatus, RealPriceObservation
from frtb_ima.regimes import RegulatoryPolicy


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
        """Return a serialisable dictionary for reporting and audit trails."""
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
            },
            "reason": self.reason.value,
        }


@dataclass(frozen=True)
class RFETEvidenceAssessment:
    """Audit-friendly RFET evidence assessment result."""

    risk_factor_name: str
    as_of_date: date
    lookback_start: date
    base_required_observations: int
    required_observations: int
    eligible_observation_count: int
    eligible_observation_dates: tuple[date, ...]
    source_count: int
    qualitative_pass: bool
    quantitative_pass: bool
    bucket_representative: bool
    new_issuance_prorated: bool
    modellability_status: ModellabilityStatus
    lookback_basis: str = ObservationWindowBasis.OBSERVATION_COUNT_PROXY.value
    calendar_source: str = ""
    calendar_version: str = ""
    official_holiday_count: int = 0
    missing_business_dates: tuple[date, ...] = ()
    shift_reason: str = ""
    source_counts: tuple[tuple[str, int], ...] = ()
    vendor_counts: tuple[tuple[str, int], ...] = ()
    exclusion_counts: tuple[tuple[str, int], ...] = ()
    bucket_counts: tuple[tuple[str, int], ...] = ()
    representative_methodology_counts: tuple[tuple[str, int], ...] = ()
    data_pool_count: int = 0
    vendor_audit_evidence_count: int = 0
    new_issuance_policy_basis: str = ""
    exclusions: tuple[RFETObservationExclusion, ...] = ()

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails."""
        return {
            "risk_factor_name": self.risk_factor_name,
            "as_of_date": self.as_of_date.isoformat(),
            "lookback_start": self.lookback_start.isoformat(),
            "base_required_observations": self.base_required_observations,
            "required_observations": self.required_observations,
            "eligible_observation_count": self.eligible_observation_count,
            "eligible_observation_dates": [
                observation_date.isoformat() for observation_date in self.eligible_observation_dates
            ],
            "source_count": self.source_count,
            "qualitative_pass": self.qualitative_pass,
            "quantitative_pass": self.quantitative_pass,
            "bucket_representative": self.bucket_representative,
            "new_issuance_prorated": self.new_issuance_prorated,
            "modellability_status": self.modellability_status.value,
            "lookback_basis": self.lookback_basis,
            "calendar_source": self.calendar_source,
            "calendar_version": self.calendar_version,
            "official_holiday_count": self.official_holiday_count,
            "missing_business_dates": [item.isoformat() for item in self.missing_business_dates],
            "shift_reason": self.shift_reason,
            "source_counts": dict(self.source_counts),
            "vendor_counts": dict(self.vendor_counts),
            "exclusion_counts": dict(self.exclusion_counts),
            "bucket_counts": dict(self.bucket_counts),
            "representative_methodology_counts": dict(self.representative_methodology_counts),
            "data_pool_count": self.data_pool_count,
            "vendor_audit_evidence_count": self.vendor_audit_evidence_count,
            "new_issuance_policy_basis": self.new_issuance_policy_basis,
            "exclusions": [exclusion.as_dict() for exclusion in self.exclusions],
        }


def base_required_observation_count(
    risk_factor: RiskFactorDefinition,
    policy: RegulatoryPolicy,
) -> int:
    """Return the policy RFET observation threshold for one risk factor."""
    if risk_factor.liquidity_horizon.value <= policy.rfet_short_lh_max_days:
        return policy.rfet_short_lh_threshold
    return policy.rfet_long_lh_threshold


def prorated_required_observation_count(
    base_required_observations: int,
    *,
    lookback_start: date,
    as_of_date: date,
    issue_date: date,
) -> int:
    """
    Prorate an RFET threshold for a new issuance.

    The proposal contemplates special treatment for new issuances. Production
    callers should provide ``RFETNewIssuanceEvidence`` on ``RFETEvidence`` so
    the assessment records the policy citation or modelling-choice rationale.
    """
    if issue_date > as_of_date:
        raise ValueError("issue_date cannot be after as_of_date")
    if issue_date <= lookback_start:
        return base_required_observations

    available_days = (as_of_date - issue_date).days + 1
    lookback_days = (as_of_date - lookback_start).days + 1
    prorated = math.ceil(base_required_observations * available_days / lookback_days)
    return max(1, min(base_required_observations, prorated))


def _legacy_bucket_representative(
    risk_factor: RiskFactorDefinition,
    evidence: RFETEvidence,
) -> bool:
    if risk_factor.bucket is None:
        return True
    return evidence.bucket_id == risk_factor.bucket.bucket_id


def _representativeness_result(
    risk_factor: RiskFactorDefinition,
    evidence: RFETEvidence,
) -> tuple[bool, tuple[RFETRepresentativenessEvidence, ...]]:
    if not evidence.representativeness:
        return _legacy_bucket_representative(risk_factor, evidence), ()
    if risk_factor.bucket is None:
        relevant = tuple(evidence.representativeness)
    else:
        relevant = tuple(
            item
            for item in evidence.representativeness
            if item.bucket_id == risk_factor.bucket.bucket_id
        )
    return bool(relevant) and all(item.passed for item in relevant), relevant


def _count_pairs(values: Iterable[str]) -> tuple[tuple[str, int], ...]:
    counter = Counter(value for value in values if value)
    return tuple(sorted(counter.items()))


def _exclusion_count_pairs(
    exclusions: Iterable[RFETObservationExclusion],
) -> tuple[tuple[str, int], ...]:
    return _count_pairs(exclusion.reason.value for exclusion in exclusions)


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


def _new_issuance_policy_basis(new_issuance: RFETNewIssuanceEvidence | None) -> str:
    if new_issuance is None:
        return ""
    if new_issuance.policy_citation:
        return new_issuance.policy_citation
    return new_issuance.rationale


def _status_from_tests(
    qualitative_pass: bool,
    quantitative_pass: bool,
) -> ModellabilityStatus:
    if not qualitative_pass:
        return ModellabilityStatus.TYPE_B_NMRF
    if quantitative_pass:
        return ModellabilityStatus.MODELLABLE
    return ModellabilityStatus.TYPE_A_NMRF


def assess_rfet_evidence(
    risk_factor: RiskFactorDefinition,
    evidence: RFETEvidence,
    policy: RegulatoryPolicy,
    *,
    issue_date: date | None = None,
    allow_new_issuance_prorating: bool = False,
    require_source: bool = True,
    calendar: BusinessCalendar | None = None,
    shifted_start_date: date | None = None,
    shifted_end_date: date | None = None,
    shift_reason: str = "",
) -> RFETEvidenceAssessment:
    """
    Assess real-price evidence for one risk factor under a policy.

    Counting rules implemented here:
    - observations must fall within the policy lookback window;
    - observations after ``as_of_date`` do not count;
    - at most one observation counts per calendar date;
    - evidence must match the risk factor's bucket or explicit representativeness checks;
    - source lineage is required by default.
    """
    policy.require_supported("type_a_type_b_nmrf_taxonomy")
    if risk_factor.name != evidence.risk_factor_name:
        raise ValueError("risk_factor and evidence names must match")

    if calendar is None:
        lookback_start = evidence.as_of_date - timedelta(days=policy.rfet_lookback_days)
        lookback_end = evidence.as_of_date
        lookback_basis = ObservationWindowBasis.OBSERVATION_COUNT_PROXY.value
        calendar_source = ""
        calendar_version = ""
        official_holiday_count = 0
        missing_business_dates: tuple[date, ...] = ()
        business_dates: set[date] | None = None
        official_holidays: set[date] = set()
    else:
        window = calendar.exact_twelve_month_window(
            evidence.as_of_date,
            shifted_start_date=shifted_start_date,
            shifted_end_date=shifted_end_date,
            shift_reason=shift_reason,
        )
        lookback_start = window.start_date
        lookback_end = window.end_date
        lookback_basis = window.basis.value
        calendar_source = window.calendar_source
        calendar_version = window.calendar_version
        official_holiday_count = window.official_holiday_count
        missing_business_dates = window.missing_business_dates
        business_dates = set(window.business_dates)
        official_holidays = set(window.official_holidays)
    base_required = base_required_observation_count(risk_factor, policy)
    new_issuance_prorated = False
    required = base_required
    new_issuance = evidence.new_issuance
    effective_issue_date = issue_date
    if new_issuance is not None:
        effective_issue_date = new_issuance.issue_date
    if (
        new_issuance is not None
        and new_issuance.prorating_approved
        and effective_issue_date is not None
    ):
        required = prorated_required_observation_count(
            base_required,
            lookback_start=lookback_start,
            as_of_date=evidence.as_of_date,
            issue_date=effective_issue_date,
        )
        new_issuance_prorated = required != base_required
    elif effective_issue_date is not None and allow_new_issuance_prorating:
        required = prorated_required_observation_count(
            base_required,
            lookback_start=lookback_start,
            as_of_date=evidence.as_of_date,
            issue_date=effective_issue_date,
        )
        new_issuance_prorated = required != base_required

    bucket_representative, representativeness = _representativeness_result(
        risk_factor,
        evidence,
    )
    seen_dates: set[date] = set()
    seen_lineage_keys: set[tuple[object, ...]] = set()
    eligible_dates: list[date] = []
    eligible_sources: set[str] = set()
    eligible_vendors: list[str] = []
    exclusions: list[RFETObservationExclusion] = []

    for observation in sorted(evidence.observations, key=lambda obs: obs.observation_date):
        reason: RFETExclusionReason | None = None
        lineage_key = _lineage_key(observation)
        if observation.observation_date > evidence.as_of_date:
            reason = RFETExclusionReason.FUTURE_OBSERVATION
        elif (
            observation.observation_date < lookback_start
            or observation.observation_date > lookback_end
        ):
            reason = RFETExclusionReason.OUTSIDE_LOOKBACK
        elif observation.observation_date in official_holidays:
            reason = RFETExclusionReason.OFFICIAL_HOLIDAY
        elif business_dates is not None and observation.observation_date not in business_dates:
            reason = RFETExclusionReason.NON_BUSINESS_DATE
        elif require_source and not observation.source:
            reason = RFETExclusionReason.MISSING_SOURCE
        elif not observation.verifiable:
            reason = RFETExclusionReason.UNVERIFIABLE_PRICE
        elif _requires_date_normalization_evidence(observation):
            reason = RFETExclusionReason.MISSING_DATE_NORMALIZATION_EVIDENCE
        elif not _has_vendor_audit_evidence(observation, evidence):
            reason = RFETExclusionReason.MISSING_VENDOR_AUDIT_EVIDENCE
        elif not bucket_representative:
            reason = (
                RFETExclusionReason.NON_REPRESENTATIVE_EVIDENCE
                if representativeness
                else RFETExclusionReason.NON_REPRESENTATIVE_BUCKET
            )
        elif lineage_key in seen_lineage_keys:
            reason = RFETExclusionReason.DUPLICATE_SOURCE_VENDOR
        elif observation.observation_date in seen_dates:
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

    eligible_count = len(eligible_dates)
    quantitative_pass = eligible_count >= required
    status = _status_from_tests(evidence.qualitative_pass, quantitative_pass)

    return RFETEvidenceAssessment(
        risk_factor_name=risk_factor.name,
        as_of_date=evidence.as_of_date,
        lookback_start=lookback_start,
        base_required_observations=base_required,
        required_observations=required,
        eligible_observation_count=eligible_count,
        eligible_observation_dates=tuple(eligible_dates),
        source_count=len(eligible_sources),
        qualitative_pass=evidence.qualitative_pass,
        quantitative_pass=quantitative_pass,
        bucket_representative=bucket_representative,
        new_issuance_prorated=new_issuance_prorated,
        modellability_status=status,
        lookback_basis=lookback_basis,
        calendar_source=calendar_source,
        calendar_version=calendar_version,
        official_holiday_count=official_holiday_count,
        missing_business_dates=missing_business_dates,
        shift_reason=shift_reason
        if lookback_basis == ObservationWindowBasis.SHIFTED_TWELVE_MONTH_BUSINESS_CALENDAR.value
        else "",
        source_counts=_count_pairs(observation.source for observation in evidence.observations),
        vendor_counts=_count_pairs(eligible_vendors),
        exclusion_counts=_exclusion_count_pairs(exclusions),
        bucket_counts=_count_pairs(
            item
            for item in (
                evidence.bucket_id,
                *(representative.bucket_id for representative in representativeness),
            )
            if item
        ),
        representative_methodology_counts=_count_pairs(
            representative.methodology for representative in representativeness
        ),
        data_pool_count=len(evidence.data_pools),
        vendor_audit_evidence_count=len(
            {
                item
                for item in (
                    *(pool.independent_audit_evidence_id for pool in evidence.data_pools),
                    *(
                        observation.vendor_audit_evidence_id
                        for observation in evidence.observations
                    ),
                )
                if item
            }
        ),
        new_issuance_policy_basis=_new_issuance_policy_basis(new_issuance),
        exclusions=tuple(exclusions),
    )
