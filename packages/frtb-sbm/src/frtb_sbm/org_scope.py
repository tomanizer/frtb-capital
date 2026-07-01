"""Organisation-scope metadata helpers for SBM audit records.

SBM preserves scope identifiers supplied by upstream systems but does not own
enterprise hierarchy traversal or rollup semantics.
"""

from __future__ import annotations

from collections.abc import Iterable

from frtb_common import CalculationScope, stable_json_dumps

from frtb_sbm._errors import SbmInputError


def validate_scope_metadata(
    scope: object,
    *,
    field: str,
    sensitivity_id: str = "",
) -> CalculationScope | None:
    """Return validated optional calculation-scope metadata.

    Parameters
    ----------
    scope, field, sensitivity_id
        Candidate scope object and error-context fields.

    Returns
    -------
    CalculationScope | None
        The validated scope, or ``None`` when no metadata was supplied.
    """

    if scope is None:
        return None
    if not isinstance(scope, CalculationScope):
        raise SbmInputError(
            f"{field} must be CalculationScope when supplied",
            field=field,
            sensitivity_id=sensitivity_id,
        )
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
        key = stable_json_dumps(payload)
        unique[key] = scope
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
