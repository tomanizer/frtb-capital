from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import date

import pytest

from frtb_rrao import (
    RraoBackToBackMatch,
    RraoCalculationContext,
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
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
from frtb_rrao import audit as audit_module


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


def sample_excluded_position(position_id: str, source_row_id: str) -> RraoPosition:
    return RraoPosition(
        position_id=position_id,
        source_row_id=source_row_id,
        desk_id="desk-a",
        legal_entity="LE-001",
        gross_effective_notional=1_000_000.0,
        currency="USD",
        evidence_type=RraoEvidenceType.EXPLICIT_EXCLUSION,
        evidence_label="listed option",
        classification_hint=RraoClassification.EXCLUDED,
        exclusion_reason=RraoExclusionReason.LISTED,
        exclusion_evidence_id="listing-evidence-001",
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


def test_input_hash_includes_back_to_back_match_payload() -> None:
    left = replace(
        sample_excluded_position("pos-001", "row-001"),
        exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
        back_to_back_match=RraoBackToBackMatch(
            match_group_id="external-match-001",
            matched_position_id="pos-002",
        ),
    )
    right = replace(
        sample_excluded_position("pos-002", "row-002"),
        exclusion_reason=RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK,
        back_to_back_match=RraoBackToBackMatch(
            match_group_id="external-match-001",
            matched_position_id="pos-001",
        ),
    )

    assert re.fullmatch(r"[0-9a-f]{64}", input_hash_for_positions((left, right)))


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


def test_reconciliation_rejects_invalid_result_hashes() -> None:
    result = calculate_rrao_capital(
        (sample_position("pos-001", "row-001"),),
        context=sample_context(),
    )

    with pytest.raises(RraoInputError, match="hash must be a sha256 hex digest"):
        validate_rrao_result_reconciliation(replace(result, profile_hash="short"))
    with pytest.raises(RraoInputError, match="hash must be a sha256 hex digest"):
        validate_rrao_result_reconciliation(replace(result, input_hash="z" * 64))


def test_reconciliation_rejects_invalid_line_partitions() -> None:
    result = calculate_rrao_capital(
        (sample_position("pos-001", "row-001"),),
        context=sample_context(),
    )
    line = result.lines[0]

    invalid_cases = (
        (
            replace(result, lines=(replace(line, is_excluded=True),), excluded_lines=()),
            "included line partition contains an excluded line",
        ),
        (
            replace(result, lines=(), excluded_lines=(replace(line, is_excluded=False),)),
            "excluded line partition contains an included line",
        ),
        (
            replace(
                result,
                lines=(),
                excluded_lines=(replace(line, is_excluded=True, add_on=1.0),),
            ),
            "excluded line add-on must be zero",
        ),
        (
            replace(result, lines=(line, line), excluded_lines=()),
            "duplicate result position id",
        ),
    )
    for invalid_result, message in invalid_cases:
        with pytest.raises(RraoInputError, match=message):
            validate_rrao_result_reconciliation(invalid_result)


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


def test_reconciliation_rejects_wrong_subtotal_amounts() -> None:
    result = calculate_rrao_capital(
        (sample_position("pos-001", "row-001"),),
        context=sample_context(),
    )
    subtotal = result.subtotals[0]
    corrupted = replace(
        result,
        subtotals=(
            replace(
                subtotal,
                gross_effective_notional=subtotal.gross_effective_notional + 1,
            ),
        ),
    )

    with pytest.raises(RraoInputError, match="subtotals do not reconcile"):
        validate_rrao_result_reconciliation(corrupted)


def test_reconciliation_rejects_missing_subtotals() -> None:
    result = calculate_rrao_capital(
        (sample_position("pos-001", "row-001"),),
        context=sample_context(),
    )

    with pytest.raises(RraoInputError, match="subtotals do not reconcile"):
        validate_rrao_result_reconciliation(replace(result, subtotals=()))


def test_audit_normalisation_helpers_are_json_ready() -> None:
    payload = {
        "enum": RraoEvidenceType.GAP_RISK,
        "date": date(2026, 3, 31),
        "items": (RraoClassification.EXOTIC,),
    }

    from audit_normalise import normalise_audit_value

    assert normalise_audit_value(payload) == {
        "date": "2026-03-31",
        "enum": "GAP_RISK",
        "items": ["EXOTIC"],
    }
    assert audit_module._lineage_payload(None) is None
