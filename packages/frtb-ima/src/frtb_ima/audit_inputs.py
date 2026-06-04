"""
Canonical input hashing for audit-record traceability.

The helper in this module computes a stable digest over the desk-run inputs that
feed capital calculations. It serialises structured Python objects and numpy
arrays into a canonical JSON payload before hashing; it does not persist input
data or perform replay.

Regulatory traceability:
    Supports input lineage and reproducibility controls for Basel MAR31-MAR33,
    U.S. NPR 2.0 model-risk governance expectations, and EU CRR internal-model
    governance. See docs/REGULATORY_TRACEABILITY.md.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np


def compute_inputs_hash(**inputs: object) -> str:
    """Return a SHA-256 digest over canonicalised calculation inputs.

    Parameters
    ----------
    **inputs : object
        Named calculation inputs serialised in sorted key order.

    Returns
    -------
    str
        Lowercase SHA-256 hex digest of the canonical payload.
    """
    payload = {
        "schema_version": "frtb_ima_inputs_hash_v1",
        "inputs": {key: _canonical_input(inputs[key]) for key in sorted(inputs)},
    }
    serialised = json.dumps(
        payload,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(bytes(f"{serialised}\n", "utf-8")).hexdigest()


def _canonical_input(value: Any) -> object:
    if isinstance(value, np.ndarray):
        return _canonical_array(value)
    if isinstance(value, np.generic):
        return _canonical_input(value.item())
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping | MappingProxyType):
        return {
            str(key): _canonical_input(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _canonical_input(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, tuple | list):
        return [_canonical_input(item) for item in value]
    if isinstance(value, set | frozenset):
        canonical_items = [_canonical_input(item) for item in value]
        return sorted(
            canonical_items,
            key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")),
        )
    if isinstance(value, bytes):
        return {"type": "bytes", "sha256": hashlib.sha256(value).hexdigest()}
    if isinstance(value, str | int | bool) or value is None:
        return value
    if isinstance(value, float):
        if not np.isfinite(value):
            raise ValueError("input hash cannot serialise non-finite floats")
        return value
    raise TypeError(f"unsupported input hash value type: {type(value).__name__}")


def _canonical_array(value: np.ndarray) -> dict[str, object]:
    if value.dtype.hasobject:
        raise TypeError("input hash cannot serialise object-dtype arrays")
    if value.dtype.kind in {"f", "c"} and not np.all(np.isfinite(value)):
        raise ValueError("input hash cannot serialise non-finite arrays")
    return {
        "type": "ndarray",
        "dtype": value.dtype.str,
        "shape": list(value.shape),
        "values": _canonical_array_values(value),
    }


def _canonical_array_values(value: np.ndarray) -> object:
    if value.dtype.kind in {"S", "U", "b", "i", "u", "f"}:
        return _canonical_input(value.tolist())
    if value.dtype.kind == "M":
        return _canonical_input(value.astype("datetime64[ns]").astype(str).tolist())
    return {
        "encoding": "raw-bytes",
        "sha256": hashlib.sha256(np.ascontiguousarray(value).tobytes()).hexdigest(),
    }
