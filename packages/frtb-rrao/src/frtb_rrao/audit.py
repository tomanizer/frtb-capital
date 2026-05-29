"""
Deterministic RRAO audit serialization and reconciliation.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for audit.py, Basel MAR23.8,
    and U.S. NPR 2.0 proposed section __.211(c).
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from enum import Enum
from typing import Any

from frtb_rrao.capital import build_rrao_subtotals, included_rrao_total
from frtb_rrao.data_models import (
    RraoBackToBackMatch,
    RraoCapitalLine,
    RraoCapitalResult,
    RraoInvestmentFundDescriptor,
    RraoPosition,
    RraoSourceLineage,
    RraoSubtotal,
)
from frtb_rrao.numeric import is_reconciled, is_zero_excluded_add_on
from frtb_rrao.validation import RraoInputError, validate_rrao_positions

_HASH_HEX_LENGTH = 64


def input_hash_for_positions(positions: object) -> str:
    """Return a deterministic hash of canonical RRAO input positions."""

    validated = validate_rrao_positions(positions)
    return _input_hash_for_validated_positions(validated)


def _input_hash_for_validated_positions(positions: tuple[RraoPosition, ...]) -> str:
    """Return an input hash for an already validated position tuple."""

    return _hash_payload({"positions": [_position_payload(position) for position in positions]})


def serialize_rrao_result(result: RraoCapitalResult) -> dict[str, object]:
    """Return a JSON-serialisable audit payload for an RRAO result."""

    return {
        "run_id": result.run_id,
        "calculation_date": result.calculation_date.isoformat(),
        "base_currency": result.base_currency,
        "profile_id": result.profile_id,
        "profile_hash": result.profile_hash,
        "input_hash": result.input_hash,
        "total_rrao": result.total_rrao,
        "citations": list(result.citations),
        "warnings": list(result.warnings),
        "lines": [_line_payload(line) for line in result.lines],
        "excluded_lines": [_line_payload(line) for line in result.excluded_lines],
        "subtotals": [_subtotal_payload(subtotal) for subtotal in result.subtotals],
    }


def validate_rrao_result_reconciliation(result: RraoCapitalResult) -> None:
    """Raise when a public RRAO result does not reconcile to its line records."""

    _validate_hash("profile_hash", result.profile_hash)
    _validate_hash("input_hash", result.input_hash)

    included_lines = tuple(result.lines)
    excluded_lines = tuple(result.excluded_lines)
    all_lines = included_lines + excluded_lines

    _validate_line_partition(included_lines, excluded_lines)
    expected_total = included_rrao_total(all_lines)
    if not is_reconciled(result.total_rrao, expected_total):
        raise RraoInputError(
            "total RRAO does not reconcile to included line add-ons",
            field="total_rrao",
        )

    expected_subtotals = build_rrao_subtotals(all_lines)
    _validate_subtotals_reconcile(tuple(result.subtotals), expected_subtotals)


def _validate_hash(field: str, value: str) -> None:
    if not isinstance(value, str) or len(value) != _HASH_HEX_LENGTH:
        raise RraoInputError("hash must be a sha256 hex digest", field=field)
    try:
        int(value, 16)
    except ValueError as exc:
        raise RraoInputError("hash must be a sha256 hex digest", field=field) from exc


def _validate_line_partition(
    included_lines: tuple[RraoCapitalLine, ...],
    excluded_lines: tuple[RraoCapitalLine, ...],
) -> None:
    seen_position_ids: set[str] = set()
    for line in included_lines:
        if line.is_excluded:
            raise RraoInputError(
                "included line partition contains an excluded line",
                field="lines",
                position_id=line.position_id,
            )
        _add_result_position_id(seen_position_ids, line.position_id, field="lines")

    for line in excluded_lines:
        if not line.is_excluded:
            raise RraoInputError(
                "excluded line partition contains an included line",
                field="excluded_lines",
                position_id=line.position_id,
            )
        if not is_zero_excluded_add_on(line.add_on):
            raise RraoInputError(
                "excluded line add-on must be zero",
                field="excluded_lines",
                position_id=line.position_id,
            )
        _add_result_position_id(seen_position_ids, line.position_id, field="excluded_lines")


def _add_result_position_id(seen_position_ids: set[str], position_id: str, *, field: str) -> None:
    if position_id in seen_position_ids:
        raise RraoInputError(
            "duplicate result position id",
            field=field,
            position_id=position_id,
        )
    seen_position_ids.add(position_id)


def _validate_subtotals_reconcile(
    actual_subtotals: tuple[RraoSubtotal, ...],
    expected_subtotals: tuple[RraoSubtotal, ...],
) -> None:
    if len(actual_subtotals) != len(expected_subtotals):
        _raise_subtotal_reconciliation_error()
    for actual, expected in zip(actual_subtotals, expected_subtotals, strict=True):
        if (
            actual.subtotal_key != expected.subtotal_key
            or actual.subtotal_type != expected.subtotal_type
            or actual.position_ids != expected.position_ids
        ):
            _raise_subtotal_reconciliation_error()
        if not is_reconciled(
            actual.gross_effective_notional,
            expected.gross_effective_notional,
        ) or not is_reconciled(actual.add_on, expected.add_on):
            _raise_subtotal_reconciliation_error()


def _raise_subtotal_reconciliation_error() -> None:
    raise RraoInputError(
        "subtotals do not reconcile to line records",
        field="subtotals",
    )


def _line_payload(line: RraoCapitalLine) -> dict[str, object]:
    return {
        "position_id": line.position_id,
        "classification": line.classification.value,
        "evidence_type": line.evidence_type.value,
        "gross_effective_notional": line.gross_effective_notional,
        "risk_weight": line.risk_weight,
        "add_on": line.add_on,
        "currency": line.currency,
        "is_excluded": line.is_excluded,
        "reason_code": line.reason_code,
        "citations": list(line.citations),
        "desk_id": line.desk_id,
        "legal_entity": line.legal_entity,
        "source_row_id": line.source_row_id,
        "exclusion_reason": line.exclusion_reason.value
        if line.exclusion_reason is not None
        else None,
        "exclusion_evidence_id": line.exclusion_evidence_id,
    }


def _subtotal_payload(subtotal: RraoSubtotal) -> dict[str, object]:
    return {
        "subtotal_key": subtotal.subtotal_key,
        "subtotal_type": subtotal.subtotal_type,
        "gross_effective_notional": subtotal.gross_effective_notional,
        "add_on": subtotal.add_on,
        "position_ids": list(subtotal.position_ids),
    }


def _hash_payload(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _position_payload(position: RraoPosition) -> dict[str, object]:
    payload: dict[str, object] = {
        "position_id": position.position_id,
        "source_row_id": position.source_row_id,
        "desk_id": position.desk_id,
        "legal_entity": position.legal_entity,
        "gross_effective_notional": position.gross_effective_notional,
        "currency": position.currency,
        "evidence_type": position.evidence_type.value,
        "evidence_label": position.evidence_label,
        "lineage": _lineage_payload(position.lineage),
        "classification_hint": position.classification_hint.value
        if position.classification_hint is not None
        else None,
        "exclusion_reason": position.exclusion_reason.value
        if position.exclusion_reason is not None
        else None,
        "exclusion_evidence_id": position.exclusion_evidence_id,
        "supervisor_directive_id": position.supervisor_directive_id,
        "underlying_count": position.underlying_count,
        "is_path_dependent": position.is_path_dependent,
        "has_maturity": position.has_maturity,
        "has_strike_or_barrier": position.has_strike_or_barrier,
        "has_multiple_strikes_or_barriers": position.has_multiple_strikes_or_barriers,
        "is_ctp_hedge": position.is_ctp_hedge,
        "is_investment_fund_exposure": position.is_investment_fund_exposure,
        "investment_fund_descriptor": _investment_fund_descriptor_payload(
            position.investment_fund_descriptor
        ),
        "notional_source": position.notional_source,
        "citations": list(position.citations),
    }
    if position.back_to_back_match is not None:
        payload["back_to_back_match"] = _back_to_back_match_payload(position.back_to_back_match)
    return payload


def _lineage_payload(lineage: RraoSourceLineage | None) -> dict[str, object] | None:
    if lineage is None:
        return None
    return {
        "source_system": lineage.source_system,
        "source_file": lineage.source_file,
        "source_row_id": lineage.source_row_id,
        "source_column_map": [list(pair) for pair in lineage.source_column_map],
    }


def _investment_fund_descriptor_payload(
    descriptor: RraoInvestmentFundDescriptor | None,
) -> dict[str, object] | None:
    if descriptor is None:
        return None
    return {
        "fund_id": descriptor.fund_id,
        "section_205_method": descriptor.section_205_method.value,
        "included_exposure_type": descriptor.included_exposure_type.value,
        "mandate_evidence_id": descriptor.mandate_evidence_id,
        "section_205_evidence_id": descriptor.section_205_evidence_id,
        "fund_gross_effective_notional": descriptor.fund_gross_effective_notional,
        "included_exposure_ratio": descriptor.included_exposure_ratio,
        "look_through_available": descriptor.look_through_available,
        "mandate_allows_rrao_exposures": descriptor.mandate_allows_rrao_exposures,
    }


def _back_to_back_match_payload(match: RraoBackToBackMatch) -> dict[str, object]:
    return {
        "match_group_id": match.match_group_id,
        "matched_position_id": match.matched_position_id,
    }


def _normalise(value: object) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalise(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple | list):
        return [_normalise(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    return value


__all__ = [
    "input_hash_for_positions",
    "serialize_rrao_result",
    "validate_rrao_result_reconciliation",
]
