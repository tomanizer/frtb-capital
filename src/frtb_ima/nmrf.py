"""
Non-Modellable Risk Factor (NMRF) Stressed Expected Shortfall (SES).

Working assumptions (NPR 2.0 / Basel FRTB IMA):

    - Type A NMRFs: included in both IMCC and SES.
    - Type B NMRFs: included in SES only, with conservative aggregation rho = 0.36.

Aggregation formulas used here:

    Type A SES (zero correlation under the NPR 2.0 proposed formula):
        SES_A_term = sum(SES_i^2 for i in Type_A)

    Type B SES (partial correlation via rho parameter):
        SES_B_term =
            rho    * (sum(SES_i))^2
            + (1 - rho) * sum(SES_i^2)

    Combined SES:
        SES = sqrt(SES_A_term + SES_B_term)

The prototype can generate only a labelled linear / sensitivity-based SES
approximation. Direct, stepwise, and full-revaluation SES values may be
recorded if supplied by an upstream risk engine, but this package raises
explicit unsupported-feature errors if asked to generate them.

Regulatory traceability:
    Basel MAR33 NMRF stress-scenario capital; U.S. NPR 2.0 SES treatment for
    Type A / Type B NMRFs; EU CRR Article 325bk. See
    docs/REGULATORY_TRACEABILITY.md.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import numpy.typing as npt

from frtb_ima.regimes import (
    RegulatoryPolicy,
    RegulatoryRegime,
    TypeASESAggregationMode,
    UnsupportedRegulatoryFeature,
)


class NMRFStressMethod(StrEnum):
    """Method used to produce an individual NMRF stress scenario SES value."""

    LINEAR_SENSITIVITY = "LINEAR_SENSITIVITY"
    DIRECT = "DIRECT"
    STEPWISE = "STEPWISE"
    FULL_REVALUATION = "FULL_REVALUATION"


_UNSUPPORTED_GENERATION_FEATURES: dict[NMRFStressMethod, str] = {
    NMRFStressMethod.DIRECT: "nmrf_direct_stress_scenario_generation",
    NMRFStressMethod.STEPWISE: "nmrf_stepwise_stress_scenario_generation",
    NMRFStressMethod.FULL_REVALUATION: "nmrf_full_revaluation_stress_scenario_generation",
}


@dataclass(frozen=True)
class NMRFStressScenarioResult:
    """
    Individual NMRF stress scenario result consumed by SES aggregation.

    ``generated_by_prototype`` is intentionally explicit. The prototype can
    produce linear-sensitivity toy SES values, but direct, stepwise, and
    full-revaluation SES values must be supplied by an upstream risk engine or
    remain unsupported for generation in this package.
    """

    risk_factor_name: str
    method: NMRFStressMethod
    ses: float
    generated_by_prototype: bool
    source: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.risk_factor_name:
            raise ValueError("risk_factor_name must be non-empty")
        if not isinstance(self.method, NMRFStressMethod):
            raise TypeError("method must be an NMRFStressMethod")
        if not math.isfinite(self.ses) or self.ses < 0.0:
            raise ValueError(f"ses must be a non-negative finite value, got {self.ses}")

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for reporting and audit trails."""
        return {
            "risk_factor_name": self.risk_factor_name,
            "method": self.method.value,
            "ses": self.ses,
            "generated_by_prototype": self.generated_by_prototype,
            "source": self.source,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class SESAggregationResult:
    """Audit-friendly decomposition of NMRF SES aggregation."""

    type_a_count: int
    type_b_count: int
    type_a_sum_of_squares: float
    type_b_correlated_term: float
    type_b_sum_of_squares: float
    type_b_linear_sum: float
    type_b_rho: float
    total_ses: float


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


def ses_for_nmrf_linear(sensitivity: float, shock: float) -> float:
    """
    Compute the SES contribution for a single NMRF using a linear approximation.

    SES_i = |sensitivity_i| * shock_i

    Args:
        sensitivity: First-order sensitivity (dollar P&L per unit of risk factor move).
        shock:       Stress shock size (in risk factor units, positive).

    Returns:
        SES contribution as a positive scalar.
    """
    return abs(sensitivity) * abs(shock)


def nmrf_stress_result_from_linear_sensitivity(
    risk_factor_name: str,
    sensitivity: float,
    shock: float,
    *,
    source: str = "",
    notes: str = "Prototype linear sensitivity approximation.",
) -> NMRFStressScenarioResult:
    """
    Build an individual NMRF SES result from the prototype linear helper.

    This is not a full regulatory direct/stepwise/full-revaluation stress
    scenario. It is retained as a transparent prototype approximation.
    """
    return NMRFStressScenarioResult(
        risk_factor_name=risk_factor_name,
        method=NMRFStressMethod.LINEAR_SENSITIVITY,
        ses=ses_for_nmrf_linear(sensitivity, shock),
        generated_by_prototype=True,
        source=source,
        notes=notes,
    )


def nmrf_stress_result_from_external_ses(
    risk_factor_name: str,
    ses: float,
    method: NMRFStressMethod,
    *,
    source: str,
    notes: str = "",
) -> NMRFStressScenarioResult:
    """
    Record an externally supplied NMRF SES value and its upstream method.

    This lets the capital layer consume risk-engine direct, stepwise, or
    full-revaluation outputs without pretending this package generated them.
    """
    return NMRFStressScenarioResult(
        risk_factor_name=risk_factor_name,
        method=method,
        ses=float(ses),
        generated_by_prototype=False,
        source=source,
        notes=notes,
    )


def require_nmrf_stress_generation_supported(
    method: NMRFStressMethod,
    policy: RegulatoryPolicy | None = None,
) -> None:
    """
    Raise a named unsupported-feature error for unimplemented SES generation.

    The prototype can generate only the linear-sensitivity approximation. Direct,
    stepwise, and full-revaluation methods are valid upstream methods to record
    via ``nmrf_stress_result_from_external_ses`` but are not generated here.
    """
    if method == NMRFStressMethod.LINEAR_SENSITIVITY:
        return
    feature_name = _UNSUPPORTED_GENERATION_FEATURES[method]
    regime = policy.regime if policy is not None else RegulatoryRegime.FED_NPR_2_0
    raise UnsupportedRegulatoryFeature(
        regime,
        feature_name,
        "NMRF stress-scenario generation",
    )


def ses_values_from_stress_results(
    results: Sequence[NMRFStressScenarioResult],
) -> tuple[float, ...]:
    """Extract SES values from individual NMRF stress scenario results."""
    return tuple(result.ses for result in results)


def aggregate_ses_type_a(values: Sequence[float] | npt.NDArray[np.float64]) -> float:
    """
    Aggregate SES contributions for Type A NMRFs.

    The NPR 2.0 proposed SES formula aggregates Type A NMRFs with zero
    correlation, so the Type A-only component is the square root of the sum of
    squared individual SES values.
    """
    abs_vals = _as_abs_ses_array(values, "values")
    return float(math.sqrt(np.dot(abs_vals, abs_vals)))


def aggregate_ses_type_b(
    values: Sequence[float] | npt.NDArray[np.float64],
    rho: float = 0.36,
) -> float:
    """
    Aggregate SES contributions for Type B NMRFs.

    Partial correlation via rho (default 0.36 per NPR 2.0 working assumption):

        SES_B = sqrt(rho * (sum SES_i)^2 + (1 - rho) * sum(SES_i^2))

    Args:
        values: Individual SES contributions (positive scalars).
        rho:    Correlation parameter. 0 = fully diversified, 1 = fully correlated.
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
    type_b_rho: float = 0.36,
) -> SESAggregationResult:
    """
    Compute total SES from Type A and Type B NMRF contributions with decomposition.

    Proposed NPR 2.0 working formula implemented here:

        SES = sqrt(
            sum(Type_A_SES_i^2)
            + rho * (sum(Type_B_SES_i))^2
            + (1 - rho) * sum(Type_B_SES_i^2)
        )
    """
    if not (0.0 <= type_b_rho <= 1.0):
        raise ValueError(f"type_b_rho must be in [0, 1], got {type_b_rho}")

    type_a = _as_abs_ses_array(type_a_values, "type_a_values")
    type_b = _as_abs_ses_array(type_b_values, "type_b_values")

    type_a_sum_of_squares = float(np.dot(type_a, type_a))
    type_b_sum_of_squares = float(np.dot(type_b, type_b))
    type_b_linear_sum = float(np.sum(type_b))
    type_b_correlated_term = (
        type_b_rho * type_b_linear_sum**2
        + (1.0 - type_b_rho) * type_b_sum_of_squares
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


def aggregate_ses(
    type_a_values: Sequence[float] | npt.NDArray[np.float64],
    type_b_values: Sequence[float] | npt.NDArray[np.float64],
    type_b_rho: float = 0.36,
) -> float:
    """Return total SES from Type A and Type B NMRF contributions."""
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
    """
    Aggregate SES using policy parameters.

    This wrapper is only valid for policies that support the prototype's
    Type A / Type B split. EU and UK profiles currently use broader NMRF
    terminology, so this wrapper raises a named unsupported-feature error.
    """
    policy.require_supported("type_a_type_b_nmrf_taxonomy")
    if (
        policy.type_a_ses_aggregation_mode
        != TypeASESAggregationMode.ZERO_CORRELATION_ROOT_SUM_SQUARES
    ):
        raise ValueError(
            "NPR 2.0 policy must use zero-correlation root-sum-square "
            "aggregation for Type A SES"
        )
    return aggregate_ses(
        type_a_values,
        type_b_values,
        type_b_rho=policy.type_b_ses_rho,
    )
