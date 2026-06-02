"""Package-neutral Arrow-to-NumPy conversion helpers for handoff adapters."""

from __future__ import annotations

import math
from typing import cast

import numpy as np
import numpy.typing as npt
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]

from frtb_common.handoff import TabularHandoffError


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
]
