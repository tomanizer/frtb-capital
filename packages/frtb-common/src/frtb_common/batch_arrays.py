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
    """Return a read-only copy or view of an existing NumPy array."""

    frozen = array.copy() if copy else array.view()
    frozen.setflags(write=False)
    return frozen


def object_array(values: NullableColumnInput, *, copy: bool) -> ObjectArray:
    """Return a read-only object array for nullable batch columns."""

    array = np.asarray(values, dtype=object)
    return readonly_array(array, copy=copy and array is values)


def immutable_object_array(values: ObjectArray) -> ObjectArray:
    """Return a copied immutable object array."""

    array = np.asarray(values, dtype=object).copy()
    array.setflags(write=False)
    return array


def immutable_float_array(values: FloatArray) -> FloatArray:
    """Return a copied immutable float64 array."""

    array = np.asarray(values, dtype=np.float64).copy()
    array.setflags(write=False)
    return array


def float_array_from_numpy(
    values: ColumnInput | NullableColumnInput,
    *,
    field: str,
    copy: bool,
    allow_nan: bool,
    require_1d: bool = True,
    require_finite: bool = True,
) -> FloatArray | None:
    """Return a read-only float64 array when ``values`` is a numeric NumPy array."""

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
    """Coerce accepted scalar boolean spellings used by batch handoffs."""

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
    """Return a read-only boolean array with optional default filling."""

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
    """Return a read-only object array for nullable boolean batch columns."""

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
