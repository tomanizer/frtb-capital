"""Shared deterministic hashing helpers for package-neutral payloads."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from frtb_common.serialization import jsonable

_SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def stable_json_dumps(payload: Any) -> str:
    """Return a deterministic compact JSON representation of *payload*."""

    return json.dumps(jsonable(payload), sort_keys=True, separators=(",", ":"))


def stable_json_hash(payload: Any) -> str:
    """Return a SHA-256 digest for a deterministic JSON payload encoding."""

    return hashlib.sha256(bytes(stable_json_dumps(payload), "utf-8")).hexdigest()


def is_sha256_hex(value: object) -> bool:
    """Return whether *value* is a lowercase SHA-256 hex digest."""

    return isinstance(value, str) and _SHA256_HEX_PATTERN.fullmatch(value) is not None


def require_sha256_hex(value: object, *, field: str = "hash") -> str:
    """Return *value* as text when it is a lowercase SHA-256 hex digest."""

    if not isinstance(value, str) or _SHA256_HEX_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field} must be a sha256 hex digest")
    return value


__all__ = [
    "is_sha256_hex",
    "require_sha256_hex",
    "stable_json_dumps",
    "stable_json_hash",
]
