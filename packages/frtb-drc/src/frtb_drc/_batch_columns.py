"""Package-private DRC column coercion helpers."""

from __future__ import annotations

import math
from collections.abc import Sequence
from enum import StrEnum
from typing import Any, TypeVar, cast

import frtb_common.batch_arrays as _batch_arrays
import numpy as np
import numpy.typing as npt

from frtb_drc._validation_utils import optional_text as _optional_text
from frtb_drc._validation_utils import require_text as _required_text
from frtb_drc.validation import DrcInputError

ObjectArray = npt.NDArray[np.object_]
FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]
ArrayInput = npt.NDArray[Any]
ColumnInput = Sequence[object] | ArrayInput
NullableColumnInput = Sequence[object | None] | ArrayInput
EnumT = TypeVar("EnumT", bound=StrEnum)


def _require_lengths(row_count: int, **columns: ColumnInput | NullableColumnInput) -> None:
    for name, values in columns.items():
        if len(values) != row_count:
            raise DrcInputError(f"{name} length does not match position_ids")


def _required_text_array(
    values: NullableColumnInput, field_name: str, *, copy: bool
) -> ObjectArray:
    array = _batch_arrays.object_array(
        [_required_text(value, field_name) for value in values],
        copy=copy,
    )
    return array


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


def _nullable_enum_array(
    values: NullableColumnInput | None,
    enum_type: type[EnumT],
    field_name: str,
    row_count: int,
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


def _required_float_array(values: ColumnInput, field_name: str, *, copy: bool) -> FloatArray:
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


def _bool_array(
    values: ColumnInput | None,
    row_count: int,
    *,
    default: bool = False,
    copy: bool,
) -> BoolArray:
    try:
        return _batch_arrays.bool_array(values, row_count, default=default, copy=copy)
    except _batch_arrays.BatchArrayCoercionError as exc:
        raise DrcInputError(str(exc)) from exc


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
        raise DrcInputError(str(exc)) from exc


def _required_float(value: object, field_name: str) -> float:
    if value is None:
        raise DrcInputError(f"{field_name} must be provided")
    try:
        number = float(cast(Any, value))
    except (TypeError, ValueError) as exc:
        raise DrcInputError(f"{field_name} must be numeric") from exc
    if not math.isfinite(number):
        raise DrcInputError(f"{field_name} must be finite")
    return number


def _optional_float(value: object | None) -> float:
    if value is None:
        return math.nan
    if isinstance(value, float) and math.isnan(value):
        return math.nan
    if isinstance(value, str) and not value.strip():
        return math.nan
    return _required_float(value, "optional numeric field")


def _coerce_enum_value(
    value: object | None,
    enum_type: type[EnumT],
    field_name: str,
) -> str:
    text = _required_text(value, field_name)
    try:
        return enum_type(text).value
    except ValueError as exc:
        raise DrcInputError(f"{field_name} contains unsupported value: {text}") from exc


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
            pairs.append((str(source), str(target)))
        frozen.append(tuple(sorted(pairs)))
    return tuple(frozen)


def _freeze_citation_ids(
    values: Sequence[Sequence[str]] | None,
    row_count: int,
) -> tuple[tuple[str, ...], ...]:
    if values is None:
        return tuple(("US_NPR_210_SCOPE",) for _ in range(row_count))
    frozen: list[tuple[str, ...]] = []
    for row in values:
        citations: list[str] = []
        for item in row:
            if not isinstance(item, str):
                raise DrcInputError("citation_ids must contain non-empty citations")
            citation_id = item.strip()
            if citation_id == "":
                raise DrcInputError("citation_ids must contain non-empty citations")
            citations.append(citation_id)
        if not citations:
            raise DrcInputError("citation_ids must contain at least one citation")
        frozen.append(tuple(citations))
    return tuple(frozen)
