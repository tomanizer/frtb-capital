"""Package-local mapping helpers for immutable IMA dataclasses."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import TypeVar

K = TypeVar("K")
V = TypeVar("V")


def empty_mapping() -> Mapping[str, object]:
    """Return an immutable empty metadata mapping."""

    return MappingProxyType({})


def freeze_mapping(values: Mapping[K, V]) -> Mapping[K, V]:
    """Return an immutable shallow copy of a mapping."""

    return MappingProxyType(dict(values))
