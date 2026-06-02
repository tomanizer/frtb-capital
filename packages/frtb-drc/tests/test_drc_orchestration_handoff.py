"""Tests for the DRC orchestration handoff projection."""

from __future__ import annotations

from datetime import date

from frtb_common import ComponentResultHandoff, StandardisedComponent
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
    to_orchestration_handoff,
)


def _sample_result():
    return calculate_drc_capital(
        (
            DrcPosition(
                position_id="drc-001",
                source_row_id="row-001",
                desk_id="desk-drc",
                legal_entity="LE-001",
                risk_class=DrcRiskClass.NON_SECURITISATION,
                instrument_type=DrcInstrumentType.BOND,
                default_direction=DefaultDirection.LONG,
                issuer_id="issuer-001",
                tranche_id=None,
                index_series_id=None,
                bucket_key="CORPORATE",
                seniority=DrcSeniority.SENIOR_DEBT,
                credit_quality=CreditQuality.INVESTMENT_GRADE,
                notional=100.0,
                market_value=100.0,
                cumulative_pnl=0.0,
                maturity_years=1.0,
                currency="USD",
                lineage=DrcSourceLineage(
                    source_system="drc-test",
                    source_file="drc.csv",
                    source_row_id="row-001",
                    source_column_map={"notional": "notional"},
                ),
                citation_ids=("US_NPR_210_SCOPE",),
            ),
        ),
        context=DrcCalculationContext(
            run_id="drc-run",
            calculation_date=date(2026, 3, 31),
            base_currency="USD",
            profile_id=US_NPR_2_0_PROFILE_ID,
        ),
    )


def test_to_orchestration_handoff_projects_shared_contract() -> None:
    result = _sample_result()

    handoff = to_orchestration_handoff(result)

    assert isinstance(handoff, ComponentResultHandoff)
    assert handoff.component is StandardisedComponent.DRC
    assert handoff.package_name == "frtb-drc"
    assert handoff.run_id == "drc-run"
    assert handoff.calculation_date == date(2026, 3, 31)
    assert handoff.base_currency == "USD"
    assert handoff.profile_id == US_NPR_2_0_PROFILE_ID
    assert handoff.total_capital == result.total_drc
    assert handoff.profile_hash == result.profile_hash
    assert handoff.input_hash == result.input_hash
    assert handoff.line_count == result.input_count
    assert handoff.excluded_line_count == result.rejected_input_count
    assert handoff.subtotal_count == len(result.categories)
    assert "US_NPR_210_SCOPE" in handoff.citations
