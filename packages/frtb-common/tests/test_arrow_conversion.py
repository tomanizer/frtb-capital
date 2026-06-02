"""Tests for package-neutral Arrow-to-NumPy handoff conversion helpers."""

from __future__ import annotations

import numpy as np
import pyarrow as pa
import pytest
from frtb_common import (
    TabularHandoffError,
    arrow_bool_array,
    arrow_bool_or_object_array,
    arrow_float64_array,
    arrow_float64_array_with_nulls,
    arrow_object_array,
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

    with pytest.raises(TabularHandoffError, match="amount must be numeric"):
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
