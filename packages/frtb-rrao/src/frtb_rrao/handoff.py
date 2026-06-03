"""Orchestration handoff projection for public ``RraoCapitalResult`` records.

``frtb-orchestration`` consumes only the shared
``frtb_common.ComponentCapitalSummary`` shape, so this adapter is the single
stable bridge from the rich RRAO result to suite aggregation.
"""

from __future__ import annotations

import warnings

from frtb_common import ComponentCapitalSummary, StandardisedComponent

from frtb_rrao.data_models import RraoCapitalResult


def to_component_summary(result: RraoCapitalResult) -> ComponentCapitalSummary:
    """Return the shared orchestration handoff view for one RRAO capital result."""

    return ComponentCapitalSummary(
        component=StandardisedComponent.RRAO,
        package_name="frtb-rrao",
        run_id=result.run_id,
        calculation_date=result.calculation_date,
        base_currency=result.base_currency,
        profile_id=result.profile_id,
        total_capital=result.total_rrao,
        profile_hash=result.profile_hash,
        input_hash=result.input_hash,
        line_count=len(result.lines),
        excluded_line_count=len(result.excluded_lines),
        subtotal_count=len(result.subtotals),
        citations=tuple(result.citations),
        warnings=tuple(result.warnings),
    )


def to_orchestration_handoff(result: RraoCapitalResult) -> ComponentCapitalSummary:
    """Deprecated alias for :func:`to_component_summary`."""

    warnings.warn(
        "to_orchestration_handoff is deprecated; use to_component_summary",
        DeprecationWarning,
        stacklevel=2,
    )
    return to_component_summary(result)


__all__ = ["to_component_summary", "to_orchestration_handoff"]
