"""Standardised Approach default risk charge scaffold."""

from frtb_drc._version import __version__
from frtb_drc.scaffold import PACKAGE_METADATA, calculate_drc_capital

__all__ = ["PACKAGE_METADATA", "__version__", "calculate_drc_capital"]
