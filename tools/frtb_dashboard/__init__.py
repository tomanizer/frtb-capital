"""Compatibility package for the moved FRTB Navigator application.

New code should import from :mod:`frtb_navigator`.
"""

from frtb_navigator import PACKAGE_METADATA, __version__

__all__ = ["PACKAGE_METADATA", "__version__"]
