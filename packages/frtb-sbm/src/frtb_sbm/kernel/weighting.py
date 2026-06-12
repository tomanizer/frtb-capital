"""Shared SBM weighted-sensitivity ordering and batch-axis helpers.

The functions in this module are stage helpers for risk-class weighting
kernels. Public callers should continue to import weighting functions from
`frtb_sbm.weighted_sensitivity` or the top-level package.
"""

from __future__ import annotations

from collections.abc import Sequence
from numbers import Integral
from typing import cast

import numpy as np
import numpy.typing as npt

from frtb_sbm.batch import SbmSensitivityBatch
from frtb_sbm.data_models import WeightedSensitivity
from frtb_sbm.validation import SbmInputError


def weighted_sensitivity_sort_key(item: WeightedSensitivity) -> tuple[str, str, str, str]:
    """Return a deterministic ordering key for one weighted sensitivity.
    Parameters
    ----------
    item : WeightedSensitivity
        See signature.

    Returns
    -------
    tuple[str, str, str, str]
    """

    return (
        item.risk_class.value,
        item.risk_measure.value,
        item.bucket,
        item.sensitivity_id,
    )


def sort_weighted_sensitivities_deterministic(
    weighted_sensitivities: Sequence[WeightedSensitivity],
) -> tuple[WeightedSensitivity, ...]:
    """Return weighted sensitivities in stable risk-class, bucket, and id order.
    Parameters
    ----------
    weighted_sensitivities : Sequence[WeightedSensitivity]
        See signature.

    Returns
    -------
    tuple[WeightedSensitivity, ...]
    """

    return tuple(sorted(weighted_sensitivities, key=weighted_sensitivity_sort_key))


def _liquidity_horizon_at(
    batch: SbmSensitivityBatch,
    row_index: int,
    *,
    default_horizon: int,
) -> int:
    if batch.liquidity_horizon_days is None:
        return default_horizon
    value = batch.liquidity_horizon_days[row_index]
    if value is None:
        return default_horizon
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise SbmInputError(
            "value must be a positive integer",
            field="liquidity_horizon_days",
            sensitivity_id=cast(str, batch.sensitivity_ids[row_index]),
        )
    horizon = int(value)
    if horizon <= 0:
        raise SbmInputError(
            "value must be a positive integer",
            field="liquidity_horizon_days",
            sensitivity_id=cast(str, batch.sensitivity_ids[row_index]),
        )
    return horizon


def _required_optional_axis_value(
    values: npt.NDArray[np.object_] | None,
    row_index: int,
    field: str,
) -> str:
    if values is None:
        raise SbmInputError(f"{field} is required", field=field)
    value = values[row_index]
    if not isinstance(value, str) or not value.strip():
        raise SbmInputError("non-empty text is required", field=field)
    return value


def _optional_axis_value(
    values: npt.NDArray[np.object_] | None,
    row_index: int,
) -> str | None:
    if values is None:
        return None
    value = values[row_index]
    if value is None:
        return None
    return cast(str, value)


__all__ = [
    "sort_weighted_sensitivities_deterministic",
    "weighted_sensitivity_sort_key",
]
