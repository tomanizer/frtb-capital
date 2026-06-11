"""Column-array coercion helpers for SBM batch validation.

Regulatory traceability:
    ADR 0045 validation stage for package-owned SBM batch ingress; Basel
    MAR21.1 input scope and SBM-NFR-002 deterministic column handling.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, cast

import numpy as np
import numpy.typing as npt

from frtb_sbm._errors import SbmInputError
from frtb_sbm.data_models import SbmRiskClass, SbmRiskMeasure
from frtb_sbm.validation.coercion import (
    coerce_risk_class,
    coerce_risk_measure,
    coerce_sign_convention,
)

ObjectArray = npt.NDArray[np.object_]
FloatArray = npt.NDArray[np.float64]


def object_array(values: Iterable[object], field: str, *, copy: bool) -> ObjectArray:
    """Return a frozen one-dimensional object array.

    Parameters
    ----------
    values
        Source column values.
    field
        Field name reported in diagnostics.
    copy
        Whether NumPy input arrays should be copied.

    Returns
    -------
    ObjectArray
    """

    if isinstance(values, np.ndarray):
        array = values.astype(object, copy=copy)
    else:
        array = np.asarray(tuple(values), dtype=object)
    if array.ndim != 1:
        raise SbmInputError("column arrays must be one-dimensional", field=field)
    freeze_array(array)
    return cast(ObjectArray, array)


def float_array(values: Iterable[object], field: str, *, copy: bool) -> FloatArray:
    """Return a frozen one-dimensional finite float array.

    Parameters
    ----------
    values
        Source numeric column values.
    field
        Field name reported in diagnostics.
    copy
        Whether NumPy input arrays should be copied.

    Returns
    -------
    FloatArray
    """

    try:
        if isinstance(values, np.ndarray):
            array = values.astype(np.float64, copy=copy)
        else:
            array = np.asarray(tuple(values), dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise SbmInputError("value must be numeric", field=field) from exc
    if array.ndim != 1:
        raise SbmInputError("column arrays must be one-dimensional", field=field)
    if not np.all(np.isfinite(array)):
        raise SbmInputError("value must be finite", field=field)
    freeze_array(array)
    return cast(FloatArray, array)


def optional_object_array(
    values: Iterable[object] | None,
    field: str,
    row_count: int,
    copy: bool,
) -> ObjectArray | None:
    """Return a frozen optional object array aligned to a batch row count.

    Parameters
    ----------
    values
        Optional source column values.
    field
        Field name reported in diagnostics.
    row_count
        Expected row count.
    copy
        Whether NumPy input arrays should be copied.

    Returns
    -------
    ObjectArray | None
    """

    if values is None:
        return None
    array = object_array(values, field, copy=copy)
    if int(array.shape[0]) != row_count:
        raise SbmInputError(f"{field} length must match batch row count", field=field)
    if not any(value is not None for value in array):
        return None
    if field in {"up_shock_amount", "down_shock_amount"}:
        validate_optional_float_column(array, field)
    return array


def require_common_length(row_count: int, arrays: Mapping[str, ObjectArray]) -> None:
    """Raise when any batch column length differs from the amount column.

    Parameters
    ----------
    row_count
        Expected row count.
    arrays
        Named arrays to validate.
    """

    for field_name, array in arrays.items():
        if int(array.shape[0]) != row_count:
            raise SbmInputError(
                f"{field_name} length must match amount length",
                field=field_name,
            )


def require_non_empty_length(row_count: int) -> None:
    """Raise when an SBM batch has no rows.

    Parameters
    ----------
    row_count
        Candidate batch row count.
    """

    if row_count == 0:
        raise SbmInputError("SBM batch must not be empty", field="sensitivities")


def normalise_risk_class_array(
    values: ObjectArray,
    *,
    sensitivity_ids: ObjectArray,
) -> ObjectArray:
    """Return a canonical risk-class string array.

    Parameters
    ----------
    values
        Candidate risk-class values.
    sensitivity_ids
        Sensitivity ids used in diagnostics.

    Returns
    -------
    ObjectArray
    """

    items: list[str] = []
    for row_index, value in enumerate(values):
        try:
            items.append(coerce_risk_class(cast(SbmRiskClass | str, value)).value)
        except SbmInputError as exc:
            raise SbmInputError(
                str(exc),
                field="risk_class",
                sensitivity_id=sensitivity_id_for_index(sensitivity_ids, row_index),
            ) from exc
    normalised = np.asarray(tuple(items), dtype=object)
    require_common_length(int(values.shape[0]), {"risk_classes": normalised})
    freeze_array(normalised)
    return cast(ObjectArray, normalised)


def normalise_risk_measure_array(
    values: ObjectArray,
    *,
    sensitivity_ids: ObjectArray,
) -> ObjectArray:
    """Return a canonical risk-measure string array.

    Parameters
    ----------
    values
        Candidate risk-measure values.
    sensitivity_ids
        Sensitivity ids used in diagnostics.

    Returns
    -------
    ObjectArray
    """

    items: list[str] = []
    for row_index, value in enumerate(values):
        try:
            items.append(coerce_risk_measure(cast(SbmRiskMeasure | str, value)).value)
        except SbmInputError as exc:
            raise SbmInputError(
                str(exc),
                field="risk_measure",
                sensitivity_id=sensitivity_id_for_index(sensitivity_ids, row_index),
            ) from exc
    normalised = np.asarray(tuple(items), dtype=object)
    require_common_length(int(values.shape[0]), {"risk_measures": normalised})
    freeze_array(normalised)
    return cast(ObjectArray, normalised)


def normalise_sign_convention_array(
    values: ObjectArray,
    *,
    sensitivity_ids: ObjectArray,
) -> ObjectArray:
    """Return a canonical sign-convention string array.

    Parameters
    ----------
    values
        Candidate sign-convention values.
    sensitivity_ids
        Sensitivity ids used in diagnostics.

    Returns
    -------
    ObjectArray
    """

    items: list[str] = []
    for row_index, value in enumerate(values):
        try:
            items.append(coerce_sign_convention(value).value)
        except SbmInputError as exc:
            raise SbmInputError(
                str(exc),
                field="sign_convention",
                sensitivity_id=sensitivity_id_for_index(sensitivity_ids, row_index),
            ) from exc
    normalised = np.asarray(tuple(items), dtype=object)
    require_common_length(int(values.shape[0]), {"sign_conventions": normalised})
    freeze_array(normalised)
    return cast(ObjectArray, normalised)


def validate_optional_float_column(values: ObjectArray, field: str) -> None:
    """Raise when optional numeric values are non-numeric or non-finite.

    Parameters
    ----------
    values
        Optional column values.
    field
        Field name reported in diagnostics.
    """

    for value in values:
        if value is None:
            continue
        try:
            float_value = float(value)
        except (TypeError, ValueError) as exc:
            raise SbmInputError("value must be numeric", field=field) from exc
        if not np.isfinite(float_value):
            raise SbmInputError("value must be finite", field=field)


def sensitivity_id_for_index(values: ObjectArray, row_index: int) -> str:
    """Return the sensitivity id for a row index when available.

    Parameters
    ----------
    values
        Sensitivity id array.
    row_index
        Candidate row index.

    Returns
    -------
    str
    """

    if row_index < int(values.shape[0]) and isinstance(values[row_index], str):
        return cast(str, values[row_index])
    return ""


def freeze_array(array: npt.NDArray[Any]) -> None:
    """Mark a NumPy array immutable in place.

    Parameters
    ----------
    array
        Array to freeze.
    """

    array.setflags(write=False)


__all__ = [
    "FloatArray",
    "ObjectArray",
    "float_array",
    "freeze_array",
    "normalise_risk_class_array",
    "normalise_risk_measure_array",
    "normalise_sign_convention_array",
    "object_array",
    "optional_object_array",
    "require_common_length",
    "require_non_empty_length",
    "sensitivity_id_for_index",
    "validate_optional_float_column",
]
