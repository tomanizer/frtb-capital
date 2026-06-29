"""
Validation helpers for canonical RRAO position rows.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for position validation,
    Basel MAR23.8, and U.S. NPR 2.0 proposed section __.211(c)(2).
"""

from __future__ import annotations

from frtb_rrao._validation_rules import (
    GROSS_NOTIONAL_NON_NEGATIVE_MESSAGE,
    SOURCE_LINEAGE_REQUIRED_MESSAGE,
    UNSUPPORTED_CLASSIFICATION_MESSAGE,
    is_unsupported_classification_hint,
)
from frtb_rrao.batch_registry import materialize_rrao_positions
from frtb_rrao.data_models import (
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoPosition,
    RraoSourceLineage,
)
from frtb_rrao.validation._back_to_back import (
    _validate_back_to_back_match_fields,
)
from frtb_rrao.validation._common import _finite_float, _require_text
from frtb_rrao.validation._errors import NotionalSignConvention, RraoInputError
from frtb_rrao.validation._evidence import (
    _validate_evidence_requirements,
    _validate_optional_fields,
)


def normalise_gross_effective_notional(
    value: float,
    *,
    source_sign_convention: NotionalSignConvention = "gross",
) -> float:
    """Return a finite non-negative gross effective notional.

    Parameters
    ----------
    value : float
        Raw gross effective notional value supplied by the adapter or caller.
    source_sign_convention : {"gross", "signed_absolute"}, optional
        Whether negative values are invalid gross notionals or signed values
        that should be converted to absolute gross notionals.

    Returns
    -------
    float
        Finite non-negative gross effective notional.
    """

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
            GROSS_NOTIONAL_NON_NEGATIVE_MESSAGE,
            field="gross_effective_notional",
        )
    return notional


def validate_rrao_positions(positions: object) -> tuple[RraoPosition, ...]:
    """Validate canonical RRAO positions.

    Parameters
    ----------
    positions : object
        Iterable of `RraoPosition` rows to validate.

    Returns
    -------
    tuple[RraoPosition, ...]
        Validated positions in input order.
    """

    materialized = materialize_rrao_positions(positions)
    if not materialized:
        return materialized
    from frtb_rrao.batch import _build_rrao_batch_from_materialized_positions

    _build_rrao_batch_from_materialized_positions(materialized)
    return materialized


def _validate_position_without_back_to_back_groups(
    position: RraoPosition,
    seen_position_ids: set[str],
) -> None:
    """Validate one row before batch-level back-to-back matching is available."""

    _validate_position(position, seen_position_ids)
    _validate_back_to_back_match_fields(position)


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
    if position.classification_hint is not None and not isinstance(
        position.classification_hint,
        RraoClassification,
    ):
        raise RraoInputError(
            "invalid classification hint",
            field="classification_hint",
            position_id=position_id,
        )
    if is_unsupported_classification_hint(position.classification_hint):
        raise RraoInputError(
            UNSUPPORTED_CLASSIFICATION_MESSAGE,
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
        raise RraoInputError(
            SOURCE_LINEAGE_REQUIRED_MESSAGE, field="lineage", position_id=position_id
        )
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


__all__ = [
    "NotionalSignConvention",
    "RraoInputError",
    "normalise_gross_effective_notional",
    "validate_rrao_positions",
]
