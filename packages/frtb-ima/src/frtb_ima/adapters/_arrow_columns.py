"""Arrow column conversion helpers for IMA handoff adapters."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any, cast

import numpy as np
import numpy.typing as npt
import pyarrow as pa  # type: ignore[import-untyped]
from frtb_common import (
    ColumnSpec,
    arrow_date_array,
    arrow_timestamp_array,
    read_arrow_columns,
    validate_arrow_table,
)

from frtb_ima.adapters._arrow_specs import (
    _IMA_LOCAL_LOGICAL_TYPES,
    _IMA_RFET_OBSERVATION_DEFAULTS,
    _IMA_SCENARIO_METADATA_DEFAULTS,
)

BooleanArray = npt.NDArray[np.bool_]
DateArray = npt.NDArray[np.datetime64]
DatetimeArray = npt.NDArray[np.datetime64]
StringArray = npt.NDArray[np.str_]


def _read_ima_arrow_columns(
    table: pa.Table,
    column_specs: tuple[ColumnSpec, ...],
) -> Mapping[str, object]:
    validate_arrow_table(table, column_specs=column_specs)
    columns: Mapping[str, object] = read_arrow_columns(
        table,
        _ima_reader_specs(column_specs),
        error=_ima_error,
        null_defaults=_ima_null_defaults(column_specs),
    )
    return columns


def _ima_reader_specs(column_specs: tuple[ColumnSpec, ...]) -> tuple[ColumnSpec, ...]:
    return tuple(spec for spec in column_specs if spec.logical_type not in _IMA_LOCAL_LOGICAL_TYPES)


def _ima_null_defaults(column_specs: Sequence[ColumnSpec]) -> Mapping[str, object]:
    spec_names = {spec.name for spec in column_specs}
    if "risk_factor_name" in spec_names:
        defaults = _IMA_RFET_OBSERVATION_DEFAULTS
    elif "scenario_id" in spec_names:
        defaults = _IMA_SCENARIO_METADATA_DEFAULTS
    else:
        defaults = {}
    return {name: default for name, default in defaults.items() if name in spec_names}


def _ima_batch_column_kwargs(
    columns: Mapping[str, object],
    column_args: Mapping[str, str],
    *,
    row_count: int,
    defaults: Mapping[str, object],
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    for column_name, argument_name in column_args.items():
        default = defaults.get(column_name)
        if isinstance(default, bool):
            kwargs[argument_name] = _bool_column_from_columns(
                columns,
                column_name,
                row_count=row_count,
                default=default,
            )
        else:
            kwargs[argument_name] = _string_column_from_columns(
                columns,
                column_name,
                row_count=row_count,
                default=cast(str | None, default),
            )
    return kwargs


def _string_column_from_columns(
    columns: Mapping[str, object],
    column_name: str,
    *,
    row_count: int,
    default: str | None = None,
) -> StringArray:
    values = columns.get(column_name)
    if values is None:
        if default is None:
            raise ValueError(f"column is required: {column_name}")
        return np.full(row_count, default, dtype=f"<U{max(1, len(default))}")
    fill = "" if default is None else default
    array = np.asarray(values, dtype=object)
    mask = np.equal(array, np.array(None, dtype=object))
    if bool(np.any(mask)):
        array = array.copy()
        array[mask] = fill
    return cast(StringArray, array.astype(np.str_))


def _bool_column_from_columns(
    columns: Mapping[str, object],
    column_name: str,
    *,
    row_count: int,
    default: bool,
) -> BooleanArray:
    values = columns.get(column_name)
    if values is None:
        return np.full(row_count, default, dtype=np.bool_)
    return cast(BooleanArray, np.asarray(values, dtype=np.bool_))


def _required_column_value(columns: Mapping[str, object], column_name: str, index: int) -> object:
    values = columns.get(column_name)
    if values is None:
        raise ValueError(f"column is required: {column_name}")
    return cast(Sequence[object], values)[index]


def _optional_column_values(
    columns: Mapping[str, object],
    column_name: str,
) -> Sequence[object | None] | None:
    values = columns.get(column_name)
    if values is None:
        return None
    return cast(Sequence[object | None], values)


def _required_text_at(columns: Mapping[str, object], column_name: str, index: int) -> str:
    value = _required_column_value(columns, column_name, index)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{column_name} must contain non-empty text")
    return value


def _optional_text_at(values: Sequence[object | None] | None, index: int) -> str | None:
    if values is None:
        return None
    value = values[index]
    if value is None:
        return None
    text = str(value)
    return text or None


def _datetime_at(table: pa.Table, column_name: str, index: int) -> datetime:
    value = _required_table_column(table, column_name)[index]
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise ValueError(f"{column_name} must contain datetimes or ISO-8601 datetime text")


def _date_at(table: pa.Table, column_name: str, index: int) -> date:
    value = _required_table_column(table, column_name)[index]
    return _parse_date(value, column_name)


def _parse_date(value: object, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError(f"{field} must contain dates or ISO-8601 date text")


def _non_negative_int_at(columns: Mapping[str, object], column_name: str, index: int) -> int:
    value = _required_column_value(columns, column_name, index)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{column_name} must contain integers")
    integer = int(value)
    if integer < 0:
        raise ValueError(f"{column_name} must be non-negative")
    if isinstance(value, float) and value != integer:
        raise ValueError(f"{column_name} must contain whole-number values")
    return integer


def _required_table_column(table: pa.Table, column_name: str) -> list[object]:
    if column_name not in table.column_names:
        raise ValueError(f"column is required: {column_name}")
    return cast(list[object], table.column(column_name).to_pylist())


def _date_column(table: pa.Table, column_name: str) -> DateArray:
    if column_name not in table.column_names:
        raise ValueError(f"column is required: {column_name}")
    return arrow_date_array(table.column(column_name), field=column_name)


def _timestamp_column(table: pa.Table, column_name: str) -> DatetimeArray:
    if column_name not in table.column_names:
        return np.full(table.num_rows, np.datetime64("NaT", "us"), dtype="datetime64[us]")
    return arrow_timestamp_array(table.column(column_name), field=column_name)


def _ima_error(message: str, _field: str | None) -> ValueError:
    return ValueError(message)
