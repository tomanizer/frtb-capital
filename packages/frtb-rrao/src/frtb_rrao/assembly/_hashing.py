"""Deterministic RRAO payload hashing helpers."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

from frtb_common import stable_json_hash


def hash_payload(payload: object) -> str:
    """
    Return the package-standard deterministic payload hash.

    Parameters
    ----------
    payload : object
        JSON-stable payload object.

    Returns
    -------
    str
        Deterministic payload hash.
    """
    return stable_json_hash(payload)


def hash_position_payloads(payloads: Iterable[dict[str, object]]) -> str:
    """
    Return the package-standard hash for normalized position payloads.

    Parameters
    ----------
    payloads : Iterable[dict[str, object]]
        Position payloads in canonical order.

    Returns
    -------
    str
        Deterministic aggregate input hash.
    """
    digest = hashlib.sha256()
    digest.update(b'{"positions":[')
    first = True
    for payload in payloads:
        if first:
            first = False
        else:
            digest.update(b",")
        digest.update(bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")), "utf-8"))
    digest.update(b"]}")
    return digest.hexdigest()
