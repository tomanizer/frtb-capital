"""Unified capital contribution types for analytical Euler decomposition."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TypeVar

from frtb_common.serialization import dataclass_as_dict


class AttributionMethod(StrEnum):
    """Supported attribution method labels."""

    ANALYTICAL_EULER = "ANALYTICAL_EULER"
    STANDALONE = "STANDALONE"
    RESIDUAL = "RESIDUAL"
    UNSUPPORTED = "UNSUPPORTED"


class ReconciliationStatus(StrEnum):
    """Reconciliation state for a set of contribution records at one aggregation level.

    A set is RECONCILED when ``sum(contribution) + sum(residual) == capital``
    within ε = 1e-6 (relative to total capital).
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
