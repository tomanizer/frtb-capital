"""Package-neutral NumPy array coercion helpers for batch handoffs."""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, TypeVar, cast

import numpy as np
import numpy.typing as npt

ObjectArray = npt.NDArray[np.object_]
FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]
ArrayInput = npt.NDArray[Any]
ColumnInput = Sequence[object] | ArrayInput
NullableColumnInput = Sequence[object | None] | ArrayInput
ArrayScalarT = TypeVar("ArrayScalarT", bound=np.generic)
EnumT = TypeVar("EnumT", bound=StrEnum)


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


def required_text_value(value: object | None, field: str) -> str:
    """Return stripped non-empty text or raise a package-neutral error.

    Parameters
    ----------
    value : object or None
        Candidate scalar text value.
    field : str
        Field label for error metadata and messages.

    Returns
    -------
    str
        Stripped non-empty text.
    """

    text = optional_text_value(value)
    if text is None:
        raise BatchArrayCoercionError(f"{field} must be non-empty", field=field)
    return text


def optional_text_value(value: object | None) -> str | None:
    """Return stripped optional text, normalising ``None`` and blanks to ``None``."""

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def optional_text_array(
    values: NullableColumnInput | None,
    row_count: int,
    *,
    copy: bool,
    optional_text: Callable[[object | None], str | None] = optional_text_value,
) -> ObjectArray:
    """Return a nullable text object array using a caller-supplied null policy."""

    if values is None:
        return object_array([None] * row_count, copy=copy)
    return object_array([optional_text(value) for value in values], copy=copy)


def text_array_with_default(
    values: ColumnInput | None,
    row_count: int,
    *,
    default: str,
    copy: bool,
    optional_text: Callable[[object | None], str | None] = optional_text_value,
) -> ObjectArray:
    """Return a text object array, filling missing or blank values with *default*."""

    if values is None:
        return object_array([default] * row_count, copy=copy)
    return object_array([optional_text(value) or default for value in values], copy=copy)


def enum_array(
    values: NullableColumnInput,
    enum_type: type[EnumT],
    field: str,
    *,
    copy: bool,
    required_text: Callable[[object | None, str], str] = required_text_value,
) -> ObjectArray:
    """Return a required enum value array containing canonical enum values."""

    return object_array(
        [_coerce_enum_value(value, enum_type, field, required_text) for value in values],
        copy=copy,
    )


def nullable_enum_array(
    values: NullableColumnInput | None,
    enum_type: type[EnumT],
    field: str,
    row_count: int,
    *,
    copy: bool,
    optional_text: Callable[[object | None], str | None] = optional_text_value,
    required_text: Callable[[object | None, str], str] = required_text_value,
) -> ObjectArray:
    """Return a nullable enum value array containing canonical enum values."""

    if values is None:
        return object_array([None] * row_count, copy=copy)
    return object_array(
        [
            None
            if optional_text(value) is None
            else _coerce_enum_value(value, enum_type, field, required_text)
            for value in values
        ],
        copy=copy,
    )


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


def required_float_value(
    value: object,
    field: str,
    *,
    allow_bool: bool = True,
) -> float:
    """Return a finite float using package-neutral batch error reporting."""

    if value is None:
        raise BatchArrayCoercionError(f"{field} must be provided", field=field)
    if not allow_bool and isinstance(value, (bool, np.bool_)):
        raise BatchArrayCoercionError(f"{field} must be numeric", field=field)
    try:
        number = float(cast(Any, value))
    except (TypeError, ValueError) as exc:
        raise BatchArrayCoercionError(f"{field} must be numeric", field=field) from exc
    if not math.isfinite(number):
        raise BatchArrayCoercionError(f"{field} must be finite", field=field)
    return number


def optional_float_value(
    value: object | None,
    *,
    field: str = "optional numeric field",
    allow_bool: bool = True,
) -> float:
    """Return a nullable scalar float encoded as ``NaN`` for missing values."""

    if value is None:
        return math.nan
    if isinstance(value, (float, np.floating)) and math.isnan(float(value)):
        return math.nan
    if isinstance(value, str) and not value.strip():
        return math.nan
    return required_float_value(value, field, allow_bool=allow_bool)


def optional_float_array(
    values: NullableColumnInput | None,
    row_count: int,
    *,
    copy: bool,
    field: str = "optional numeric field",
    allow_bool: bool = True,
    require_1d_fast_path: bool = False,
) -> FloatArray:
    """Return a read-only float array with missing optional values as ``NaN``."""

    if values is None:
        array = np.full(row_count, np.nan, dtype=np.float64)
    elif (
        fast_array := float_array_from_numpy(
            values,
            field=field,
            copy=copy,
            allow_nan=True,
            require_1d=require_1d_fast_path,
            require_finite=False,
        )
    ) is not None:
        return fast_array
    else:
        array = np.asarray(
            [optional_float_value(value, field=field, allow_bool=allow_bool) for value in values],
            dtype=np.float64,
        )
    return readonly_array(array, copy=False)


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


def freeze_source_column_maps(
    values: Sequence[Sequence[tuple[object, object]]] | None,
    row_count: int,
    *,
    text_coercer: Callable[[object], str] = str,
    sort_pairs: bool = False,
) -> tuple[tuple[tuple[str, str], ...], ...]:
    """Freeze source-to-canonical column mappings for audit payloads."""

    if values is None:
        return tuple(() for _ in range(row_count))
    frozen: list[tuple[tuple[str, str], ...]] = []
    for row in values:
        pairs = tuple((text_coercer(source), text_coercer(target)) for source, target in row)
        frozen.append(tuple(sorted(pairs)) if sort_pairs else pairs)
    return tuple(frozen)


def _coerce_enum_value(
    value: object | None,
    enum_type: type[EnumT],
    field: str,
    required_text: Callable[[object | None, str], str],
) -> str:
    text = required_text(value, field)
    try:
        return enum_type(text).value
    except ValueError as exc:
        raise BatchArrayCoercionError(
            f"{field} contains unsupported value: {text}",
            field=field,
        ) from exc
