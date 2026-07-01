"""Organisation-scope metadata helpers for CVA audit records.

CVA preserves supplied scope identifiers for downstream result-store rollups,
but enterprise hierarchy traversal remains outside the capital package.
"""

from __future__ import annotations

from collections.abc import Sequence

from frtb_common import CalculationScope

_SCOPE_PAYLOAD_CACHE_SIZE = 128
_SCOPE_PAYLOAD_CACHE: dict[int, tuple[CalculationScope, dict[str, object] | None]] = {}


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
        from frtb_cva.validation import CvaInputError

        raise CvaInputError(f"{field} must be CalculationScope when supplied", field=field)
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
    scope_id = id(scope)
    cached = _SCOPE_PAYLOAD_CACHE.get(scope_id)
    if cached is not None:
        cached_scope, cached_payload = cached
        if cached_scope is scope:
            return cached_payload.copy() if cached_payload is not None else None

    payload = scope.as_dict()
    filtered = {key: value for key, value in payload.items() if value not in (None, {})}
    result = filtered if filtered else None
    if len(_SCOPE_PAYLOAD_CACHE) >= _SCOPE_PAYLOAD_CACHE_SIZE:
        _SCOPE_PAYLOAD_CACHE.pop(next(iter(_SCOPE_PAYLOAD_CACHE)))
    _SCOPE_PAYLOAD_CACHE[scope_id] = (scope, result)
    return result


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


def scopes_from_columns(
    org_scopes: Sequence[CalculationScope | None] | None,
    row_count: int,
    *,
    field: str,
) -> tuple[CalculationScope | None, ...] | None:
    """Validate optional per-row scope metadata for columnar batches.

    Parameters
    ----------
    org_scopes
        Optional sequence aligned to the batch row count.
    row_count
        Expected number of rows in the owning batch.
    field
        Field name to report on validation errors.

    Returns
    -------
    tuple[CalculationScope | None, ...] | None
        Validated per-row scope tuple, or ``None`` when all rows are unscoped.
    """

    if org_scopes is None:
        return None
    if len(org_scopes) != row_count:
        from frtb_cva.validation import CvaInputError

        raise CvaInputError(f"{field} length does not match row count", field=field)
    rows = tuple(
        validate_scope_metadata(scope, field=f"{field}[{index}]")
        for index, scope in enumerate(org_scopes)
    )
    if not any(scope is not None for scope in rows):
        return None
    return rows


__all__ = [
    "scope_at",
    "scope_payload",
    "scopes_from_columns",
    "validate_scope_metadata",
]
