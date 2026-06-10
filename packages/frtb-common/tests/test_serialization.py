"""Tests for frtb_common.serialization.jsonable."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum, StrEnum

import pytest
from frtb_common.serialization import dataclass_as_dict, jsonable


class _Color(Enum):
    RED = "red"


class _Status(StrEnum):
    OPEN = "open"


@dataclass(frozen=True)
class _ExampleRecord:
    name: str
    color: _Color
    dates: tuple[date, ...]


def _round_trip(value: object) -> object:
    """Assert the result is JSON-serialisable and return it."""
    result = jsonable(value)
    json.dumps(result)  # must not raise
    return result


def test_primitives_pass_through() -> None:
    assert jsonable(42) == 42
    assert jsonable(3.14) == 3.14
    assert jsonable("hello") == "hello"
    assert jsonable(True) is True
    assert jsonable(None) is None


def test_enum_returns_value() -> None:
    assert jsonable(_Color.RED) == "red"
    assert jsonable(_Status.OPEN) == "open"


def test_date_returns_isoformat() -> None:
    assert jsonable(date(2024, 1, 15)) == "2024-01-15"


def test_datetime_returns_isoformat() -> None:
    assert jsonable(datetime(2024, 1, 15, 10, 30, 0)) == "2024-01-15T10:30:00"


def test_mapping_is_converted_recursively() -> None:
    result = _round_trip({"a": _Color.RED, "b": date(2023, 6, 1)})
    assert result == {"a": "red", "b": "2023-06-01"}


def test_list_is_converted_recursively() -> None:
    result = _round_trip([_Color.RED, date(2023, 6, 1)])
    assert result == ["red", "2023-06-01"]


def test_tuple_is_converted_to_list() -> None:
    result = _round_trip((_Color.RED,))
    assert result == ["red"]


def test_exception_returns_repr() -> None:
    exc = ValueError("oops")
    result = jsonable(exc)
    assert isinstance(result, str)
    assert "ValueError" in result


def test_non_serialisable_falls_back_to_str() -> None:
    class _Opaque:
        def __str__(self) -> str:
            return "opaque-value"

    result = jsonable(_Opaque())
    assert result == "opaque-value"


def test_object_with_as_dict_is_unwrapped() -> None:
    class _HasAsDict:
        def as_dict(self) -> dict[str, object]:
            return {"x": 1, "color": _Color.RED}

    result = _round_trip(_HasAsDict())
    assert result == {"x": 1, "color": "red"}


def test_nested_mapping_keys_are_coerced_to_str() -> None:
    result = _round_trip({1: "one", 2: "two"})
    assert result == {"1": "one", "2": "two"}


def test_jsonable_is_exported_from_top_level_package() -> None:
    from frtb_common import jsonable as top_level_jsonable

    assert top_level_jsonable is jsonable


def test_dataclass_as_dict_serializes_fields_with_jsonable_values() -> None:
    record = _ExampleRecord("example", _Color.RED, (date(2024, 1, 15),))

    assert dataclass_as_dict(record) == {
        "name": "example",
        "color": "red",
        "dates": ["2024-01-15"],
    }


def test_dataclass_as_dict_rejects_non_dataclass_instances() -> None:
    with pytest.raises(TypeError, match="dataclass instance"):
        dataclass_as_dict({"name": "not-a-dataclass"})


def test_dataclass_as_dict_is_exported_from_top_level_package() -> None:
    from frtb_common import dataclass_as_dict as top_level_dataclass_as_dict

    assert top_level_dataclass_as_dict is dataclass_as_dict
