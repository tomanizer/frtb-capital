"""Standardised Approach component composition.

Orchestration owns SA composition but never imports component packages. It
consumes the shared :class:`frtb_common.ComponentCapitalSummary` shape that each
SA component projects via its own ``to_component_summary`` adapter. This
keeps orchestration decoupled from component-internal result fields and avoids
any sibling capital-package import.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from frtb_common import CalculationScope, CalculationScopeLevel, ComponentCapitalSummary

from frtb_orchestration._standardised_models import (
    StandardisedApproachCapitalResult,
    StandardisedComponentSubtotal,
    StandardisedFallbackRoute,
)
from frtb_orchestration._standardised_validation import (
    normalise_fallback_routes as _normalise_fallback_routes,
)
from frtb_orchestration._standardised_validation import (
    normalise_result_run_id as _normalise_result_run_id,
)
from frtb_orchestration._standardised_validation import (
    resolve_required_standardised_summaries as _resolve_required_standardised_summaries,
)
from frtb_orchestration._standardised_validation import standardised_jurisdiction_family
from frtb_orchestration._standardised_validation import unique_texts as _unique_texts
from frtb_orchestration._validation import OrchestrationInputError

_FALLBACK_DESK_IDS_METADATA_KEY = "fallback_desk_ids"


def compose_standardised_approach_capital(
    *,
    sbm_summary: ComponentCapitalSummary | None = None,
    drc_summary: ComponentCapitalSummary | None = None,
    rrao_summary: ComponentCapitalSummary | None = None,
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
    Parameters
    ----------
    sbm_summary : ComponentCapitalSummary | None, optional
        Sbm summary.
    drc_summary : ComponentCapitalSummary | None, optional
        Drc summary.
    rrao_summary : ComponentCapitalSummary | None, optional
        Rrao summary.
    ima_desk_eligibility : Mapping[str, object] | None, optional
        Ima desk eligibility.
    run_id : str | None, optional
        Run id.

    Returns
    -------
    StandardisedApproachCapitalResult
        Result of the operation.
    """

    required_summaries = _resolve_required_standardised_summaries(
        sbm_summary=sbm_summary,
        drc_summary=drc_summary,
        rrao_summary=rrao_summary,
    )
    total_capital = math.fsum(summary.total_capital for summary in required_summaries)
    if not math.isfinite(total_capital):
        raise OrchestrationInputError(
            "SA total capital must be finite after component aggregation",
            field="total_capital",
        )

    jurisdiction_family = standardised_jurisdiction_family(required_summaries[0].profile_id)
    component_subtotals = tuple(
        StandardisedComponentSubtotal.from_summary(summary) for summary in required_summaries
    )
    fallback_routes = _normalise_fallback_routes(ima_desk_eligibility)
    _validate_fallback_scope_evidence(required_summaries, fallback_routes)
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


def _validate_fallback_scope_evidence(
    summaries: Sequence[ComponentCapitalSummary],
    fallback_routes: Sequence[StandardisedFallbackRoute],
) -> None:
    if not fallback_routes:
        return

    missing = tuple(
        summary.component.value for summary in summaries if summary.calculation_scope is None
    )
    if missing:
        raise OrchestrationInputError(
            "SA fallback routes require calculation_scope evidence on every component summary; "
            f"missing for {', '.join(missing)}",
            field="calculation_scope",
        )

    scopes = tuple(summary.calculation_scope for summary in summaries)
    assert all(scope is not None for scope in scopes)
    first_scope = scopes[0]
    assert first_scope is not None
    first_payload = first_scope.as_dict()
    if any(scope.as_dict() != first_payload for scope in scopes[1:] if scope is not None):
        raise OrchestrationInputError(
            "SA fallback component summaries must carry identical calculation_scope evidence",
            field="calculation_scope",
        )

    fallback_desk_ids = tuple(route.desk_id for route in fallback_routes)
    if not _scope_covers_fallback_desk_ids(first_scope, fallback_desk_ids):
        raise OrchestrationInputError(
            "SA fallback calculation_scope does not cover the routed fallback desks; "
            f"expected {', '.join(fallback_desk_ids)}",
            field="calculation_scope",
        )


def _scope_covers_fallback_desk_ids(
    scope: CalculationScope,
    fallback_desk_ids: Sequence[str],
) -> bool:
    expected = tuple(sorted(fallback_desk_ids))
    if scope.level is CalculationScopeLevel.DESK:
        return expected == (scope.desk_id,)
    covered = scope.metadata.get(_FALLBACK_DESK_IDS_METADATA_KEY)
    if covered is None:
        return False
    actual = tuple(sorted(desk_id.strip() for desk_id in covered.split(",") if desk_id.strip()))
    return actual == expected


__all__ = [
    "OrchestrationInputError",
    "StandardisedApproachCapitalResult",
    "StandardisedComponentSubtotal",
    "StandardisedFallbackRoute",
    "compose_standardised_approach_capital",
    "standardised_jurisdiction_family",
]
