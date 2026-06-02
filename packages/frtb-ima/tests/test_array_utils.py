from __future__ import annotations

import numpy as np
import pytest

from frtb_ima._array_utils import (
    date_from_datetime64,
    readonly_date_array,
    readonly_string_array,
    validate_equal_lengths,
)


def test_readonly_string_array_rejects_multidimensional_input() -> None:
    with pytest.raises(ValueError, match="labels must be one-dimensional"):
        readonly_string_array([["a"], ["b"]], "labels")


def test_readonly_date_array_rejects_multidimensional_and_null_dates() -> None:
    with pytest.raises(ValueError, match="dates must be one-dimensional"):
        readonly_date_array([["2026-01-01"], ["2026-01-02"]], "dates")

    with pytest.raises(ValueError, match="dates cannot contain null dates"):
        readonly_date_array(["2026-01-01", "NaT"], "dates")


def test_validate_equal_lengths_reports_column_group() -> None:
    with pytest.raises(ValueError, match="scenario columns must have equal lengths"):
        validate_equal_lengths(
            "scenario",
            np.array(["a", "b"]),
            np.array(["a"]),
        )


def test_date_from_datetime64_rejects_nat() -> None:
    with pytest.raises(TypeError, match="observation date did not convert to date"):
        date_from_datetime64(np.datetime64("NaT", "D"), "observation date")
