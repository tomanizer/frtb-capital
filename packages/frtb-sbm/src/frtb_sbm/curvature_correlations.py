"""Compatibility facade for curvature correlation helpers.

Regulatory traceability:
    Basel MAR21.5, MAR21.96-MAR21.101, and SBM-CURV-001.
"""

from __future__ import annotations

from frtb_sbm.curvature_inter_correlations import (
    _bucket_sort_key,
    _build_curvature_inter_bucket_correlation_map,
    _curvature_inter_bucket_correlation,
    _curvature_inter_citation_ids,
    _curvature_intra_citation_ids,
)
from frtb_sbm.curvature_intra_correlations import (
    CurvatureCorrelationFactor,
    _curvature_intra_bucket_correlation,
    _required_factor_qualifier,
)
from frtb_sbm.curvature_intra_matrices import (
    _build_curvature_intra_bucket_correlation_matrix,
    _build_vectorized_curvature_intra_bucket_correlation_matrix,
)

__all__ = [
    "CurvatureCorrelationFactor",
    "_bucket_sort_key",
    "_build_curvature_inter_bucket_correlation_map",
    "_build_curvature_intra_bucket_correlation_matrix",
    "_build_vectorized_curvature_intra_bucket_correlation_matrix",
    "_curvature_inter_bucket_correlation",
    "_curvature_inter_citation_ids",
    "_curvature_intra_bucket_correlation",
    "_curvature_intra_citation_ids",
    "_required_factor_qualifier",
]
