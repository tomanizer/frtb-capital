"""Tests for package-neutral NumPy batch array helpers."""

from __future__ import annotations

from enum import StrEnum

import frtb_common
import numpy as np
import pytest
from frtb_common.batch_arrays import (
    BatchArrayCoercionError,
    bool_array,
    coerce_bool_value,
    enum_array,
    float_array_from_numpy,
    freeze_source_column_maps,
    nullable_enum_array,
    object_array,
    optional_bool_object_array,
    optional_float_array,
    optional_text_array,
    readonly_array,
    text_array_with_default,
)


class SampleEnum(StrEnum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"


@pytest.mark.parametrize(
    "name",
    [
        "BatchArrayCoercionError",
        "bool_array",
        "coerce_bool_value",
        "enum_array",
        "freeze_source_column_maps",
        "float_array_from_numpy",
        "immutable_float_array",
        "immutable_object_array",
        "nullable_enum_array",
        "object_array",
        "optional_bool_object_array",
        "optional_float_array",
        "optional_text_array",
        "readonly_array",
        "text_array_with_default",
    ],
)
def test_batch_helpers_are_not_top_level_exports(name: str) -> None:
    assert name not in frtb_common.__all__
    assert not hasattr(frtb_common, name)


def test_readonly_array_can_copy_or_view() -> None:
    source = np.array([1.0, 2.0])

    copied = readonly_array(source, copy=True)
    viewed = readonly_array(source, copy=False)

    assert copied.flags.writeable is False
    assert viewed.flags.writeable is False
    source[0] = 9.0
    assert copied.tolist() == [1.0, 2.0]
    assert viewed.tolist() == [9.0, 2.0]


def test_object_array_is_readonly() -> None:
    objects = object_array(["desk-1", None], copy=True)

    assert objects.dtype == np.dtype(object)
    assert objects.flags.writeable is False


def test_text_arrays_normalise_missing_and_defaults() -> None:
    optional = optional_text_array([None, " desk ", ""], 3, copy=True)
    defaulted = text_array_with_default([None, " file ", ""], 3, default="source", copy=True)

    assert optional.tolist() == [None, "desk", None]
    assert defaulted.tolist() == ["source", "file", "source"]
    assert optional.flags.writeable is False
    assert defaulted.flags.writeable is False


def test_enum_arrays_coerce_and_reject_values() -> None:
    required = enum_array(["LEFT"], SampleEnum, "side", copy=True)
    nullable = nullable_enum_array([None, "RIGHT", ""], SampleEnum, "side", 3, copy=True)

    assert required.tolist() == ["LEFT"]
    assert nullable.tolist() == [None, "RIGHT", None]
    with pytest.raises(BatchArrayCoercionError, match="side contains unsupported value"):
        enum_array(["MIDDLE"], SampleEnum, "side", copy=True)


def test_float_array_from_numpy_accepts_numeric_numpy_fast_path() -> None:
    values = np.array([1, 2], dtype=np.int64)

    result = float_array_from_numpy(values, field="amount", copy=True, allow_nan=False)

    assert result is not None
    assert result.dtype == np.dtype(np.float64)
    assert result.tolist() == [1.0, 2.0]
    assert result.flags.writeable is False


def test_float_array_from_numpy_returns_none_for_non_numpy_or_non_numeric_inputs() -> None:
    assert float_array_from_numpy([1.0], field="amount", copy=True, allow_nan=False) is None
    assert (
        float_array_from_numpy(
            np.array(["1.0"], dtype=object),
            field="amount",
            copy=True,
            allow_nan=False,
        )
        is None
    )


def test_float_array_from_numpy_validates_shape_and_finite_options() -> None:
    with pytest.raises(
        BatchArrayCoercionError, match="amount must be 1-dimensional"
    ) as shape_error:
        float_array_from_numpy(
            np.array([[1.0]]),
            field="amount",
            copy=True,
            allow_nan=False,
        )
    assert shape_error.value.field == "amount"

    with pytest.raises(BatchArrayCoercionError, match="value must be finite"):
        float_array_from_numpy(
            np.array([np.inf]),
            field="amount",
            copy=True,
            allow_nan=True,
        )

    with pytest.raises(BatchArrayCoercionError, match="value must be finite"):
        float_array_from_numpy(
            np.array([np.nan]),
            field="amount",
            copy=True,
            allow_nan=False,
        )

    result = float_array_from_numpy(
        np.array([[np.inf]]),
        field="amount",
        copy=True,
        allow_nan=False,
        require_1d=False,
        require_finite=False,
    )
    assert result is not None
    assert result.shape == (1, 1)


def test_optional_float_array_preserves_missing_values_and_fast_path() -> None:
    from_sequence = optional_float_array([None, "", np.nan, "1.5"], 4, copy=True)
    from_numpy = optional_float_array(np.array([1.0, np.nan]), 2, copy=True)

    assert np.isnan(from_sequence[:3]).all()
    assert from_sequence[3] == 1.5
    assert from_numpy[0] == 1.0
    assert np.isnan(from_numpy[1])
    with pytest.raises(BatchArrayCoercionError, match="optional numeric field must be numeric"):
        optional_float_array(["bad"], 1, copy=True)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (True, True),
        (np.bool_(False), False),
        ("1", True),
        ("true", True),
        ("YES", True),
        ("y", True),
        (1.0, True),
        (np.int64(1), True),
        ("0", False),
        ("false", False),
        ("No", False),
        ("n", False),
        (0.0, False),
        (np.int64(0), False),
        ("", False),
    ],
)
def test_coerce_bool_value_accepts_supported_spellings(value: object, expected: bool) -> None:
    assert coerce_bool_value(value) is expected


def test_bool_array_defaults_and_invalid_values() -> None:
    defaulted = bool_array(None, 3, default=True, copy=True)
    explicit = bool_array(["yes", "0"], 2, default=False, copy=True)

    assert defaulted.tolist() == [True, True, True]
    assert defaulted.flags.writeable is False
    assert explicit.tolist() == [True, False]
    with pytest.raises(BatchArrayCoercionError, match="unsupported value"):
        bool_array(["maybe"], 1, default=False, copy=True)


def test_optional_bool_object_array_preserves_nulls_blanks_and_nan() -> None:
    defaulted = optional_bool_object_array(None, 2, copy=True)
    explicit = optional_bool_object_array([None, "", np.nan, "yes", "no"], 5, copy=True)

    assert defaulted.tolist() == [None, None]
    assert explicit.tolist() == [None, None, None, True, False]
    assert explicit.dtype == np.dtype(object)
    assert explicit.flags.writeable is False


def test_freeze_source_column_maps_can_sort_and_coerce_pairs() -> None:
    result = freeze_source_column_maps(
        [[("b", "canonical_b"), ("a", "canonical_a")]],
        1,
        sort_pairs=True,
    )

    assert result == ((("a", "canonical_a"), ("b", "canonical_b")),)
    assert freeze_source_column_maps(None, 2) == ((), ())
