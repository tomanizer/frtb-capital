"""Package-private CVA column coercion helpers."""

from __future__ import annotations

import math
from collections.abc import Sequence, Sized
from enum import StrEnum
from typing import Any, TypeVar, cast

import frtb_common.batch_arrays as _batch_arrays
import numpy as np
import numpy.typing as npt

from frtb_cva.validation import (
    VALID_EAD_SIGN_CONVENTIONS,
    CvaInputError,
    normalise_ead_amount,
)

ObjectArray = npt.NDArray[np.object_]
FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]
ArrayInput = npt.NDArray[Any]
ColumnInput = Sequence[object] | ArrayInput
NullableColumnInput = Sequence[object | None] | ArrayInput
EnumT = TypeVar("EnumT", bound=StrEnum)


def _require_lengths(row_count: int, **columns: Sized) -> None:
    for name, values in columns.items():
        if len(values) != row_count:
            raise CvaInputError(f"{name} length does not match ids", field=name)


def _require_optional_lengths(row_count: int, **columns: Sized | None) -> None:
    for name, values in columns.items():
        if values is not None and len(values) != row_count:
            raise CvaInputError(f"{name} length does not match ids", field=name)


def _required_text_array(values: ColumnInput, field: str, *, copy: bool) -> ObjectArray:
    return _batch_arrays.object_array([_required_text(value, field) for value in values], copy=copy)


def _optional_text_array(
    values: NullableColumnInput | None,
    row_count: int,
    *,
    copy: bool,
) -> ObjectArray:
    return _batch_arrays.optional_text_array(
        values,
        row_count,
        copy=copy,
        optional_text=_optional_text,
    )


def _enum_array(
    values: ColumnInput,
    enum_type: type[EnumT],
    field: str,
    *,
    copy: bool,
) -> ObjectArray:
    try:
        return _batch_arrays.enum_array(
            values,
            enum_type,
            field,
            copy=copy,
            required_text=_required_text,
            invalid_message=_invalid_enum_message,
        )
    except _batch_arrays.BatchArrayCoercionError as exc:
        raise CvaInputError(str(exc), field=exc.field or field) from exc


def _optional_enum_array(
    values: NullableColumnInput | None,
    row_count: int,
    enum_type: type[EnumT],
    field: str,
    *,
    copy: bool,
) -> ObjectArray:
    try:
        return _batch_arrays.nullable_enum_array(
            values,
            enum_type,
            field,
            row_count,
            copy=copy,
            optional_text=_optional_enum_text,
            required_text=_required_text,
            invalid_message=_invalid_enum_message,
        )
    except _batch_arrays.BatchArrayCoercionError as exc:
        raise CvaInputError(str(exc), field=exc.field or field) from exc


def _float_array(values: ColumnInput, field: str, *, copy: bool) -> FloatArray:
    fast_array = _float_array_from_numpy(values, field=field, copy=copy, allow_nan=False)
    if fast_array is not None:
        return fast_array
    array = np.asarray([_finite_float(value, field) for value in values], dtype=np.float64)
    return _batch_arrays.readonly_array(array, copy=copy)


def _normalised_ead_array(
    eads: FloatArray,
    sign_conventions: ObjectArray,
    *,
    record_ids: ObjectArray,
) -> FloatArray:
    normalised = np.empty_like(eads, dtype=np.float64)
    for index in range(eads.shape[0]):
        record_id = cast(str, record_ids[index])
        sign_convention = cast(str, sign_conventions[index])
        if sign_convention not in VALID_EAD_SIGN_CONVENTIONS:
            raise CvaInputError(
                f"sign_convention must be one of {sorted(VALID_EAD_SIGN_CONVENTIONS)}",
                field="sign_convention",
                record_id=record_id,
            )
        normalised[index] = normalise_ead_amount(
            float(eads[index]),
            source_sign_convention=sign_convention,  # type: ignore[arg-type]
        )
    normalised.setflags(write=False)
    return normalised


def _optional_float_array(
    values: NullableColumnInput | None,
    row_count: int,
    *,
    copy: bool,
) -> FloatArray:
    try:
        return _batch_arrays.optional_float_array(
            values,
            row_count,
            copy=copy,
            optional_float=_optional_float,
        )
    except _batch_arrays.BatchArrayCoercionError as exc:
        raise CvaInputError(str(exc), field=exc.field or "optional numeric field") from exc


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
        raise CvaInputError(str(exc)) from exc


def _float_array_from_numpy(
    values: ColumnInput | NullableColumnInput,
    *,
    field: str,
    copy: bool,
    allow_nan: bool,
) -> FloatArray | None:
    try:
        return _batch_arrays.float_array_from_numpy(
            values,
            field=field,
            copy=copy,
            allow_nan=allow_nan,
        )
    except _batch_arrays.BatchArrayCoercionError as exc:
        raise CvaInputError(str(exc), field=exc.field or field) from exc


def _required_text(value: object, field: str, record_id: str = "") -> str:
    if not isinstance(value, str) or not value.strip():
        raise CvaInputError("non-empty text is required", field=field, record_id=record_id)
    return value


def _optional_text(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return _required_text(value, "optional text field")


def _optional_enum_text(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, (float, np.floating)) and math.isnan(float(value)):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return str(value)


def _invalid_enum_message(field: str, _value: str) -> str:
    return f"invalid {field}"


def _finite_float(value: object, field: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value,
        (int, float, np.integer, np.floating),
    ):
        raise CvaInputError("value must be numeric", field=field)
    number = float(value)
    if not math.isfinite(number):
        raise CvaInputError("value must be finite", field=field)
    return number


def _optional_float(value: object | None) -> float:
    if value is None:
        return math.nan
    if isinstance(value, (float, np.floating)) and math.isnan(float(value)):
        return math.nan
    if isinstance(value, str) and not value.strip():
        return math.nan
    return _finite_float(value, "optional numeric field")


def _optional_float_value(value: object) -> float | None:
    if isinstance(value, (int, float, np.integer, np.floating)):
        raw = float(value)
        if math.isnan(raw):
            return None
    number = _finite_float(value, "optional numeric field")
    if math.isnan(number):
        return None
    return number


def _require_unique(values: ObjectArray, *, field: str) -> None:
    seen: set[str] = set()
    for value in values:
        text = cast(str, value)
        if text in seen:
            raise CvaInputError(f"duplicate {field.replace('_', ' ')}", field=field, record_id=text)
        seen.add(text)


def _freeze_source_column_maps(
    values: Sequence[Sequence[tuple[str, str]]] | None,
    row_count: int,
) -> tuple[tuple[tuple[str, str], ...], ...]:
    return _batch_arrays.freeze_source_column_maps(
        values,
        row_count,
        source_text=lambda value: _required_text(value, "lineage.source_column_map.source"),
        target_text=lambda value: _required_text(value, "lineage.source_column_map.canonical"),
    )


def _default_text_sequence(
    values: ColumnInput | None,
    row_count: int,
    default: str,
) -> ColumnInput:
    if values is not None:
        return values
    return [default] * row_count
