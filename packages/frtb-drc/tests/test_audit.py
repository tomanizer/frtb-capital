from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from frtb_drc import (
    US_NPR_2_0_PROFILE_ID,
    CreditQuality,
    DefaultDirection,
    DrcCalculationContext,
    DrcInputError,
    DrcInstrumentType,
    DrcPosition,
    DrcRiskClass,
    DrcSeniority,
    DrcSourceLineage,
    calculate_drc_capital,
    input_snapshot_hash,
    result_json,
    rule_profile_hash,
    serialize_result,
    validate_reconciliation,
)


def test_input_snapshot_hash_is_stable_for_input_order() -> None:
    long = _position("long", DefaultDirection.LONG, 100.0)
    short = _position("short", DefaultDirection.SHORT, 40.0)

    assert input_snapshot_hash((long, short)) == input_snapshot_hash((short, long))


def test_rule_profile_hash_returns_profile_content_hash() -> None:
    profile_hash = rule_profile_hash(US_NPR_2_0_PROFILE_ID)

    assert len(profile_hash) == 64


def test_result_serialization_is_json_ready_and_deterministic() -> None:
    result = calculate_drc_capital(
        (
            _position("long", DefaultDirection.LONG, 100.0),
            _position("short", DefaultDirection.SHORT, 40.0, issuer="issuer-b"),
        ),
        context=_context(),
    )

    snapshot = serialize_result(result)
    assert snapshot["run_id"] == "run-audit"
    assert snapshot["package_name"] == "frtb-drc"
    assert result_json(result) == result_json(result)


def test_validate_reconciliation_rejects_broken_total() -> None:
    result = calculate_drc_capital(
        (_position("long", DefaultDirection.LONG, 100.0),),
        context=_context(),
    )
    broken = replace(result, total_drc=result.total_drc + 1.0)

    with pytest.raises(DrcInputError, match="total DRC does not reconcile"):
        validate_reconciliation(broken)


def _context() -> DrcCalculationContext:
    return DrcCalculationContext(
        run_id="run-audit",
        calculation_date=date(2026, 5, 29),
        base_currency="USD",
        profile_id=US_NPR_2_0_PROFILE_ID,
    )


def _position(
    position_id: str,
    direction: DefaultDirection,
    notional: float,
    *,
    issuer: str = "issuer-a",
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
            source_file="audit.csv",
            source_row_id=f"row-{position_id}",
            source_column_map={"position_id": "position_id"},
        ),
    )
