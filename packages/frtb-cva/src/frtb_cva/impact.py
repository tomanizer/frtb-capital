"""
Baseline-vs-candidate CVA capital impact assessment.
"""

from __future__ import annotations

from dataclasses import dataclass

from frtb_cva.data_models import CvaCapitalResult


@dataclass(frozen=True)
class CvaCapitalImpact:
    """Capital delta between two reconciled CVA results."""

    baseline_run_id: str
    candidate_run_id: str
    baseline_total: float
    candidate_total: float
    delta: float
    method: str
    baseline_input_hash: str
    candidate_input_hash: str


def assess_cva_capital_impact(
    baseline: CvaCapitalResult,
    candidate: CvaCapitalResult,
) -> CvaCapitalImpact:
    """Return the capital delta between two results (finite-difference label)."""

    return CvaCapitalImpact(
        baseline_run_id=baseline.run_id,
        candidate_run_id=candidate.run_id,
        baseline_total=baseline.total_cva_capital,
        candidate_total=candidate.total_cva_capital,
        delta=candidate.total_cva_capital - baseline.total_cva_capital,
        method="finite_difference",
        baseline_input_hash=baseline.input_hash,
        candidate_input_hash=candidate.input_hash,
    )


__all__ = ["CvaCapitalImpact", "assess_cva_capital_impact"]
