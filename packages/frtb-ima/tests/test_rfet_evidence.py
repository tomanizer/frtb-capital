"""Tests for RFET evidence assessment."""

from datetime import date, timedelta

import pytest

from frtb_ima.data_contracts import RFETEvidence, RiskFactorBucket, RiskFactorDefinition
from frtb_ima.data_models import (
    LiquidityHorizon,
    ModellabilityStatus,
    RealPriceObservation,
    RiskClass,
)
from frtb_ima.regimes import RegulatoryRegime, UnsupportedRegulatoryFeature, get_policy
from frtb_ima.rfet_evidence import (
    RFETExclusionReason,
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


def test_prorated_required_observation_count_rejects_future_issue_date() -> None:
    with pytest.raises(ValueError, match="issue_date"):
        prorated_required_observation_count(
            24,
            lookback_start=AS_OF - timedelta(days=365),
            as_of_date=AS_OF,
            issue_date=AS_OF + timedelta(days=1),
        )


def test_ecb_policy_rejects_type_a_type_b_evidence_assessment() -> None:
    with pytest.raises(UnsupportedRegulatoryFeature, match="type_a_type_b"):
        assess_rfet_evidence(
            _risk_factor(),
            _evidence(_observations(24)),
            get_policy(RegulatoryRegime.ECB_CRR3),
        )
