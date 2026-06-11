"""Compatibility exports for BA-CVA batch capital kernels."""

from __future__ import annotations

from frtb_cva.kernel.ba_full import calculate_full_portfolio_from_batches
from frtb_cva.kernel.ba_reduced import calculate_reduced_portfolio_from_batches

__all__ = [
    "calculate_full_portfolio_from_batches",
    "calculate_reduced_portfolio_from_batches",
]
