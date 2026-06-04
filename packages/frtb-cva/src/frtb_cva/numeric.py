"""Shared numeric tolerances for CVA reconciliation checks."""

from __future__ import annotations

import math

CVA_RECONCILIATION_REL_TOLERANCE = 1e-12  # aligned with frtb-rrao
CVA_RECONCILIATION_ABS_TOLERANCE = 1e-9


def is_reconciled(actual: float, expected: float) -> bool:
    """Return whether two CVA totals reconcile within the documented budget.

    Parameters
    ----------
    actual : float
        Observed capital or component total from the calculation path.
    expected : float
        Reference total expected from summed line items or components.

    Returns
    -------
    bool
        ``True`` when ``actual`` and ``expected`` are close per the CVA tolerances.
    """

    return math.isclose(
        actual,
        expected,
        rel_tol=CVA_RECONCILIATION_REL_TOLERANCE,
        abs_tol=CVA_RECONCILIATION_ABS_TOLERANCE,
    )


__all__ = [
    "CVA_RECONCILIATION_ABS_TOLERANCE",
    "CVA_RECONCILIATION_REL_TOLERANCE",
    "is_reconciled",
]
