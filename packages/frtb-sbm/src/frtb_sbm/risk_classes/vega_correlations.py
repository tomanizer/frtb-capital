"""
Compatibility facade for non-GIRR vega correlation helpers.

Regulatory traceability:
    Basel MAR21.94-MAR21.95 — non-GIRR vega intra-bucket and
    inter-bucket correlations.
"""

from __future__ import annotations

from frtb_sbm.risk_classes.vega_correlation_maps import (
    build_non_girr_vega_inter_bucket_correlation_map,
)
from frtb_sbm.risk_classes.vega_correlation_matrices import (
    build_non_girr_vega_intra_bucket_correlation_matrix,
)
from frtb_sbm.risk_classes.vega_correlation_scalars import (
    non_girr_vega_intra_bucket_correlation,
)

__all__ = [
    "build_non_girr_vega_inter_bucket_correlation_map",
    "build_non_girr_vega_intra_bucket_correlation_matrix",
    "non_girr_vega_intra_bucket_correlation",
]
