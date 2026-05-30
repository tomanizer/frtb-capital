"""
Typed orchestration handoff for public ``SbmCapitalResult`` records.

Regulatory traceability:
    SBM-FUNC-021, SBM-DEC-007 — package-level results consumed by orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from frtb_sbm.data_models import SbmCapitalResult, SbmUnsupportedFeature
from frtb_sbm.validation import SbmInputError


@dataclass(frozen=True)
class SbmOrchestrationHandoff:
    """Stable SBM result view consumed by ``frtb-orchestration``."""

    package_name: str
    run_id: str
    calculation_date: date
    base_currency: str
    profile_id: str
    total_sbm: float
    profile_hash: str
    input_hash: str
    sensitivity_count: int
    unsupported_count: int
    risk_class_results: tuple[object, ...]
    citations: tuple[str, ...]
    warnings: tuple[str, ...]


def to_orchestration_handoff(result: SbmCapitalResult) -> SbmOrchestrationHandoff:
    """Return the orchestration-facing handoff view for one SBM capital result."""

    if result.run_context is None:
        raise SbmInputError("SbmCapitalResult.run_context is required for orchestration handoff")
    reconciliation = result.reconciliation
    citations: list[str] = []
    if reconciliation is not None:
        citations.extend(reconciliation.citation_ids)
    citations.extend(result.warnings)
    return SbmOrchestrationHandoff(
        package_name="frtb-sbm",
        run_id=result.run_context.run_id,
        calculation_date=result.run_context.calculation_date,
        base_currency=result.run_context.base_currency,
        profile_id=result.profile_id,
        total_sbm=result.total_capital,
        profile_hash=result.profile_hash,
        input_hash=result.input_hash,
        sensitivity_count=reconciliation.input_count if reconciliation else 0,
        unsupported_count=len(result.unsupported_features),
        risk_class_results=result.risk_classes,
        citations=tuple(dict.fromkeys(citations)),
        warnings=result.warnings,
    )


def unsupported_features_from_result(
    result: SbmCapitalResult,
) -> tuple[SbmUnsupportedFeature, ...]:
    """Return structured unsupported-feature metadata carried on a result."""

    return result.unsupported_features


__all__ = [
    "SbmOrchestrationHandoff",
    "to_orchestration_handoff",
    "unsupported_features_from_result",
]
