"""Unified capital contribution types for analytical Euler decomposition."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar

from frtb_common.serialization import dataclass_as_dict

DEFAULT_RECONCILIATION_TOLERANCE = 1e-6


class AttributionMethod(StrEnum):
    """Supported attribution method labels."""

    ANALYTICAL_EULER = "ANALYTICAL_EULER"
    STANDALONE = "STANDALONE"
    RESIDUAL = "RESIDUAL"
    UNSUPPORTED = "UNSUPPORTED"


class ReconciliationStatus(StrEnum):
    """Reconciliation state for a set of contribution records at one aggregation level.

    A set is RECONCILED when ``sum(contribution) + sum(residual) == capital``
    within epsilon = 1e-6 (relative to total capital).
    """

    RECONCILED = "RECONCILED"
    PARTIAL_RESIDUAL = "PARTIAL_RESIDUAL"
    UNRECONCILED = "UNRECONCILED"
    UNKNOWN = "UNKNOWN"


EnumT = TypeVar("EnumT", bound=StrEnum)


def _coerce_enum(value: EnumT | str, enum_type: type[EnumT], field_name: str) -> EnumT:
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in enum_type)
        raise ValueError(f"{field_name} must be one of: {allowed}") from exc


@dataclass(frozen=True)
class CapitalContribution:
    """Stable, package-neutral view of one capital source attribution record.

    Sign convention: ``base_amount`` and ``contribution`` are non-negative for
    positive capital charges, or signed according to the default-risk direction
    specified in the underlying component.

    Audit fields (``citations``, ``input_hash``, ``profile_hash``,
    ``reconciliation_status``) default to empty / UNKNOWN so existing callers
    are unaffected.  Packages are encouraged to populate them for full
    traceability; see ADR 0038.
    """

    contribution_id: str
    source_id: str
    source_level: str
    bucket_key: str | None
    category: str
    base_amount: float
    marginal_multiplier: float | None
    contribution: float | None
    method: AttributionMethod | str
    residual: float = 0.0
    reason: str = ""
    citations: tuple[str, ...] = ()
    input_hash: str = ""
    profile_hash: str = ""
    reconciliation_status: ReconciliationStatus | str = ReconciliationStatus.UNKNOWN

    def __post_init__(self) -> None:
        coerced_method = _coerce_enum(self.method, AttributionMethod, "method")
        object.__setattr__(self, "method", coerced_method)
        coerced_status = _coerce_enum(
            self.reconciliation_status, ReconciliationStatus, "reconciliation_status"
        )
        object.__setattr__(self, "reconciliation_status", coerced_status)
        if coerced_method == AttributionMethod.ANALYTICAL_EULER:
            if self.marginal_multiplier is None:
                raise ValueError(
                    "marginal_multiplier must not be None when method is ANALYTICAL_EULER"
                )
            if self.contribution is None:
                raise ValueError("contribution must not be None when method is ANALYTICAL_EULER")

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable dictionary representation.

        Returns
        -------
        dict[str, object]
            Dataclass field names mapped through :func:`frtb_common.serialization.jsonable`.
        """
        return dataclass_as_dict(self)


@dataclass(frozen=True)
class ContributionReconciliation:
    """Package-neutral reconciliation report for a contribution set.

    Parameters
    ----------
    record_count : int
        Number of contribution records assessed.
    contribution_sum : float
        Sum of non-null ``contribution`` values.
    residual_sum : float
        Sum of ``residual`` values.
    explained_total : float
        ``contribution_sum + residual_sum``.
    capital_total : float
        Target capital amount supplied by the caller.
    difference : float
        ``explained_total - capital_total``.
    tolerance : float
        Absolute tolerance applied to the comparison.
    status : ReconciliationStatus
        ``RECONCILED`` when no residual is needed, ``PARTIAL_RESIDUAL`` when
        residual records reconcile the set, otherwise ``UNRECONCILED``.
    """

    record_count: int
    contribution_sum: float
    residual_sum: float
    explained_total: float
    capital_total: float
    difference: float
    tolerance: float
    status: ReconciliationStatus

    @property
    def is_reconciled(self) -> bool:
        """Return whether the contribution set reconciles within tolerance."""

        return self.status in {
            ReconciliationStatus.RECONCILED,
            ReconciliationStatus.PARTIAL_RESIDUAL,
        }

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable dictionary representation.

        Returns
        -------
        dict[str, object]
            Dataclass field names mapped through :func:`frtb_common.serialization.jsonable`.
        """

        return dataclass_as_dict(self)


def reconcile_contribution_set(
    contributions: Sequence[CapitalContribution],
    capital_total: float,
    *,
    relative_tolerance: float = DEFAULT_RECONCILIATION_TOLERANCE,
) -> ContributionReconciliation:
    """Return package-neutral reconciliation details for contribution records.

    Parameters
    ----------
    contributions : Sequence[CapitalContribution]
        Contribution, residual, and unsupported records to compare with the
        target capital amount. ``None`` contributions are treated as zero.
    capital_total : float
        Target capital amount for the contribution set.
    relative_tolerance : float, optional
        Relative tolerance scaled by ``max(abs(capital_total), 1.0)``.

    Returns
    -------
    ContributionReconciliation
        Reconciliation report with sums, tolerance, difference, and status.

    Raises
    ------
    ValueError
        If any supplied numeric value or tolerance is non-finite.
    """

    tolerance = _absolute_reconciliation_tolerance(capital_total, relative_tolerance)
    contribution_sum = 0.0
    residual_sum = 0.0
    for record in contributions:
        contribution_amount = 0.0 if record.contribution is None else record.contribution
        _require_finite(contribution_amount, f"contribution {record.contribution_id}")
        _require_finite(record.residual, f"residual {record.contribution_id}")
        contribution_sum += contribution_amount
        residual_sum += record.residual

    explained_total = contribution_sum + residual_sum
    difference = explained_total - capital_total
    reconciled = abs(difference) <= tolerance
    status = (
        ReconciliationStatus.PARTIAL_RESIDUAL
        if reconciled and abs(residual_sum) > tolerance
        else ReconciliationStatus.RECONCILED
        if reconciled
        else ReconciliationStatus.UNRECONCILED
    )
    return ContributionReconciliation(
        record_count=len(contributions),
        contribution_sum=contribution_sum,
        residual_sum=residual_sum,
        explained_total=explained_total,
        capital_total=capital_total,
        difference=difference,
        tolerance=tolerance,
        status=status,
    )


def validate_contribution_reconciliation(
    contributions: Sequence[CapitalContribution],
    capital_total: float,
    *,
    relative_tolerance: float = DEFAULT_RECONCILIATION_TOLERANCE,
) -> ContributionReconciliation:
    """Validate that contribution plus residual amounts reconcile to capital.

    Parameters
    ----------
    contributions : Sequence[CapitalContribution]
        Contribution, residual, and unsupported records to validate.
    capital_total : float
        Target capital amount for the contribution set.
    relative_tolerance : float, optional
        Relative tolerance scaled by ``max(abs(capital_total), 1.0)``.

    Returns
    -------
    ContributionReconciliation
        Reconciliation report when the contribution set reconciles.

    Raises
    ------
    ValueError
        If the set is unreconciled or contains non-finite values.
    """

    reconciliation = reconcile_contribution_set(
        contributions,
        capital_total,
        relative_tolerance=relative_tolerance,
    )
    if not reconciliation.is_reconciled:
        raise ValueError(
            "sum of contributions + residuals "
            f"({reconciliation.explained_total:.6g}) does not match capital_total "
            f"({capital_total:.6g}) within tolerance {reconciliation.tolerance:.2e}"
        )
    return reconciliation


def _absolute_reconciliation_tolerance(
    capital_total: float,
    relative_tolerance: float,
) -> float:
    _require_finite(capital_total, "capital_total")
    _require_finite(relative_tolerance, "relative_tolerance")
    if relative_tolerance < 0.0:
        raise ValueError("relative_tolerance must be non-negative")
    return relative_tolerance * max(abs(capital_total), 1.0)


def _require_finite(value: float, field_name: str) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{field_name} must be finite")


__all__ = [
    "DEFAULT_RECONCILIATION_TOLERANCE",
    "AttributionMethod",
    "CapitalContribution",
    "ContributionReconciliation",
    "ReconciliationStatus",
    "reconcile_contribution_set",
    "validate_contribution_reconciliation",
]
