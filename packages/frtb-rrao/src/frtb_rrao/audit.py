"""
Deterministic RRAO audit serialization and reconciliation.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for audit.py, Basel MAR23.8,
    and U.S. NPR 2.0 proposed section __.211(c).
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict
from datetime import date
from enum import Enum
from typing import Any, cast

from frtb_rrao.capital import build_rrao_subtotals, included_rrao_total
from frtb_rrao.data_models import (
    RraoCapitalLine,
    RraoCapitalResult,
    RraoPosition,
    RraoSubtotal,
)
from frtb_rrao.validation import RraoInputError, validate_rrao_positions

_HASH_HEX_LENGTH = 64
_RECONCILIATION_TOLERANCE = 1e-9


def input_hash_for_positions(positions: object) -> str:
    """Return a deterministic hash of canonical RRAO input positions."""

    validated = validate_rrao_positions(positions)
    return _hash_payload({"positions": [_normalise(position) for position in validated]})


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
    if not math.isclose(
        result.total_rrao,
        expected_total,
        rel_tol=0.0,
        abs_tol=_RECONCILIATION_TOLERANCE,
    ):
        raise RraoInputError(
            "total RRAO does not reconcile to included line add-ons",
            field="total_rrao",
        )

    expected_subtotals = build_rrao_subtotals(all_lines)
    if tuple(result.subtotals) != expected_subtotals:
        raise RraoInputError(
            "subtotals do not reconcile to line records",
            field="subtotals",
        )


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
        if line.add_on != 0.0:
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


def _line_payload(line: RraoCapitalLine) -> dict[str, object]:
    return cast(dict[str, object], _normalise(line))


def _subtotal_payload(subtotal: RraoSubtotal) -> dict[str, object]:
    return cast(dict[str, object], _normalise(subtotal))


def _hash_payload(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _normalise(value: object) -> Any:
    if isinstance(value, RraoPosition | RraoCapitalLine | RraoSubtotal):
        return _normalise(asdict(value))
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
