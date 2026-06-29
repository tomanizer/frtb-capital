"""Deterministic hashing helpers for v1 IMA mapping-spec adapters."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping


def stable_mapping_hash(payload: Mapping[str, object]) -> str:
    """Return a deterministic SHA-256 hash for mapping provenance payloads.

    Parameters
    ----------
    payload : Mapping[str, object]
        JSON-serializable provenance payload to hash with stable key ordering.

    Returns
    -------
    str
        Hex-encoded SHA-256 digest for the normalized payload.
    """

    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(data).hexdigest()
