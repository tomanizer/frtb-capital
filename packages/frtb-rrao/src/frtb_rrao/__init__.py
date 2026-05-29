"""Standardised Approach residual risk add-on scaffold."""

from frtb_rrao._version import __version__
from frtb_rrao.scaffold import PACKAGE_METADATA, calculate_rrao_capital

__all__ = ["PACKAGE_METADATA", "__version__", "calculate_rrao_capital"]
