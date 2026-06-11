"""Compatibility exports for DRC CTP kernel calculations."""

from frtb_drc.kernel import ctp as _ctp
from frtb_drc.kernel.ctp import *  # noqa: F403

__all__ = _ctp.__all__
