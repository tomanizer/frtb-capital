"""Compatibility exports for DRC securitisation non-CTP kernel calculations."""

from frtb_drc.kernel import securitisation as _securitisation
from frtb_drc.kernel.securitisation import *  # noqa: F403

__all__ = _securitisation.__all__
