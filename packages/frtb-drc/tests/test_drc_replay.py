from __future__ import annotations

from datetime import date

from frtb_drc import (
    US_NPR_2_0_PROFILE_ID,
    CreditQuality,
    DefaultDirection,
    DrcCalculationContext,
    DrcInstrumentType,
    DrcPosition,
    DrcRiskClass,
    DrcSeniority,
    DrcSourceLineage,
    calculate_drc_capital,
    result_json,
)


def test_public_result_replays_deterministically_across_input_order() -> None:
    long = _position("long", DefaultDirection.LONG, 100.0, issuer="issuer-a")
    short = _position("short", DefaultDirection.SHORT, 40.0, issuer="issuer-b")

    first = calculate_drc_capital((long, short), context=_context())
    second = calculate_drc_capital((short, long), context=_context())

    assert first.input_hash == second.input_hash
    assert [record.position_id for record in first.gross_jtds] == ["long", "short"]
    assert result_json(first) == result_json(second)


def _context() -> DrcCalculationContext:
    return DrcCalculationContext(
        run_id="run-replay",
        calculation_date=date(2026, 5, 29),
        base_currency="USD",
        profile_id=US_NPR_2_0_PROFILE_ID,
    )


def _position(
    position_id: str,
    direction: DefaultDirection,
    notional: float,
    *,
    issuer: str,
) -> DrcPosition:
    return DrcPosition(
        position_id=position_id,
        source_row_id=f"row-{position_id}",
        desk_id="desk-a",
        legal_entity="bank-na",
        risk_class=DrcRiskClass.NON_SECURITISATION,
        instrument_type=DrcInstrumentType.BOND,
        default_direction=direction,
        issuer_id=issuer,
        tranche_id=None,
        index_series_id=None,
        bucket_key="CORPORATE",
        seniority=DrcSeniority.SENIOR_DEBT,
        credit_quality=CreditQuality.INVESTMENT_GRADE,
        notional=notional,
        market_value=notional,
        cumulative_pnl=0.0,
        maturity_years=1.0,
        currency="USD",
        lineage=DrcSourceLineage(
            source_system="synthetic",
            source_file="replay.csv",
            source_row_id=f"row-{position_id}",
            source_column_map={"position_id": "position_id"},
        ),
    )
