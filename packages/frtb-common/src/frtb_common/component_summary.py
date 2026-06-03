"""Shared standardised-component summary contract.

Each Standardised Approach component package (`frtb-sbm`, `frtb-drc`,
`frtb-rrao`) projects its rich public capital result down to this small, stable
shape via its own ``to_component_summary`` adapter. ``frtb-orchestration``
consumes only this shape, so it never couples to component-internal result
fields and no component package needs to depend on orchestration.

This type is deliberately neutral: it carries audited identity, the additive
capital total, lineage hashes, coarse line/subtotal counts, and citations.
Component-specific breakdowns stay inside their owning package.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

__all__ = [
    "ComponentCapitalSummary",
    "ComponentSummaryError",
    "StandardisedComponent",
]


class ComponentSummaryError(ValueError):
    """Raised when a component summary violates the shared contract."""

    def __init__(self, message: str, *, field: str = "") -> None:
        self.field = field
        super().__init__(message)


class StandardisedComponent(StrEnum):
    """Standardised Approach component identifiers."""

    SBM = "SBM"
    DRC = "DRC"
    RRAO = "RRAO"


@dataclass(frozen=True)
class ComponentCapitalSummary:
    """Stable, package-neutral view of one SA component capital result.

    Sign convention: ``total_capital`` is a non-negative capital charge in
    ``base_currency``. Counts are coarse, audit-friendly cardinalities, not
    full breakdowns:

    - ``line_count`` — accepted input lines that contributed to the charge.
    - ``excluded_line_count`` — input lines rejected or excluded from capital.
    - ``subtotal_count`` — aggregated subtotals (risk classes / categories /
      residual-risk subtotals) carried in the owning package's result.
    """

    component: StandardisedComponent
    package_name: str
    run_id: str
    calculation_date: date
    base_currency: str
    profile_id: str
    total_capital: float
    profile_hash: str
    input_hash: str
    line_count: int
    excluded_line_count: int
    subtotal_count: int
    citations: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.component, StandardisedComponent):
            raise ComponentSummaryError(
                "component must be a StandardisedComponent", field="component"
            )
        _require_non_empty_text(self.package_name, "package_name")
        _require_non_empty_text(self.run_id, "run_id")
        if not isinstance(self.calculation_date, date):
            raise ComponentSummaryError("calculation_date must be a date", field="calculation_date")
        _require_non_empty_text(self.base_currency, "base_currency")
        _require_non_empty_text(self.profile_id, "profile_id")
        _require_non_empty_text(self.profile_hash, "profile_hash")
        _require_non_empty_text(self.input_hash, "input_hash")
        object.__setattr__(
            self, "total_capital", _require_finite_number(self.total_capital, "total_capital")
        )
        _require_non_negative_int(self.line_count, "line_count")
        _require_non_negative_int(self.excluded_line_count, "excluded_line_count")
        _require_non_negative_int(self.subtotal_count, "subtotal_count")
        _require_text_tuple(self.citations, "citations")
        _require_text_tuple(self.warnings, "warnings")


def _require_non_empty_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise ComponentSummaryError(f"{field} must be non-empty text", field=field)


def _require_finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ComponentSummaryError(f"{field} must be numeric", field=field)
    number = float(value)
    if not math.isfinite(number):
        raise ComponentSummaryError(f"{field} must be finite", field=field)
    return number


def _require_non_negative_int(value: object, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ComponentSummaryError(f"{field} must be a non-negative integer", field=field)


def _require_text_tuple(value: object, field: str) -> tuple[str, ...]:
    if not isinstance(value, tuple) or not all(isinstance(item, str) for item in value):
        raise ComponentSummaryError(f"{field} must be a tuple of text values", field=field)
    return value
