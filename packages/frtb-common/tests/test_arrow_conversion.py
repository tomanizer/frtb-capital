"""Tests for package-neutral Arrow-to-NumPy handoff conversion helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import frtb_common.arrow_conversion as arrow_conversion_module
import numpy as np
import pyarrow as pa
import pytest
from frtb_common import (
    ColumnSpec,
    NormalizedTableError,
    NullPolicy,
    TabularLogicalType,
    arrow_bool_array,
    arrow_bool_or_object_array,
    arrow_date_array,
    arrow_float64_array,
    arrow_float64_array_with_nulls,
    arrow_object_array,
    arrow_timestamp_array,
    read_arrow_columns,
    unique_non_null_text_values,
)


def test_arrow_object_array_preserves_dictionary_nulls() -> None:
    dictionary = pa.array(["rates", "credit"])
    indices = pa.array([0, None, 1], type=pa.int8())
    column = pa.chunked_array([pa.DictionaryArray.from_arrays(indices, dictionary)])

    values = arrow_object_array(column)

    assert values.dtype == np.dtype(object)
    assert values.tolist() == ["rates", None, "credit"]


def test_arrow_object_array_preserves_integer_nulls_across_chunks() -> None:
    column = pa.chunked_array(
        [
            pa.array([1, None], type=pa.int64()),
            pa.array([3], type=pa.int64()),
        ]
    )

    values = arrow_object_array(column)

    assert values.dtype == np.dtype(object)
    assert values.tolist() == [1, None, 3]
    assert isinstance(values[0], (int, np.integer))


@pytest.mark.parametrize(
    "array",
    [
        pa.array(["rates", None], type=pa.utf8()),
        pa.array([1.0, None], type=pa.float64()),
        pa.array([True, None], type=pa.bool_()),
        pa.array(["rates", None, "credit"], type=pa.dictionary(pa.int8(), pa.utf8())),
    ],
)
def test_supported_handoff_dtypes_do_not_need_pylist_fallback(array: pa.Array) -> None:
    column = pa.chunked_array([array])

    for chunk in column.chunks:
        values = chunk.to_numpy(zero_copy_only=False)
        assert len(values) == len(chunk)
        if pa.types.is_dictionary(chunk.type):
            dictionary = chunk.dictionary.to_numpy(zero_copy_only=False)
            assert len(dictionary) == len(chunk.dictionary)


def test_arrow_float64_array_casts_numeric_chunks() -> None:
    column = pa.chunked_array(
        [
            pa.array([1, 2], type=pa.int64()),
            pa.array([3], type=pa.int64()),
        ]
    )

    values = arrow_float64_array(column, field="amount")

    assert values.dtype == np.dtype(np.float64)
    assert values.tolist() == [1.0, 2.0, 3.0]


def test_arrow_float64_array_reports_non_numeric_fields() -> None:
    column = pa.chunked_array([pa.array(["not-a-number"])])

    with pytest.raises(NormalizedTableError, match="amount must be numeric"):
        arrow_float64_array(column, field="amount")


def test_arrow_float64_array_with_nulls_fills_nan() -> None:
    column = pa.chunked_array([pa.array([1.0, None], type=pa.float64())])

    values = arrow_float64_array_with_nulls(column, field="amount")

    assert values[0] == 1.0
    assert np.isnan(values[1])


def test_arrow_bool_array_fills_nulls() -> None:
    column = pa.chunked_array([pa.array([True, None, False], type=pa.bool_())])

    values = arrow_bool_array(column, field="flag")

    assert values.dtype == np.dtype(np.bool_)
    assert values.tolist() == [True, False, False]


def test_arrow_bool_or_object_array_preserves_non_boolean_values() -> None:
    column = pa.chunked_array([pa.array(["Y", None, "N"])])

    values = arrow_bool_or_object_array(column)

    assert values.dtype == np.dtype(object)
    assert values.tolist() == ["Y", False, "N"]


def test_arrow_date_array_handles_arrow_and_iso_text_values() -> None:
    arrow_dates = arrow_date_array(
        pa.chunked_array([pa.array([date(2026, 6, 10)], type=pa.date32())]),
        field="as_of_date",
    )
    text_dates = arrow_date_array(
        pa.chunked_array([pa.array(["2026-06-10"]), pa.array(["2026-06-11"])]),
        field="as_of_date",
    )

    assert arrow_dates.dtype == np.dtype("datetime64[D]")
    assert arrow_dates.tolist() == [date(2026, 6, 10)]
    assert text_dates.tolist() == [date(2026, 6, 10), date(2026, 6, 11)]


def test_arrow_timestamp_array_handles_nullable_arrow_timestamps() -> None:
    values = arrow_timestamp_array(
        pa.chunked_array(
            [
                pa.array(
                    [datetime(2026, 6, 10, 12, 30, tzinfo=UTC), None],
                    type=pa.timestamp("us", tz="UTC"),
                ),
            ]
        ),
        field="observation_timestamp",
    )

    assert values.dtype == np.dtype("datetime64[us]")
    assert values[0] == np.datetime64("2026-06-10T12:30:00", "us")
    assert np.isnat(values[1])


def test_arrow_timestamp_array_normalizes_timezone_aware_arrow_timestamps() -> None:
    values = arrow_timestamp_array(
        pa.chunked_array(
            [
                pa.array(
                    [datetime(2026, 6, 10, 8, 30, tzinfo=ZoneInfo("America/New_York"))],
                    type=pa.timestamp("us", tz="America/New_York"),
                ),
            ]
        ),
        field="observation_timestamp",
    )

    assert values.dtype == np.dtype("datetime64[us]")
    assert values[0] == np.datetime64("2026-06-10T12:30:00", "us")


def test_arrow_timestamp_array_handles_chunked_iso_text_values() -> None:
    values = arrow_timestamp_array(
        pa.chunked_array(
            [
                pa.array(["2026-06-10T13:30:00Z"], type=pa.utf8()),
                pa.array([None], type=pa.utf8()),
            ]
        ),
        field="observation_timestamp",
    )

    assert values.dtype == np.dtype("datetime64[us]")
    assert values[0] == np.datetime64("2026-06-10T13:30:00", "us")
    assert np.isnat(values[1])


class ReaderError(Exception):
    def __init__(self, message: str, field: str | None) -> None:
        super().__init__(message)
        self.field = field


def _reader_error(message: str, field: str | None) -> ReaderError:
    return ReaderError(message, field)


@pytest.mark.parametrize(
    ("logical_type", "array", "expected", "expected_dtype"),
    [
        (
            TabularLogicalType.STRING,
            pa.array(["desk-a", None], type=pa.utf8()),
            ["desk-a", None],
            np.dtype(object),
        ),
        (
            TabularLogicalType.DICTIONARY,
            pa.DictionaryArray.from_arrays(
                pa.array([0, None, 1], type=pa.int8()),
                pa.array(["rates", "credit"], type=pa.utf8()),
            ),
            ["rates", None, "credit"],
            np.dtype(object),
        ),
        (
            TabularLogicalType.DICTIONARY_CODE,
            pa.array([1, None], type=pa.int16()),
            [1, None],
            np.dtype(object),
        ),
        (
            TabularLogicalType.INTEGER,
            pa.array([7, None], type=pa.int64()),
            [7, None],
            np.dtype(object),
        ),
        (
            TabularLogicalType.FLOAT,
            pa.array([1.25, 2.5], type=pa.float64()),
            [1.25, 2.5],
            np.dtype(np.float64),
        ),
        (
            TabularLogicalType.DECIMAL,
            pa.array([Decimal("1.25"), Decimal("2.50")], type=pa.decimal128(8, 2)),
            [1.25, 2.5],
            np.dtype(np.float64),
        ),
        (
            TabularLogicalType.BOOLEAN,
            pa.array([True, None], type=pa.bool_()),
            [True, False],
            np.dtype(np.bool_),
        ),
    ],
)
def test_read_arrow_columns_dispatches_by_logical_type(
    logical_type: TabularLogicalType,
    array: pa.Array,
    expected: list[object],
    expected_dtype: np.dtype[object],
) -> None:
    null_policy = NullPolicy.ALLOW if array.null_count else NullPolicy.FORBID
    table = pa.table({"value": array})

    columns = read_arrow_columns(
        table,
        (ColumnSpec("value", logical_type=logical_type, null_policy=null_policy),),
        error=_reader_error,
    )

    assert columns["value"].dtype == expected_dtype
    assert columns["value"].tolist() == expected
    assert not columns["value"].flags.writeable


def test_read_arrow_columns_fills_allowed_float_nulls() -> None:
    table = pa.table({"amount": pa.array([1.0, None], type=pa.float64())})

    columns = read_arrow_columns(
        table,
        (
            ColumnSpec(
                "amount",
                logical_type=TabularLogicalType.FLOAT,
                required=False,
                null_policy=NullPolicy.ALLOW,
            ),
        ),
        error=_reader_error,
    )

    assert columns["amount"][0] == 1.0
    assert np.isnan(columns["amount"][1])
    assert not columns["amount"].flags.writeable


def test_read_arrow_columns_restores_per_column_null_defaults() -> None:
    table = pa.table(
        {
            "amountAlias": pa.array([1.0, None], type=pa.float64()),
            "flagAlias": pa.array([None, False], type=pa.bool_()),
            "textAlias": pa.array([None, "desk-1"], type=pa.string()),
        }
    )

    columns = read_arrow_columns(
        table,
        (
            ColumnSpec(
                "amount",
                aliases=("amountAlias",),
                logical_type=TabularLogicalType.FLOAT,
                required=False,
                null_policy=NullPolicy.ALLOW,
            ),
            ColumnSpec(
                "flag",
                aliases=("flagAlias",),
                logical_type=TabularLogicalType.BOOLEAN,
                required=False,
                null_policy=NullPolicy.ALLOW,
            ),
            ColumnSpec(
                "text",
                aliases=("textAlias",),
                logical_type=TabularLogicalType.STRING,
                required=False,
                null_policy=NullPolicy.ALLOW,
            ),
        ),
        error=_reader_error,
        null_defaults={"amount": None, "flag": True, "text": ""},
    )

    assert columns["amount"].tolist() == [1.0, None]
    assert columns["flag"].tolist() == [True, False]
    assert columns["text"].tolist() == ["", "desk-1"]
    assert all(not column.flags.writeable for column in columns.values())


def test_read_arrow_columns_uses_float_zero_copy_when_nulls_are_allowed_but_absent() -> None:
    table = pa.table({"amount": pa.array([1.0, 2.0], type=pa.float64())})

    columns = read_arrow_columns(
        table,
        (
            ColumnSpec(
                "amount",
                logical_type=TabularLogicalType.FLOAT,
                required=False,
                null_policy=NullPolicy.ALLOW,
            ),
        ),
        error=_reader_error,
    )

    arrow_view = table.column("amount").chunk(0).to_numpy(zero_copy_only=True)
    assert np.shares_memory(columns["amount"], arrow_view)
    assert not columns["amount"].flags.writeable


def test_unique_non_null_text_values_handles_chunked_dictionary_columns() -> None:
    table = pa.table(
        {
            "risk_class": pa.chunked_array(
                [
                    pa.array(["GIRR", None, "GIRR"]).dictionary_encode(),
                    pa.array(["FX", "GIRR"]).dictionary_encode(),
                ]
            )
        }
    )

    assert unique_non_null_text_values(table, "risk_class") == ("GIRR", "FX")


def test_unique_non_null_text_values_rejects_missing_columns() -> None:
    with pytest.raises(NormalizedTableError, match="Required column 'risk_class' is missing"):
        unique_non_null_text_values(pa.table({"other": pa.array(["GIRR"])}), "risk_class")


def test_read_arrow_columns_rejects_required_missing_column() -> None:
    with pytest.raises(ReaderError) as exc_info:
        read_arrow_columns(
            pa.table({"other": pa.array(["x"])}),
            (ColumnSpec("value", logical_type=TabularLogicalType.STRING),),
            error=_reader_error,
        )

    assert exc_info.value.field == "value"
    assert "Required column 'value' is missing" in str(exc_info.value)


def test_read_arrow_columns_rejects_forbidden_nulls() -> None:
    with pytest.raises(ReaderError) as exc_info:
        read_arrow_columns(
            pa.table({"value": pa.array(["x", None])}),
            (ColumnSpec("value", logical_type=TabularLogicalType.STRING),),
            error=_reader_error,
        )

    assert exc_info.value.field == "value"
    assert "Column 'value' contains nulls" in str(exc_info.value)


def test_read_arrow_columns_omits_missing_optional_columns() -> None:
    columns = read_arrow_columns(
        pa.table({"other": pa.array(["x"])}),
        (
            ColumnSpec(
                "value",
                logical_type=TabularLogicalType.STRING,
                required=False,
                null_policy=NullPolicy.ALLOW,
            ),
        ),
        error=_reader_error,
    )

    assert columns == {}


def test_read_arrow_columns_rejects_unknown_logical_type() -> None:
    with pytest.raises(ReaderError) as exc_info:
        read_arrow_columns(
            pa.table({"value": pa.array(["x"])}),
            (ColumnSpec("value"),),
            error=_reader_error,
        )

    assert exc_info.value.field == "value"
    assert "unknown logical_type" in str(exc_info.value)


def test_read_arrow_columns_wraps_tabular_errors() -> None:
    with pytest.raises(ReaderError) as exc_info:
        read_arrow_columns(
            pa.table({"amount": pa.array(["not-a-number"])}),
            (ColumnSpec("amount", logical_type=TabularLogicalType.FLOAT),),
            error=_reader_error,
        )

    assert exc_info.value.field == "amount"
    assert isinstance(exc_info.value.__cause__, NormalizedTableError)


def test_read_arrow_columns_wraps_arrow_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_arrow_invalid(column: pa.ChunkedArray) -> np.ndarray:
        raise pa.ArrowInvalid("broken arrow array")

    monkeypatch.setattr(arrow_conversion_module, "arrow_object_array", raise_arrow_invalid)

    with pytest.raises(ReaderError) as exc_info:
        read_arrow_columns(
            pa.table({"value": pa.array(["x"])}),
            (ColumnSpec("value", logical_type=TabularLogicalType.STRING),),
            error=_reader_error,
        )

    assert exc_info.value.field == "value"
    assert isinstance(exc_info.value.__cause__, pa.ArrowInvalid)
