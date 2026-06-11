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

from datetime import date

from frtb_ima.assembly.rfet import RFETEvidenceAssessment as RFETEvidenceAssessment
from frtb_ima.assembly.rfet import _count_pairs as _count_pairs
from frtb_ima.assembly.rfet import _exclusion_count_pairs as _exclusion_count_pairs
from frtb_ima.assembly.rfet import (
    _new_issuance_policy_basis as _new_issuance_policy_basis,
)
from frtb_ima.assembly.rfet import _status_from_tests as _status_from_tests
from frtb_ima.calendar import BusinessCalendar, ObservationWindowBasis
from frtb_ima.data_contracts import RFETEvidence, RiskFactorDefinition
from frtb_ima.regimes import RegulatoryPolicy
from frtb_ima.validation.rfet_batch import (
    RFETObservationBatch as RFETObservationBatch,
)
from frtb_ima.validation.rfet_batch import (
    input_hash_for_rfet_observation_batch as input_hash_for_rfet_observation_batch,
)
from frtb_ima.validation.rfet_batch_assessment import (
    assess_rfet_observation_batch as assess_rfet_observation_batch,
)
from frtb_ima.validation.rfet_qualitative import _rfet_qualitative_stage
from frtb_ima.validation.rfet_quantitative import (
    RFETExclusionReason as RFETExclusionReason,
)
from frtb_ima.validation.rfet_quantitative import (
    RFETObservationExclusion as RFETObservationExclusion,
)
from frtb_ima.validation.rfet_quantitative import (
    _rfet_quantitative_stage,
)
from frtb_ima.validation.rfet_thresholds import (
    _rfet_required_observations,
)
from frtb_ima.validation.rfet_thresholds import (
    base_required_observation_count as base_required_observation_count,
)
from frtb_ima.validation.rfet_thresholds import (
    prorated_required_observation_count as prorated_required_observation_count,
)
from frtb_ima.validation.rfet_window import (
    _rfet_observation_window as _rfet_observation_window,
)
from frtb_ima.validation.rfet_window import (
    _RFETObservationWindow as _RFETObservationWindow,
)


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
    """Assess real-price evidence for one risk factor under a policy.

    Counting rules implemented here:
    - observations must fall within the policy lookback window;
    - observations after ``as_of_date`` do not count;
    - at most one observation counts per calendar date;
    - evidence must match the risk factor's bucket or explicit representativeness checks;
    - source lineage is required by default.
    Parameters
    ----------
    risk_factor : RiskFactorDefinition
        Risk factor.
    evidence : RFETEvidence
        Evidence.
    policy : RegulatoryPolicy
        Policy.
    issue_date : date | None, optional
        Issue date.
    allow_new_issuance_prorating : bool, optional
        Allow new issuance prorating.
    require_source : bool, optional
        Require source.
    calendar : BusinessCalendar | None, optional
        Calendar.
    shifted_start_date : date | None, optional
        Shifted start date.
    shifted_end_date : date | None, optional
        Shifted end date.
    shift_reason : str, optional
        Shift reason.

    Returns
    -------
    RFETEvidenceAssessment
        Result of the operation.
    """
    if risk_factor.name != evidence.risk_factor_name:
        raise ValueError("risk_factor and evidence names must match")

    window = _rfet_observation_window(
        evidence.as_of_date,
        policy,
        calendar=calendar,
        shifted_start_date=shifted_start_date,
        shifted_end_date=shifted_end_date,
        shift_reason=shift_reason,
    )
    required_observations = _rfet_required_observations(
        risk_factor,
        evidence,
        policy,
        window,
        issue_date=issue_date,
        allow_new_issuance_prorating=allow_new_issuance_prorating,
    )
    qualitative = _rfet_qualitative_stage(risk_factor, evidence)
    quantitative = _rfet_quantitative_stage(
        evidence,
        window,
        qualitative,
        require_source=require_source,
    )

    eligible_count = len(quantitative.eligible_dates)
    quantitative_pass = eligible_count >= required_observations.required
    status = _status_from_tests(qualitative.qualitative_pass, quantitative_pass)

    return RFETEvidenceAssessment(
        risk_factor_name=risk_factor.name,
        as_of_date=evidence.as_of_date,
        lookback_start=window.lookback_start,
        base_required_observations=required_observations.base_required,
        required_observations=required_observations.required,
        eligible_observation_count=eligible_count,
        eligible_observation_dates=quantitative.eligible_dates,
        source_count=len(quantitative.eligible_sources),
        qualitative_pass=qualitative.qualitative_pass,
        quantitative_pass=quantitative_pass,
        bucket_representative=qualitative.bucket_representative,
        new_issuance_prorated=required_observations.new_issuance_prorated,
        modellability_status=status,
        lookback_basis=window.lookback_basis,
        calendar_source=window.calendar_source,
        calendar_version=window.calendar_version,
        official_holiday_count=window.official_holiday_count,
        missing_business_dates=window.missing_business_dates,
        shift_reason=shift_reason
        if window.lookback_basis
        == ObservationWindowBasis.SHIFTED_TWELVE_MONTH_BUSINESS_CALENDAR.value
        else "",
        source_counts=_count_pairs(observation.source for observation in evidence.observations),
        vendor_counts=_count_pairs(quantitative.eligible_vendors),
        exclusion_counts=_exclusion_count_pairs(quantitative.exclusions),
        bucket_counts=_count_pairs(
            item
            for item in (
                evidence.bucket_id,
                *(representative.bucket_id for representative in qualitative.representativeness),
            )
            if item
        ),
        representative_methodology_counts=_count_pairs(
            representative.methodology for representative in qualitative.representativeness
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
        new_issuance_policy_basis=_new_issuance_policy_basis(evidence.new_issuance),
        exclusions=quantitative.exclusions,
    )
