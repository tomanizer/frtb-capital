"""Package-neutral NumPy array coercion helpers for batch handoffs."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, TypeVar

import numpy as np
import numpy.typing as npt

ObjectArray = npt.NDArray[np.object_]
FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]
ArrayInput = npt.NDArray[Any]
ColumnInput = Sequence[object] | ArrayInput
NullableColumnInput = Sequence[object | None] | ArrayInput
ArrayScalarT = TypeVar("ArrayScalarT", bound=np.generic)


@dataclass(frozen=True)
class BatchArrayCoercionError(ValueError):
    """Error raised when package-neutral batch array coercion fails."""

    message: str
    field: str | None = None

    def __str__(self) -> str:
        return self.message


def readonly_array(
    array: npt.NDArray[ArrayScalarT],
    *,
    copy: bool,
) -> npt.NDArray[ArrayScalarT]:
    """Return a read-only copy or view of an existing NumPy array.

    Parameters
    ----------
    array : ndarray
        Source array to freeze.
    copy : bool
        When ``True``, materialise a copy before clearing write access.

    Returns
    -------
    ndarray
        Read-only array sharing or owning the underlying buffer.
    """

    frozen = array.copy() if copy else array.view()
    frozen.setflags(write=False)
    return frozen


def object_array(values: NullableColumnInput, *, copy: bool) -> ObjectArray:
    """Return a read-only object array for nullable batch columns.

    Parameters
    ----------
    values : sequence or ndarray
        Column values, including ``None`` for missing entries.
    copy : bool
        When ``True`` and *values* is already an ndarray, copy before freezing.

    Returns
    -------
    ObjectArray
        One-dimensional read-only object dtype array.
    """

    array = np.asarray(values, dtype=object)
    return readonly_array(array, copy=copy and array is values)


def float_array_from_numpy(
    values: ColumnInput | NullableColumnInput,
    *,
    field: str,
    copy: bool,
    allow_nan: bool,
    require_1d: bool = True,
    require_finite: bool = True,
) -> FloatArray | None:
    """Return a read-only float64 array when ``values`` is a numeric NumPy array.

    Parameters
    ----------
    values : sequence or ndarray
        Candidate numeric column input.
    field : str
        Field label used in coercion errors.
    copy : bool
        When ``True`` and coercion succeeds, copy before freezing.
    allow_nan : bool
        Whether NaN values are permitted when ``require_finite`` is ``False``.
    require_1d : bool, optional
        Require a one-dimensional ndarray (default ``True``).
    require_finite : bool, optional
        Reject non-finite values except optional NaNs (default ``True``).

    Returns
    -------
    FloatArray or None
        Read-only float64 array when *values* is numeric; otherwise ``None``.
    """

    if not isinstance(values, np.ndarray) or values.dtype.kind not in {"f", "i", "u"}:
        return None
    if require_1d and values.ndim != 1:
        raise BatchArrayCoercionError(f"{field} must be 1-dimensional", field=field)
    array = np.asarray(values, dtype=np.float64)
    if require_finite:
        invalid = (~np.isnan(array) & ~np.isfinite(array)) if allow_nan else ~np.isfinite(array)
        if bool(np.any(invalid)):
            raise BatchArrayCoercionError("value must be finite", field=field)
    return readonly_array(array, copy=copy and array is values)


def coerce_bool_value(value: object) -> bool:
    """Coerce accepted scalar boolean spellings used by batch handoffs.

    Parameters
    ----------
    value : object
        Scalar boolean, numeric zero/one, or common text spellings.

    Returns
    -------
    bool
        Coerced boolean value.

    Raises
    ------
    BatchArrayCoercionError
        When *value* cannot be interpreted as a boolean.
    """

    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, float, np.integer, np.floating)):
        numeric = float(value)
        if numeric == 1.0:
            return True
        if numeric == 0.0:
            return False
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n", ""}:
        return False
    raise BatchArrayCoercionError(f"boolean field contains unsupported value: {value!r}")


def bool_array(
    values: ColumnInput | None,
    row_count: int,
    *,
    default: bool,
    copy: bool,
) -> BoolArray:
    """Return a read-only boolean array with optional default filling.

    Parameters
    ----------
    values : sequence, ndarray, or None
        Column values; ``None`` fills the column with *default*.
    row_count : int
        Expected row count when *values* is ``None``.
    default : bool
        Value used for every row when *values* is ``None``.
    copy : bool
        When ``True`` and *values* is a boolean ndarray, copy before freezing.

    Returns
    -------
    BoolArray
        One-dimensional read-only boolean array of length *row_count*.
    """

    if values is None:
        array = np.full(row_count, default, dtype=np.bool_)
        return readonly_array(array, copy=False)
    elif isinstance(values, np.ndarray) and values.dtype == np.bool_:
        array = np.asarray(values, dtype=np.bool_)
        return readonly_array(array, copy=copy and array is values)
    else:
        array = np.asarray([coerce_bool_value(value) for value in values], dtype=np.bool_)
        return readonly_array(array, copy=False)


def optional_bool_object_array(
    values: NullableColumnInput | None,
    row_count: int,
    *,
    copy: bool,
) -> ObjectArray:
    """Return a read-only object array for nullable boolean batch columns.

    Parameters
    ----------
    values : sequence, ndarray, or None
        Column values with optional missing entries.
    row_count : int
        Expected row count when *values* is ``None``.
    copy : bool
        Forwarded to :func:`object_array` when materialising from sequences.

    Returns
    -------
    ObjectArray
        One-dimensional read-only object array of ``bool`` or ``None`` entries.
    """

    if values is None:
        array = np.full(row_count, None, dtype=object)
        return readonly_array(array, copy=False)
    return object_array([_optional_bool_value(value) for value in values], copy=copy)


def _optional_bool_value(value: object | None) -> bool | None:
    if value is None:
        return None
    if isinstance(value, (float, np.floating)) and np.isnan(value):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return coerce_bool_value(value)
