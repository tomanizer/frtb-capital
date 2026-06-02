"""Package-local array helpers for IMA batch and vector inputs."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

import numpy as np
import numpy.typing as npt


def finite_1d_float_array(
    values: object,
    name: str,
    *,
    descriptor: str = "",
    empty_message: str | None = None,
    require_float_sequence: bool = False,
) -> npt.NDArray[np.float64]:
    """Return a finite one-dimensional float64 array."""

    if require_float_sequence and (
        values is None
        or isinstance(values, (str, bytes))
        or not isinstance(values, (Sequence, np.ndarray))
    ):
        raise ValueError(f"{name} must be a sequence or numpy array of floats")
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name}{descriptor} must be one-dimensional")
    if arr.size == 0:
        raise ValueError(empty_message or f"{name}{descriptor} is empty")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name}{descriptor} must contain only finite values")
    return arr.astype(np.float64, copy=False)


def readonly_string_array(values: object, field_name: str) -> npt.NDArray[np.str_]:
    """Return a read-only one-dimensional string array."""

    array = np.array(values, dtype=np.str_, copy=True)
    if array.ndim != 1:
        raise ValueError(f"{field_name} must be one-dimensional")
    array.flags.writeable = False
    return array


def readonly_date_array(values: object, field_name: str) -> npt.NDArray[np.datetime64]:
    """Return a read-only one-dimensional daily datetime64 array."""

    array = np.array(values, dtype="datetime64[D]", copy=True)
    if array.ndim != 1:
        raise ValueError(f"{field_name} must be one-dimensional")
    if bool(np.any(np.isnat(array))):
        raise ValueError(f"{field_name} cannot contain null dates")
    array.flags.writeable = False
    return array


def validate_equal_lengths(label: str, first: np.ndarray, *others: np.ndarray) -> None:
    """Require a set of column arrays to have the same first dimension."""

    expected = first.shape[0]
    for array in others:
        if array.shape[0] != expected:
            raise ValueError(f"{label} columns must have equal lengths")


def date_from_datetime64(value: np.datetime64, label: str) -> date:
    """Convert a datetime64 value to ``datetime.date`` with a package-local error."""

    parsed = value.astype("datetime64[D]").item()
    if not isinstance(parsed, date) or isinstance(parsed, datetime):
        raise TypeError(f"{label} did not convert to date")
    return parsed
