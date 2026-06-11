"""
Correlation-scenario adjustment helpers for SBM aggregation kernels.

Regulatory traceability:
    Basel MAR21.6 — low, medium, and high correlation scenarios.
"""

from __future__ import annotations

import numpy as np
import numpy.typing as npt

from frtb_sbm.data_models import SbmRegulatoryProfile, SbmScenarioLabel
from frtb_sbm.reference_data import apply_correlation_scenario, correlation_scenario_definition
from frtb_sbm.validation import SbmInputError


def adjust_correlation_for_scenario(
    base_correlation: float,
    scenario: SbmScenarioLabel,
    *,
    profile_id: SbmRegulatoryProfile | str = SbmRegulatoryProfile.BASEL_MAR21,
) -> float:
    """Apply MAR21.6 correlation-scenario adjustments to one parameter.

    Delegates to profile-owned reference data so aggregation and lookup paths
    share one implementation.
    Parameters
    ----------
    base_correlation : float
        See signature.
    scenario : SbmScenarioLabel
        See signature.
    profile_id : SbmRegulatoryProfile | str, optional
        See signature.

    Returns
    -------
    float
    """
    adjusted, _ = apply_correlation_scenario(
        profile_id,
        base_correlation=base_correlation,
        scenario=scenario,
    )
    return adjusted


def adjust_correlation_matrix_for_scenario(
    base_matrix: npt.NDArray[np.float64],
    scenario: SbmScenarioLabel,
    *,
    profile_id: SbmRegulatoryProfile | str = SbmRegulatoryProfile.BASEL_MAR21,
) -> npt.NDArray[np.float64]:
    """Return a copy of ``base_matrix`` with off-diagonal entries scenario-adjusted.
    Parameters
    ----------
    base_matrix : npt.NDArray[np.float64]
        See signature.
    scenario : SbmScenarioLabel
        See signature.
    profile_id : SbmRegulatoryProfile | str, optional
        See signature.

    Returns
    -------
    npt.NDArray[np.float64]
    """

    matrix = np.array(base_matrix, dtype=np.float64, copy=True)
    if not np.all(np.isfinite(matrix)):
        raise SbmInputError("base_matrix must contain only finite values", field="base_matrix")
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise SbmInputError("base_matrix must be a square matrix", field="base_matrix")

    size = matrix.shape[0]
    if size <= 1:
        return matrix

    row_indices, col_indices = np.triu_indices(size, k=1)
    adjusted = _adjust_correlation_values_for_scenario(
        matrix[row_indices, col_indices],
        scenario,
        profile_id=profile_id,
    )
    matrix[row_indices, col_indices] = adjusted
    matrix[col_indices, row_indices] = adjusted
    return matrix


def _adjust_correlation_values_for_scenario(
    base_correlations: npt.NDArray[np.float64],
    scenario: SbmScenarioLabel,
    *,
    profile_id: SbmRegulatoryProfile | str = SbmRegulatoryProfile.BASEL_MAR21,
) -> npt.NDArray[np.float64]:
    values = np.asarray(base_correlations, dtype=np.float64)
    if not np.all(np.isfinite(values)):
        raise SbmInputError("base_correlation must be finite", field="base_correlation")

    definition = correlation_scenario_definition(profile_id, scenario)
    if definition.scenario is SbmScenarioLabel.LOW:
        return np.maximum(2.0 * values - 1.0, definition.multiplier * values)
    if definition.scenario is SbmScenarioLabel.HIGH:
        cap = definition.cap if definition.cap is not None else 1.0
        return np.minimum(cap, definition.multiplier * values)
    return definition.multiplier * values


__all__ = [
    "adjust_correlation_for_scenario",
    "adjust_correlation_matrix_for_scenario",
]
