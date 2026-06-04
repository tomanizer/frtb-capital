"""Package-local mapping helpers for immutable IMA dataclasses."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import TypeVar

K = TypeVar("K")
V = TypeVar("V")


def empty_mapping() -> Mapping[str, object]:
    """Return an immutable empty metadata mapping.
    Returns
    -------
    Mapping[str, object]
        Result of the operation.
    """

    return MappingProxyType({})


def freeze_mapping(values: Mapping[K, V]) -> Mapping[K, V]:
    """Return an immutable shallow copy of a mapping.
    Parameters
    ----------
    values : Mapping[K, V]
        Values.

    Returns
    -------
    Mapping[K, V]
        Result of the operation.
    """

    return MappingProxyType(dict(values))
