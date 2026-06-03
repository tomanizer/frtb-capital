"""Shared row-codec primitives for the Parquet result store."""

from __future__ import annotations

import json
from collections.abc import Mapping
from enum import StrEnum

from frtb_common.hashing import stable_json_dumps

from frtb_result_store.model import ResultStoreContractError

__all__ = [
    "float_value",
    "int_value",
    "json_mapping",
    "json_text_tuple",
    "metadata_json",
    "optional_float",
    "optional_text",
    "stored_value",
]


def metadata_json(metadata: Mapping[str, object]) -> str:
    return str(stable_json_dumps(dict(metadata)))


def json_mapping(value: object) -> Mapping[str, object]:
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ResultStoreContractError(f"malformed JSON object: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ResultStoreContractError("JSON field must decode to an object")
    return parsed


def json_text_tuple(value: object) -> tuple[str, ...]:
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ResultStoreContractError(f"malformed JSON text list: {exc}") from exc
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ResultStoreContractError("JSON field must decode to a list of strings")
    return tuple(parsed)


def optional_text(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float_value(value)


def float_value(value: object) -> float:
    if isinstance(value, bool):
        raise ResultStoreContractError("numeric field must not be boolean")
    if isinstance(value, int | float | str):
        try:
            return float(value)
        except ValueError as exc:
            raise ResultStoreContractError(f"invalid numeric value: {value}") from exc
    raise ResultStoreContractError("numeric field must be int, float, or numeric text")


def int_value(value: object) -> int:
    if isinstance(value, bool):
        raise ResultStoreContractError("integer field must not be boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise ResultStoreContractError(f"invalid integer value: {value}") from exc
    raise ResultStoreContractError("integer field must be int or integer text")


def stored_value(value: StrEnum | str) -> str:
    if isinstance(value, StrEnum):
        return value.value
    return value
