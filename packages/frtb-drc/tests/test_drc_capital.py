from __future__ import annotations

import pytest
from frtb_drc import (
    BranchType,
    CapitalInput,
    CreditQuality,
    DefaultDirection,
    DrcInputError,
    DrcRiskClass,
    NetJtd,
    calculate_bucket_drc,
    calculate_category_drc,
    calculate_hedge_benefit_ratio,
)


def test_hbr_uses_aggregate_net_long_and_short_amounts() -> None:
    hbr = calculate_hedge_benefit_ratio(
        (
            _net("long-a", DefaultDirection.LONG, 100.0),
            _net("long-b", DefaultDirection.LONG, 50.0),
            _net("short-a", DefaultDirection.SHORT, 50.0),
        ),
        bucket_key="CORPORATE",
    )

    assert hbr.aggregate_net_long == 150.0
    assert hbr.aggregate_net_short == 50.0
    assert hbr.denominator == 200.0
    assert hbr.ratio == 0.75
    assert hbr.citations == ("US_NPR_210_A_2_IV_A",)


def test_hbr_zero_denominator_records_branch_metadata() -> None:
    hbr = calculate_hedge_benefit_ratio(
        (_net("zero", DefaultDirection.LONG, 0.0),),
        bucket_key="CORPORATE",
    )

    assert hbr.ratio == 0.0
    assert hbr.branch_metadata[0].branch_type is BranchType.ZERO_DENOMINATOR


def test_bucket_capital_applies_risk_weights_and_hbr() -> None:
    bucket = calculate_bucket_drc(
        (
            CapitalInput(
                _net("long", DefaultDirection.LONG, 100.0),
                CreditQuality.INVESTMENT_GRADE,
            ),
            CapitalInput(
                _net("short", DefaultDirection.SHORT, 40.0),
                CreditQuality.INVESTMENT_GRADE,
            ),
        ),
        bucket_key="CORPORATE",
    )

    assert bucket.hbr.ratio == pytest.approx(100.0 / 140.0)
    assert bucket.weighted_long == pytest.approx(4.1)
    assert bucket.weighted_short == pytest.approx(1.64)
    assert bucket.capital == pytest.approx(2.928571428571429)
    assert bucket.floor_applied is False
    assert bucket.net_jtd_ids == ("long", "short")
    assert "US_NPR_210_A_2_IV_C" in bucket.citations
    assert "US_NPR_210_B_3_II" in bucket.citations


def test_bucket_capital_accepts_string_credit_quality() -> None:
    bucket = calculate_bucket_drc(
        (CapitalInput(_net("long", DefaultDirection.LONG, 100.0), "INVESTMENT_GRADE"),),
        bucket_key="CORPORATE",
    )

    assert bucket.weighted_long == pytest.approx(4.1)
    assert bucket.capital == pytest.approx(4.1)


def test_bucket_capital_floors_negative_bucket_at_zero() -> None:
    bucket = calculate_bucket_drc(
        (
            CapitalInput(
                _net("long", DefaultDirection.LONG, 100.0),
                CreditQuality.INVESTMENT_GRADE,
            ),
            CapitalInput(
                _net("short", DefaultDirection.SHORT, 100.0),
                CreditQuality.SUB_SPECULATIVE_GRADE,
            ),
        ),
        bucket_key="CORPORATE",
    )

    assert bucket.weighted_long == pytest.approx(4.1)
    assert bucket.weighted_short == pytest.approx(50.0)
    assert bucket.capital == 0.0
    assert bucket.floor_applied is True
    assert bucket.branch_metadata[0].branch_type is BranchType.FLOOR


def test_category_capital_sums_bucket_results_in_stable_bucket_order() -> None:
    category = calculate_category_drc(
        (
            CapitalInput(
                _net("pse", DefaultDirection.LONG, 100.0, bucket="PSE_GSE"),
                CreditQuality.INVESTMENT_GRADE,
            ),
            CapitalInput(
                _net("corp", DefaultDirection.LONG, 200.0, bucket="CORPORATE"),
                CreditQuality.INVESTMENT_GRADE,
            ),
        )
    )

    assert [bucket.bucket_key for bucket in category.bucket_results] == ["CORPORATE", "PSE_GSE"]
    assert category.capital == pytest.approx(10.3)
    assert category.risk_class is DrcRiskClass.NON_SECURITISATION
    assert category.branch_metadata[0].citations == ("US_NPR_210_B_3_III",)


def test_bucket_capital_rejects_missing_risk_weight() -> None:
    with pytest.raises(DrcInputError, match="missing DRC risk weight"):
        calculate_bucket_drc(
            (CapitalInput(_net("bad", DefaultDirection.LONG, 10.0), CreditQuality.DEFAULTED),),
            bucket_key="CORPORATE",
        )


def test_bucket_capital_rejects_bucket_mismatch() -> None:
    with pytest.raises(DrcInputError, match="bucket mismatch"):
        calculate_bucket_drc(
            (
                CapitalInput(
                    _net("bad", DefaultDirection.LONG, 10.0, bucket="PSE_GSE"),
                    CreditQuality.INVESTMENT_GRADE,
                ),
            ),
            bucket_key="CORPORATE",
        )


def test_bucket_capital_rejects_explicit_empty_bucket_key() -> None:
    with pytest.raises(DrcInputError, match="bucket_key must be non-empty"):
        calculate_bucket_drc(
            (
                CapitalInput(
                    _net("bad", DefaultDirection.LONG, 10.0), CreditQuality.INVESTMENT_GRADE
                ),
            ),
            bucket_key="",
        )


def test_bucket_capital_rejects_securitisation_net_jtd() -> None:
    with pytest.raises(DrcInputError, match="non-securitisation"):
        calculate_bucket_drc(
            (
                CapitalInput(
                    _net(
                        "sec",
                        DefaultDirection.LONG,
                        10.0,
                        risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
                    ),
                    CreditQuality.INVESTMENT_GRADE,
                ),
            ),
            bucket_key="CORPORATE",
        )


def _net(
    net_jtd_id: str,
    direction: DefaultDirection,
    amount: float,
    *,
    bucket: str = "CORPORATE",
    risk_class: DrcRiskClass = DrcRiskClass.NON_SECURITISATION,
) -> NetJtd:
    return NetJtd(
        net_jtd_id=net_jtd_id,
        netting_group_id=f"group-{net_jtd_id}",
        risk_class=risk_class,
        bucket_key=bucket,
        obligor_or_tranche_key=f"issuer-{net_jtd_id}",
        seniority_layer="SENIOR_DEBT",
        gross_long=amount if direction is DefaultDirection.LONG else 0.0,
        gross_short=amount if direction is DefaultDirection.SHORT else 0.0,
        scaled_long=amount if direction is DefaultDirection.LONG else 0.0,
        scaled_short=amount if direction is DefaultDirection.SHORT else 0.0,
        net_amount=amount,
        net_direction=direction,
        position_ids=(f"position-{net_jtd_id}",),
        scaled_jtd_ids=(f"scaled-{net_jtd_id}",),
    )
