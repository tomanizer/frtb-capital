"""Shared row-mapping helpers for v1 IMA mapping-spec materializers."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from frtb_ima.adapters.mapping_spec import FieldMapping, MappingFinding


def mapped_value(row: Mapping[str, object], mapping: FieldMapping, field_name: str) -> object:
    """Resolve one mapped source or constant value from a client row.

    Parameters
    ----------
    row : Mapping[str, object]
        Source row keyed by client column name.
    mapping : FieldMapping
        Field mapping that names a source column or constant value.
    field_name : str
        Target field name used in validation errors.

    Returns
    -------
    object
        Raw mapped value after applying optional value aliases.
    """

    if mapping.constant is not None:
        value: object = mapping.constant
    elif mapping.source is None:
        raise ValueError(f"{field_name} mapping has neither source nor constant")
    else:
        if mapping.source not in row:
            raise ValueError(f"{field_name} source column {mapping.source!r} is missing")
        value = row[mapping.source]
    if value is None:
        return None
    text = str(value)
    return mapping.values.get(text, value)


def mapped_str(row: Mapping[str, object], mapping: FieldMapping, field_name: str) -> str:
    """Resolve one required mapped value as a non-empty string.

    Parameters
    ----------
    row : Mapping[str, object]
        Source row keyed by client column name.
    mapping : FieldMapping
        Field mapping that names a source column or constant value.
    field_name : str
        Target field name used in validation errors.

    Returns
    -------
    str
        Trimmed non-empty string value.
    """

    value = mapped_value(row, mapping, field_name)
    text = "" if value is None else str(value).strip()
    if not text:
        raise ValueError(f"{field_name} is required")
    return text


def mapped_date(row: Mapping[str, object], mapping: FieldMapping, field_name: str) -> date:
    """Resolve one required mapped value as an ISO calendar date.

    Parameters
    ----------
    row : Mapping[str, object]
        Source row keyed by client column name.
    mapping : FieldMapping
        Field mapping that names a source column or constant value.
    field_name : str
        Target field name used in validation errors.

    Returns
    -------
    date
        Parsed ISO ``YYYY-MM-DD`` date value.
    """

    try:
        return date.fromisoformat(mapped_str(row, mapping, field_name))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an ISO date") from exc


def plain_mapping(row: Mapping[str, object]) -> dict[str, str]:
    """Return a stable string-only copy of a source row for hashing.

    Parameters
    ----------
    row : Mapping[str, object]
        Source row keyed by client column name.

    Returns
    -------
    dict[str, str]
        Mapping with string keys and string values, using an empty string for nulls.
    """

    return {str(key): "" if value is None else str(value) for key, value in row.items()}


def resolve_source_row_id(
    row: Mapping[str, object],
    row_index: int,
    fields: Mapping[str, FieldMapping],
    *,
    findings: list[MappingFinding] | None = None,
) -> str:
    """Resolve a source row id and optionally report fallback provenance.

    Parameters
    ----------
    row : Mapping[str, object]
        Source row keyed by client column name.
    row_index : int
        One-based row position used for deterministic fallback ids.
    fields : Mapping[str, FieldMapping]
        Target field mappings that may include ``source_row_id``.
    findings : list[MappingFinding] | None, optional
        Validation findings collection that receives fallback warnings when supplied.

    Returns
    -------
    str
        Explicit source row id, or deterministic ``row-N`` fallback.
    """

    mapping = fields.get("source_row_id")
    if mapping is None:
        return f"row-{row_index}"
    try:
        return mapped_str(row, mapping, "source_row_id")
    except ValueError as exc:
        fallback = f"row-{row_index}"
        if findings is not None:
            findings.append(
                MappingFinding(
                    severity="WARNING",
                    code="SOURCE_ROW_ID_FALLBACK",
                    message=str(exc),
                    row_id=fallback,
                    field="source_row_id",
                )
            )
        return fallback
