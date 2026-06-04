"""Package-local lookup helpers for package-owned SBM batches."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import numpy.typing as npt

from frtb_sbm.validation import SbmInputError


def batch_text_by_id(
    batch: Any,
    values: npt.NDArray[np.object_] | None,
    field: str,
) -> Mapping[str, str]:
    """Return required batch text values keyed by sensitivity id.
    Parameters
    ----------
    batch : Any
        See signature.
    values : npt.NDArray[np.object_] | None
        See signature.
    field : str
        See signature.

    Returns
    -------
    Mapping[str, str]
    """

    if values is None:
        raise SbmInputError(f"{field} is required", field=field)
    return {
        str(sensitivity_id): str(value)
        for sensitivity_id, value in zip(batch.sensitivity_ids, values)
    }


def batch_optional_text_by_id(
    batch: Any,
    values: npt.NDArray[np.object_] | None,
) -> Mapping[str, str]:
    """Return optional batch text values keyed by sensitivity id.
    Parameters
    ----------
    batch : Any
        See signature.
    values : npt.NDArray[np.object_] | None
        See signature.

    Returns
    -------
    Mapping[str, str]
    """

    if values is None:
        return {}
    return {
        str(sensitivity_id): str(value)
        for sensitivity_id, value in zip(batch.sensitivity_ids, values)
        if value is not None
    }
