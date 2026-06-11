"""Compatibility exports for SBM CRIF adapters."""

from __future__ import annotations

from frtb_sbm.adapters.crif_arrow import (
    normalize_girr_delta_crif_arrow_table,
    normalize_girr_delta_crif_records,
)
from frtb_sbm.adapters.crif_models import SbmAdapterResult, SbmAdapterWarning, SbmRejectedRow
from frtb_sbm.adapters.crif_rows import adapt_crif_records
from frtb_sbm.data_models import SbmSensitivity as SbmSensitivity

__all__ = [
    "SbmAdapterResult",
    "SbmAdapterWarning",
    "SbmRejectedRow",
    "adapt_crif_records",
    "normalize_girr_delta_crif_arrow_table",
    "normalize_girr_delta_crif_records",
]
