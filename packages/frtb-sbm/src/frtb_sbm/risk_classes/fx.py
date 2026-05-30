"""
FX delta assembly onto shared SBM aggregation primitives.

Regulatory traceability:
    Basel MAR21.14 — FX delta risk-factor definition.
    Basel MAR21.86-MAR21.89 — FX buckets, risk weights, and correlations.
    SBM-FUNC-019.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import numpy.typing as npt

from frtb_sbm.aggregation import (
    aggregate_intra_bucket,
    aggregate_risk_class_with_scenarios,
    group_weighted_sensitivities_by_bucket,
)
from frtb_sbm.data_models import (
    RiskClassCapital,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    WeightedSensitivity,
)
from frtb_sbm.reference_data import (
    fx_delta_intra_bucket_correlation,
    fx_inter_bucket_correlation,
)
from frtb_sbm.weighted_sensitivity import weight_fx_delta_sensitivities


def calculate_fx_delta_risk_class_capital(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
    reporting_currency: str,
) -> RiskClassCapital:
    """Calculate cited FX delta risk-class capital for a supported profile."""

    weighted = weight_fx_delta_sensitivities(
        sensitivities,
        profile_id=profile_id,
        reporting_currency=reporting_currency,
    )
    return aggregate_fx_delta_measure_capital(
        weighted,
        profile_id=profile_id,
    )


def aggregate_fx_delta_measure_capital(
    weighted: tuple[WeightedSensitivity, ...],
    *,
    profile_id: str,
) -> RiskClassCapital:
    """Aggregate weighted FX delta sensitivities through shared bucket primitives."""

    grouped = group_weighted_sensitivities_by_bucket(weighted)

    intra_results = []
    for (_risk_class, _risk_measure, bucket_id), bucket_weighted in sorted(grouped.items()):
        matrix = build_fx_delta_intra_bucket_correlation_matrix(
            bucket_weighted,
            profile_id=profile_id,
        )
        intra_results.append(
            aggregate_intra_bucket(
                bucket_id,
                bucket_weighted,
                matrix,
                risk_class=SbmRiskClass.FX,
                risk_measure=SbmRiskMeasure.DELTA,
                sb_correlation_floor=None,
            )
        )

    bucket_ids = tuple(sorted({result.bucket_capital.bucket_id for result in intra_results}))
    inter_bucket_correlations = build_fx_inter_bucket_correlation_map(
        bucket_ids,
        profile_id=profile_id,
    )
    return aggregate_risk_class_with_scenarios(
        intra_results,
        inter_bucket_correlations,
        risk_class=SbmRiskClass.FX,
        risk_measure=SbmRiskMeasure.DELTA,
    )


def build_fx_delta_intra_bucket_correlation_matrix(
    ordered: Sequence[WeightedSensitivity],
    *,
    profile_id: str,
) -> npt.NDArray[np.float64]:
    """Return the cited FX delta intra-bucket correlation matrix."""

    size = len(ordered)
    if size == 0:
        return np.zeros((0, 0), dtype=np.float64)
    # MAR21.86: FX delta intra-bucket correlation is constant within a bucket.
    correlation, _ = fx_delta_intra_bucket_correlation(
        profile_id,
        bucket1=ordered[0].bucket,
        bucket2=ordered[0].bucket,
    )
    matrix = np.full((size, size), correlation, dtype=np.float64)
    np.fill_diagonal(matrix, 1.0)
    return matrix


def build_fx_inter_bucket_correlation_map(
    bucket_ids: Sequence[str],
    *,
    profile_id: str,
) -> dict[tuple[str, str], float]:
    """Return cited FX inter-bucket correlations for distinct bucket pairs."""

    correlations: dict[tuple[str, str], float] = {}
    ordered_ids = tuple(sorted(bucket_ids))
    for left_index, bucket_a in enumerate(ordered_ids):
        for bucket_b in ordered_ids[left_index + 1 :]:
            gamma, _ = fx_inter_bucket_correlation(
                profile_id,
                bucket1=bucket_a,
                bucket2=bucket_b,
            )
            correlations[(bucket_a, bucket_b)] = gamma
    return correlations


__all__ = [
    "aggregate_fx_delta_measure_capital",
    "build_fx_delta_intra_bucket_correlation_matrix",
    "build_fx_inter_bucket_correlation_map",
    "calculate_fx_delta_risk_class_capital",
]
