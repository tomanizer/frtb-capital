"""Standardised Approach composition result records."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from frtb_common import CalculationScope, ComponentCapitalSummary, StandardisedComponent

from frtb_orchestration._validation import OrchestrationInputError
from frtb_orchestration._validation import require_non_empty_text as _require_non_empty_text
from frtb_orchestration._validation import (
    require_non_negative_finite_number as _require_non_negative_finite_number,
)
from frtb_orchestration._validation import (
    require_non_negative_int as _require_non_negative_int,
)
from frtb_orchestration._validation import require_text_tuple as _require_text_tuple
from frtb_orchestration._validation import require_tuple_of as _require_tuple_of

_IMA_ELIGIBLE = "IMA_ELIGIBLE"
_SA_FALLBACK = "SA_FALLBACK"
_STANDARDISED_APPROACH_ROUTE = "STANDARDISED_APPROACH"
_SA_FALLBACK_REASON_CODE = "ima_desk_not_model_eligible"

# Maps every known SA component profile_id to a jurisdiction family.
# Components from different families must never be composed into a single SA charge.
# Basel note: SBM uses "BASEL_MAR21", RRAO uses "BASEL_MAR23", and DRC would use
# "BASEL_MAR22" — three different MAR chapter labels, one Basel jurisdiction.
# See ADR 0022.
_SA_JURISDICTION_FAMILY: dict[str, str] = {
    "BASEL_MAR21": "BASEL",
    "BASEL_MAR22": "BASEL",
    "BASEL_MAR23": "BASEL",
    "US_NPR_2_0": "US_NPR",
    "EU_CRR3": "EU_CRR3",
}


@dataclass(frozen=True)
class StandardisedComponentSubtotal:
    """Audit-ready subtotal contributed by one SA component summary."""

    component: StandardisedComponent
    package_name: str
    run_id: str
    profile_id: str
    profile_hash: str
    input_hash: str
    total_capital: float
    line_count: int
    excluded_line_count: int
    subtotal_count: int
    calculation_scope: CalculationScope | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.component, StandardisedComponent):
            raise OrchestrationInputError(
                "component subtotal component must be a StandardisedComponent",
                field="component",
            )
        _require_non_empty_text(self.package_name, "package_name")
        _require_non_empty_text(self.run_id, "run_id")
        _require_non_empty_text(self.profile_id, "profile_id")
        _require_non_empty_text(self.profile_hash, "profile_hash")
        _require_non_empty_text(self.input_hash, "input_hash")
        object.__setattr__(
            self,
            "total_capital",
            _require_non_negative_finite_number(self.total_capital, "total_capital"),
        )
        _require_non_negative_int(self.line_count, "line_count")
        _require_non_negative_int(self.excluded_line_count, "excluded_line_count")
        _require_non_negative_int(self.subtotal_count, "subtotal_count")
        if self.calculation_scope is not None and not isinstance(
            self.calculation_scope, CalculationScope
        ):
            raise OrchestrationInputError(
                "calculation_scope must be a CalculationScope when supplied",
                field="calculation_scope",
            )

    @classmethod
    def from_summary(cls, summary: ComponentCapitalSummary) -> StandardisedComponentSubtotal:
        """Build a subtotal record from a shared component summary.

        Parameters
        ----------
        summary : ComponentCapitalSummary
            Public component summary produced by an SA component package.

        Returns
        -------
        StandardisedComponentSubtotal
            Audit-ready subtotal projected from the shared summary.
        """

        return cls(
            component=summary.component,
            package_name=summary.package_name,
            run_id=summary.run_id,
            profile_id=summary.profile_id,
            profile_hash=summary.profile_hash,
            input_hash=summary.input_hash,
            total_capital=summary.total_capital,
            line_count=summary.line_count,
            excluded_line_count=summary.excluded_line_count,
            subtotal_count=summary.subtotal_count,
            calculation_scope=summary.calculation_scope,
        )

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic audit payload for this component subtotal.

        Returns
        -------
        dict[str, object]
            Result of the operation.
        """

        payload: dict[str, object] = {
            "component": self.component.value,
            "package_name": self.package_name,
            "run_id": self.run_id,
            "profile_id": self.profile_id,
            "profile_hash": self.profile_hash,
            "input_hash": self.input_hash,
            "total_capital": self.total_capital,
            "line_count": self.line_count,
            "excluded_line_count": self.excluded_line_count,
            "subtotal_count": self.subtotal_count,
        }
        if self.calculation_scope is not None:
            payload["calculation_scope"] = self.calculation_scope.as_dict()
        return payload


@dataclass(frozen=True)
class StandardisedFallbackRoute:
    """Desk-level route from IMA ineligibility to the SA fallback stack."""

    desk_id: str
    source_eligibility_status: str = _SA_FALLBACK
    route: str = _STANDARDISED_APPROACH_ROUTE
    reason_code: str = _SA_FALLBACK_REASON_CODE

    def __post_init__(self) -> None:
        _require_non_empty_text(self.desk_id, "desk_id")
        if self.source_eligibility_status != _SA_FALLBACK:
            raise OrchestrationInputError(
                "fallback route source_eligibility_status must be SA_FALLBACK",
                field="source_eligibility_status",
            )
        if self.route != _STANDARDISED_APPROACH_ROUTE:
            raise OrchestrationInputError(
                "fallback route route must be STANDARDISED_APPROACH",
                field="route",
            )
        _require_non_empty_text(self.reason_code, "reason_code")

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic audit payload for this fallback route.

        Returns
        -------
        dict[str, object]
            Result of the operation.
        """

        return {
            "desk_id": self.desk_id,
            "source_eligibility_status": self.source_eligibility_status,
            "route": self.route,
            "reason_code": self.reason_code,
        }


@dataclass(frozen=True)
class StandardisedApproachCapitalResult:
    """Composed Standardised Approach capital result.

    Regulatory composition: SA capital equals SBM + DRC + RRAO. Component
    summaries retain the MAR21/MAR22/MAR23, US NPR 2.0, or EU CRR3 calculation
    citations supplied by the owning packages.
    """

    run_id: str
    calculation_date: date
    base_currency: str
    jurisdiction_family: str
    total_capital: float
    component_subtotals: tuple[StandardisedComponentSubtotal, ...]
    fallback_routes: tuple[StandardisedFallbackRoute, ...]
    citations: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        if not isinstance(self.calculation_date, date):
            raise OrchestrationInputError(
                "calculation_date must be a date", field="calculation_date"
            )
        _require_non_empty_text(self.base_currency, "base_currency")
        if self.jurisdiction_family not in set(_SA_JURISDICTION_FAMILY.values()):
            raise OrchestrationInputError(
                "jurisdiction_family must be a known SA jurisdiction family",
                field="jurisdiction_family",
            )
        object.__setattr__(
            self,
            "total_capital",
            _require_non_negative_finite_number(self.total_capital, "total_capital"),
        )
        _require_tuple_of(
            self.component_subtotals, StandardisedComponentSubtotal, "component_subtotals"
        )
        _require_component_subtotal_set(self.component_subtotals)
        expected_total = math.fsum(subtotal.total_capital for subtotal in self.component_subtotals)
        # This is a capital-total reconciliation guard, not a bit-identical drift check.
        # Use both absolute and relative tolerances so large-but-equivalent totals do not
        # fail only because of IEEE-754 representation limits.
        if not math.isclose(self.total_capital, expected_total, rel_tol=1e-12, abs_tol=1e-12):
            raise OrchestrationInputError(
                "total_capital must reconcile to component_subtotals",
                field="total_capital",
            )
        _require_tuple_of(self.fallback_routes, StandardisedFallbackRoute, "fallback_routes")
        _require_text_tuple(self.citations, "citations")
        _require_text_tuple(self.warnings, "warnings")

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic audit payload for the composed SA result.

        Returns
        -------
        dict[str, object]
            Result of the operation.
        """

        return {
            "run_id": self.run_id,
            "calculation_date": self.calculation_date.isoformat(),
            "base_currency": self.base_currency,
            "jurisdiction_family": self.jurisdiction_family,
            "total_capital": self.total_capital,
            "component_subtotals": [subtotal.as_dict() for subtotal in self.component_subtotals],
            "fallback_routes": [route.as_dict() for route in self.fallback_routes],
            "citations": list(self.citations),
            "warnings": list(self.warnings),
        }


def _require_component_subtotal_set(
    subtotals: tuple[StandardisedComponentSubtotal, ...],
) -> None:
    components = tuple(subtotal.component for subtotal in subtotals)
    expected = (
        StandardisedComponent.SBM,
        StandardisedComponent.DRC,
        StandardisedComponent.RRAO,
    )
    if components != expected:
        expected_label = ", ".join(component.value for component in expected)
        actual_label = ", ".join(component.value for component in components)
        raise OrchestrationInputError(
            "component_subtotals must contain SBM, DRC, and RRAO in aggregation order; "
            f"got {actual_label or '<empty>'}, expected {expected_label}",
            field="component_subtotals",
        )


__all__ = [
    "StandardisedApproachCapitalResult",
    "StandardisedComponentSubtotal",
    "StandardisedFallbackRoute",
]
