from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import date

import pytest
from frtb_rrao import (
    RraoCalculationContext,
    RraoClassification,
    RraoEvidenceType,
    RraoInputError,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
    RraoSubtotal,
    calculate_rrao_capital,
    input_hash_for_positions,
    serialize_rrao_result,
    validate_rrao_result_reconciliation,
)


def sample_lineage(row_id: str) -> RraoSourceLineage:
    return RraoSourceLineage(
        source_system="synthetic-risk",
        source_file="rrao.csv",
        source_row_id=row_id,
        source_column_map=(("RiskType", "evidence_type"),),
    )


def sample_position(position_id: str, source_row_id: str) -> RraoPosition:
    return RraoPosition(
        position_id=position_id,
        source_row_id=source_row_id,
        desk_id="desk-a",
        legal_entity="LE-001",
        gross_effective_notional=1_000_000.0,
        currency="USD",
        evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
        evidence_label="weather derivative",
        classification_hint=RraoClassification.EXOTIC,
        lineage=sample_lineage(source_row_id),
    )


def sample_context() -> RraoCalculationContext:
    return RraoCalculationContext(
        run_id="rrao-run-001",
        calculation_date=date(2026, 3, 31),
        base_currency="USD",
        profile=RraoRegulatoryProfile.US_NPR_2_0,
    )


def test_input_hash_is_deterministic_and_input_sensitive() -> None:
    positions = (
        sample_position("pos-001", "row-001"),
        sample_position("pos-002", "row-002"),
    )
    same_positions = (
        sample_position("pos-001", "row-001"),
        sample_position("pos-002", "row-002"),
    )
    reordered_positions = tuple(reversed(positions))

    digest = input_hash_for_positions(positions)

    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    assert digest == input_hash_for_positions(same_positions)
    assert digest != input_hash_for_positions(reordered_positions)


def test_result_serialization_is_json_stable() -> None:
    result = calculate_rrao_capital(
        (sample_position("pos-001", "row-001"),),
        context=sample_context(),
    )
    payload = serialize_rrao_result(result)

    assert payload == result.as_dict()
    assert json.dumps(payload, sort_keys=True)
    assert payload["profile_id"] == "US_NPR_2_0"
    assert payload["lines"] == [
        {
            "position_id": "pos-001",
            "classification": "EXOTIC",
            "evidence_type": "EXOTIC_UNDERLYING",
            "gross_effective_notional": 1_000_000.0,
            "risk_weight": 0.01,
            "add_on": 10_000.0,
            "currency": "USD",
            "is_excluded": False,
            "reason_code": "US_NPR_EXOTIC_EXPOSURE",
            "citations": ["us_npr_211_a_1", "us_npr_211_c_1_i"],
            "desk_id": "desk-a",
            "legal_entity": "LE-001",
            "source_row_id": "row-001",
            "exclusion_reason": None,
            "exclusion_evidence_id": None,
        }
    ]


def test_reconciliation_rejects_wrong_total() -> None:
    result = calculate_rrao_capital(
        (sample_position("pos-001", "row-001"),),
        context=sample_context(),
    )
    corrupted = replace(result, total_rrao=0.0)

    with pytest.raises(RraoInputError, match="total RRAO does not reconcile"):
        validate_rrao_result_reconciliation(corrupted)


def test_reconciliation_rejects_wrong_subtotals() -> None:
    result = calculate_rrao_capital(
        (sample_position("pos-001", "row-001"),),
        context=sample_context(),
    )
    corrupted = replace(
        result,
        subtotals=(
            RraoSubtotal(
                subtotal_key="wrong",
                subtotal_type="classification",
                gross_effective_notional=1_000_000.0,
                add_on=10_000.0,
                position_ids=("pos-001",),
            ),
        ),
    )

    with pytest.raises(RraoInputError, match="subtotals do not reconcile"):
        validate_rrao_result_reconciliation(corrupted)
