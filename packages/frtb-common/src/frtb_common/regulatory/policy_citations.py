"""Regulatory citation enforcement utilities for policy objects.

This module provides reusable helpers to ensure that numeric parameters
in regulatory policy/configuration objects have explicit citations to
source regulations (Basel MARxx, U.S. NPR 2.0 sections, PRA rules, CRR3
articles, etc.).

It is intended to be used in test suites across all packages in the
frtb-capital suite to maintain consistent traceability discipline.

Example usage::

    from frtb_common.regulatory.policy_citations import (
        assert_policy_has_regulatory_citations,
    )

    def test_my_policy_is_fully_traced():
        policy = get_my_policy()
        assert_policy_has_regulatory_citations(
            policy,
            allowed_without_citation={"my_internal_modelling_choice"},
        )
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import fields, is_dataclass
from typing import Any

__all__ = [
    "MissingRegulatoryCitationsError",
    "assert_policy_has_regulatory_citations",
]


class MissingRegulatoryCitationsError(AssertionError):
    """Raised when one or more numeric policy fields lack regulatory citations."""

    pass


def assert_policy_has_regulatory_citations(
    obj: Any,
    *,
    citation_attr: str = "cited_by",
    allowed_without_citation: Iterable[str] | None = None,
    recurse: bool = True,
    max_depth: int = 5,
    _current_path: str = "",
    _depth: int = 0,
) -> None:
    """
    Recursively assert that every numeric field on a policy object (and any
    nested policy objects) has a corresponding entry in its citation mapping.

    Parameters
    ----------
    obj
        The policy/configuration object to validate. Expected to be a dataclass
        (frozen or not) that carries a citation mapping attribute.
    citation_attr
        Name of the attribute holding the citation mapping (default: "cited_by").
        This allows different policy objects to use different attribute names.
    allowed_without_citation
        Field names that are intentionally modelling choices and do not require
        a regulatory citation (e.g. "es_estimator", "nmrf_taxonomy_mode").
    recurse
        Whether to descend into nested policy-like objects.
    max_depth
        Safety limit to prevent runaway recursion on circular structures.
    """
    if _depth > max_depth:
        raise RecursionError(
            f"Maximum recursion depth ({max_depth}) exceeded while checking "
            f"regulatory citations at {_current_path or type(obj).__name__}"
        )

    allowed = set(allowed_without_citation or ())
    current_path = _current_path or type(obj).__name__

    # Retrieve the citation mapping (supports dict and MappingProxyType).
    citation_keys: set[str] = set()
    if hasattr(obj, citation_attr):
        citation_keys = _valid_citation_keys(getattr(obj, citation_attr))

    # Discover fields that contain numeric values
    numeric_fields = _discover_numeric_fields(obj)

    missing = numeric_fields - citation_keys - allowed

    if missing:
        missing_list = "\n    - ".join(sorted(missing))
        raise MissingRegulatoryCitationsError(
            f"Missing regulatory citations in {current_path} "
            f"(citation attribute: '{citation_attr}'):\n"
            f"    - {missing_list}\n\n"
            "Add the missing fields to the citation mapping, or list them "
            "explicitly in `allowed_without_citation` if they are modelling choices."
        )

    if not recurse:
        return

    # Recurse into nested policy-like objects
    for field_info in fields(obj) if is_dataclass(obj) else []:
        try:
            value = getattr(obj, field_info.name)
        except Exception:
            continue

        child_path = f"{current_path}.{field_info.name}"

        for item_path, item in _iter_policy_like_children(value, child_path):
            assert_policy_has_regulatory_citations(
                item,
                citation_attr=citation_attr,
                allowed_without_citation=allowed,
                recurse=True,
                max_depth=max_depth,
                _current_path=item_path,
                _depth=_depth + 1,
            )


def _discover_numeric_fields(obj: Any) -> set[str]:
    """Return names of fields whose direct value contains numeric data.

    Nested policy objects are excluded here (they are handled via recursion).
    """
    if not is_dataclass(obj) or isinstance(obj, type):
        return set()

    numeric_names: set[str] = set()
    for f in fields(obj):
        try:
            value = getattr(obj, f.name)
            if _is_directly_numeric(value):
                numeric_names.add(f.name)
        except Exception:
            continue
    return numeric_names


def _is_directly_numeric(value: Any) -> bool:
    """True for primitive numbers or simple containers of numbers.

    Returns False for nested policy objects or other complex structures.
    """
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, (list, tuple, set)):
        if any(_is_policy_like(v) for v in value):
            return False
        return any(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value)
    if isinstance(value, Mapping):
        if any(_is_policy_like(v) for v in value.values()):
            return False
        return any(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value.values())
    return False


def _iter_policy_like_children(value: Any, path: str) -> Iterable[tuple[str, Any]]:
    if _is_policy_like(value):
        yield path, value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            if _is_policy_like(item):
                yield f"{path}[{key!r}]", item
    elif isinstance(value, (list, tuple, set)):
        for idx, item in enumerate(value):
            if _is_policy_like(item):
                yield f"{path}[{idx}]", item


def _valid_citation_keys(raw: Any) -> set[str]:
    if not isinstance(raw, Mapping):
        return set()
    return {str(key) for key, value in raw.items() if _has_citation_value(value)}


def _has_citation_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, bytes):
        return value.strip() != b""
    if isinstance(value, Iterable) and not isinstance(value, Mapping):
        return any(_has_citation_value(item) for item in value)
    return str(value).strip() != ""


def _is_policy_like(obj: Any) -> bool:
    """Heuristic to detect objects that should be recursed into for citation checks."""
    if obj is None or isinstance(obj, (str, bytes, int, float, bool)):
        return False
    if not is_dataclass(obj) or isinstance(obj, type):
        return False

    # Strong signals
    if any(hasattr(obj, attr) for attr in ("cited_by", "citations", "regulatory_citations")):
        return True

    try:
        return len(fields(obj)) >= 3
    except Exception:
        return False
