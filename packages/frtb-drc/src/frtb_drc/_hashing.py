"""Package-local deterministic hashing helpers for DRC payload contracts."""

from __future__ import annotations

from typing import Any

from frtb_common import stable_json_hash


def hash_payload(payload: Any) -> str:
    """Return the stable SHA-256 JSON hash used by DRC audit contracts.
    Parameters
    ----------
    payload : Any
        Canonical payload to hash deterministically.

    Returns
    -------
    str
        Result of the operation.
    """

    return stable_json_hash(payload)


__all__ = ["hash_payload"]
