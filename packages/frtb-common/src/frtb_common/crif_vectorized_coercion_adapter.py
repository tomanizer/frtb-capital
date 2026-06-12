"""Vectorized CRIF field coercion helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]

from frtb_common.arrow_table import TabularLogicalType
from frtb_common.crif_types import (
    _FLOAT_TEXT_PATTERN,
    _INTEGER_TEXT_PATTERN,
    _NON_FINITE_TEXT_VALUES,
    CrifColumnSpec,
)
from frtb_common.crif_vectorized_masks_adapter import (
    _bool_array,
    _empty_text_mask,
    _filled_text,
    _mask_and,
    _mask_not,
    _mask_or,
)


@dataclass(frozen=True, slots=True)
class _VectorizedColumn:
    values: pa.Array
    errors: tuple[_VectorizedError, ...] = ()


@dataclass(frozen=True, slots=True)
class _VectorizedError:
    mask: pa.Array
    message: str


def _coerce_column_arrow(
    table: pa.Table,
    source_name: str | None,
    spec: CrifColumnSpec,
) -> _VectorizedColumn:
    text = _source_text_array(table, source_name, spec)
    trimmed = pc.utf8_trim_whitespace(text)
    is_empty = _empty_text_mask(trimmed)
    missing_column = (
        (source_name is None or _source_column_is_all_null(table, source_name))
        and spec.required
        and spec.default is None
    )
    required_empty = is_empty if spec.required else _bool_array(False, table.num_rows)

    if spec.logical_type is TabularLogicalType.FLOAT:
        return _coerce_float_arrow(trimmed, is_empty, required_empty, spec, missing_column)
    if spec.logical_type is TabularLogicalType.INTEGER:
        return _coerce_integer_arrow(trimmed, is_empty, required_empty, spec, missing_column)
    if spec.logical_type is TabularLogicalType.BOOLEAN:
        return _coerce_boolean_arrow(trimmed, is_empty, required_empty, spec, missing_column)
    values = pc.if_else(is_empty, pa.scalar(None, type=pa.string()), trimmed)
    return _VectorizedColumn(
        cast(pa.Array, values),
        errors=_required_text_errors(required_empty, spec, missing_column),
    )


def _source_column_is_all_null(table: pa.Table, source_name: str | None) -> bool:
    if source_name is None or table.num_rows == 0:
        return source_name is None
    column = table.column(source_name)
    return bool(pc.all(pc.is_null(column)).as_py())


def _source_text_array(
    table: pa.Table,
    source_name: str | None,
    spec: CrifColumnSpec,
) -> pa.Array:
    if source_name is None:
        if spec.default is None:
            return pa.nulls(table.num_rows, type=pa.string())
        return pa.repeat(pa.scalar(str(spec.default), type=pa.string()), table.num_rows)
    column = table.column(source_name).combine_chunks()
    text = cast(pa.Array, pc.cast(column, pa.string()))
    if spec.default is None:
        return text
    return cast(
        pa.Array,
        pc.if_else(
            pc.is_null(text),
            pa.scalar(str(spec.default), type=pa.string()),
            text,
        ),
    )


def _coerce_float_arrow(
    trimmed: pa.Array,
    is_empty: pa.Array,
    required_empty: pa.Array,
    spec: CrifColumnSpec,
    missing_column: bool,
) -> _VectorizedColumn:
    filled = _filled_text(trimmed)
    numeric_text = cast(pa.Array, pc.match_substring_regex(filled, _FLOAT_TEXT_PATTERN))
    non_finite_text = cast(
        pa.Array,
        pc.is_in(pc.utf8_upper(filled), value_set=pa.array(sorted(_NON_FINITE_TEXT_VALUES))),
    )
    invalid_numeric = _mask_and(
        _mask_not(is_empty), _mask_not(_mask_or(numeric_text, non_finite_text))
    )
    invalid_finite = _mask_and(_mask_not(is_empty), non_finite_text)
    safe_text = pc.if_else(numeric_text, trimmed, pa.scalar(None, type=pa.string()))
    values = cast(pa.Array, pc.cast(safe_text, pa.float64()))
    finite_values = cast(pa.Array, pc.fill_null(pc.is_finite(values), True))
    invalid_finite = _mask_or(
        invalid_finite, _mask_and(_mask_not(is_empty), _mask_not(finite_values))
    )
    errors = (
        *_required_text_errors(required_empty, spec, missing_column),
        _VectorizedError(invalid_numeric, f"CRIF field {spec.name!r} must be numeric"),
        _VectorizedError(invalid_finite, f"CRIF field {spec.name!r} must be finite"),
    )
    return _VectorizedColumn(values, errors=errors)


def _coerce_integer_arrow(
    trimmed: pa.Array,
    is_empty: pa.Array,
    required_empty: pa.Array,
    spec: CrifColumnSpec,
    missing_column: bool,
) -> _VectorizedColumn:
    filled = _filled_text(trimmed)
    integer_text = cast(pa.Array, pc.match_substring_regex(filled, _INTEGER_TEXT_PATTERN))
    invalid_integer = _mask_and(_mask_not(is_empty), _mask_not(integer_text))
    safe_text = pc.if_else(integer_text, trimmed, pa.scalar(None, type=pa.string()))
    values = cast(pa.Array, pc.cast(safe_text, pa.int64()))
    errors = (
        *_required_text_errors(required_empty, spec, missing_column),
        _VectorizedError(invalid_integer, f"CRIF field {spec.name!r} must be an integer"),
    )
    return _VectorizedColumn(values, errors=errors)


def _coerce_boolean_arrow(
    trimmed: pa.Array,
    is_empty: pa.Array,
    required_empty: pa.Array,
    spec: CrifColumnSpec,
    missing_column: bool,
) -> _VectorizedColumn:
    lowered = pc.utf8_lower(_filled_text(trimmed))
    true_mask = cast(
        pa.Array,
        pc.is_in(lowered, value_set=pa.array(["1", "true", "yes", "y"])),
    )
    false_mask = cast(
        pa.Array,
        pc.is_in(lowered, value_set=pa.array(["0", "false", "no", "n"])),
    )
    valid_boolean = _mask_or(true_mask, false_mask)
    invalid_boolean = _mask_and(_mask_not(is_empty), _mask_not(valid_boolean))
    values = cast(
        pa.Array,
        pc.if_else(
            true_mask,
            pa.scalar(True, type=pa.bool_()),
            pc.if_else(false_mask, pa.scalar(False, type=pa.bool_()), pa.scalar(None, pa.bool_())),
        ),
    )
    errors = (
        *_required_text_errors(required_empty, spec, missing_column),
        _VectorizedError(invalid_boolean, f"CRIF field {spec.name!r} must be boolean"),
    )
    return _VectorizedColumn(values, errors=errors)


def _required_text_errors(
    required_empty: pa.Array,
    spec: CrifColumnSpec,
    missing_column: bool,
) -> tuple[_VectorizedError, ...]:
    if not spec.required:
        return ()
    message = (
        f"required CRIF column {spec.name!r} is missing"
        if missing_column
        else f"CRIF field {spec.name!r} is required"
    )
    return (_VectorizedError(required_empty, message),)
