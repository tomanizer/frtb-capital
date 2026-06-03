"""Orchestration handoff projection for public ``DrcCapitalResult`` records.

``frtb-orchestration`` consumes only the shared
``frtb_common.ComponentCapitalSummary`` shape, so this adapter is the single
stable bridge from the rich DRC result to suite aggregation.
"""

from __future__ import annotations

import warnings

from frtb_common import ComponentCapitalSummary, StandardisedComponent

from frtb_drc.data_models import DrcCapitalResult


def to_component_summary(result: DrcCapitalResult) -> ComponentCapitalSummary:
    """Return the shared orchestration handoff view for one DRC capital result."""

    return ComponentCapitalSummary(
        component=StandardisedComponent.DRC,
        package_name=result.package_name,
        run_id=result.run_id,
        calculation_date=result.calculation_date,
        base_currency=result.base_currency,
        profile_id=result.profile_id,
        total_capital=result.total_drc,
        profile_hash=result.profile_hash,
        input_hash=result.input_hash,
        line_count=result.input_count,
        excluded_line_count=result.rejected_input_count,
        subtotal_count=len(result.categories),
        citations=tuple(result.citations),
        warnings=tuple(result.warnings),
    )


def to_orchestration_handoff(result: DrcCapitalResult) -> ComponentCapitalSummary:
    """Deprecated alias for :func:`to_component_summary`."""

    warnings.warn(
        "to_orchestration_handoff is deprecated; use to_component_summary",
        DeprecationWarning,
        stacklevel=2,
    )
    return to_component_summary(result)


__all__ = ["to_component_summary", "to_orchestration_handoff"]
