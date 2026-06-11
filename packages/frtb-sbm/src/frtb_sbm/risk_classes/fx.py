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

from frtb_sbm.adapters.sensitivities import build_sbm_batch
from frtb_sbm.aggregation import (
    IntraBucketScenarioSpec,
    aggregate_risk_class_with_scenarios,
    group_weighted_sensitivities_by_bucket,
)
from frtb_sbm.batch import SbmSensitivityBatch
from frtb_sbm.data_models import (
    DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
    RiskClassCapital,
    SbmPairwiseEvidenceMode,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    WeightedSensitivity,
)
from frtb_sbm.reference_data import (
    fx_delta_intra_bucket_correlation,
    fx_inter_bucket_correlation,
)
from frtb_sbm.risk_classes.fx_weighting import weight_fx_delta_sensitivity_batch


def calculate_fx_delta_risk_class_capital(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
    reporting_currency: str,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Calculate cited FX delta risk-class capital for a supported profile.
    Parameters
    ----------
    sensitivities, profile_id, reporting_currency, pairwise_evidence_mode, pairwise_evidence_limit :
        See function signature for types and defaults.

    Returns
    -------
    RiskClassCapital
    """

    batch = build_sbm_batch(sensitivities, SbmRiskClass.FX, SbmRiskMeasure.DELTA)
    return calculate_fx_delta_risk_class_capital_from_batch(
        batch,
        profile_id=profile_id,
        reporting_currency=reporting_currency,
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def calculate_fx_delta_risk_class_capital_from_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
    reporting_currency: str,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Calculate cited FX delta risk-class capital from a package-owned batch.
    Parameters
    ----------
    batch, profile_id, reporting_currency, pairwise_evidence_mode, pairwise_evidence_limit :
        See function signature for types and defaults.

    Returns
    -------
    RiskClassCapital
    """

    weighted = weight_fx_delta_sensitivity_batch(
        batch,
        profile_id=profile_id,
        reporting_currency=reporting_currency,
    )
    return aggregate_fx_delta_measure_capital(
        weighted,
        profile_id=profile_id,
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def aggregate_fx_delta_measure_capital(
    weighted: tuple[WeightedSensitivity, ...],
    *,
    profile_id: str,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Aggregate weighted FX delta sensitivities through shared bucket primitives.
    Parameters
    ----------
    weighted, profile_id, pairwise_evidence_mode, pairwise_evidence_limit :
        See function signature for types and defaults.

    Returns
    -------
    RiskClassCapital
    """

    grouped = group_weighted_sensitivities_by_bucket(weighted)

    intra_specs: list[IntraBucketScenarioSpec] = []
    for (_risk_class, _risk_measure, bucket_id), bucket_weighted in sorted(grouped.items()):
        matrix = build_fx_delta_intra_bucket_correlation_matrix(
            bucket_weighted,
            profile_id=profile_id,
        )
        intra_specs.append(
            IntraBucketScenarioSpec(
                bucket_id=bucket_id,
                weighted_sensitivities=tuple(bucket_weighted),
                base_correlation_matrix=matrix,
                sb_correlation_floor=None,
            )
        )

    bucket_ids = tuple(sorted(spec.bucket_id for spec in intra_specs))
    inter_bucket_correlations = build_fx_inter_bucket_correlation_map(
        bucket_ids,
        profile_id=profile_id,
    )
    return aggregate_risk_class_with_scenarios(
        tuple(intra_specs),
        inter_bucket_correlations,
        risk_class=SbmRiskClass.FX,
        risk_measure=SbmRiskMeasure.DELTA,
        intra_bucket_citation_ids=("basel_mar21_4_intra_bucket", "basel_mar21_86"),
        inter_bucket_citation_ids=("basel_mar21_4_inter_bucket", "basel_mar21_89"),
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def build_fx_delta_intra_bucket_correlation_matrix(
    ordered: Sequence[WeightedSensitivity],
    *,
    profile_id: str,
) -> npt.NDArray[np.float64]:
    """Return the cited FX delta intra-bucket correlation matrix.
    Parameters
    ----------
    ordered : Sequence[WeightedSensitivity]
        See signature.
    profile_id : str
        See signature.

    Returns
    -------
    npt.NDArray[np.float64]
    """

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
    """Return cited FX inter-bucket correlations for distinct bucket pairs.
    Parameters
    ----------
    bucket_ids : Sequence[str]
        See signature.
    profile_id : str
        See signature.

    Returns
    -------
    dict[tuple[str, str], float]
    """

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
    "calculate_fx_delta_risk_class_capital_from_batch",
]
