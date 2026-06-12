"""Curvature inter-bucket aggregation helpers.

Regulatory traceability:
    Basel MAR21.5, MAR21.6-MAR21.7, and SBM-CURV-001.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

import numpy as np
import numpy.typing as npt

from frtb_sbm.aggregation import adjust_correlation_for_scenario
from frtb_sbm.curvature_bucket_scenarios import _CurvatureBucketScenario
from frtb_sbm.data_models import SbmScenarioLabel


def _aggregate_curvature_inter_bucket(
    bucket_scenarios: tuple[_CurvatureBucketScenario, ...],
    inter_bucket_correlations: Mapping[tuple[str, str], float],
    *,
    scenario: SbmScenarioLabel,
) -> tuple[float, tuple[tuple[str, str, float], ...]]:
    bucket_ids = tuple(bucket.bucket_id for bucket in bucket_scenarios)
    kb_values = np.array([bucket.selected.bucket_capital for bucket in bucket_scenarios])
    sb_values = np.array([bucket.selected.branch_sum for bucket in bucket_scenarios])
    gamma = _build_curvature_inter_bucket_gamma_matrix(
        bucket_ids,
        inter_bucket_correlations,
        scenario=scenario,
    )
    psi = _curvature_psi_matrix(sb_values)
    variance = float(np.dot(kb_values, kb_values) + sb_values @ (gamma * psi) @ sb_values)
    capital = math.sqrt(max(0.0, variance))
    return capital, _curvature_inter_bucket_correlation_audit(
        bucket_ids,
        inter_bucket_correlations,
        scenario=scenario,
    )


def _curvature_psi_matrix(values: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    size = len(values)
    psi = np.ones((size, size), dtype=np.float64)
    if size:
        np.fill_diagonal(psi, 0.0)
    if size <= 1:
        return psi
    row_indices, col_indices = np.triu_indices(size, k=1)
    zero_mask = (values[row_indices] < 0.0) & (values[col_indices] < 0.0)
    psi[row_indices[zero_mask], col_indices[zero_mask]] = 0.0
    psi[col_indices[zero_mask], row_indices[zero_mask]] = 0.0
    return psi


def _build_curvature_inter_bucket_gamma_matrix(
    bucket_ids: Sequence[str],
    inter_bucket_correlations: Mapping[tuple[str, str], float],
    *,
    scenario: SbmScenarioLabel,
) -> npt.NDArray[np.float64]:
    size = len(bucket_ids)
    gamma = np.zeros((size, size), dtype=np.float64)
    index = {bucket_id: position for position, bucket_id in enumerate(bucket_ids)}
    for (bucket_a, bucket_b), base_gamma in sorted(inter_bucket_correlations.items()):
        if bucket_a not in index or bucket_b not in index:
            continue
        applied = adjust_correlation_for_scenario(base_gamma, scenario)
        row = index[bucket_a]
        col = index[bucket_b]
        gamma[row, col] = applied
        gamma[col, row] = applied
    return gamma


def _curvature_inter_bucket_correlation_audit(
    bucket_ids: Sequence[str],
    inter_bucket_correlations: Mapping[tuple[str, str], float],
    *,
    scenario: SbmScenarioLabel,
) -> tuple[tuple[str, str, float], ...]:
    return tuple(
        (bucket_a, bucket_b, adjust_correlation_for_scenario(base_gamma, scenario))
        for (bucket_a, bucket_b), base_gamma in sorted(inter_bucket_correlations.items())
        if bucket_a in bucket_ids and bucket_b in bucket_ids
    )


__all__ = [
    "_aggregate_curvature_inter_bucket",
    "_build_curvature_inter_bucket_gamma_matrix",
    "_curvature_inter_bucket_correlation_audit",
    "_curvature_psi_matrix",
]
