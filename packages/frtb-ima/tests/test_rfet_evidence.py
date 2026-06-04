"""Tests for RFET evidence assessment."""

from datetime import UTC, date, datetime, timedelta

import pytest

from frtb_ima.calendar import BusinessCalendar, ObservationWindowBasis
from frtb_ima.data_contracts import (
    RFETDataPoolEvidence,
    RFETEvidence,
    RFETNewIssuanceEvidence,
    RFETRepresentativenessEvidence,
    RiskFactorBucket,
    RiskFactorDefinition,
)
from frtb_ima.data_models import (
    LiquidityHorizon,
    ModellabilityStatus,
    RealPriceObservation,
    RiskClass,
)
from frtb_ima.regimes import RegulatoryRegime, get_policy
from frtb_ima.rfet_evidence import (
    RFETExclusionReason,
    _rfet_observation_window,
    _rfet_qualitative_stage,
    _rfet_quantitative_stage,
    assess_rfet_evidence,
    base_required_observation_count,
    prorated_required_observation_count,
)

AS_OF = date(2025, 6, 30)


def _risk_factor(lh: LiquidityHorizon = LiquidityHorizon.LH10) -> RiskFactorDefinition:
    bucket = RiskFactorBucket(
        bucket_id="USD_RATES",
        risk_class=RiskClass.GIRR,
        liquidity_horizon=lh,
    )
    return RiskFactorDefinition(
        name="USD_SWAP_5Y",
        risk_class=RiskClass.GIRR,
        liquidity_horizon=lh,
        bucket=bucket,
    )


def _observations(n: int, *, source: str = "VENDOR_A") -> tuple[RealPriceObservation, ...]:
    return tuple(
        RealPriceObservation(
            "USD_SWAP_5Y",
            AS_OF - timedelta(days=index * 10),
            source=source,
        )
        for index in range(n)
    )


def _weekdays(start: date, end: date, holidays: set[date] | None = None) -> tuple[date, ...]:
    holidays = set() if holidays is None else holidays
    days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5 and current not in holidays:
            days.append(current)
        current += timedelta(days=1)
    return tuple(days)


def _evidence(
    observations: tuple[RealPriceObservation, ...],
    *,
    qualitative_pass: bool = True,
    bucket_id: str = "USD_RATES",
) -> RFETEvidence:
    return RFETEvidence(
        risk_factor_name="USD_SWAP_5Y",
        as_of_date=AS_OF,
        observations=observations,
        qualitative_pass=qualitative_pass,
        bucket_id=bucket_id,
    )


def test_base_required_observation_count_uses_policy_thresholds() -> None:
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    assert base_required_observation_count(_risk_factor(LiquidityHorizon.LH10), policy) == 24
    assert base_required_observation_count(_risk_factor(LiquidityHorizon.LH40), policy) == 16


def test_assess_rfet_evidence_passes_with_required_unique_dates() -> None:
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    result = assess_rfet_evidence(_risk_factor(), _evidence(_observations(24)), policy)

    assert result.eligible_observation_count == 24
    assert result.required_observations == 24
    assert result.quantitative_pass is True
    assert result.modellability_status == ModellabilityStatus.MODELLABLE
    assert result.source_count == 1
    assert result.exclusions == ()


def test_assess_rfet_evidence_deduplicates_dates_and_records_exclusions() -> None:
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    duplicate_date = AS_OF - timedelta(days=1)
    observations = (
        *_observations(23),
        RealPriceObservation("USD_SWAP_5Y", duplicate_date, source="VENDOR_A"),
        RealPriceObservation("USD_SWAP_5Y", duplicate_date, source="VENDOR_B"),
    )

    result = assess_rfet_evidence(_risk_factor(), _evidence(observations), policy)

    assert result.eligible_observation_count == 24
    assert result.quantitative_pass is True
    assert [exclusion.reason for exclusion in result.exclusions] == [
        RFETExclusionReason.DUPLICATE_DATE
    ]


def test_assess_rfet_evidence_deduplicates_source_vendor_lineage() -> None:
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    duplicate_date = AS_OF - timedelta(days=1)
    observations = (
        RealPriceObservation(
            "USD_SWAP_5Y",
            duplicate_date,
            source="TRADE_STORE",
            vendor_id="INTERNAL",
            venue="SEF_A",
            feed="EXECUTIONS",
            vendor_audit_evidence_id="internal-lineage-control-2026",
        ),
        RealPriceObservation(
            "USD_SWAP_5Y",
            duplicate_date,
            source="TRADE_STORE",
            vendor_id="INTERNAL",
            venue="SEF_A",
            feed="EXECUTIONS",
            vendor_audit_evidence_id="internal-lineage-control-2026",
        ),
        RealPriceObservation(
            "USD_SWAP_5Y",
            duplicate_date,
            source="VENDOR_A",
            vendor_id="VENDOR_A",
            venue="SEF_A",
            feed="COMPOSITE",
            vendor_audit_evidence_id="audit-vendor-a-2026",
        ),
    )

    result = assess_rfet_evidence(_risk_factor(), _evidence(observations), policy)

    assert result.eligible_observation_count == 1
    assert [exclusion.reason for exclusion in result.exclusions] == [
        RFETExclusionReason.DUPLICATE_SOURCE_VENDOR,
        RFETExclusionReason.DUPLICATE_DATE,
    ]
    assert result.as_dict()["source_counts"] == {"TRADE_STORE": 2, "VENDOR_A": 1}


def test_assess_rfet_evidence_excludes_missing_source_and_old_observations() -> None:
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    observations = (
        RealPriceObservation("USD_SWAP_5Y", AS_OF - timedelta(days=1), source=""),
        RealPriceObservation("USD_SWAP_5Y", AS_OF - timedelta(days=400), source="VENDOR_A"),
    )

    result = assess_rfet_evidence(_risk_factor(), _evidence(observations), policy)

    assert result.eligible_observation_count == 0
    assert result.modellability_status == ModellabilityStatus.TYPE_A_NMRF
    assert {exclusion.reason for exclusion in result.exclusions} == {
        RFETExclusionReason.MISSING_SOURCE,
        RFETExclusionReason.OUTSIDE_LOOKBACK,
    }


def test_assess_rfet_evidence_records_calendar_and_holiday_exclusions() -> None:
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    holiday = date(2024, 12, 25)
    calendar = BusinessCalendar(
        business_dates=_weekdays(date(2024, 7, 1), AS_OF, {holiday}),
        official_holidays=(holiday,),
        source="FED",
        version="2026.1",
    )
    observations = (
        RealPriceObservation("USD_SWAP_5Y", holiday, source="VENDOR_A"),
        RealPriceObservation("USD_SWAP_5Y", date(2025, 1, 4), source="VENDOR_A"),
        *_observations(24),
    )

    result = assess_rfet_evidence(
        _risk_factor(),
        _evidence(observations),
        policy,
        calendar=calendar,
    )

    assert result.lookback_basis == ObservationWindowBasis.EXACT_TWELVE_MONTH_BUSINESS_CALENDAR
    assert result.calendar_source == "FED"
    assert result.official_holiday_count == 1
    assert {exclusion.reason for exclusion in result.exclusions} >= {
        RFETExclusionReason.OFFICIAL_HOLIDAY,
        RFETExclusionReason.NON_BUSINESS_DATE,
    }
    assert result.as_dict()["official_holiday_count"] == 1


def test_rfet_observation_window_stage_keeps_calendar_metadata() -> None:
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    holiday = date(2024, 12, 25)
    calendar = BusinessCalendar(
        business_dates=_weekdays(date(2024, 7, 1), AS_OF, {holiday}),
        official_holidays=(holiday,),
        source="FED",
        version="2026.1",
    )

    window = _rfet_observation_window(AS_OF, policy, calendar=calendar)

    assert window.lookback_start == date(2024, 7, 1)
    assert window.lookback_end == AS_OF
    assert window.lookback_basis == ObservationWindowBasis.EXACT_TWELVE_MONTH_BUSINESS_CALENDAR
    assert window.calendar_source == "FED"
    assert window.official_holiday_count == 1
    assert holiday in window.official_holidays
    assert date(2025, 1, 4) not in window.business_dates


def test_rfet_qualitative_stage_isolates_representativeness_controls() -> None:
    evidence = RFETEvidence(
        risk_factor_name="USD_SWAP_5Y",
        as_of_date=AS_OF,
        observations=_observations(3),
        qualitative_pass=True,
        bucket_id="USD_RATES",
        representativeness=(
            RFETRepresentativenessEvidence(
                bucket_id="USD_RATES",
                methodology="curve-node-proximity",
                passed=False,
                rationale="Observed tenors do not represent the 5Y node.",
            ),
        ),
    )

    qualitative = _rfet_qualitative_stage(_risk_factor(), evidence)

    assert qualitative.qualitative_pass is True
    assert qualitative.bucket_representative is False
    assert [item.methodology for item in qualitative.representativeness] == [
        "curve-node-proximity"
    ]


def test_rfet_quantitative_stage_records_window_and_dedup_exclusions() -> None:
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    window = _rfet_observation_window(AS_OF, policy)
    evidence = _evidence(
        (
            RealPriceObservation(
                "USD_SWAP_5Y",
                AS_OF - timedelta(days=2),
                source="TRADE_STORE",
                vendor_id="INTERNAL",
                venue="SEF_A",
                feed="EXECUTIONS",
                vendor_audit_evidence_id="internal-lineage-control-2026",
            ),
            RealPriceObservation(
                "USD_SWAP_5Y",
                AS_OF - timedelta(days=2),
                source="TRADE_STORE",
                vendor_id="INTERNAL",
                venue="SEF_A",
                feed="EXECUTIONS",
                vendor_audit_evidence_id="internal-lineage-control-2026",
            ),
            RealPriceObservation("USD_SWAP_5Y", AS_OF - timedelta(days=400), source="VENDOR_A"),
        )
    )
    qualitative = _rfet_qualitative_stage(_risk_factor(), evidence)

    quantitative = _rfet_quantitative_stage(evidence, window, qualitative)

    assert quantitative.eligible_dates == (AS_OF - timedelta(days=2),)
    assert quantitative.eligible_sources == frozenset({"TRADE_STORE"})
    assert [exclusion.reason for exclusion in quantitative.exclusions] == [
        RFETExclusionReason.OUTSIDE_LOOKBACK,
        RFETExclusionReason.DUPLICATE_SOURCE_VENDOR,
    ]


def test_assess_rfet_evidence_requires_representative_bucket() -> None:
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    result = assess_rfet_evidence(
        _risk_factor(),
        _evidence(_observations(24), bucket_id="WRONG_BUCKET"),
        policy,
    )

    assert result.bucket_representative is False
    assert result.eligible_observation_count == 0
    assert result.modellability_status == ModellabilityStatus.TYPE_A_NMRF
    assert {exclusion.reason for exclusion in result.exclusions} == {
        RFETExclusionReason.NON_REPRESENTATIVE_BUCKET
    }


def test_assess_rfet_evidence_uses_explicit_representativeness_evidence() -> None:
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    evidence = RFETEvidence(
        risk_factor_name="USD_SWAP_5Y",
        as_of_date=AS_OF,
        observations=_observations(3),
        qualitative_pass=True,
        bucket_id="USD_RATES",
        representativeness=(
            RFETRepresentativenessEvidence(
                bucket_id="USD_RATES",
                methodology="curve-node-proximity",
                passed=False,
                rationale="Observed tenors do not represent the 5Y node.",
            ),
        ),
    )

    result = assess_rfet_evidence(_risk_factor(), evidence, policy)

    assert result.bucket_representative is False
    assert result.eligible_observation_count == 0
    assert {exclusion.reason for exclusion in result.exclusions} == {
        RFETExclusionReason.NON_REPRESENTATIVE_EVIDENCE
    }
    assert result.as_dict()["representative_methodology_counts"] == {"curve-node-proximity": 1}


def test_assess_rfet_evidence_requires_vendor_audit_or_data_pool_evidence() -> None:
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    observations = (
        RealPriceObservation(
            "USD_SWAP_5Y",
            AS_OF - timedelta(days=1),
            source="VENDOR_A",
            vendor_id="VENDOR_A",
            feed="COMPOSITE",
        ),
        RealPriceObservation(
            "USD_SWAP_5Y",
            AS_OF - timedelta(days=2),
            source="VENDOR_B",
            vendor_id="VENDOR_B",
            feed="COMPOSITE",
            data_pool_id="pool-b",
        ),
    )
    evidence = RFETEvidence(
        risk_factor_name="USD_SWAP_5Y",
        as_of_date=AS_OF,
        observations=observations,
        qualitative_pass=True,
        bucket_id="USD_RATES",
        data_pools=(
            RFETDataPoolEvidence(
                pool_id="pool-b",
                vendor_id="VENDOR_B",
                independent_audit_evidence_id="vendor-b-audit-2026",
            ),
        ),
    )

    result = assess_rfet_evidence(_risk_factor(), evidence, policy)

    assert result.eligible_observation_count == 1
    assert {exclusion.reason for exclusion in result.exclusions} == {
        RFETExclusionReason.MISSING_VENDOR_AUDIT_EVIDENCE
    }
    assert result.as_dict()["vendor_counts"] == {"VENDOR_B": 1}
    assert result.as_dict()["data_pool_count"] == 1
    assert result.as_dict()["vendor_audit_evidence_count"] == 1


def test_assess_rfet_evidence_maps_qualitative_failure_to_type_b() -> None:
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    result = assess_rfet_evidence(
        _risk_factor(),
        _evidence(_observations(24), qualitative_pass=False),
        policy,
    )

    assert result.quantitative_pass is True
    assert result.modellability_status == ModellabilityStatus.TYPE_B_NMRF


def test_new_issuance_prorating_is_explicit_opt_in() -> None:
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    issue_date = AS_OF - timedelta(days=90)
    risk_factor = _risk_factor()
    evidence = _evidence(_observations(8))

    without_prorating = assess_rfet_evidence(
        risk_factor,
        evidence,
        policy,
        issue_date=issue_date,
    )
    with_prorating = assess_rfet_evidence(
        risk_factor,
        evidence,
        policy,
        issue_date=issue_date,
        allow_new_issuance_prorating=True,
    )

    assert without_prorating.required_observations == 24
    assert without_prorating.modellability_status == ModellabilityStatus.TYPE_A_NMRF
    assert with_prorating.required_observations < 24
    assert with_prorating.new_issuance_prorated is True
    assert with_prorating.modellability_status == ModellabilityStatus.MODELLABLE


def test_new_issuance_prorating_uses_policy_governed_evidence() -> None:
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    evidence = RFETEvidence(
        risk_factor_name="USD_SWAP_5Y",
        as_of_date=AS_OF,
        observations=_observations(8),
        qualitative_pass=True,
        bucket_id="USD_RATES",
        new_issuance=RFETNewIssuanceEvidence(
            issue_date=AS_OF - timedelta(days=90),
            prorating_approved=True,
            policy_citation="U.S. NPR 2.0 proposed RFET new-issuance treatment",
        ),
    )

    result = assess_rfet_evidence(_risk_factor(), evidence, policy)

    assert result.required_observations < result.base_required_observations
    assert result.new_issuance_prorated is True
    assert result.as_dict()["new_issuance_policy_basis"] == (
        "U.S. NPR 2.0 proposed RFET new-issuance treatment"
    )


def test_assess_rfet_evidence_requires_timestamp_normalization_evidence() -> None:
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    observations = (
        RealPriceObservation(
            "USD_SWAP_5Y",
            AS_OF,
            source="VENDOR_A",
            vendor_id="VENDOR_A",
            observation_timestamp=datetime(2025, 7, 1, 0, 30, tzinfo=UTC),
            vendor_audit_evidence_id="vendor-a-audit-2026",
        ),
        RealPriceObservation(
            "USD_SWAP_5Y",
            AS_OF - timedelta(days=1),
            source="VENDOR_A",
            vendor_id="VENDOR_A",
            observation_timestamp=datetime(2025, 6, 30, 23, 30, tzinfo=UTC),
            date_normalization_evidence="New York market close normalized to local date.",
            vendor_audit_evidence_id="vendor-a-audit-2026",
        ),
    )

    result = assess_rfet_evidence(_risk_factor(), _evidence(observations), policy)

    assert result.eligible_observation_count == 1
    assert {exclusion.reason for exclusion in result.exclusions} == {
        RFETExclusionReason.MISSING_DATE_NORMALIZATION_EVIDENCE
    }


def test_prorated_required_observation_count_rejects_future_issue_date() -> None:
    with pytest.raises(ValueError, match="issue_date"):
        prorated_required_observation_count(
            24,
            lookback_start=AS_OF - timedelta(days=365),
            as_of_date=AS_OF,
            issue_date=AS_OF + timedelta(days=1),
        )


def test_ecb_policy_assesses_rfet_evidence_without_type_a_type_b_taxonomy() -> None:
    result = assess_rfet_evidence(
        _risk_factor(),
        _evidence(_observations(24)),
        get_policy(RegulatoryRegime.ECB_CRR3),
    )
    assert result.modellability_status is ModellabilityStatus.MODELLABLE
