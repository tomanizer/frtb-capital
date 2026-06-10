"""Compatibility exports for BA-CVA batch capital kernels."""

from __future__ import annotations

from frtb_cva._ba_full_batch_kernel import calculate_full_portfolio_from_batches
from frtb_cva._ba_reduced_batch_kernel import calculate_reduced_portfolio_from_batches

__all__ = [
    "calculate_full_portfolio_from_batches",
    "calculate_reduced_portfolio_from_batches",
]
