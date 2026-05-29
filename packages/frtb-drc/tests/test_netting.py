from __future__ import annotations

import pytest
from frtb_drc import (
    DefaultDirection,
    DrcInputError,
    DrcRiskClass,
    DrcSeniority,
    GrossJtd,
    MaturityScaledJtd,
    NettingInput,
    calculate_net_jtds,
)


def test_same_obligor_same_seniority_offsets_net_correctly() -> None:
    records = calculate_net_jtds(
        (
            _input("long-1", DefaultDirection.LONG, 100.0, seniority=DrcSeniority.SENIOR_DEBT),
            _input("short-1", DefaultDirection.SHORT, 40.0, seniority=DrcSeniority.SENIOR_DEBT),
        )
    )

    assert len(records) == 1
    assert records[0].net_direction is DefaultDirection.LONG
    assert records[0].scaled_long == 100.0
    assert records[0].scaled_short == 40.0
    assert records[0].net_amount == 60.0
    assert records[0].rejected_offsets == ()


def test_cross_obligor_exposures_do_not_offset() -> None:
    records = calculate_net_jtds(
        (
            _input("long-1", DefaultDirection.LONG, 100.0, issuer="issuer-a"),
            _input("short-1", DefaultDirection.SHORT, 40.0, issuer="issuer-b"),
        )
    )

    net_records = [
        (record.obligor_or_tranche_key, record.net_direction, record.net_amount)
        for record in records
    ]
    assert net_records == [
        ("issuer-a", DefaultDirection.LONG, 100.0),
        ("issuer-b", DefaultDirection.SHORT, 40.0),
    ]


def test_cross_bucket_exposures_do_not_offset() -> None:
    records = calculate_net_jtds(
        (
            _input("long-1", DefaultDirection.LONG, 100.0, bucket="CORPORATE"),
            _input("short-1", DefaultDirection.SHORT, 40.0, bucket="PSE_GSE"),
        )
    )

    assert [(record.bucket_key, record.net_direction, record.net_amount) for record in records] == [
        ("CORPORATE", DefaultDirection.LONG, 100.0),
        ("PSE_GSE", DefaultDirection.SHORT, 40.0),
    ]


def test_same_obligor_lower_seniority_short_offsets_higher_seniority_long() -> None:
    records = calculate_net_jtds(
        (
            _input("long-1", DefaultDirection.LONG, 100.0, seniority=DrcSeniority.SENIOR_DEBT),
            _input("short-1", DefaultDirection.SHORT, 40.0, seniority=DrcSeniority.NON_SENIOR_DEBT),
        )
    )

    assert len(records) == 1
    assert records[0].seniority_layer == "SENIOR_DEBT"
    assert records[0].net_direction is DefaultDirection.LONG
    assert records[0].net_amount == 60.0


def test_same_obligor_higher_seniority_short_is_rejected_against_lower_seniority_long() -> None:
    records = calculate_net_jtds(
        (
            _input("long-1", DefaultDirection.LONG, 100.0, seniority=DrcSeniority.NON_SENIOR_DEBT),
            _input("short-1", DefaultDirection.SHORT, 40.0, seniority=DrcSeniority.SENIOR_DEBT),
        )
    )

    assert [(record.net_direction, record.net_amount) for record in records] == [
        (DefaultDirection.LONG, 100.0),
        (DefaultDirection.SHORT, 40.0),
    ]
    rejected = records[0].rejected_offsets
    assert len(rejected) == 1
    assert rejected[0].reason_code == "SHORT_HIGHER_SENIORITY_THAN_LONG"
    assert rejected[0].citations == ("US_NPR_210_B_2",)


def test_netting_reconciles_signed_scaled_jtd() -> None:
    inputs = (
        _input("long-1", DefaultDirection.LONG, 100.0, seniority=DrcSeniority.SENIOR_DEBT),
        _input("short-1", DefaultDirection.SHORT, 40.0, seniority=DrcSeniority.NON_SENIOR_DEBT),
        _input("short-2", DefaultDirection.SHORT, 10.0, seniority=DrcSeniority.EQUITY),
    )

    records = calculate_net_jtds(inputs)

    signed_input = 100.0 - 40.0 - 10.0
    signed_output = sum(
        record.net_amount if record.net_direction is DefaultDirection.LONG else -record.net_amount
        for record in records
    )
    assert signed_output == signed_input


def test_netting_rejects_mismatched_gross_and_scaled_ids() -> None:
    bad = _input("long-1", DefaultDirection.LONG, 100.0)
    bad = NettingInput(
        gross_jtd=bad.gross_jtd,
        scaled_jtd=_scaled("other", DefaultDirection.LONG, 100.0),
        seniority=bad.seniority,
    )

    with pytest.raises(DrcInputError, match="gross_jtd_id mismatch"):
        calculate_net_jtds((bad,))


def _input(
    position_id: str,
    direction: DefaultDirection,
    amount: float,
    *,
    seniority: DrcSeniority = DrcSeniority.SENIOR_DEBT,
    issuer: str = "issuer-a",
    bucket: str = "CORPORATE",
) -> NettingInput:
    return NettingInput(
        gross_jtd=_gross(position_id, direction, amount, issuer=issuer, bucket=bucket),
        scaled_jtd=_scaled(position_id, direction, amount),
        seniority=seniority,
    )


def _gross(
    position_id: str,
    direction: DefaultDirection,
    amount: float,
    *,
    issuer: str,
    bucket: str,
) -> GrossJtd:
    return GrossJtd(
        gross_jtd_id=f"gross-{position_id}",
        position_id=position_id,
        risk_class=DrcRiskClass.NON_SECURITISATION,
        issuer_or_tranche_key=issuer,
        bucket_key=bucket,
        default_direction=direction,
        lgd_rate=0.75,
        lgd_source="profile",
        notional=100.0,
        pnl_component=0.0,
        gross_jtd=amount,
        citations=("BASEL_MAR22_11",),
    )


def _scaled(position_id: str, _direction: DefaultDirection, amount: float) -> MaturityScaledJtd:
    return MaturityScaledJtd(
        scaled_jtd_id=f"scaled-{position_id}",
        gross_jtd_id=f"gross-{position_id}",
        position_id=position_id,
        gross_jtd=amount,
        maturity_years=1.0,
        maturity_weight=1.0,
        scaled_jtd=amount,
        floor_applied=False,
        citations=("US_NPR_210_A_2_III",),
    )
