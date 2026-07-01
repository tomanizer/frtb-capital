"""Organisation-scope metadata helpers for DRC audit records.

DRC preserves supplied scope identifiers for downstream result-store rollups,
but enterprise hierarchy traversal remains outside the capital package.
"""

from __future__ import annotations

from collections.abc import Iterable

from frtb_common import CalculationScope, stable_json_dumps

from frtb_drc.validation import DrcInputError


def validate_scope_metadata(scope: object, *, field: str) -> CalculationScope | None:
    """Return validated optional calculation-scope metadata.

    Parameters
    ----------
    scope, field
        Candidate scope object and error field name.

    Returns
    -------
    CalculationScope | None
        Validated scope metadata, or ``None`` when absent.
    """

    if scope is None:
        return None
    if not isinstance(scope, CalculationScope):
        raise DrcInputError(f"{field} must be CalculationScope when supplied")
    return scope


def scope_payload(scope: CalculationScope | None) -> dict[str, object] | None:
    """Return a stable JSON-compatible payload for optional scope metadata.

    Parameters
    ----------
    scope
        Optional calculation-scope metadata to serialize.

    Returns
    -------
    dict[str, object] | None
        Scope payload without null fields, or ``None`` for missing metadata.
    """

    if scope is None:
        return None
    payload = scope.as_dict()
    filtered = {key: value for key, value in payload.items() if value not in (None, {})}
    return filtered if filtered else None


def scope_at(
    scopes: tuple[CalculationScope | None, ...] | None,
    row_index: int,
) -> CalculationScope | None:
    """Return optional scope metadata for a batch row.

    Parameters
    ----------
    scopes, row_index
        Optional per-row scope tuple and zero-based row index.

    Returns
    -------
    CalculationScope | None
        The row scope when supplied, otherwise ``None``.
    """

    if scopes is None:
        return None
    return scopes[row_index]


def unique_scope_metadata(
    scopes: Iterable[CalculationScope | None],
) -> tuple[CalculationScope, ...]:
    """Return non-null scopes in deterministic payload order without duplicates.

    Parameters
    ----------
    scopes
        Scope metadata candidates from contributing rows.

    Returns
    -------
    tuple[CalculationScope, ...]
        Unique non-null scopes sorted by stable JSON payload.
    """

    unique: dict[str, CalculationScope] = {}
    for scope in scopes:
        if scope is None:
            continue
        payload = scope_payload(scope)
        if payload is None:
            continue
        unique[stable_json_dumps(payload)] = scope
    return tuple(unique[key] for key in sorted(unique))


def single_scope_metadata(
    scopes: Iterable[CalculationScope | None],
) -> CalculationScope | None:
    """Return the sole unique scope, or None when rows span scopes.

    Parameters
    ----------
    scopes
        Scope metadata candidates from contributing rows.

    Returns
    -------
    CalculationScope | None
        The single unique scope, or ``None`` for missing or mixed metadata.
    """

    unique = unique_scope_metadata(scopes)
    if len(unique) == 1:
        return unique[0]
    return None


__all__ = [
    "scope_at",
    "scope_payload",
    "single_scope_metadata",
    "unique_scope_metadata",
    "validate_scope_metadata",
]
