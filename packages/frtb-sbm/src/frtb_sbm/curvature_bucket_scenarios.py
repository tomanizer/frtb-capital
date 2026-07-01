"""Curvature bucket scenario and branch evaluation helpers.

Regulatory traceability:
    Basel MAR21.5, MAR21.6-MAR21.7, and SBM-CURV-001.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from frtb_sbm.aggregation import adjust_correlation_matrix_for_scenario
from frtb_sbm.curvature_correlations import (
    _build_curvature_intra_bucket_correlation_matrix,
    _curvature_intra_citation_ids,
)
from frtb_sbm.curvature_factors import _CurvatureFactor
from frtb_sbm.data_models import SbmRiskClass, SbmScenarioLabel

_CURVATURE_UP_BRANCH = "up"
_CURVATURE_DOWN_BRANCH = "down"


@dataclass(frozen=True)
class _CurvatureBranchEvaluation:
    branch: str
    bucket_capital: float
    branch_sum: float
    variance_before_floor: float
    floor_applied: bool
    psi_zero_count: int


@dataclass(frozen=True)
class _CurvatureBucketScenario:
    bucket_id: str
    scenario: SbmScenarioLabel
    selected: _CurvatureBranchEvaluation
    rejected: _CurvatureBranchEvaluation
    up: _CurvatureBranchEvaluation
    down: _CurvatureBranchEvaluation
    factors: tuple[_CurvatureFactor, ...]
    correlation_matrix: npt.NDArray[np.float64]
    citation_ids: tuple[str, ...]


def _evaluate_curvature_bucket_scenario(
    bucket_id: str,
    factors: tuple[_CurvatureFactor, ...],
    *,
    profile_id: str,
    risk_class: SbmRiskClass,
    scenario: SbmScenarioLabel,
) -> _CurvatureBucketScenario:
    base_matrix = _build_curvature_intra_bucket_correlation_matrix(
        factors,
        profile_id=profile_id,
        risk_class=risk_class,
    )
    adjusted_matrix = adjust_correlation_matrix_for_scenario(
        base_matrix,
        scenario,
        profile_id=profile_id,
    )
    up = _evaluate_curvature_branch(
        tuple(factor.up_cvr for factor in factors),
        adjusted_matrix,
        branch=_CURVATURE_UP_BRANCH,
    )
    down = _evaluate_curvature_branch(
        tuple(factor.down_cvr for factor in factors),
        adjusted_matrix,
        branch=_CURVATURE_DOWN_BRANCH,
    )
    selected, rejected = _select_curvature_bucket_branch(up, down)
    return _CurvatureBucketScenario(
        bucket_id=bucket_id,
        scenario=scenario,
        selected=selected,
        rejected=rejected,
        up=up,
        down=down,
        factors=factors,
        correlation_matrix=adjusted_matrix,
        citation_ids=_curvature_intra_citation_ids(risk_class, profile_id),
    )


def _evaluate_curvature_branch(
    values: Sequence[float],
    correlation_matrix: npt.NDArray[np.float64],
    *,
    branch: str,
) -> _CurvatureBranchEvaluation:
    cvr = np.asarray(values, dtype=np.float64)
    positive_diagonal = float(np.dot(np.maximum(cvr, 0.0), np.maximum(cvr, 0.0)))
    if len(cvr) <= 1:
        pair_contribution = 0.0
        psi_zero_count = 0
    else:
        row_indices, col_indices = np.triu_indices(len(cvr), k=1)
        left = cvr[row_indices]
        right = cvr[col_indices]
        psi = ~((left < 0.0) & (right < 0.0))
        psi_zero_count = int(np.count_nonzero(~psi))
        pair_contribution = float(
            2.0 * np.sum(correlation_matrix[row_indices, col_indices] * left * right * psi)
        )
    variance = positive_diagonal + pair_contribution
    return _CurvatureBranchEvaluation(
        branch=branch,
        bucket_capital=math.sqrt(max(0.0, variance)),
        branch_sum=float(np.sum(cvr)),
        variance_before_floor=variance,
        floor_applied=variance < 0.0,
        psi_zero_count=psi_zero_count,
    )


def _select_curvature_bucket_branch(
    up: _CurvatureBranchEvaluation,
    down: _CurvatureBranchEvaluation,
) -> tuple[_CurvatureBranchEvaluation, _CurvatureBranchEvaluation]:
    if not math.isclose(up.bucket_capital, down.bucket_capital, rel_tol=1e-12, abs_tol=1e-12):
        return (up, down) if up.bucket_capital > down.bucket_capital else (down, up)
    return (up, down) if up.branch_sum > down.branch_sum else (down, up)


__all__ = [
    "_CURVATURE_DOWN_BRANCH",
    "_CURVATURE_UP_BRANCH",
    "_CurvatureBranchEvaluation",
    "_CurvatureBucketScenario",
    "_evaluate_curvature_branch",
    "_evaluate_curvature_bucket_scenario",
    "_select_curvature_bucket_branch",
]
