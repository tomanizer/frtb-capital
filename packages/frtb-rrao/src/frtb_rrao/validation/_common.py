"""Primitive validators shared by RRAO position-validation stages."""

from __future__ import annotations

import math

from frtb_rrao.validation._errors import RraoInputError


def _finite_float(value: object, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise RraoInputError("value must be numeric", field=field)
    number = float(value)
    if not math.isfinite(number):
        raise RraoInputError("value must be finite", field=field)
    return number


def _require_text(value: object, field: str, position_id: str = "") -> str:
    if not isinstance(value, str) or not value.strip():
        raise RraoInputError("non-empty text is required", field=field, position_id=position_id)
    return value
