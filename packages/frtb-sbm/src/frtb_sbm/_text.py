"""Package-local text validation helpers for SBM."""

from __future__ import annotations

from frtb_sbm._errors import SbmInputError


def require_text(value: object, field: str, sensitivity_id: str = "") -> str:
    """Return stripped non-empty text or raise the package input error.
    Parameters
    ----------
    value : object
        See signature.
    field : str
        See signature.
    sensitivity_id : str, optional
        See signature.

    Returns
    -------
    str
    """

    if not isinstance(value, str) or not value.strip():
        raise SbmInputError(
            "non-empty text is required",
            field=field,
            sensitivity_id=sensitivity_id,
        )
    return value.strip()
