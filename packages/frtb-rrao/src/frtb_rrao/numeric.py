"""Shared numeric tolerances for RRAO reconciliation checks."""

from __future__ import annotations

import math

RRAO_RECONCILIATION_REL_TOLERANCE = 1e-12
RRAO_RECONCILIATION_ABS_TOLERANCE = 1e-9
RRAO_EXCLUDED_ADD_ON_ABS_TOLERANCE = 1e-12


def is_reconciled(actual: float, expected: float) -> bool:
    """Return whether two RRAO totals reconcile within the documented budget."""

    return math.isclose(
        actual,
        expected,
        rel_tol=RRAO_RECONCILIATION_REL_TOLERANCE,
        abs_tol=RRAO_RECONCILIATION_ABS_TOLERANCE,
    )


def is_zero_excluded_add_on(value: float) -> bool:
    """Return whether an excluded-line add-on is zero within the invariant tolerance."""

    return math.isclose(value, 0.0, rel_tol=0.0, abs_tol=RRAO_EXCLUDED_ADD_ON_ABS_TOLERANCE)


__all__ = [
    "RRAO_EXCLUDED_ADD_ON_ABS_TOLERANCE",
    "RRAO_RECONCILIATION_ABS_TOLERANCE",
    "RRAO_RECONCILIATION_REL_TOLERANCE",
    "is_reconciled",
    "is_zero_excluded_add_on",
]
