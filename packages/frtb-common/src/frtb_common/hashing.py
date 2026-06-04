"""Shared deterministic hashing helpers for package-neutral payloads."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from frtb_common.serialization import jsonable

_SHA256_HEX_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def stable_json_dumps(payload: Any) -> str:
    """Return a deterministic compact JSON representation of *payload*.

    Parameters
    ----------
    payload : Any
        Value tree passed through :func:`frtb_common.serialization.jsonable`.

    Returns
    -------
    str
        Sorted-keys JSON text with compact separators.
    """

    return json.dumps(jsonable(payload), sort_keys=True, separators=(",", ":"))


def stable_json_hash(payload: Any) -> str:
    """Return a SHA-256 digest for a deterministic JSON payload encoding.

    Parameters
    ----------
    payload : Any
        Value tree hashed via :func:`stable_json_dumps`.

    Returns
    -------
    str
        Lowercase SHA-256 hex digest of the canonical JSON bytes.
    """

    return hashlib.sha256(bytes(stable_json_dumps(payload), "utf-8")).hexdigest()


def is_sha256_hex(value: object) -> bool:
    """Return whether *value* is a lowercase SHA-256 hex digest.

    Parameters
    ----------
    value : object
        Candidate digest text.

    Returns
    -------
    bool
        ``True`` when *value* is a 64-character lowercase hex string.
    """

    return isinstance(value, str) and _SHA256_HEX_PATTERN.fullmatch(value) is not None


def require_sha256_hex(value: object, *, field: str = "hash") -> str:
    """Return *value* as text when it is a lowercase SHA-256 hex digest.

    Parameters
    ----------
    value : object
        Candidate digest text.
    field : str, optional
        Label used in validation errors (default ``"hash"``).

    Returns
    -------
    str
        The validated digest string.

    Raises
    ------
    ValueError
        When *value* is not a lowercase SHA-256 hex digest.
    """

    if not isinstance(value, str) or _SHA256_HEX_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{field} must be a sha256 hex digest")
    return value


__all__ = [
    "is_sha256_hex",
    "require_sha256_hex",
    "stable_json_dumps",
    "stable_json_hash",
]
