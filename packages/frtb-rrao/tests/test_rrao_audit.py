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
from frtb_rrao._payloads import hash_payload, position_payload


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


def test_input_hash_matches_legacy_full_payload_encoding() -> None:
    positions = (
        sample_position("pos-001", "row-001"),
        sample_excluded_position("pos-002", "row-002"),
    )
    legacy_digest = hash_payload(
        {"positions": [position_payload(position) for position in positions]}
    )

    assert input_hash_for_positions(positions) == legacy_digest


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
    assert set(payload) == {
        "run_id",
        "calculation_date",
        "base_currency",
        "profile_id",
        "profile_hash",
        "input_hash",
        "input_hash_algorithm",
        "total_rrao",
        "citations",
        "warnings",
        "lines",
        "excluded_lines",
        "subtotals",
    }
    assert payload["run_id"] == "rrao-run-001"
    assert payload["calculation_date"] == "2026-03-31"
    assert payload["base_currency"] == "USD"
    assert payload["profile_id"] == "US_NPR_2_0"
    assert payload["input_hash_algorithm"] == "json-row-v1"
    assert payload["total_rrao"] == 10_000.0
    assert payload["citations"] == ["us_npr_211_a_1", "us_npr_211_c_1_i"]
    assert payload["warnings"] == [
        "US_NPR_2_0 is proposed-rule material; do not present outputs as final regulatory capital."
    ]
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
    assert payload["excluded_lines"] == []
    assert payload["subtotals"] == [
        {
            "subtotal_key": "EXOTIC",
            "subtotal_type": "classification",
            "gross_effective_notional": 1_000_000.0,
            "add_on": 10_000.0,
            "position_ids": ["pos-001"],
        },
        {
            "subtotal_key": "EXOTIC_UNDERLYING",
            "subtotal_type": "evidence_type",
            "gross_effective_notional": 1_000_000.0,
            "add_on": 10_000.0,
            "position_ids": ["pos-001"],
        },
        {
            "subtotal_key": "desk-a",
            "subtotal_type": "desk_id",
            "gross_effective_notional": 1_000_000.0,
            "add_on": 10_000.0,
            "position_ids": ["pos-001"],
        },
        {
            "subtotal_key": "LE-001",
            "subtotal_type": "legal_entity",
            "gross_effective_notional": 1_000_000.0,
            "add_on": 10_000.0,
            "position_ids": ["pos-001"],
        },
    ]


def test_reconciliation_rejects_wrong_total() -> None:
    result = calculate_rrao_capital(
        (sample_position("pos-001", "row-001"),),
        context=sample_context(),
    )
    corrupted = replace(result, total_rrao=0.0)

    with pytest.raises(RraoInputError, match="total RRAO does not reconcile") as exc_info:
        validate_rrao_result_reconciliation(corrupted)
    assert exc_info.value.field == "total_rrao"


def test_reconciliation_rejects_invalid_result_hashes() -> None:
    result = calculate_rrao_capital(
        (sample_position("pos-001", "row-001"),),
        context=sample_context(),
    )

    with pytest.raises(RraoInputError, match="hash must be a sha256 hex digest") as exc_info:
        validate_rrao_result_reconciliation(replace(result, profile_hash="short"))
    assert exc_info.value.field == "profile_hash"
    with pytest.raises(RraoInputError, match="hash must be a sha256 hex digest") as exc_info:
        validate_rrao_result_reconciliation(replace(result, input_hash="z" * 64))
    assert exc_info.value.field == "input_hash"
    base17_only_hash = "g" * 64
    with pytest.raises(RraoInputError, match="hash must be a sha256 hex digest") as exc_info:
        validate_rrao_result_reconciliation(replace(result, input_hash=base17_only_hash))
    assert exc_info.value.field == "input_hash"


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
            "lines",
            "pos-001",
        ),
        (
            replace(result, lines=(), excluded_lines=(replace(line, is_excluded=False),)),
            "excluded line partition contains an included line",
            "excluded_lines",
            "pos-001",
        ),
        (
            replace(
                result,
                lines=(),
                excluded_lines=(replace(line, is_excluded=True, add_on=1.0),),
            ),
            "excluded line add-on must be zero",
            "excluded_lines",
            "pos-001",
        ),
        (
            replace(result, lines=(line, line), excluded_lines=()),
            "duplicate result position id",
            "lines",
            "pos-001",
        ),
    )
    for invalid_result, message, field, position_id in invalid_cases:
        with pytest.raises(RraoInputError, match=message) as exc_info:
            validate_rrao_result_reconciliation(invalid_result)
        assert exc_info.value.field == field
        assert exc_info.value.position_id == position_id


def test_reconciliation_rejects_duplicate_excluded_position_ids_with_metadata() -> None:
    result = calculate_rrao_capital(
        (sample_excluded_position("pos-001", "row-001"),),
        context=sample_context(),
    )
    line = result.excluded_lines[0]
    corrupted = replace(result, excluded_lines=(line, line))

    with pytest.raises(RraoInputError, match="duplicate result position id") as exc_info:
        validate_rrao_result_reconciliation(corrupted)

    assert exc_info.value.field == "excluded_lines"
    assert exc_info.value.position_id == "pos-001"


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

    with pytest.raises(RraoInputError, match="subtotals do not reconcile") as exc_info:
        validate_rrao_result_reconciliation(corrupted)
    assert exc_info.value.field == "subtotals"


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

    with pytest.raises(RraoInputError, match="subtotals do not reconcile") as exc_info:
        validate_rrao_result_reconciliation(corrupted)
    assert exc_info.value.field == "subtotals"


def test_reconciliation_rejects_missing_subtotals() -> None:
    result = calculate_rrao_capital(
        (sample_position("pos-001", "row-001"),),
        context=sample_context(),
    )

    with pytest.raises(RraoInputError, match="subtotals do not reconcile") as exc_info:
        validate_rrao_result_reconciliation(replace(result, subtotals=()))
    assert exc_info.value.field == "subtotals"


def test_audit_normalisation_helpers_are_json_ready() -> None:
    payload = {
        "enum": RraoEvidenceType.GAP_RISK,
        "date": date(2026, 3, 31),
        "items": (RraoClassification.EXOTIC,),
    }

    from tests._helpers import normalise_audit_value

    assert normalise_audit_value(payload) == {
        "date": "2026-03-31",
        "enum": "GAP_RISK",
        "items": ["EXOTIC"],
    }
    assert audit_module._lineage_payload(None) is None
    assert audit_module._lineage_payload(sample_lineage("row-001")) == {
        "source_system": "synthetic-risk",
        "source_file": "rrao.csv",
        "source_row_id": "row-001",
        "source_column_map": [["RiskType", "evidence_type"]],
    }
