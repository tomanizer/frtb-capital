"""
Commodity delta assembly onto shared SBM aggregation primitives.

Regulatory traceability:
    Basel MAR21.13 — commodity spot/forward delta risk factors and tenors.
    Basel MAR21.81-MAR21.85 — buckets, weights, correlations.
    SBM-FUNC-018.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import numpy.typing as npt

from frtb_sbm.aggregation import (
    IntraBucketScenarioSpec,
    aggregate_risk_class_with_scenarios,
    group_weighted_sensitivities_by_bucket,
)
from frtb_sbm.commodity_reference_data import commodity_delta_intra_bucket_correlation
from frtb_sbm.commodity_reference_data import (
    commodity_inter_bucket_correlation as commodity_inter_bucket_gamma,
)
from frtb_sbm.data_models import (
    RiskClassCapital,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    WeightedSensitivity,
)
from frtb_sbm.weighted_sensitivity import weight_commodity_delta_sensitivities


def calculate_commodity_delta_risk_class_capital(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
) -> RiskClassCapital:
    """Calculate cited commodity delta risk-class capital for a supported profile."""

    weighted = weight_commodity_delta_sensitivities(
        sensitivities,
        profile_id=profile_id,
    )
    return aggregate_commodity_delta_measure_capital(
        weighted,
        profile_id=profile_id,
        commodity_by_id={item.sensitivity_id: item.risk_factor for item in sensitivities},
        tenor_by_id={item.sensitivity_id: item.tenor or "" for item in sensitivities},
        location_by_id={item.sensitivity_id: item.qualifier or "" for item in sensitivities},
    )


def aggregate_commodity_delta_measure_capital(
    weighted: tuple[WeightedSensitivity, ...],
    *,
    profile_id: str,
    commodity_by_id: Mapping[str, str],
    tenor_by_id: Mapping[str, str],
    location_by_id: Mapping[str, str],
) -> RiskClassCapital:
    """Aggregate weighted commodity delta sensitivities through shared bucket primitives."""

    grouped = group_weighted_sensitivities_by_bucket(weighted)
    intra_specs: list[IntraBucketScenarioSpec] = []
    for (_risk_class, _risk_measure, bucket_id), bucket_weighted in sorted(grouped.items()):
        matrix = build_commodity_delta_intra_bucket_correlation_matrix(
            bucket_weighted,
            profile_id=profile_id,
            bucket_id=bucket_id,
            commodity_by_id=commodity_by_id,
            tenor_by_id=tenor_by_id,
            location_by_id=location_by_id,
        )
        intra_specs.append(
            IntraBucketScenarioSpec(
                bucket_id=bucket_id,
                weighted_sensitivities=tuple(bucket_weighted),
                base_correlation_matrix=matrix,
                sb_correlation_floor=None,
            )
        )

    bucket_ids = tuple(
        sorted((spec.bucket_id for spec in intra_specs), key=lambda value: int(value))
    )
    inter_bucket_correlations = build_commodity_inter_bucket_correlation_map(
        bucket_ids,
        profile_id=profile_id,
    )
    return aggregate_risk_class_with_scenarios(
        tuple(intra_specs),
        inter_bucket_correlations,
        risk_class=SbmRiskClass.COMMODITY,
        risk_measure=SbmRiskMeasure.DELTA,
    )


def build_commodity_delta_intra_bucket_correlation_matrix(
    ordered: Sequence[WeightedSensitivity],
    *,
    profile_id: str,
    bucket_id: str,
    commodity_by_id: Mapping[str, str],
    tenor_by_id: Mapping[str, str],
    location_by_id: Mapping[str, str],
) -> npt.NDArray[np.float64]:
    """Return the cited commodity delta intra-bucket correlation matrix."""

    size = len(ordered)
    matrix = np.eye(size, dtype=np.float64)
    for row_index, sensitivity_a in enumerate(ordered):
        for col_index in range(row_index + 1, size):
            sensitivity_b = ordered[col_index]
            correlation, _ = commodity_delta_intra_bucket_correlation(
                profile_id,
                bucket_id=bucket_id,
                commodity_a=commodity_by_id[sensitivity_a.sensitivity_id],
                commodity_b=commodity_by_id[sensitivity_b.sensitivity_id],
                tenor_a=tenor_by_id[sensitivity_a.sensitivity_id],
                tenor_b=tenor_by_id[sensitivity_b.sensitivity_id],
                location_a=location_by_id[sensitivity_a.sensitivity_id],
                location_b=location_by_id[sensitivity_b.sensitivity_id],
            )
            matrix[row_index, col_index] = correlation
            matrix[col_index, row_index] = correlation
    return matrix


def build_commodity_inter_bucket_correlation_map(
    bucket_ids: Sequence[str],
    *,
    profile_id: str,
) -> dict[tuple[str, str], float]:
    """Return cited commodity inter-bucket correlations for distinct bucket pairs."""

    correlations: dict[tuple[str, str], float] = {}
    ordered_ids = tuple(sorted(bucket_ids, key=lambda value: int(value)))
    for left_index, bucket_a in enumerate(ordered_ids):
        for bucket_b in ordered_ids[left_index + 1 :]:
            gamma, _ = commodity_inter_bucket_gamma(
                profile_id,
                bucket1=bucket_a,
                bucket2=bucket_b,
            )
            correlations[(bucket_a, bucket_b)] = gamma
    return correlations


__all__ = [
    "aggregate_commodity_delta_measure_capital",
    "build_commodity_delta_intra_bucket_correlation_matrix",
    "build_commodity_inter_bucket_correlation_map",
    "calculate_commodity_delta_risk_class_capital",
]
