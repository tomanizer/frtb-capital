"""Shared numeric tolerances for SBM reconciliation checks."""

from __future__ import annotations

import math

SBM_RECONCILIATION_REL_TOLERANCE = 1e-12
SBM_RECONCILIATION_ABS_TOLERANCE = 1e-9


def is_reconciled(actual: float, expected: float) -> bool:
    """Return whether two SBM totals reconcile within the documented budget."""

    return math.isclose(
        actual,
        expected,
        rel_tol=SBM_RECONCILIATION_REL_TOLERANCE,
        abs_tol=SBM_RECONCILIATION_ABS_TOLERANCE,
    )


__all__ = [
    "SBM_RECONCILIATION_ABS_TOLERANCE",
    "SBM_RECONCILIATION_REL_TOLERANCE",
    "is_reconciled",
]
