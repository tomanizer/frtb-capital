"""
CSR non-securitisation delta assembly onto shared SBM aggregation primitives.

Regulatory traceability:
    Basel MAR21.9 — bond and CDS credit-spread delta risk factors.
    Basel MAR21.51-MAR21.57 — buckets, weights, correlations, other-sector rule.
    SBM-FUNC-014.
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
from frtb_sbm.csr_nonsec_reference_data import (
    CSR_OTHER_SECTOR_BUCKET,
    csr_nonsec_delta_intra_bucket_correlation,
    csr_nonsec_inter_bucket_correlation,
)
from frtb_sbm.data_models import (
    RiskClassCapital,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    WeightedSensitivity,
)
from frtb_sbm.weighted_sensitivity import weight_csr_nonsec_delta_sensitivities

_MAR21_CSR_OTHER_SECTOR_CITATION = ("basel_mar21_56",)
_MAR21_CSR_INTRA_CITATION = ("basel_mar21_4_intra_bucket", "basel_mar21_54")
_MAR21_CSR_INDEX_INTRA_CITATION = ("basel_mar21_4_intra_bucket", "basel_mar21_55")
_MAR21_CSR_INTER_CITATION = ("basel_mar21_4_inter_bucket", "basel_mar21_57")


def calculate_csr_nonsec_delta_risk_class_capital(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
) -> RiskClassCapital:
    """Calculate cited CSR non-securitisation delta risk-class capital."""

    weighted = weight_csr_nonsec_delta_sensitivities(
        sensitivities,
        profile_id=profile_id,
    )
    return aggregate_csr_nonsec_delta_measure_capital(
        weighted,
        profile_id=profile_id,
        issuer_by_id={item.sensitivity_id: item.qualifier or "" for item in sensitivities},
        tenor_by_id={item.sensitivity_id: item.tenor or "" for item in sensitivities},
        risk_factor_by_id={item.sensitivity_id: item.risk_factor for item in sensitivities},
    )


def aggregate_csr_nonsec_delta_measure_capital(
    weighted: tuple[WeightedSensitivity, ...],
    *,
    profile_id: str,
    issuer_by_id: Mapping[str, str],
    tenor_by_id: Mapping[str, str],
    risk_factor_by_id: Mapping[str, str],
) -> RiskClassCapital:
    """Aggregate weighted CSR non-securitisation delta sensitivities."""

    grouped = group_weighted_sensitivities_by_bucket(weighted)
    intra_specs: list[IntraBucketScenarioSpec] = []
    for (_risk_class, _risk_measure, bucket_id), bucket_weighted in sorted(grouped.items()):
        matrix = build_csr_nonsec_delta_intra_bucket_correlation_matrix(
            bucket_weighted,
            profile_id=profile_id,
            bucket_id=bucket_id,
            issuer_by_id=issuer_by_id,
            tenor_by_id=tenor_by_id,
            risk_factor_by_id=risk_factor_by_id,
        )
        intra_specs.append(
            IntraBucketScenarioSpec(
                bucket_id=bucket_id,
                weighted_sensitivities=tuple(bucket_weighted),
                base_correlation_matrix=matrix,
                sb_correlation_floor=None,
                absolute_weight_intra=bucket_id == CSR_OTHER_SECTOR_BUCKET,
                absolute_weight_citation_ids=_MAR21_CSR_OTHER_SECTOR_CITATION
                if bucket_id == CSR_OTHER_SECTOR_BUCKET
                else (),
            )
        )

    bucket_ids = tuple(spec.bucket_id for spec in intra_specs)
    inter_bucket_correlations = build_csr_nonsec_inter_bucket_correlation_map(
        bucket_ids,
        profile_id=profile_id,
    )
    has_index = any(spec.bucket_id in {"17", "18"} for spec in intra_specs)
    has_non_index = any(spec.bucket_id not in {"17", "18"} for spec in intra_specs)
    if has_index and has_non_index:
        intra_citations = (
            "basel_mar21_4_intra_bucket",
            "basel_mar21_54",
            "basel_mar21_55",
        )
    elif has_index:
        intra_citations = _MAR21_CSR_INDEX_INTRA_CITATION
    else:
        intra_citations = _MAR21_CSR_INTRA_CITATION
    return aggregate_risk_class_with_scenarios(
        tuple(intra_specs),
        inter_bucket_correlations,
        risk_class=SbmRiskClass.CSR_NONSEC,
        risk_measure=SbmRiskMeasure.DELTA,
        intra_bucket_citation_ids=intra_citations,
        inter_bucket_citation_ids=_MAR21_CSR_INTER_CITATION,
    )


def build_csr_nonsec_delta_intra_bucket_correlation_matrix(
    ordered: Sequence[WeightedSensitivity],
    *,
    profile_id: str,
    bucket_id: str,
    issuer_by_id: Mapping[str, str],
    tenor_by_id: Mapping[str, str],
    risk_factor_by_id: Mapping[str, str],
) -> npt.NDArray[np.float64]:
    """Return the cited CSR non-securitisation delta intra-bucket correlation matrix."""

    if bucket_id == CSR_OTHER_SECTOR_BUCKET:
        size = len(ordered)
        return np.eye(size, dtype=np.float64)

    size = len(ordered)
    if size == 0:
        return np.zeros((0, 0), dtype=np.float64)
    matrix = np.eye(size, dtype=np.float64)
    for row_index, sensitivity_a in enumerate(ordered):
        for col_index in range(row_index + 1, size):
            sensitivity_b = ordered[col_index]
            correlation, _ = csr_nonsec_delta_intra_bucket_correlation(
                profile_id,
                bucket_id=bucket_id,
                risk_factor_a=risk_factor_by_id[sensitivity_a.sensitivity_id],
                risk_factor_b=risk_factor_by_id[sensitivity_b.sensitivity_id],
                issuer_a=issuer_by_id[sensitivity_a.sensitivity_id],
                issuer_b=issuer_by_id[sensitivity_b.sensitivity_id],
                tenor_a=tenor_by_id[sensitivity_a.sensitivity_id],
                tenor_b=tenor_by_id[sensitivity_b.sensitivity_id],
            )
            matrix[row_index, col_index] = correlation
            matrix[col_index, row_index] = correlation
    return matrix


def build_csr_nonsec_inter_bucket_correlation_map(
    bucket_ids: Sequence[str],
    *,
    profile_id: str,
) -> dict[tuple[str, str], float]:
    """Return cited CSR non-securitisation inter-bucket correlations."""

    correlations: dict[tuple[str, str], float] = {}
    ordered_ids = tuple(sorted(bucket_ids))
    for left_index, bucket_a in enumerate(ordered_ids):
        for bucket_b in ordered_ids[left_index + 1 :]:
            gamma, _ = csr_nonsec_inter_bucket_correlation(
                profile_id,
                bucket1=bucket_a,
                bucket2=bucket_b,
            )
            correlations[(bucket_a, bucket_b)] = gamma
    return correlations


__all__ = [
    "aggregate_csr_nonsec_delta_measure_capital",
    "build_csr_nonsec_delta_intra_bucket_correlation_matrix",
    "build_csr_nonsec_inter_bucket_correlation_map",
    "calculate_csr_nonsec_delta_risk_class_capital",
]
