"""Non-GIRR vega weighting validation compatibility exports."""

from __future__ import annotations

from frtb_sbm.risk_classes.vega_batch_validation import _validate_non_girr_vega_batch_row
from frtb_sbm.risk_classes.vega_row_validation import _validate_non_girr_vega_sensitivity

__all__ = [
    "_validate_non_girr_vega_batch_row",
    "_validate_non_girr_vega_sensitivity",
]
