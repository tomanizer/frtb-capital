"""Shared JSON serialisation utilities for the frtb-capital suite."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from types import TracebackType
from typing import Any


def jsonable(value: Any) -> object:
    """Recursively coerce *value* into a JSON-serialisable object.

    Handles common domain types (enums, dates, dataclasses with ``as_dict``,
    exceptions) and falls back to ``str`` for anything else that ``json.dumps``
    cannot handle.

    Parameters
    ----------
    value : Any
        Scalar, mapping, sequence, dataclass, enum, date, or exception to encode.

    Returns
    -------
    object
        JSON-compatible structure of dicts, lists, strings, numbers, and booleans.
    """
    if hasattr(value, "as_dict") and callable(value.as_dict):
        return jsonable(value.as_dict())
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [jsonable(item) for item in value]
    if isinstance(value, BaseException):
        return repr(value)
    if isinstance(value, TracebackType):
        return repr(value)
    try:
        json.dumps(value)
    except TypeError:
        return str(value)
    return value


def dataclass_as_dict(value: Any) -> dict[str, object]:
    """Return dataclass fields as a JSON-compatible dictionary.

    Parameters
    ----------
    value : Any
        Dataclass instance whose fields should be serialized.

    Returns
    -------
    dict[str, object]
        Dataclass field names mapped through :func:`jsonable`.

    Raises
    ------
    TypeError
        If *value* is not a dataclass instance.
    """
    if not is_dataclass(value) or isinstance(value, type):
        raise TypeError("dataclass_as_dict requires a dataclass instance")
    return {field.name: jsonable(getattr(value, field.name)) for field in fields(value)}
