"""
Intra-bucket SBM aggregation kernels and bucket grouping helpers.

Regulatory traceability:
    Basel MAR21.4(4) — within-bucket delta/vega aggregation.
    SBM-REQ-005.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from frtb_sbm.data_models import (
    DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
    BucketCapital,
    PairwiseCorrelationSummary,
    SbmPairwiseEvidenceMode,
    SbmRiskClass,
    SbmRiskMeasure,
    WeightedSensitivity,
)
from frtb_sbm.kernel.pairwise_evidence import (
    PairwiseCorrelationEvidence,
    _pairwise_correlation_audit,
)
from frtb_sbm.validation import SbmInputError

_MAR21_INTRA_BUCKET_CITATION = ("basel_mar21_4_intra_bucket",)


@dataclass(frozen=True)
class IntraBucketScenarioSpec:
    """Inputs required to recompute intra-bucket capital under each scenario."""

    bucket_id: str
    weighted_sensitivities: tuple[WeightedSensitivity, ...]
    base_correlation_matrix: npt.NDArray[np.float64]
    sb_correlation_floor: float | None = None
    absolute_weight_intra: bool = False
    absolute_weight_citation_ids: tuple[str, ...] = ()
    curvature_absolute_floor: bool = False


@dataclass(frozen=True)
class IntraBucketAggregationResult:
    """Intra-bucket capital with scale-aware audit evidence."""

    bucket_capital: BucketCapital
    pairwise_correlations: tuple[PairwiseCorrelationEvidence, ...]
    pairwise_correlation_summary: PairwiseCorrelationSummary
    variance_before_floor: float
    zero_variance_floor_applied: bool
    sb_correlation_floor_applied: bool


def aggregate_intra_bucket(
    bucket_id: str,
    weighted_sensitivities: Sequence[WeightedSensitivity],
    correlation_matrix: npt.NDArray[np.float64],
    *,
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
    sb_correlation_floor: float | None = None,
    curvature_absolute_floor: bool = False,
    citation_ids: tuple[str, ...] = _MAR21_INTRA_BUCKET_CITATION,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> IntraBucketAggregationResult:
    """Aggregate weighted sensitivities within one bucket (MAR21.4 step 4).

    Computes the signed bucket aggregate ``Sb = sum_k WS_k`` and bucket capital
    ``Kb = sqrt(max(0, sum_k sum_l rho_kl WS_k WS_l))``. When ``sb_correlation_floor``
    is supplied, ``Kb`` is additionally floored at ``abs(sb_correlation_floor * Sb)``.
    When ``curvature_absolute_floor`` is True, ``Kb`` is floored at ``sum_k |WS_k|``
    per MAR21.5(3).
    Parameters
    ----------
    bucket_id, weighted_sensitivities, correlation_matrix, risk_class, risk_measure,
    sb_correlation_floor, curvature_absolute_floor, citation_ids, pairwise_evidence_mode,
    pairwise_evidence_limit :
        See function signature for types and defaults.

    Returns
    -------
    IntraBucketAggregationResult
    """
    ordered = _sort_weighted_sensitivities(weighted_sensitivities)
    _validate_bucket_scope(bucket_id, ordered, risk_class, risk_measure)
    matrix = _validate_correlation_matrix(correlation_matrix, n_factors=len(ordered))

    ws = np.array([item.scaled_amount for item in ordered], dtype=np.float64)
    sb = float(np.sum(ws))
    variance = float(ws @ matrix @ ws)

    zero_floor_applied = variance < 0.0
    variance_floored = max(0.0, variance)

    kb_squared = variance_floored
    sb_floor_applied = False
    if sb_correlation_floor is not None:
        if not math.isfinite(sb_correlation_floor) or sb_correlation_floor < 0.0:
            raise SbmInputError(
                "sb_correlation_floor must be a finite non-negative number",
                field="sb_correlation_floor",
            )
        sb_floor_value = (sb_correlation_floor * sb) ** 2
        if sb_floor_value > kb_squared:
            kb_squared = sb_floor_value
            sb_floor_applied = True

    kb = math.sqrt(kb_squared)
    absolute_sum_floor_applied = False
    if curvature_absolute_floor:
        absolute_kb = float(np.sum(np.abs(ws)))
        if absolute_kb > kb:
            kb = absolute_kb
            absolute_sum_floor_applied = True
    pairwise, pairwise_summary = _pairwise_correlation_audit(
        ordered,
        matrix,
        citation_ids,
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )

    bucket_capital = BucketCapital(
        bucket_id=bucket_id,
        risk_class=risk_class,
        risk_measure=risk_measure,
        kb=kb,
        weighted_sensitivities=tuple(ordered),
        citation_ids=citation_ids,
        sb=sb,
        floor_applied=zero_floor_applied or sb_floor_applied or absolute_sum_floor_applied,
    )
    return IntraBucketAggregationResult(
        bucket_capital=bucket_capital,
        pairwise_correlations=pairwise,
        pairwise_correlation_summary=pairwise_summary,
        variance_before_floor=variance,
        zero_variance_floor_applied=zero_floor_applied,
        sb_correlation_floor_applied=sb_floor_applied,
    )


def group_weighted_sensitivities_by_bucket(
    weighted_sensitivities: Sequence[WeightedSensitivity],
) -> dict[tuple[SbmRiskClass, SbmRiskMeasure, str], tuple[WeightedSensitivity, ...]]:
    """Group weighted sensitivities by risk class, measure, and bucket id.
    Parameters
    ----------
    weighted_sensitivities : Sequence[WeightedSensitivity]
        See signature.

    Returns
    -------
    dict[tuple[SbmRiskClass, SbmRiskMeasure, str], tuple[WeightedSensitivity, ...]]
    """
    grouped: dict[tuple[SbmRiskClass, SbmRiskMeasure, str], list[WeightedSensitivity]] = {}
    for item in weighted_sensitivities:
        key = (item.risk_class, item.risk_measure, item.bucket)
        grouped.setdefault(key, []).append(item)
    return {
        key: tuple(_sort_weighted_sensitivities(values)) for key, values in sorted(grouped.items())
    }


def _sort_weighted_sensitivities(
    weighted_sensitivities: Sequence[WeightedSensitivity],
) -> tuple[WeightedSensitivity, ...]:
    return tuple(
        sorted(
            weighted_sensitivities,
            key=lambda item: (item.sensitivity_id, item.bucket, item.qualifier or ""),
        )
    )


def _validate_bucket_scope(
    bucket_id: str,
    weighted_sensitivities: Sequence[WeightedSensitivity],
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
) -> None:
    if not bucket_id.strip():
        raise SbmInputError("bucket_id must be non-empty", field="bucket_id")
    if not weighted_sensitivities:
        raise SbmInputError(
            "weighted_sensitivities must not be empty",
            field="weighted_sensitivities",
        )
    for item in weighted_sensitivities:
        if item.bucket != bucket_id:
            raise SbmInputError(
                "weighted sensitivity bucket does not match bucket_id",
                field="bucket",
                sensitivity_id=item.sensitivity_id,
            )
        if item.risk_class is not risk_class:
            raise SbmInputError(
                "weighted sensitivity risk_class does not match aggregation scope",
                field="risk_class",
                sensitivity_id=item.sensitivity_id,
            )
        if item.risk_measure is not risk_measure:
            raise SbmInputError(
                "weighted sensitivity risk_measure does not match aggregation scope",
                field="risk_measure",
                sensitivity_id=item.sensitivity_id,
            )
        if not math.isfinite(item.scaled_amount):
            raise SbmInputError(
                "scaled_amount must be finite",
                field="scaled_amount",
                sensitivity_id=item.sensitivity_id,
            )


def _validate_correlation_matrix(
    correlation_matrix: npt.NDArray[np.float64],
    *,
    n_factors: int,
) -> npt.NDArray[np.float64]:
    matrix = np.asarray(correlation_matrix, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape != (n_factors, n_factors):
        raise SbmInputError(
            "correlation_matrix shape must match weighted_sensitivities count",
            field="correlation_matrix",
        )
    if not np.all(np.isfinite(matrix)):
        raise SbmInputError(
            "correlation_matrix must contain finite values",
            field="correlation_matrix",
        )
    if not np.allclose(matrix, matrix.T):
        raise SbmInputError("correlation_matrix must be symmetric", field="correlation_matrix")
    if not np.allclose(np.diag(matrix), 1.0):
        raise SbmInputError("correlation_matrix diagonal must be 1.0", field="correlation_matrix")
    return matrix


__all__ = [
    "IntraBucketAggregationResult",
    "IntraBucketScenarioSpec",
    "aggregate_intra_bucket",
    "group_weighted_sensitivities_by_bucket",
]
