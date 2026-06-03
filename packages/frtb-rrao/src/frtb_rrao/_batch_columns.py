"""Package-private RRAO column coercion helpers."""

from __future__ import annotations

import math
from collections.abc import Sequence
from enum import StrEnum
from typing import Any, TypeVar, cast

import frtb_common.batch_arrays as _batch_arrays
import numpy as np
import numpy.typing as npt

from frtb_rrao.validation import RraoInputError

ObjectArray = npt.NDArray[np.object_]
FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]
ArrayInput = npt.NDArray[Any]
ColumnInput = Sequence[object] | ArrayInput
NullableColumnInput = Sequence[object | None] | ArrayInput
EnumT = TypeVar("EnumT", bound=StrEnum)


def _require_lengths(row_count: int, **columns: ColumnInput) -> None:
    for name, values in columns.items():
        if len(values) != row_count:
            raise RraoInputError(f"{name} length does not match position_ids", field=name)


def _require_unique(values: ObjectArray) -> None:
    unique_values, counts = np.unique(values, return_counts=True)
    duplicate_mask = counts > 1
    if bool(np.any(duplicate_mask)):
        duplicate = str(unique_values[np.nonzero(duplicate_mask)[0][0]])
        raise RraoInputError(
            "duplicate position id",
            field="position_id",
            position_id=duplicate,
        )


def _required_text_array(
    values: NullableColumnInput,
    field_name: str,
    *,
    copy: bool,
) -> ObjectArray:
    return _batch_arrays.object_array(
        [_required_text(value, field_name) for value in values],
        copy=copy,
    )


def _optional_text_array(
    values: NullableColumnInput | None,
    row_count: int,
    *,
    copy: bool,
) -> ObjectArray:
    if values is None:
        return _batch_arrays.object_array([None] * row_count, copy=copy)
    return _batch_arrays.object_array([_optional_text(value) for value in values], copy=copy)


def _text_array_with_default(
    values: ColumnInput | None,
    row_count: int,
    *,
    default: str,
    copy: bool,
) -> ObjectArray:
    if values is None:
        return _batch_arrays.object_array([default] * row_count, copy=copy)
    return _batch_arrays.object_array(
        [_optional_text(value) or default for value in values],
        copy=copy,
    )


def _enum_array(
    values: NullableColumnInput,
    enum_type: type[EnumT],
    field_name: str,
    *,
    copy: bool,
) -> ObjectArray:
    return _batch_arrays.object_array(
        [_coerce_enum_value(value, enum_type, field_name) for value in values],
        copy=copy,
    )


def _optional_enum_array(
    values: NullableColumnInput | None,
    row_count: int,
    enum_type: type[EnumT],
    field_name: str,
    *,
    copy: bool,
) -> ObjectArray:
    if values is None:
        return _batch_arrays.object_array([None] * row_count, copy=copy)
    return _batch_arrays.object_array(
        [
            None
            if _optional_text(value) is None
            else _coerce_enum_value(value, enum_type, field_name)
            for value in values
        ],
        copy=copy,
    )


def _required_float_array(
    values: ColumnInput,
    field_name: str,
    *,
    copy: bool,
) -> FloatArray:
    fast_array = _float_array_from_numpy(values, copy=copy)
    if fast_array is not None:
        return fast_array
    array = np.asarray([_required_float(value, field_name) for value in values], dtype=np.float64)
    return _batch_arrays.readonly_array(array, copy=copy)


def _optional_float_array(
    values: NullableColumnInput | None,
    row_count: int,
    *,
    copy: bool,
) -> FloatArray:
    if values is None:
        array = np.full(row_count, np.nan, dtype=np.float64)
    elif (fast_array := _float_array_from_numpy(values, copy=copy)) is not None:
        return fast_array
    else:
        array = np.asarray([_optional_float(value) for value in values], dtype=np.float64)
    return _batch_arrays.readonly_array(array, copy=copy)


def _optional_int_array(
    values: NullableColumnInput | None,
    row_count: int,
    *,
    copy: bool,
) -> ObjectArray:
    if values is None:
        return _batch_arrays.object_array([None] * row_count, copy=copy)
    return _batch_arrays.object_array([_optional_int(value) for value in values], copy=copy)


def _bool_array(
    values: ColumnInput | None,
    row_count: int,
    *,
    default: bool,
    copy: bool,
) -> BoolArray:
    try:
        return _batch_arrays.bool_array(values, row_count, default=default, copy=copy)
    except _batch_arrays.BatchArrayCoercionError as exc:
        raise RraoInputError(str(exc)) from exc


def _optional_bool_object_array(
    values: NullableColumnInput | None,
    row_count: int,
    *,
    copy: bool,
) -> ObjectArray:
    try:
        return _batch_arrays.optional_bool_object_array(values, row_count, copy=copy)
    except _batch_arrays.BatchArrayCoercionError as exc:
        raise RraoInputError(str(exc)) from exc


def _float_array_from_numpy(
    values: ColumnInput | NullableColumnInput,
    *,
    copy: bool,
) -> FloatArray | None:
    try:
        return _batch_arrays.float_array_from_numpy(
            values,
            field="numeric field",
            copy=copy,
            allow_nan=True,
            require_1d=False,
            require_finite=False,
        )
    except _batch_arrays.BatchArrayCoercionError as exc:
        raise RraoInputError(str(exc)) from exc


def _required_text(value: object | None, field_name: str) -> str:
    text = _optional_text(value)
    if text is None:
        raise RraoInputError("non-empty text is required", field=field_name)
    return text


def _optional_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _required_float(value: object, field_name: str) -> float:
    if value is None:
        raise RraoInputError("value must be numeric", field=field_name)
    try:
        number = float(cast(Any, value))
    except (TypeError, ValueError) as exc:
        raise RraoInputError("value must be numeric", field=field_name) from exc
    if not math.isfinite(number):
        raise RraoInputError("value must be finite", field=field_name)
    return number


def _optional_float(value: object | None) -> float:
    if value is None:
        return math.nan
    if isinstance(value, float) and math.isnan(value):
        return math.nan
    if isinstance(value, str) and not value.strip():
        return math.nan
    return _required_float(value, "optional numeric field")


def _optional_int(value: object | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    if isinstance(value, (bool, np.bool_)):
        raise RraoInputError("underlying count must be an integer", field="underlying_count")
    if isinstance(value, (int, np.integer)):
        if value < 0:
            raise RraoInputError(
                "underlying count must be non-negative",
                field="underlying_count",
            )
        return int(value)
    raise RraoInputError("underlying count must be an integer", field="underlying_count")


def _coerce_enum_value(
    value: object | None,
    enum_type: type[EnumT],
    field_name: str,
) -> str:
    text = _required_text(value, field_name)
    try:
        return enum_type(text).value
    except ValueError as exc:
        raise RraoInputError(f"invalid {field_name}", field=field_name) from exc


def _freeze_source_column_maps(
    values: Sequence[Sequence[tuple[str, str]]] | None,
    row_count: int,
) -> tuple[tuple[tuple[str, str], ...], ...]:
    if values is None:
        return tuple(() for _ in range(row_count))
    frozen: list[tuple[tuple[str, str], ...]] = []
    for row in values:
        pairs: list[tuple[str, str]] = []
        for source, target in row:
            pairs.append(
                (
                    _required_text(source, "lineage.source_column_map.source"),
                    _required_text(target, "lineage.source_column_map.canonical"),
                )
            )
        frozen.append(tuple(pairs))
    return tuple(frozen)


def _freeze_citations(
    values: Sequence[Sequence[str]] | None,
    row_count: int,
) -> tuple[tuple[str, ...], ...]:
    if values is None:
        return tuple(() for _ in range(row_count))
    frozen: list[tuple[str, ...]] = []
    for row in values:
        citations: list[str] = []
        for item in row:
            if not isinstance(item, str):
                raise RraoInputError("non-empty text is required", field="citations")
            citation = item.strip()
            if citation == "":
                raise RraoInputError("non-empty text is required", field="citations")
            citations.append(citation)
        frozen.append(tuple(citations))
    return tuple(frozen)
