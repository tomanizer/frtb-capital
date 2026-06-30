"""Package-local DRC validation primitives."""

from __future__ import annotations

import math
from typing import Any, cast

from frtb_drc.validation import DrcInputError


def require_text(value: object | None, field_name: str) -> str:
    """Return stripped non-empty text or raise a DRC input error.
    Parameters
    ----------
    value : object | None
        Input value to validate.
    field_name : str
        Human-readable field label for error messages.

    Returns
    -------
    str
        Non-empty text value after validation.
    """

    text = optional_text(value)
    if text is None:
        raise DrcInputError(f"{field_name} must be non-empty")
    return text


def optional_text(value: object | None) -> str | None:
    """Return stripped optional text, normalising blanks to None.
    Parameters
    ----------
    value : object | None
        Input value to validate.

    Returns
    -------
    str | None
        Non-empty text value, or None when the input is absent.
    """

    if value is None:
        return None
    text = str(value).strip()
    return text or None


def require_finite_non_negative(value: object, field_name: str) -> float:
    """Return a finite non-negative float or raise a DRC input error.
    Parameters
    ----------
    value : object
        Input value to validate.
    field_name : str
        Human-readable field label for error messages.

    Returns
    -------
    float
        Finite non-negative numeric value after validation.
    """

    try:
        result = float(cast(Any, value))
    except (ValueError, TypeError) as exc:
        raise DrcInputError(f"{field_name} must be a valid finite number") from exc
    if not math.isfinite(result) or result < 0.0:
        raise DrcInputError(f"{field_name} must be finite and non-negative")
    return result


__all__ = ["optional_text", "require_finite_non_negative", "require_text"]
