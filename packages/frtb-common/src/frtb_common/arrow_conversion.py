"""Package-neutral Arrow-to-NumPy conversion helpers for Arrow adapters."""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from typing import Any, cast

import numpy as np
import numpy.typing as npt
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]

import frtb_common.arrow_table as _arrow_table
from frtb_common.arrow_table import (
    ColumnSpec,
    NormalizedTableError,
    NullPolicy,
    TabularLogicalType,
    resolve_column_name,
    validate_column_specs,
)

ErrorFactory = Callable[[str, str | None], Exception]
ArrowColumnArray = npt.NDArray[Any]


def arrow_object_array(column: pa.ChunkedArray) -> npt.NDArray[np.object_]:
    """Return a NumPy object array, preserving Arrow nulls as ``None``.

    Parameters
    ----------
    column : pyarrow.ChunkedArray
        Arrow column to materialise, including dictionary-encoded chunks.

    Returns
    -------
    ndarray
        One-dimensional object array with Arrow nulls mapped to ``None``.
    """

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
    """Return a float64 NumPy view or array, casting numeric Arrow columns if needed.

    Parameters
    ----------
    column : pyarrow.ChunkedArray
        Numeric Arrow column to convert.
    field : str
        Column label used in validation errors.

    Returns
    -------
    ndarray
        One-dimensional float64 array; empty columns return a zero-length array.
    """

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
    """Return a float64 NumPy array after filling Arrow nulls.

    Parameters
    ----------
    column : pyarrow.ChunkedArray
        Numeric Arrow column to convert.
    field : str
        Column label used in validation errors.
    null_value : float, optional
        Replacement for Arrow nulls (default ``math.nan``).

    Returns
    -------
    ndarray
        One-dimensional float64 array with nulls filled.
    """

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
    """Return a boolean NumPy array after filling Arrow nulls.

    Parameters
    ----------
    column : pyarrow.ChunkedArray
        Boolean Arrow column to convert.
    field : str
        Column label used in validation errors.
    null_value : bool, optional
        Replacement for Arrow nulls (default ``False``).

    Returns
    -------
    ndarray
        One-dimensional boolean array with nulls filled.
    """

    if len(column) == 0:
        return np.empty(0, dtype=np.bool_)
    array = _single_arrow_array(column)
    if not pa.types.is_boolean(array.type):
        try:
            array = cast(pa.Array, pc.cast(array, pa.bool_()))
        except (pa.ArrowInvalid, TypeError, ValueError) as exc:
            raise NormalizedTableError(f"{field} must be boolean") from exc
    values = pc.fill_null(array, pa.scalar(null_value, type=pa.bool_())).to_numpy(
        zero_copy_only=False
    )
    return np.asarray(values, dtype=np.bool_)


def arrow_bool_or_object_array(
    column: pa.ChunkedArray,
    *,
    null_value: bool = False,
) -> npt.NDArray[np.bool_] | npt.NDArray[np.object_]:
    """Return bool arrays for boolean Arrow columns, otherwise object arrays with nulls filled.

    Parameters
    ----------
    column : pyarrow.ChunkedArray
        Arrow column to materialise.
    null_value : bool, optional
        Replacement for Arrow nulls on boolean columns (default ``False``).

    Returns
    -------
    ndarray
        Boolean array for boolean Arrow types; otherwise an object array.
    """

    if len(column) == 0:
        return np.empty(0, dtype=np.bool_)
    array = _single_arrow_array(column)
    if pa.types.is_boolean(array.type):
        values = pc.fill_null(array, pa.scalar(null_value, type=pa.bool_())).to_numpy(
            zero_copy_only=False
        )
        return np.asarray(values, dtype=np.bool_)

    return _object_array_from_arrow_array(array, null_value=null_value)


def read_arrow_columns(
    table: pa.Table,
    specs: Sequence[ColumnSpec],
    *,
    error: ErrorFactory,
    null_defaults: Mapping[str, object] | None = None,
) -> dict[str, ArrowColumnArray]:
    """Read declared Arrow columns into read-only NumPy arrays.

    ``null_defaults`` restores originally-null Arrow positions to package-specific values.

    Parameters
    ----------
    table : pyarrow.Table
        Source Arrow table.
    specs : sequence of ColumnSpec
        Declared column contracts to read and validate.
    error : callable
        Factory ``(message, column) -> Exception`` used for adapter errors.
    null_defaults : mapping, optional
        Map of canonical column names to values restored at originally-null positions.

    Returns
    -------
    dict[str, ndarray]
        Canonical column names mapped to read-only NumPy arrays.
    """

    if not isinstance(table, pa.Table):
        raise error("table must be a pyarrow.Table", None)
    try:
        column_specs = validate_column_specs(specs)
        _arrow_table._validate_unique_column_names(table)
    except NormalizedTableError as exc:
        raise error(str(exc), None) from exc

    columns: dict[str, ArrowColumnArray] = {}
    for spec in column_specs:
        columns.update(_read_arrow_column(table, spec, error=error))
    if null_defaults:
        columns = _restore_null_defaults(
            table,
            column_specs,
            columns,
            null_defaults,
            error=error,
        )
    return columns


def unique_non_null_text_values(table: pa.Table, column_name: str) -> tuple[str, ...]:
    """Return distinct non-null Arrow column values as strings.

    Parameters
    ----------
    table : pyarrow.Table
        Source Arrow table.
    column_name : str
        Canonical column name to inspect.

    Returns
    -------
    tuple of str
        Distinct non-null values in Arrow's stable unique order.
    """

    if not isinstance(table, pa.Table):
        raise NormalizedTableError("table must be a pyarrow.Table")
    if column_name not in table.column_names:
        raise NormalizedTableError(f"Required column {column_name!r} is missing")
    try:
        unique_values = pc.drop_null(pc.unique(table[column_name]))
    except pa.ArrowException as exc:
        raise NormalizedTableError(str(exc)) from exc
    return tuple(str(unique_values[index].as_py()) for index in range(len(unique_values)))


def _read_arrow_column(
    table: pa.Table,
    spec: ColumnSpec,
    *,
    error: ErrorFactory,
) -> dict[str, ArrowColumnArray]:
    if spec.logical_type is TabularLogicalType.UNKNOWN:
        raise error(f"Column {spec.name!r} has unknown logical_type", spec.name)

    try:
        column_name = resolve_column_name(table, spec)
    except NormalizedTableError as exc:
        raise error(str(exc), spec.name) from exc

    if column_name is None:
        if spec.required:
            raise error(f"Required column {spec.name!r} is missing", spec.name)
        return {}

    column = table.column(column_name)
    try:
        _arrow_table._validate_column_policy(spec, column)
        values = _read_typed_arrow_column(column, spec)
    except (NormalizedTableError, pa.ArrowException) as exc:
        raise error(str(exc), spec.name) from exc

    values.setflags(write=False)
    return {spec.name: values}


def _read_typed_arrow_column(
    column: pa.ChunkedArray,
    spec: ColumnSpec,
) -> ArrowColumnArray:
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
            raise NormalizedTableError(
                f"Column {spec.name!r} has unsupported logical_type {spec.logical_type.value!r}"
            )


def _restore_null_defaults(
    table: pa.Table,
    specs: Sequence[ColumnSpec],
    columns: dict[str, ArrowColumnArray],
    null_defaults: Mapping[str, object],
    *,
    error: ErrorFactory,
) -> dict[str, ArrowColumnArray]:
    specs_by_name = {spec.name: spec for spec in specs}
    restored = dict(columns)
    for field, default in null_defaults.items():
        values = restored.get(field)
        if values is None:
            continue
        spec = specs_by_name.get(field)
        if spec is None:
            raise error(f"null default references unknown column {field!r}", field)
        try:
            column_name = resolve_column_name(table, spec)
            if column_name is None:
                continue
            column = table.column(column_name)
            if not column.null_count:
                continue
            restored[field] = _restore_column_null_default(column, values, default, field=field)
        except (NormalizedTableError, pa.ArrowException, TypeError, ValueError) as exc:
            raise error(str(exc), field) from exc
    return restored


def _restore_column_null_default(
    column: pa.ChunkedArray,
    values: ArrowColumnArray,
    default: object,
    *,
    field: str,
) -> ArrowColumnArray:
    array = _single_arrow_array(column)
    valid = np.asarray(array.is_valid().to_numpy(zero_copy_only=False), dtype=np.bool_)
    restored = np.asarray(values, dtype=object).copy()
    if restored.shape != valid.shape:
        raise NormalizedTableError(f"{field} length must match accepted row count")
    restored[~valid] = default
    restored.setflags(write=False)
    return restored


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
        raise NormalizedTableError(f"{field} must be numeric") from exc


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
    "read_arrow_columns",
    "unique_non_null_text_values",
]
