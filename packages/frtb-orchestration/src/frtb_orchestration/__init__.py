"""Suite-level orchestration scaffold."""

from frtb_orchestration._version import __version__
from frtb_orchestration.scaffold import PACKAGE_METADATA, calculate_suite_capital

__all__ = ["PACKAGE_METADATA", "__version__", "calculate_suite_capital"]
