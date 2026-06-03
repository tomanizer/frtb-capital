"""Standardised Approach component composition.

Orchestration owns SA composition but never imports component packages. It
consumes the shared :class:`frtb_common.ComponentCapitalSummary` shape that each
SA component projects via its own ``to_component_summary`` adapter. This
keeps orchestration decoupled from component-internal result fields and avoids
any sibling capital-package import.
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from frtb_common import (
    ComponentCapitalSummary,
    NotImplementedCapitalComponentError,
    StandardisedComponent,
)

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

_IMA_ELIGIBLE = "IMA_ELIGIBLE"
_SA_FALLBACK = "SA_FALLBACK"
_STANDARDISED_APPROACH_ROUTE = "STANDARDISED_APPROACH"
_SA_FALLBACK_REASON_CODE = "ima_desk_not_model_eligible"


class OrchestrationInputError(ValueError):
    """Raised when a component summary cannot be consumed by orchestration."""

    def __init__(self, message: str, *, field: str = "") -> None:
        self.field = field
        super().__init__(message)


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

    @classmethod
    def from_summary(cls, summary: ComponentCapitalSummary) -> StandardisedComponentSubtotal:
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
        )

    @classmethod
    def from_handoff(cls, handoff: ComponentCapitalSummary) -> StandardisedComponentSubtotal:
        """Deprecated alias for :meth:`from_summary`."""

        warnings.warn(
            "StandardisedComponentSubtotal.from_handoff is deprecated; use from_summary",
            DeprecationWarning,
            stacklevel=2,
        )
        return cls.from_summary(handoff)

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic audit payload for this component subtotal."""

        return {
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
        """Return a deterministic audit payload for this fallback route."""

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
    handoffs retain the MAR21/MAR22/MAR23, US NPR 2.0, or EU CRR3 calculation
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
        """Return a deterministic audit payload for the composed SA result."""

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


def compose_standardised_approach_capital(
    *,
    sbm_summary: ComponentCapitalSummary | None = None,
    drc_summary: ComponentCapitalSummary | None = None,
    rrao_summary: ComponentCapitalSummary | None = None,
    sbm_handoff: ComponentCapitalSummary | None = None,
    drc_handoff: ComponentCapitalSummary | None = None,
    rrao_handoff: ComponentCapitalSummary | None = None,
    ima_desk_eligibility: Mapping[str, object] | None = None,
    run_id: str | None = None,
) -> StandardisedApproachCapitalResult:
    """Compose Standardised Approach capital from SBM, DRC, and RRAO summaries.

    Each argument is the shared ``ComponentCapitalSummary`` produced by the
    owning package's ``to_component_summary`` adapter. The function validates
    component slots, regulatory jurisdiction family (ADR 0022), calculation
    date, and base currency before applying the additive SA formula:
    ``SBM + DRC + RRAO``.

    ``ima_desk_eligibility`` may carry desk ids mapped to structural eligibility
    values such as ``"IMA_ELIGIBLE"`` or ``"SA_FALLBACK"``. Desks marked
    ``SA_FALLBACK`` are recorded as routed to the Standardised Approach stack
    without importing ``frtb_ima``.
    """

    required_summaries = _resolve_required_standardised_summaries(
        sbm_summary=sbm_summary,
        drc_summary=drc_summary,
        rrao_summary=rrao_summary,
        sbm_handoff=sbm_handoff,
        drc_handoff=drc_handoff,
        rrao_handoff=rrao_handoff,
    )
    total_capital = math.fsum(summary.total_capital for summary in required_summaries)
    if not math.isfinite(total_capital):
        raise OrchestrationInputError(
            "SA total capital must be finite after component aggregation",
            field="total_capital",
        )

    jurisdiction_family = _jurisdiction_family(required_summaries[0])
    component_subtotals = tuple(
        StandardisedComponentSubtotal.from_summary(summary) for summary in required_summaries
    )
    fallback_routes = _normalise_fallback_routes(ima_desk_eligibility)
    citations = _unique_texts(
        citation for summary in required_summaries for citation in summary.citations
    )
    warnings = _unique_texts(
        warning for summary in required_summaries for warning in summary.warnings
    )
    return StandardisedApproachCapitalResult(
        run_id=_normalise_result_run_id(run_id, required_summaries),
        calculation_date=required_summaries[0].calculation_date,
        base_currency=required_summaries[0].base_currency,
        jurisdiction_family=jurisdiction_family,
        total_capital=total_capital,
        component_subtotals=component_subtotals,
        fallback_routes=fallback_routes,
        citations=citations,
        warnings=warnings,
    )


def standardised_jurisdiction_family(profile_id: str) -> str:
    """Return the ADR 0022 SA jurisdiction family for a public profile id."""

    _require_non_empty_text(profile_id, "profile_id")
    family = _SA_JURISDICTION_FAMILY.get(profile_id)
    if family is None:
        raise OrchestrationInputError(
            f"profile_id {profile_id!r} is not recognised as a known SA jurisdiction profile",
            field="profile_id",
        )
    return family


def _resolve_required_standardised_summaries(
    *,
    sbm_summary: ComponentCapitalSummary | None,
    drc_summary: ComponentCapitalSummary | None,
    rrao_summary: ComponentCapitalSummary | None,
    sbm_handoff: ComponentCapitalSummary | None,
    drc_handoff: ComponentCapitalSummary | None,
    rrao_handoff: ComponentCapitalSummary | None,
) -> tuple[ComponentCapitalSummary, ComponentCapitalSummary, ComponentCapitalSummary]:
    sbm_summary, drc_summary, rrao_summary = _coalesce_standardised_summaries(
        sbm_summary=sbm_summary,
        drc_summary=drc_summary,
        rrao_summary=rrao_summary,
        sbm_handoff=sbm_handoff,
        drc_handoff=drc_handoff,
        rrao_handoff=rrao_handoff,
    )
    _require_component(rrao_summary, StandardisedComponent.RRAO, "rrao_summary")
    _require_component(drc_summary, StandardisedComponent.DRC, "drc_summary")
    _require_component(sbm_summary, StandardisedComponent.SBM, "sbm_summary")

    summaries = [
        summary for summary in (rrao_summary, drc_summary, sbm_summary) if summary is not None
    ]
    _assert_consistent_jurisdiction(summaries)
    missing = _missing_standardised_components(
        sbm_summary=sbm_summary,
        drc_summary=drc_summary,
        rrao_summary=rrao_summary,
    )
    if missing:
        raise NotImplementedCapitalComponentError(
            component="frtb-orchestration",
            feature=(
                "standardised approach aggregation; missing required component "
                f"outputs: {', '.join(component.value for component in missing)}"
            ),
        )

    assert sbm_summary is not None
    assert drc_summary is not None
    assert rrao_summary is not None
    required_summaries = (sbm_summary, drc_summary, rrao_summary)
    _assert_consistent_run_context(required_summaries)
    for summary in required_summaries:
        _assert_non_negative_component_capital(summary)
    return required_summaries


def _require_component(
    summary: ComponentCapitalSummary | None,
    expected: StandardisedComponent,
    param_name: str,
) -> None:
    if summary is None:
        return
    if not isinstance(summary, ComponentCapitalSummary):
        raise OrchestrationInputError(
            f"{param_name} must be a frtb_common.ComponentCapitalSummary",
            field=param_name,
        )
    if summary.component is not expected:
        raise OrchestrationInputError(
            f"{param_name} carries a {summary.component.value} summary but "
            f"{expected.value} was expected",
            field=param_name,
        )


def _coalesce_summary_keyword(
    new_name: str,
    new_value: ComponentCapitalSummary | None,
    old_name: str,
    old_value: ComponentCapitalSummary | None,
) -> ComponentCapitalSummary | None:
    if old_value is None:
        return new_value
    if new_value is not None:
        raise OrchestrationInputError(
            f"{new_name} and deprecated {old_name} cannot both be supplied",
            field=new_name,
        )
    warnings.warn(
        f"{old_name} is deprecated; use {new_name}",
        DeprecationWarning,
        stacklevel=5,
    )
    return old_value


def _coalesce_standardised_summaries(
    *,
    sbm_summary: ComponentCapitalSummary | None,
    drc_summary: ComponentCapitalSummary | None,
    rrao_summary: ComponentCapitalSummary | None,
    sbm_handoff: ComponentCapitalSummary | None,
    drc_handoff: ComponentCapitalSummary | None,
    rrao_handoff: ComponentCapitalSummary | None,
) -> tuple[
    ComponentCapitalSummary | None,
    ComponentCapitalSummary | None,
    ComponentCapitalSummary | None,
]:
    return (
        _coalesce_summary_keyword("sbm_summary", sbm_summary, "sbm_handoff", sbm_handoff),
        _coalesce_summary_keyword("drc_summary", drc_summary, "drc_handoff", drc_handoff),
        _coalesce_summary_keyword("rrao_summary", rrao_summary, "rrao_handoff", rrao_handoff),
    )


def _assert_consistent_jurisdiction(handoffs: Sequence[ComponentCapitalSummary]) -> None:
    """Raise OrchestrationInputError when supplied components span multiple jurisdictions."""

    families: dict[StandardisedComponent, tuple[str, str]] = {}
    for handoff in handoffs:
        family = _jurisdiction_family(handoff)
        families[handoff.component] = (handoff.profile_id, family)

    unique_families = {family for _, family in families.values()}
    if len(unique_families) > 1:
        detail = ", ".join(
            f"{component.value}={profile_id!r}"
            for component, (profile_id, _) in sorted(families.items(), key=lambda item: item[0])
        )
        raise OrchestrationInputError(
            "SA components must share the same regulatory jurisdiction; "
            f"mixed profiles supplied: {detail}. "
            "All components must be from the same family (Basel, US_NPR, or EU_CRR3). "
            "See ADR 0022.",
            field="profile_id",
        )


def _missing_standardised_components(
    *,
    sbm_summary: ComponentCapitalSummary | None,
    drc_summary: ComponentCapitalSummary | None,
    rrao_summary: ComponentCapitalSummary | None,
) -> tuple[StandardisedComponent, ...]:
    missing: list[StandardisedComponent] = []
    if sbm_summary is None:
        missing.append(StandardisedComponent.SBM)
    if drc_summary is None:
        missing.append(StandardisedComponent.DRC)
    if rrao_summary is None:
        missing.append(StandardisedComponent.RRAO)
    return tuple(missing)


def _jurisdiction_family(handoff: ComponentCapitalSummary) -> str:
    try:
        return standardised_jurisdiction_family(handoff.profile_id)
    except OrchestrationInputError as exc:
        raise OrchestrationInputError(
            f"{handoff.component.value} profile_id {handoff.profile_id!r} is not "
            "recognised as a known SA jurisdiction profile",
            field="profile_id",
        ) from exc


def _assert_consistent_run_context(handoffs: Sequence[ComponentCapitalSummary]) -> None:
    calculation_dates = {handoff.calculation_date for handoff in handoffs}
    if len(calculation_dates) > 1:
        detail = _context_detail(handoffs, "calculation_date")
        raise OrchestrationInputError(
            f"SA components must share the same calculation_date; mixed dates supplied: {detail}",
            field="calculation_date",
        )

    base_currencies = {handoff.base_currency for handoff in handoffs}
    if len(base_currencies) > 1:
        detail = _context_detail(handoffs, "base_currency")
        raise OrchestrationInputError(
            "SA components must share the same base_currency before aggregation; "
            f"mixed currencies supplied: {detail}",
            field="base_currency",
        )


def _assert_non_negative_component_capital(handoff: ComponentCapitalSummary) -> None:
    if handoff.total_capital < 0.0:
        raise OrchestrationInputError(
            f"{handoff.component.value} total_capital must be non-negative for SA composition",
            field="total_capital",
        )


def _normalise_result_run_id(
    run_id: str | None,
    handoffs: Sequence[ComponentCapitalSummary],
) -> str:
    if run_id is None:
        return _default_sa_run_id(handoffs)
    _require_non_empty_text(run_id, "run_id")
    return run_id


def _context_detail(handoffs: Sequence[ComponentCapitalSummary], field: str) -> str:
    return ", ".join(
        f"{handoff.component.value}={getattr(handoff, field)!r}"
        for handoff in sorted(handoffs, key=lambda item: item.component)
    )


def _default_sa_run_id(handoffs: Sequence[ComponentCapitalSummary]) -> str:
    return "sa:" + ":".join(handoff.run_id for handoff in handoffs)


def _normalise_fallback_routes(
    ima_desk_eligibility: Mapping[str, object] | None,
) -> tuple[StandardisedFallbackRoute, ...]:
    if ima_desk_eligibility is None:
        return ()
    if not isinstance(ima_desk_eligibility, Mapping):
        raise OrchestrationInputError(
            "ima_desk_eligibility must be a mapping of desk_id to eligibility status",
            field="ima_desk_eligibility",
        )

    routes: list[StandardisedFallbackRoute] = []
    entries: list[tuple[str, object]] = []
    for desk_id, raw_status in ima_desk_eligibility.items():
        if not isinstance(desk_id, str) or not desk_id:
            raise OrchestrationInputError(
                "ima_desk_eligibility keys must be non-empty desk_id strings",
                field="ima_desk_eligibility",
            )
        entries.append((desk_id, raw_status))

    for desk_id, raw_status in sorted(entries, key=lambda item: item[0]):
        status = _eligibility_status_value(raw_status)
        if status == _SA_FALLBACK:
            routes.append(StandardisedFallbackRoute(desk_id=desk_id))
        elif status != _IMA_ELIGIBLE:
            raise OrchestrationInputError(
                f"desk {desk_id!r} has unsupported eligibility status {status!r}; "
                f"expected {_IMA_ELIGIBLE!r} or {_SA_FALLBACK!r}",
                field="ima_desk_eligibility",
            )
    return tuple(routes)


def _eligibility_status_value(raw_status: object) -> str:
    value = getattr(raw_status, "value", raw_status)
    if not isinstance(value, str) or not value:
        raise OrchestrationInputError(
            "IMA desk eligibility status values must be non-empty strings or string enums",
            field="ima_desk_eligibility",
        )
    return value


def _unique_texts(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _require_non_empty_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise OrchestrationInputError(f"{field} must be non-empty text", field=field)


def _require_non_negative_finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OrchestrationInputError(f"{field} must be numeric", field=field)
    number = float(value)
    if not math.isfinite(number):
        raise OrchestrationInputError(f"{field} must be finite", field=field)
    if number < 0.0:
        raise OrchestrationInputError(f"{field} must be non-negative", field=field)
    return number


def _require_non_negative_int(value: object, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise OrchestrationInputError(f"{field} must be a non-negative integer", field=field)


def _require_text_tuple(value: object, field: str) -> None:
    if not isinstance(value, tuple) or not all(isinstance(item, str) for item in value):
        raise OrchestrationInputError(f"{field} must be a tuple of text values", field=field)


def _require_tuple_of(value: object, expected_type: type[object], field: str) -> None:
    if not isinstance(value, tuple) or not all(isinstance(item, expected_type) for item in value):
        raise OrchestrationInputError(
            f"{field} must be a tuple of {expected_type.__name__} values",
            field=field,
        )


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
    "OrchestrationInputError",
    "StandardisedApproachCapitalResult",
    "StandardisedComponentSubtotal",
    "StandardisedFallbackRoute",
    "compose_standardised_approach_capital",
    "standardised_jurisdiction_family",
]
