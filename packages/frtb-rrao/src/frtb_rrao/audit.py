"""
Deterministic RRAO audit serialization and reconciliation.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for audit.py, Basel MAR23.8,
    and U.S. NPR 2.0 proposed section __.211(c).
"""

from __future__ import annotations

from frtb_rrao.assembly._payload_components import lineage_payload
from frtb_rrao.assembly.payloads import hash_position_payloads, position_payload
from frtb_rrao.capital import build_rrao_subtotals, included_rrao_total
from frtb_rrao.data_models import (
    RraoCapitalLine,
    RraoCapitalResult,
    RraoPosition,
    RraoSourceLineage,
    RraoSubtotal,
)
from frtb_rrao.numeric import is_reconciled, is_zero_excluded_add_on
from frtb_rrao.validation import RraoInputError, validate_rrao_positions

_HASH_HEX_LENGTH = 64


def input_hash_for_positions(positions: object) -> str:
    """Return a deterministic hash of canonical RRAO input positions.
    Parameters
    ----------
    positions : object
        Positions.

    Returns
    -------
    str
        Result of the operation.
    """

    validated = validate_rrao_positions(positions)
    return _input_hash_for_validated_positions(validated)


def _input_hash_for_validated_positions(positions: tuple[RraoPosition, ...]) -> str:
    """Return an input hash for an already validated position tuple."""

    return hash_position_payloads(position_payload(position) for position in positions)


def _lineage_payload(lineage: RraoSourceLineage | None) -> dict[str, object] | None:
    """Compatibility wrapper for tests covering audit JSON normalization."""

    return lineage_payload(lineage)


def serialize_rrao_result(result: RraoCapitalResult) -> dict[str, object]:
    """Return a JSON-serialisable audit payload for an RRAO result.
    Parameters
    ----------
    result : RraoCapitalResult
        Result.

    Returns
    -------
    dict[str, object]
        Result of the operation.
    """

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
    """Raise when a public RRAO result does not reconcile to its line records.
    Parameters
    ----------
    result : RraoCapitalResult
        Result.
    """

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


__all__ = [
    "input_hash_for_positions",
    "serialize_rrao_result",
    "validate_rrao_result_reconciliation",
]
