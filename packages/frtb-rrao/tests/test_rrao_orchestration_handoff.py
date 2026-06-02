"""Tests for the RRAO orchestration handoff projection."""

from __future__ import annotations

from datetime import date

from frtb_common import ComponentResultHandoff, StandardisedComponent

from frtb_rrao import (
    RraoCalculationContext,
    RraoClassification,
    RraoEvidenceType,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
    calculate_rrao_capital,
    to_orchestration_handoff,
)


def _sample_result():
    return calculate_rrao_capital(
        (
            RraoPosition(
                position_id="rrao-001",
                source_row_id="row-001",
                desk_id="desk-rrao",
                legal_entity="LE-001",
                gross_effective_notional=1_000_000.0,
                currency="USD",
                evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
                evidence_label="longevity derivative",
                lineage=RraoSourceLineage(
                    source_system="rrao-test",
                    source_file="rrao.csv",
                    source_row_id="row-001",
                    source_column_map=(("gross", "gross_effective_notional"),),
                ),
                classification_hint=RraoClassification.EXOTIC,
            ),
        ),
        context=RraoCalculationContext(
            run_id="rrao-run",
            calculation_date=date(2026, 3, 31),
            base_currency="USD",
            profile=RraoRegulatoryProfile.US_NPR_2_0,
        ),
    )


def test_to_orchestration_handoff_projects_shared_contract() -> None:
    result = _sample_result()

    handoff = to_orchestration_handoff(result)

    assert isinstance(handoff, ComponentResultHandoff)
    assert handoff.component is StandardisedComponent.RRAO
    assert handoff.package_name == "frtb-rrao"
    assert handoff.run_id == "rrao-run"
    assert handoff.calculation_date == date(2026, 3, 31)
    assert handoff.base_currency == "USD"
    assert handoff.profile_id == "US_NPR_2_0"
    assert handoff.total_capital == result.total_rrao
    assert handoff.profile_hash == result.profile_hash
    assert handoff.input_hash == result.input_hash
    assert handoff.line_count == len(result.lines)
    assert handoff.excluded_line_count == len(result.excluded_lines)
    assert handoff.subtotal_count == len(result.subtotals)
