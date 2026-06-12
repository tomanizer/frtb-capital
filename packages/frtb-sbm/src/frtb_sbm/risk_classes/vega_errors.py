"""Shared non-GIRR vega exceptions."""

from __future__ import annotations

from frtb_sbm.validation import SbmInputError


class UnsupportedNonGirrVegaPathError(SbmInputError):
    """Raised for inconsistent non-GIRR vega path requests."""


__all__ = ["UnsupportedNonGirrVegaPathError"]
