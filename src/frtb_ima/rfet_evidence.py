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
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum

from frtb_ima.data_contracts import RFETEvidence, RiskFactorDefinition
from frtb_ima.data_models import ModellabilityStatus, RealPriceObservation
from frtb_ima.regimes import RegulatoryPolicy


class RFETExclusionReason(StrEnum):
    """Why a real-price observation did not count for RFET."""

    DUPLICATE_DATE = "DUPLICATE_DATE"
    FUTURE_OBSERVATION = "FUTURE_OBSERVATION"
    MISSING_SOURCE = "MISSING_SOURCE"
    NON_REPRESENTATIVE_BUCKET = "NON_REPRESENTATIVE_BUCKET"
    OUTSIDE_LOOKBACK = "OUTSIDE_LOOKBACK"


@dataclass(frozen=True)
class RFETObservationExclusion:
    """One excluded observation with reason for audit review."""

    observation: RealPriceObservation
    reason: RFETExclusionReason


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
    exclusions: tuple[RFETObservationExclusion, ...] = ()


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

    The proposal contemplates special treatment for new issuances. The exact
    operational evidence standard may require policy confirmation, so this
    helper is opt-in from ``assess_rfet_evidence`` and documented as a working
    implementation assumption.
    """
    if issue_date > as_of_date:
        raise ValueError("issue_date cannot be after as_of_date")
    if issue_date <= lookback_start:
        return base_required_observations

    available_days = (as_of_date - issue_date).days + 1
    lookback_days = (as_of_date - lookback_start).days + 1
    prorated = math.ceil(base_required_observations * available_days / lookback_days)
    return max(1, min(base_required_observations, prorated))


def _bucket_representative(
    risk_factor: RiskFactorDefinition,
    evidence: RFETEvidence,
) -> bool:
    if risk_factor.bucket is None:
        return True
    return evidence.bucket_id == risk_factor.bucket.bucket_id


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
) -> RFETEvidenceAssessment:
    """
    Assess real-price evidence for one risk factor under a policy.

    Counting rules implemented here:
    - observations must fall within the policy lookback window;
    - observations after ``as_of_date`` do not count;
    - at most one observation counts per calendar date;
    - evidence must match the risk factor's bucket when a bucket is defined;
    - source lineage is required by default.
    """
    policy.require_supported("type_a_type_b_nmrf_taxonomy")
    if risk_factor.name != evidence.risk_factor_name:
        raise ValueError("risk_factor and evidence names must match")

    lookback_start = evidence.as_of_date - timedelta(days=policy.rfet_lookback_days)
    base_required = base_required_observation_count(risk_factor, policy)
    new_issuance_prorated = False
    required = base_required
    if issue_date is not None and allow_new_issuance_prorating:
        required = prorated_required_observation_count(
            base_required,
            lookback_start=lookback_start,
            as_of_date=evidence.as_of_date,
            issue_date=issue_date,
        )
        new_issuance_prorated = required != base_required

    bucket_representative = _bucket_representative(risk_factor, evidence)
    seen_dates: set[date] = set()
    eligible_dates: list[date] = []
    eligible_sources: set[str] = set()
    exclusions: list[RFETObservationExclusion] = []

    for observation in sorted(evidence.observations, key=lambda obs: obs.observation_date):
        reason: RFETExclusionReason | None = None
        if observation.observation_date > evidence.as_of_date:
            reason = RFETExclusionReason.FUTURE_OBSERVATION
        elif observation.observation_date < lookback_start:
            reason = RFETExclusionReason.OUTSIDE_LOOKBACK
        elif require_source and not observation.source:
            reason = RFETExclusionReason.MISSING_SOURCE
        elif not bucket_representative:
            reason = RFETExclusionReason.NON_REPRESENTATIVE_BUCKET
        elif observation.observation_date in seen_dates:
            reason = RFETExclusionReason.DUPLICATE_DATE

        if reason is not None:
            exclusions.append(RFETObservationExclusion(observation, reason))
            continue

        seen_dates.add(observation.observation_date)
        eligible_dates.append(observation.observation_date)
        if observation.source:
            eligible_sources.add(observation.source)

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
        exclusions=tuple(exclusions),
    )
