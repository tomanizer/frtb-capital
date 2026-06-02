"""Package-neutral Arrow-to-NumPy conversion helpers for handoff adapters."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Any, cast

import numpy as np
import numpy.typing as npt
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]

import frtb_common.handoff as _handoff
from frtb_common.handoff import (
    ColumnSpec,
    NullPolicy,
    TabularHandoffError,
    TabularLogicalType,
    resolve_column_name,
    validate_column_specs,
)

ErrorFactory = Callable[[str, str | None], Exception]
HandoffColumnArray = npt.NDArray[Any]


def arrow_object_array(column: pa.ChunkedArray) -> npt.NDArray[np.object_]:
    """Return a NumPy object array, preserving Arrow nulls as ``None``."""

    arrays = tuple(_object_array_from_arrow_array(chunk) for chunk in column.chunks)
    if not arrays:
        return np.empty(0, dtype=object)
    if len(arrays) == 1:
        return arrays[0]
    return np.concatenate(arrays).astype(object, copy=False)


def arrow_float64_array(
    column: pa.ChunkedArray,
    *,
    field: str,
) -> npt.NDArray[np.float64]:
    """Return a float64 NumPy view or array, casting numeric Arrow columns if needed."""

    if len(column) == 0:
        return np.empty(0, dtype=np.float64)
    array = _float64_array_from_arrow_column(column, field=field)
    try:
        return cast(npt.NDArray[np.float64], array.to_numpy(zero_copy_only=True))
    except (pa.ArrowInvalid, TypeError, ValueError):
        return np.asarray(array.to_numpy(zero_copy_only=False), dtype=np.float64)


def arrow_float64_array_with_nulls(
    column: pa.ChunkedArray,
    *,
    field: str,
    null_value: float = math.nan,
) -> npt.NDArray[np.float64]:
    """Return a float64 NumPy array after filling Arrow nulls."""

    if len(column) == 0:
        return np.empty(0, dtype=np.float64)
    array = _float64_array_from_arrow_column(column, field=field)
    if array.null_count:
        array = cast(
            pa.Array,
            pc.fill_null(array, pa.scalar(null_value, type=pa.float64())),
        )
    return np.asarray(array.to_numpy(zero_copy_only=False), dtype=np.float64)


def arrow_bool_array(
    column: pa.ChunkedArray,
    *,
    field: str,
    null_value: bool = False,
) -> npt.NDArray[np.bool_]:
    """Return a boolean NumPy array after filling Arrow nulls."""

    if len(column) == 0:
        return np.empty(0, dtype=np.bool_)
    array = _single_arrow_array(column)
    if not pa.types.is_boolean(array.type):
        try:
            array = cast(pa.Array, pc.cast(array, pa.bool_()))
        except (pa.ArrowInvalid, TypeError, ValueError) as exc:
            raise TabularHandoffError(f"{field} must be boolean") from exc
    values = pc.fill_null(array, pa.scalar(null_value, type=pa.bool_())).to_numpy(
        zero_copy_only=False
    )
    return np.asarray(values, dtype=np.bool_)


def arrow_bool_or_object_array(
    column: pa.ChunkedArray,
    *,
    null_value: bool = False,
) -> npt.NDArray[np.bool_] | npt.NDArray[np.object_]:
    """Return bool arrays for boolean Arrow columns, otherwise object arrays with nulls filled."""

    if len(column) == 0:
        return np.empty(0, dtype=np.bool_)
    array = _single_arrow_array(column)
    if pa.types.is_boolean(array.type):
        values = pc.fill_null(array, pa.scalar(null_value, type=pa.bool_())).to_numpy(
            zero_copy_only=False
        )
        return np.asarray(values, dtype=np.bool_)

    return _object_array_from_arrow_array(array, null_value=null_value)


def read_handoff_columns(
    table: pa.Table,
    specs: Sequence[ColumnSpec],
    *,
    error: ErrorFactory,
) -> dict[str, HandoffColumnArray]:
    """Read declared Arrow handoff columns into read-only NumPy arrays."""

    if not isinstance(table, pa.Table):
        raise error("table must be a pyarrow.Table", None)
    try:
        column_specs = validate_column_specs(specs)
        _handoff._validate_unique_column_names(table)
    except TabularHandoffError as exc:
        raise error(str(exc), None) from exc

    columns: dict[str, HandoffColumnArray] = {}
    for spec in column_specs:
        columns.update(_read_handoff_column(table, spec, error=error))
    return columns


def _read_handoff_column(
    table: pa.Table,
    spec: ColumnSpec,
    *,
    error: ErrorFactory,
) -> dict[str, HandoffColumnArray]:
    if spec.logical_type is TabularLogicalType.UNKNOWN:
        raise error(f"Column {spec.name!r} has unknown logical_type", spec.name)

    try:
        column_name = resolve_column_name(table, spec)
    except TabularHandoffError as exc:
        raise error(str(exc), spec.name) from exc

    if column_name is None:
        if spec.required:
            raise error(f"Required column {spec.name!r} is missing", spec.name)
        return {}

    column = table.column(column_name)
    try:
        _handoff._validate_column_policy(spec, column)
        values = _read_typed_handoff_column(column, spec)
    except (TabularHandoffError, pa.ArrowException) as exc:
        raise error(str(exc), spec.name) from exc

    values.setflags(write=False)
    return {spec.name: values}


def _read_typed_handoff_column(
    column: pa.ChunkedArray,
    spec: ColumnSpec,
) -> HandoffColumnArray:
    match spec.logical_type:
        case (
            TabularLogicalType.STRING
            | TabularLogicalType.DICTIONARY
            | TabularLogicalType.DICTIONARY_CODE
            | TabularLogicalType.INTEGER
        ):
            return arrow_object_array(column)
        case TabularLogicalType.FLOAT | TabularLogicalType.DECIMAL:
            if spec.null_policy is NullPolicy.ALLOW and column.null_count:
                return arrow_float64_array_with_nulls(column, field=spec.name)
            return arrow_float64_array(column, field=spec.name)
        case TabularLogicalType.BOOLEAN:
            return arrow_bool_array(column, field=spec.name)
        case _:
            raise TabularHandoffError(
                f"Column {spec.name!r} has unsupported logical_type {spec.logical_type.value!r}"
            )


def _single_arrow_array(column: pa.ChunkedArray) -> pa.Array:
    return column.chunk(0) if column.num_chunks == 1 else column.combine_chunks()


def _float64_array_from_arrow_column(
    column: pa.ChunkedArray,
    *,
    field: str,
) -> pa.Array:
    array = _single_arrow_array(column)
    if pa.types.is_float64(array.type):
        return array
    try:
        return cast(pa.Array, pc.cast(array, pa.float64()))
    except (pa.ArrowInvalid, TypeError, ValueError) as exc:
        raise TabularHandoffError(f"{field} must be numeric") from exc


def _object_array_from_arrow_array(
    array: pa.Array,
    *,
    null_value: object = None,
) -> npt.NDArray[np.object_]:
    if len(array) == 0:
        return np.empty(0, dtype=object)
    if pa.types.is_dictionary(array.type):
        return _dictionary_array_to_object_array(
            cast(pa.DictionaryArray, array),
            null_value=null_value,
        )
    if pa.types.is_integer(array.type):
        return _integer_array_to_object_array(array, null_value=null_value)

    values = np.asarray(array.to_numpy(zero_copy_only=False), dtype=object)
    if array.null_count:
        valid = np.asarray(array.is_valid().to_numpy(zero_copy_only=False), dtype=np.bool_)
        values[~valid] = null_value
    return values


def _integer_array_to_object_array(
    array: pa.Array,
    *,
    null_value: object = None,
) -> npt.NDArray[np.object_]:
    filled = pc.fill_null(array, pa.scalar(0, type=array.type))
    values = np.asarray(filled.to_numpy(zero_copy_only=False), dtype=object)
    if array.null_count:
        valid = np.asarray(array.is_valid().to_numpy(zero_copy_only=False), dtype=np.bool_)
        values[~valid] = null_value
    return values


def _dictionary_array_to_object_array(
    array: pa.DictionaryArray,
    *,
    null_value: object = None,
) -> npt.NDArray[np.object_]:
    if len(array) == 0:
        return np.empty(0, dtype=object)

    dictionary = np.asarray(array.dictionary.to_numpy(zero_copy_only=False), dtype=object)
    indices = np.asarray(
        pc.fill_null(array.indices, pa.scalar(0, type=array.indices.type)).to_numpy(
            zero_copy_only=False
        ),
        dtype=np.int64,
    )
    valid = np.asarray(array.is_valid().to_numpy(zero_copy_only=False), dtype=np.bool_)
    values = np.empty(len(array), dtype=object)
    values[valid] = dictionary[indices[valid]]
    values[~valid] = null_value
    return values


__all__ = [
    "arrow_bool_array",
    "arrow_bool_or_object_array",
    "arrow_float64_array",
    "arrow_float64_array_with_nulls",
    "arrow_object_array",
    "read_handoff_columns",
]
