from __future__ import annotations

import json
from datetime import date

from frtb_rrao import (
    RraoCalculationContext,
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
    calculate_rrao_capital,
    serialize_rrao_result,
)


def sample_lineage(row_id: str) -> RraoSourceLineage:
    return RraoSourceLineage(
        source_system="synthetic-risk",
        source_file="rrao.csv",
        source_row_id=row_id,
        source_column_map=(("AmountUSD", "gross_effective_notional"),),
    )


def sample_context() -> RraoCalculationContext:
    return RraoCalculationContext(
        run_id="rrao-replay-001",
        calculation_date=date(2026, 3, 31),
        base_currency="USD",
        profile=RraoRegulatoryProfile.US_NPR_2_0,
    )


def sample_positions() -> tuple[RraoPosition, ...]:
    return (
        RraoPosition(
            position_id="exotic-001",
            source_row_id="row-001",
            desk_id="desk-a",
            legal_entity="LE-001",
            gross_effective_notional=1_000_000.0,
            currency="USD",
            evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
            evidence_label="weather derivative",
            classification_hint=RraoClassification.EXOTIC,
            lineage=sample_lineage("row-001"),
        ),
        RraoPosition(
            position_id="listed-001",
            source_row_id="row-002",
            desk_id="desk-b",
            legal_entity="LE-001",
            gross_effective_notional=3_000_000.0,
            currency="USD",
            evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
            evidence_label="listed option",
            classification_hint=RraoClassification.EXCLUDED,
            exclusion_reason=RraoExclusionReason.LISTED,
            exclusion_evidence_id="exchange-listing-001",
            lineage=sample_lineage("row-002"),
        ),
    )


def test_public_result_replay_is_deterministic() -> None:
    first = calculate_rrao_capital(sample_positions(), context=sample_context())
    second = calculate_rrao_capital(sample_positions(), context=sample_context())

    assert first == second
    assert first.input_hash == second.input_hash
    assert first.profile_hash == second.profile_hash
    assert serialize_rrao_result(first) == serialize_rrao_result(second)
    assert json.dumps(serialize_rrao_result(first), sort_keys=True) == json.dumps(
        serialize_rrao_result(second),
        sort_keys=True,
    )
