"""Orchestration handoff projection for public ``SbmCapitalResult`` records.

Regulatory traceability:
    SBM-FUNC-021, SBM-DEC-007 — package-level results consumed by orchestration.

``frtb-orchestration`` consumes only the shared
``frtb_common.ComponentCapitalSummary`` shape, so this adapter is the single
stable bridge from the rich SBM result to suite aggregation.
"""

from __future__ import annotations

import warnings

from frtb_common import ComponentCapitalSummary, StandardisedComponent

from frtb_sbm.data_models import SbmCapitalResult, SbmUnsupportedFeature
from frtb_sbm.validation import SbmInputError


def to_component_summary(result: SbmCapitalResult) -> ComponentCapitalSummary:
    """Return the shared orchestration handoff view for one SBM capital result."""

    if result.run_context is None:
        raise SbmInputError("SbmCapitalResult.run_context is required for orchestration handoff")
    reconciliation = result.reconciliation
    citations = tuple(dict.fromkeys(reconciliation.citation_ids)) if reconciliation else ()
    return ComponentCapitalSummary(
        component=StandardisedComponent.SBM,
        package_name="frtb-sbm",
        run_id=result.run_context.run_id,
        calculation_date=result.run_context.calculation_date,
        base_currency=result.run_context.base_currency,
        profile_id=result.profile_id,
        total_capital=result.total_capital,
        profile_hash=result.profile_hash,
        input_hash=result.input_hash,
        line_count=reconciliation.input_count if reconciliation else 0,
        excluded_line_count=reconciliation.rejected_input_count if reconciliation else 0,
        subtotal_count=len(result.risk_classes),
        citations=citations,
        warnings=tuple(result.warnings),
    )


def unsupported_features_from_result(
    result: SbmCapitalResult,
) -> tuple[SbmUnsupportedFeature, ...]:
    """Return structured unsupported-feature metadata carried on a result."""

    return result.unsupported_features


def to_orchestration_handoff(result: SbmCapitalResult) -> ComponentCapitalSummary:
    """Deprecated alias for :func:`to_component_summary`."""

    warnings.warn(
        "to_orchestration_handoff is deprecated; use to_component_summary",
        DeprecationWarning,
        stacklevel=2,
    )
    return to_component_summary(result)


__all__ = [
    "to_component_summary",
    "to_orchestration_handoff",
    "unsupported_features_from_result",
]
