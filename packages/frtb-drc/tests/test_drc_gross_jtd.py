from __future__ import annotations

import pytest
from frtb_drc import (
    CreditQuality,
    DefaultDirection,
    DrcInputError,
    DrcInstrumentType,
    DrcPosition,
    DrcRiskClass,
    DrcSeniority,
    DrcSourceLineage,
    calculate_gross_jtd,
    calculate_gross_jtds,
)


def test_long_default_risk_produces_gross_long_jtd() -> None:
    gross = calculate_gross_jtd(
        _position(default_direction=DefaultDirection.LONG, notional=100.0, cumulative_pnl=-10.0)
    )

    assert gross.gross_jtd_id == "gross-pos-1"
    assert gross.default_direction is DefaultDirection.LONG
    assert gross.lgd_rate == 0.75
    assert gross.gross_jtd == 65.0
    assert "BASEL_MAR22_11" in gross.citations
    assert "BASEL_MAR22_13" in gross.citations
    assert "US_NPR_210_B_1_IV" in gross.citations


def test_short_default_risk_produces_readable_short_magnitude() -> None:
    gross = calculate_gross_jtd(
        _position(default_direction=DefaultDirection.SHORT, notional=100.0, cumulative_pnl=10.0)
    )

    assert gross.default_direction is DefaultDirection.SHORT
    assert gross.gross_jtd == 65.0
    assert gross.notional == 100.0


def test_market_value_derives_pnl_when_cumulative_pnl_is_absent() -> None:
    gross = calculate_gross_jtd(
        _position(
            default_direction=DefaultDirection.LONG,
            notional=100.0,
            market_value=90.0,
            cumulative_pnl=None,
        )
    )

    assert gross.pnl_component == -10.0
    assert gross.gross_jtd == 65.0


def test_zero_lgd_recovery_unlinked_position_produces_zero_gross_jtd() -> None:
    gross = calculate_gross_jtd(
        _position(
            seniority=DrcSeniority.NOT_RECOVERY_LINKED,
            notional=100.0,
            cumulative_pnl=0.0,
        )
    )

    assert gross.lgd_rate == 0.0
    assert gross.gross_jtd == 0.0


def test_defaulted_position_uses_defaulted_lgd_treatment() -> None:
    gross = calculate_gross_jtd(
        _position(
            seniority=DrcSeniority.SENIOR_DEBT,
            credit_quality=CreditQuality.DEFAULTED,
            is_defaulted=True,
            notional=100.0,
            cumulative_pnl=-10.0,
        )
    )

    assert gross.lgd_rate == 1.0
    assert gross.gross_jtd == 90.0


def test_gross_jtd_rejects_lgd_override_until_profile_supports_it() -> None:
    with pytest.raises(DrcInputError, match="LGD overrides are not supported"):
        calculate_gross_jtd(_position(lgd_override=0.40))


def test_gross_jtd_rejects_missing_pnl_inputs() -> None:
    with pytest.raises(DrcInputError, match="cumulative_pnl or market_value is required"):
        calculate_gross_jtd(_position(market_value=None, cumulative_pnl=None))


def test_gross_jtd_helper_rejects_securitisation_risk_class() -> None:
    position = _position(
        risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
        instrument_type=DrcInstrumentType.SECURITISATION_TRANCHE,
        issuer_id="issuer-a",
        tranche_id="tranche-a",
        bucket_key="SEC_CLO_NORTH_AMERICA",
        seniority=None,
    )

    with pytest.raises(DrcInputError, match="gross JTD is not implemented"):
        calculate_gross_jtd(position)


def test_calculate_gross_jtds_preserves_input_order() -> None:
    positions = (
        _position(position_id="pos-1", source_row_id="row-1"),
        _position(position_id="pos-2", source_row_id="row-2"),
    )

    records = calculate_gross_jtds(positions)

    assert [record.position_id for record in records] == ["pos-1", "pos-2"]


def test_calculate_gross_jtds_rejects_duplicate_position_ids() -> None:
    positions = (
        _position(position_id="pos-1", source_row_id="row-1"),
        _position(position_id="pos-1", source_row_id="row-2"),
    )

    with pytest.raises(DrcInputError, match="duplicate position_id"):
        calculate_gross_jtds(positions)


def _position(**overrides: object) -> DrcPosition:
    values: dict[str, object] = {
        "position_id": "pos-1",
        "source_row_id": "row-1",
        "desk_id": "desk-a",
        "legal_entity": "bank-na",
        "risk_class": DrcRiskClass.NON_SECURITISATION,
        "instrument_type": DrcInstrumentType.BOND,
        "default_direction": DefaultDirection.LONG,
        "issuer_id": "issuer-a",
        "tranche_id": None,
        "index_series_id": None,
        "bucket_key": "CORPORATE",
        "seniority": DrcSeniority.SENIOR_DEBT,
        "credit_quality": CreditQuality.INVESTMENT_GRADE,
        "notional": 100.0,
        "market_value": 99.0,
        "cumulative_pnl": 0.0,
        "maturity_years": 1.0,
        "currency": "USD",
        "lineage": DrcSourceLineage(
            source_system="test",
            source_file="positions.csv",
            source_row_id=str(overrides.get("source_row_id", "row-1")),
        ),
        "citation_ids": ("US_NPR_210_SCOPE",),
    }
    values.update(overrides)
    return DrcPosition(**values)  # type: ignore[arg-type]
