"""
Equity delta assembly onto shared SBM aggregation primitives.

Regulatory traceability:
    Basel MAR21.12 — equity spot and repo delta risk factors.
    Basel MAR21.71-MAR21.80 — buckets, weights, correlations, other-sector rule.
    SBM-FUNC-017.
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
from frtb_sbm.batch import SbmSensitivityBatch, build_equity_delta_batch_from_sensitivities
from frtb_sbm.data_models import (
    DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
    RiskClassCapital,
    SbmPairwiseEvidenceMode,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    WeightedSensitivity,
)
from frtb_sbm.equity_reference_data import (
    EQUITY_OTHER_SECTOR_BUCKET,
    _require_equity_bucket_number,
    equity_delta_intra_bucket_correlation,
    equity_inter_bucket_correlation,
)
from frtb_sbm.weighted_sensitivity import weight_equity_delta_sensitivity_batch

_MAR21_EQUITY_OTHER_SECTOR_CITATION = ("basel_mar21_79",)


def calculate_equity_delta_risk_class_capital(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Calculate cited equity delta risk-class capital for a supported profile."""

    batch = build_equity_delta_batch_from_sensitivities(sensitivities)
    return calculate_equity_delta_risk_class_capital_from_batch(
        batch,
        profile_id=profile_id,
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def calculate_equity_delta_risk_class_capital_from_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Calculate cited equity delta risk-class capital from a package-owned batch."""

    from frtb_sbm.batch import _batch_text_by_id

    weighted = weight_equity_delta_sensitivity_batch(
        batch,
        profile_id=profile_id,
    )
    return aggregate_equity_delta_measure_capital(
        weighted,
        profile_id=profile_id,
        issuer_by_id=_batch_text_by_id(batch, batch.qualifiers, field="qualifier"),
        risk_factor_by_id=_batch_text_by_id(batch, batch.risk_factors, field="risk_factor"),
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def aggregate_equity_delta_measure_capital(
    weighted: tuple[WeightedSensitivity, ...],
    *,
    profile_id: str,
    issuer_by_id: Mapping[str, str],
    risk_factor_by_id: Mapping[str, str],
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Aggregate weighted equity delta sensitivities through shared bucket primitives."""

    grouped = group_weighted_sensitivities_by_bucket(weighted)
    intra_specs: list[IntraBucketScenarioSpec] = []
    for (_risk_class, _risk_measure, bucket_id), bucket_weighted in sorted(grouped.items()):
        matrix = build_equity_delta_intra_bucket_correlation_matrix(
            bucket_weighted,
            profile_id=profile_id,
            bucket_id=bucket_id,
            issuer_by_id=issuer_by_id,
            risk_factor_by_id=risk_factor_by_id,
        )
        intra_specs.append(
            IntraBucketScenarioSpec(
                bucket_id=bucket_id,
                weighted_sensitivities=tuple(bucket_weighted),
                base_correlation_matrix=matrix,
                sb_correlation_floor=None,
                absolute_weight_intra=bucket_id == EQUITY_OTHER_SECTOR_BUCKET,
                absolute_weight_citation_ids=_MAR21_EQUITY_OTHER_SECTOR_CITATION
                if bucket_id == EQUITY_OTHER_SECTOR_BUCKET
                else (),
            )
        )

    bucket_ids = tuple(spec.bucket_id for spec in intra_specs)
    inter_bucket_correlations = build_equity_inter_bucket_correlation_map(
        bucket_ids,
        profile_id=profile_id,
    )
    return aggregate_risk_class_with_scenarios(
        tuple(intra_specs),
        inter_bucket_correlations,
        risk_class=SbmRiskClass.EQUITY,
        risk_measure=SbmRiskMeasure.DELTA,
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def build_equity_delta_intra_bucket_correlation_matrix(
    ordered: Sequence[WeightedSensitivity],
    *,
    profile_id: str,
    bucket_id: str,
    issuer_by_id: Mapping[str, str],
    risk_factor_by_id: Mapping[str, str],
) -> npt.NDArray[np.float64]:
    """Return the cited equity delta intra-bucket correlation matrix."""

    if bucket_id == EQUITY_OTHER_SECTOR_BUCKET:
        size = len(ordered)
        return np.eye(size, dtype=np.float64)

    size = len(ordered)
    matrix = np.eye(size, dtype=np.float64)
    for row_index, sensitivity_a in enumerate(ordered):
        for col_index in range(row_index + 1, size):
            sensitivity_b = ordered[col_index]
            correlation, _ = equity_delta_intra_bucket_correlation(
                profile_id,
                bucket_id=bucket_id,
                risk_factor_a=risk_factor_by_id[sensitivity_a.sensitivity_id],
                risk_factor_b=risk_factor_by_id[sensitivity_b.sensitivity_id],
                issuer_a=issuer_by_id[sensitivity_a.sensitivity_id],
                issuer_b=issuer_by_id[sensitivity_b.sensitivity_id],
            )
            matrix[row_index, col_index] = correlation
            matrix[col_index, row_index] = correlation
    return matrix


def build_equity_inter_bucket_correlation_map(
    bucket_ids: Sequence[str],
    *,
    profile_id: str,
) -> dict[tuple[str, str], float]:
    """Return cited equity inter-bucket correlations for distinct bucket pairs."""

    correlations: dict[tuple[str, str], float] = {}
    ordered_ids = tuple(sorted(bucket_ids, key=_require_equity_bucket_number))
    for left_index, bucket_a in enumerate(ordered_ids):
        for bucket_b in ordered_ids[left_index + 1 :]:
            gamma, _ = equity_inter_bucket_correlation(
                profile_id,
                bucket1=bucket_a,
                bucket2=bucket_b,
            )
            correlations[(bucket_a, bucket_b)] = gamma
    return correlations


__all__ = [
    "aggregate_equity_delta_measure_capital",
    "build_equity_delta_intra_bucket_correlation_matrix",
    "build_equity_inter_bucket_correlation_map",
    "calculate_equity_delta_risk_class_capital",
    "calculate_equity_delta_risk_class_capital_from_batch",
]
