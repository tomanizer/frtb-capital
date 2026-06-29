"""NMRF SES aggregation helpers."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

from frtb_ima.nmrf_types import NMRFStressScenarioResult, SESAggregationResult
from frtb_ima.regimes import (
    EU_CRR3_NMRF_RHO_FEATURE,
    RegulatoryPolicy,
    RegulatoryRegime,
    TypeASESAggregationMode,
)


def _as_abs_ses_array(
    values: Sequence[float] | npt.NDArray[np.float64],
    name: str,
) -> npt.NDArray[np.float64]:
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be one-dimensional")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} must contain only finite values")
    return np.abs(arr.astype(np.float64, copy=False))


def ses_values_from_stress_results(
    results: Sequence[NMRFStressScenarioResult],
) -> tuple[float, ...]:
    """Extract SES values from individual NMRF stress scenario results.
    Parameters
    ----------
    results : Sequence[NMRFStressScenarioResult]
        Results.

    Returns
    -------
    tuple[float, ...]
        SES values in the same order as the supplied stress results.
    """
    return tuple(result.ses for result in results)


def aggregate_ses_type_a(values: Sequence[float] | npt.NDArray[np.float64]) -> float:
    """Aggregate SES contributions for Type A NMRFs.

    The NPR 2.0 proposed SES formula aggregates Type A NMRFs with zero
    correlation, so the Type A-only component is the square root of the sum of
    squared individual SES values.
    Parameters
    ----------
    values : Sequence[float] | npt.NDArray[np.float64]
        Values.

    Returns
    -------
    float
        Aggregated Type A SES as a non-negative root-sum-square scalar.
    """
    abs_vals = _as_abs_ses_array(values, "values")
    return float(math.sqrt(np.dot(abs_vals, abs_vals)))


def aggregate_ses_type_b(
    values: Sequence[float] | npt.NDArray[np.float64],
    rho: float,
) -> float:
    """Aggregate SES contributions for Type B NMRFs.

    Partial correlation via rho, supplied by the applicable policy:

        SES_B = sqrt(rho * (sum SES_i)^2 + (1 - rho) * sum(SES_i^2))

    Parameters
    ----------
    values : Sequence[float] | npt.NDArray[np.float64]
        Values.
    rho : float
        Rho.

    Returns
    -------
    float
        Aggregated Type B SES as a non-negative scalar using the
        partial-correlation formula.
    """
    if not (0.0 <= rho <= 1.0):
        raise ValueError(f"rho must be in [0, 1], got {rho}")

    abs_vals = _as_abs_ses_array(values, "values")
    if abs_vals.size == 0:
        return 0.0
    linear_sum = float(np.sum(abs_vals))
    sum_of_squares = float(np.dot(abs_vals, abs_vals))

    return math.sqrt(rho * linear_sum**2 + (1.0 - rho) * sum_of_squares)


def aggregate_ses_breakdown(
    type_a_values: Sequence[float] | npt.NDArray[np.float64],
    type_b_values: Sequence[float] | npt.NDArray[np.float64],
    type_b_rho: float,
) -> SESAggregationResult:
    """Compute total SES from Type A and Type B NMRF contributions with decomposition.

    Proposed U.S. NPR 2.0 SES formula implemented here:

        SES = sqrt(
            sum(Type_A_SES_i^2)
            + rho * (sum(Type_B_SES_i))^2
            + (1 - rho) * sum(Type_B_SES_i^2)
        )
    Parameters
    ----------
    type_a_values : Sequence[float] | npt.NDArray[np.float64]
        Type a values.
    type_b_values : Sequence[float] | npt.NDArray[np.float64]
        Type b values.
    type_b_rho : float
        Type b rho.

    Returns
    -------
    SESAggregationResult
        Audit decomposition for Type A, Type B, and total SES terms.
    """
    if not (0.0 <= type_b_rho <= 1.0):
        raise ValueError(f"type_b_rho must be in [0, 1], got {type_b_rho}")

    type_a = _as_abs_ses_array(type_a_values, "type_a_values")
    type_b = _as_abs_ses_array(type_b_values, "type_b_values")

    type_a_sum_of_squares = float(np.dot(type_a, type_a))
    type_b_sum_of_squares = float(np.dot(type_b, type_b))
    type_b_linear_sum = float(np.sum(type_b))
    type_b_correlated_term = (
        type_b_rho * type_b_linear_sum**2 + (1.0 - type_b_rho) * type_b_sum_of_squares
    )
    total = math.sqrt(type_a_sum_of_squares + type_b_correlated_term)

    return SESAggregationResult(
        type_a_count=int(type_a.size),
        type_b_count=int(type_b.size),
        type_a_sum_of_squares=type_a_sum_of_squares,
        type_b_correlated_term=type_b_correlated_term,
        type_b_sum_of_squares=type_b_sum_of_squares,
        type_b_linear_sum=type_b_linear_sum,
        type_b_rho=type_b_rho,
        total_ses=total,
    )


def aggregate_ses_breakdown_for_policy(
    type_a_values: Sequence[float] | npt.NDArray[np.float64],
    type_b_values: Sequence[float] | npt.NDArray[np.float64],
    policy: RegulatoryPolicy,
) -> SESAggregationResult:
    """Compute decomposed SES using policy parameters and taxonomy support gates.
    Parameters
    ----------
    type_a_values : Sequence[float] | npt.NDArray[np.float64]
        Type a values.
    type_b_values : Sequence[float] | npt.NDArray[np.float64]
        Type b values.
    policy : RegulatoryPolicy
        Policy.

    Returns
    -------
    SESAggregationResult
        Policy-routed SES aggregation decomposition.
    """
    policy.require_capital_runtime_supported()
    if policy.uses_type_a_type_b_taxonomy:
        policy.require_type_a_type_b_taxonomy()
        if (
            policy.type_a_ses_aggregation_mode
            != TypeASESAggregationMode.ZERO_CORRELATION_ROOT_SUM_SQUARES
        ):
            raise ValueError(
                "NPR 2.0 policy must use zero-correlation root-sum-square aggregation "
                "for Type A SES"
            )
        return aggregate_ses_breakdown(
            type_a_values,
            type_b_values,
            type_b_rho=policy.type_b_ses_rho,
        )
    if policy.regime is RegulatoryRegime.ECB_CRR3:
        policy.require_supported(EU_CRR3_NMRF_RHO_FEATURE)

    # Basel MAR33.16 / UK CRR Article 325bk comparison path: profiles without
    # U.S. Type A / Type B taxonomy aggregate the supplied NMRF SES values
    # independently unless a profile-specific rho feature is implemented.
    return aggregate_ses_breakdown(
        type_a_values,
        type_b_values,
        type_b_rho=0.0,
    )


def aggregate_ses(
    type_a_values: Sequence[float] | npt.NDArray[np.float64],
    type_b_values: Sequence[float] | npt.NDArray[np.float64],
    type_b_rho: float,
) -> float:
    """Return total SES from Type A and Type B NMRF contributions.
    Parameters
    ----------
    type_a_values : Sequence[float] | npt.NDArray[np.float64]
        Type a values.
    type_b_values : Sequence[float] | npt.NDArray[np.float64]
        Type b values.
    type_b_rho : float
        Type b rho.

    Returns
    -------
    float
        Total SES scalar from Type A and Type B contributions.
    """
    return aggregate_ses_breakdown(
        type_a_values,
        type_b_values,
        type_b_rho=type_b_rho,
    ).total_ses


def aggregate_ses_for_policy(
    type_a_values: Sequence[float] | npt.NDArray[np.float64],
    type_b_values: Sequence[float] | npt.NDArray[np.float64],
    policy: RegulatoryPolicy,
) -> float:
    """Aggregate SES using policy parameters.

    Fed NPR profiles use the Type A / Type B split with the policy rho
    parameter. ECB CRR3 profiles currently raise ``UnsupportedRegulatoryFeature``
    for the CRR3 NMRF rho parameter. PRA UK CRR comparison profiles use the
    Basel/UK Article 325bk independent aggregation path with ``rho=0.0``.
    Parameters
    ----------
    type_a_values : Sequence[float] | npt.NDArray[np.float64]
        Type a values.
    type_b_values : Sequence[float] | npt.NDArray[np.float64]
        Type b values.
    policy : RegulatoryPolicy
        Policy.

    Returns
    -------
    float
        Policy-routed total SES scalar.
    """
    return aggregate_ses_breakdown_for_policy(
        type_a_values,
        type_b_values,
        policy,
    ).total_ses


__all__ = [
    "aggregate_ses",
    "aggregate_ses_breakdown",
    "aggregate_ses_breakdown_for_policy",
    "aggregate_ses_for_policy",
    "aggregate_ses_type_a",
    "aggregate_ses_type_b",
    "ses_values_from_stress_results",
]
