"""
Baseline-vs-candidate capital impact assessment for SBM.

Regulatory traceability:
    ADR 0038 — suite-wide attribution and impact contract.
"""

from __future__ import annotations

from frtb_common.impact import CapitalImpact, ImpactMethod

from frtb_sbm.data_models import SbmCapitalResult

_COMPONENT = "frtb_sbm"


def calculate_sbm_capital_impact(
    baseline: SbmCapitalResult,
    candidate: SbmCapitalResult,
) -> CapitalImpact:
    """Return the finite-difference capital delta between two reconciled SBM results.

    Both results must be independently reconciled before calling this function.
    The returned record must not be presented as a marginal contribution; it is
    a cross-run impact assessment (ADR 0038 §3).
    """
    return CapitalImpact(
        baseline_run_id=baseline.run_context.run_id if baseline.run_context else "",
        candidate_run_id=candidate.run_context.run_id if candidate.run_context else "",
        component=_COMPONENT,
        baseline_total=baseline.total_capital,
        candidate_total=candidate.total_capital,
        delta=candidate.total_capital - baseline.total_capital,
        method=ImpactMethod.FINITE_DIFFERENCE,
        baseline_input_hash=baseline.input_hash,
        candidate_input_hash=candidate.input_hash,
        baseline_profile_hash=baseline.profile_hash,
        candidate_profile_hash=candidate.profile_hash,
    )


__all__ = ["calculate_sbm_capital_impact"]
