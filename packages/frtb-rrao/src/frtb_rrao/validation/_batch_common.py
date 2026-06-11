"""Shared helpers for RRAO batch validation stages."""

from __future__ import annotations

from typing import Any, cast

import numpy as np
import numpy.typing as npt

from frtb_rrao._batch_columns import ObjectArray
from frtb_rrao.validation._errors import RraoInputError


def position_id_at_first(batch: Any, mask: npt.NDArray[np.bool_]) -> str:
    """Return the position id at the first true mask location.

    Parameters
    ----------
    batch : RraoPositionBatch
        Canonical RRAO position batch.
    mask : numpy.ndarray
        Boolean mask with at least one true value.

    Returns
    -------
    str
        Position id from the first true mask location.
    """

    index = int(np.nonzero(mask)[0][0])
    return cast(str, batch.position_ids[index])


def require_non_empty_object_column(
    batch: Any,
    values: ObjectArray,
    *,
    field: str,
) -> None:
    """Require non-empty text in a whole batch column.

    Parameters
    ----------
    batch : RraoPositionBatch
        Canonical RRAO position batch.
    values : numpy.ndarray
        Object column to validate.
    field : str
        Field name used in validation errors.
    """

    mask = values == ""
    if bool(np.any(mask)):
        raise RraoInputError(
            "non-empty text is required",
            field=field,
            position_id=position_id_at_first(batch, mask),
        )


def require_text_where(
    batch: Any,
    values: ObjectArray,
    mask: npt.NDArray[np.bool_],
    *,
    field: str,
) -> None:
    """Require non-empty text where a boolean mask is true.

    Parameters
    ----------
    batch : RraoPositionBatch
        Canonical RRAO position batch.
    values : numpy.ndarray
        Object column to validate.
    mask : numpy.ndarray
        Boolean mask selecting rows where text is required.
    field : str
        Field name used in validation errors.
    """

    missing = mask & (values == None)  # noqa: E711
    if bool(np.any(missing)):
        raise RraoInputError(
            "non-empty text is required",
            field=field,
            position_id=position_id_at_first(batch, missing),
        )


__all__ = ["position_id_at_first", "require_non_empty_object_column", "require_text_where"]
