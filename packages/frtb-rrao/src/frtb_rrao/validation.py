"""
Validation helpers for canonical RRAO inputs.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for validation.py, Basel MAR23.8,
    and U.S. NPR 2.0 proposed section __.211(c)(2).
"""

from __future__ import annotations

import math
from typing import Literal

from frtb_rrao.data_models import (
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoPosition,
    RraoSourceLineage,
)

NotionalSignConvention = Literal["gross", "signed_absolute"]

_UNSUPPORTED_V1_EVIDENCE_TYPES = frozenset(
    {
        RraoEvidenceType.INVESTMENT_FUND_EXPOSURE,
    }
)


class RraoInputError(ValueError):
    """Raised when canonical RRAO inputs fail deterministic validation."""

    def __init__(self, message: str, *, field: str = "", position_id: str = "") -> None:
        self.field = field
        self.position_id = position_id
        prefix = f"position {position_id}: " if position_id else ""
        suffix = f" [{field}]" if field else ""
        super().__init__(f"{prefix}{message}{suffix}")


def normalise_gross_effective_notional(
    value: float,
    *,
    source_sign_convention: NotionalSignConvention = "gross",
) -> float:
    """Return a finite non-negative gross effective notional."""

    if source_sign_convention not in {"gross", "signed_absolute"}:
        raise RraoInputError(
            "source_sign_convention must be 'gross' or 'signed_absolute'",
            field="source_sign_convention",
        )
    notional = _finite_float(value, field="gross_effective_notional")
    if notional < 0:
        if source_sign_convention == "signed_absolute":
            return abs(notional)
        raise RraoInputError(
            "gross effective notional must be non-negative",
            field="gross_effective_notional",
        )
    return notional


def validate_rrao_positions(positions: object) -> tuple[RraoPosition, ...]:
    """Validate canonical RRAO positions and return them as a tuple."""

    if isinstance(positions, RraoPosition):
        raise RraoInputError("positions must be an iterable of RraoPosition objects")
    try:
        candidates: tuple[object, ...] = tuple(positions)  # type: ignore[arg-type]
    except TypeError as exc:
        raise RraoInputError("positions must be an iterable of RraoPosition objects") from exc

    seen_position_ids: set[str] = set()
    validated: list[RraoPosition] = []
    for candidate in candidates:
        if not isinstance(candidate, RraoPosition):
            raise RraoInputError("positions must contain only RraoPosition objects")
        position = candidate
        _validate_position(position, seen_position_ids)
        seen_position_ids.add(position.position_id)
        validated.append(position)
    return tuple(validated)


def _validate_position(position: RraoPosition, seen_position_ids: set[str]) -> None:
    position_id = _require_text(position.position_id, "position_id")
    if position_id in seen_position_ids:
        raise RraoInputError(
            "duplicate position id",
            field="position_id",
            position_id=position_id,
        )

    _require_text(position.source_row_id, "source_row_id", position_id)
    _require_text(position.desk_id, "desk_id", position_id)
    _require_text(position.legal_entity, "legal_entity", position_id)
    _require_text(position.currency, "currency", position_id)
    _require_text(position.evidence_label, "evidence_label", position_id)
    _require_text(position.notional_source, "notional_source", position_id)
    normalise_gross_effective_notional(position.gross_effective_notional)

    if not isinstance(position.evidence_type, RraoEvidenceType):
        raise RraoInputError(
            "invalid evidence type", field="evidence_type", position_id=position_id
        )
    if position.evidence_type in _UNSUPPORTED_V1_EVIDENCE_TYPES:
        raise RraoInputError(
            "unsupported classification evidence for v1 validation",
            field="evidence_type",
            position_id=position_id,
        )
    if position.classification_hint is not None and not isinstance(
        position.classification_hint,
        RraoClassification,
    ):
        raise RraoInputError(
            "invalid classification hint",
            field="classification_hint",
            position_id=position_id,
        )
    if position.classification_hint is RraoClassification.UNSUPPORTED:
        raise RraoInputError(
            "unsupported classification path",
            field="classification_hint",
            position_id=position_id,
        )
    if position.exclusion_reason is not None and not isinstance(
        position.exclusion_reason,
        RraoExclusionReason,
    ):
        raise RraoInputError(
            "invalid exclusion reason",
            field="exclusion_reason",
            position_id=position_id,
        )

    _validate_lineage(position.lineage, position_id)
    _validate_optional_fields(position)
    _validate_evidence_requirements(position)


def _validate_lineage(lineage: RraoSourceLineage | None, position_id: str) -> None:
    if lineage is None:
        raise RraoInputError("source lineage is required", field="lineage", position_id=position_id)
    if not isinstance(lineage, RraoSourceLineage):
        raise RraoInputError("invalid source lineage", field="lineage", position_id=position_id)

    _require_text(lineage.source_system, "lineage.source_system", position_id)
    _require_text(lineage.source_file, "lineage.source_file", position_id)
    _require_text(lineage.source_row_id, "lineage.source_row_id", position_id)
    for mapping in lineage.source_column_map:
        if not isinstance(mapping, tuple) or len(mapping) != 2:
            raise RraoInputError(
                "source column map entries must be field pairs",
                field="lineage.source_column_map",
                position_id=position_id,
            )
        source_field, canonical_field = mapping
        _require_text(source_field, "lineage.source_column_map.source", position_id)
        _require_text(canonical_field, "lineage.source_column_map.canonical", position_id)


def _validate_optional_fields(position: RraoPosition) -> None:
    if position.underlying_count is not None:
        if not isinstance(position.underlying_count, int) or isinstance(
            position.underlying_count,
            bool,
        ):
            raise RraoInputError(
                "underlying count must be an integer",
                field="underlying_count",
                position_id=position.position_id,
            )
        if position.underlying_count < 0:
            raise RraoInputError(
                "underlying count must be non-negative",
                field="underlying_count",
                position_id=position.position_id,
            )

    for field_name in (
        "is_path_dependent",
        "has_maturity",
        "has_strike_or_barrier",
        "has_multiple_strikes_or_barriers",
    ):
        value = getattr(position, field_name)
        if value is not None and not isinstance(value, bool):
            raise RraoInputError(
                f"{field_name} must be a bool when provided",
                field=field_name,
                position_id=position.position_id,
            )

    for field_name in ("is_ctp_hedge", "is_investment_fund_exposure"):
        if not isinstance(getattr(position, field_name), bool):
            raise RraoInputError(
                f"{field_name} must be a bool",
                field=field_name,
                position_id=position.position_id,
            )
    if position.is_investment_fund_exposure:
        raise RraoInputError(
            "investment fund exposure path is unsupported for v1 validation",
            field="is_investment_fund_exposure",
            position_id=position.position_id,
        )
    for citation in position.citations:
        _require_text(citation, "citations", position.position_id)


def _validate_evidence_requirements(position: RraoPosition) -> None:
    if position.evidence_type is RraoEvidenceType.SUPERVISOR_DIRECTIVE:
        _require_text(
            position.supervisor_directive_id,
            "supervisor_directive_id",
            position.position_id,
        )
    if position.classification_hint is RraoClassification.SUPERVISOR_DIRECTED:
        _require_text(
            position.supervisor_directive_id,
            "supervisor_directive_id",
            position.position_id,
        )
    if (
        position.classification_hint is RraoClassification.EXCLUDED
        and position.exclusion_reason is None
    ):
        raise RraoInputError(
            "excluded classification requires an exclusion reason",
            field="exclusion_reason",
            position_id=position.position_id,
        )
    if position.exclusion_reason is not None:
        _require_text(position.exclusion_evidence_id, "exclusion_evidence_id", position.position_id)
    if position.evidence_type is RraoEvidenceType.EXPLICIT_EXCLUSION:
        if position.exclusion_reason is None:
            raise RraoInputError(
                "explicit exclusion evidence requires an exclusion reason",
                field="exclusion_reason",
                position_id=position.position_id,
            )
        _require_text(position.exclusion_evidence_id, "exclusion_evidence_id", position.position_id)


def _finite_float(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise RraoInputError("value must be numeric", field=field)
    number = float(value)
    if not math.isfinite(number):
        raise RraoInputError("value must be finite", field=field)
    return number


def _require_text(value: object, field: str, position_id: str = "") -> str:
    if not isinstance(value, str) or not value.strip():
        raise RraoInputError("non-empty text is required", field=field, position_id=position_id)
    return value


__all__ = [
    "NotionalSignConvention",
    "RraoInputError",
    "normalise_gross_effective_notional",
    "validate_rrao_positions",
]
