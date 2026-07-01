"""Organisation-scope metadata helpers for IMA evidence records.

IMA preserves supplied scope identifiers for downstream result-store rollups,
but enterprise hierarchy traversal remains outside the capital package.
"""

from __future__ import annotations

from frtb_common import CalculationScope


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
        raise TypeError(f"{field} must be CalculationScope when supplied")
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


def add_scope_payload(
    payload: dict[str, object],
    scope: CalculationScope | None,
    *,
    key: str = "org_scope",
) -> dict[str, object]:
    """Return ``payload`` with optional scope metadata attached.

    Parameters
    ----------
    payload
        JSON-compatible payload to extend.
    scope
        Optional scope metadata.
    key
        Output key used when the scope is present.

    Returns
    -------
    dict[str, object]
        The supplied payload, with ``key`` added when scope metadata exists.
    """

    serialized = scope_payload(scope)
    if serialized is not None:
        payload[key] = serialized
    return payload


__all__ = [
    "add_scope_payload",
    "scope_payload",
    "validate_scope_metadata",
]
