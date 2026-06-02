"""
CSR securitisation CTP delta assembly onto shared SBM aggregation primitives.

Regulatory traceability:
    Basel MAR21.11 — underlying-name credit-spread delta risk factors.
    Basel MAR21.58-MAR21.60 — buckets, weights, correlations.
    SBM-FUNC-016.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import numpy.typing as npt

from frtb_sbm._batch_lookup import batch_text_by_id as _batch_text_by_id
from frtb_sbm.aggregation import (
    IntraBucketScenarioSpec,
    aggregate_risk_class_with_scenarios,
    group_weighted_sensitivities_by_bucket,
)
from frtb_sbm.batch import SbmSensitivityBatch, build_csr_sec_ctp_delta_batch_from_sensitivities
from frtb_sbm.csr_sec_ctp_reference_data import csr_sec_ctp_delta_intra_bucket_correlation
from frtb_sbm.data_models import (
    DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
    RiskClassCapital,
    SbmPairwiseEvidenceMode,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    WeightedSensitivity,
)
from frtb_sbm.risk_classes.csr_nonsec import build_csr_nonsec_inter_bucket_correlation_map
from frtb_sbm.weighted_sensitivity import weight_csr_sec_ctp_delta_sensitivity_batch

_MAR21_CSR_CTP_INTRA_CITATION = ("basel_mar21_4_intra_bucket", "basel_mar21_58")
_MAR21_CSR_CTP_INTER_CITATION = ("basel_mar21_4_inter_bucket", "basel_mar21_57")


def calculate_csr_sec_ctp_delta_risk_class_capital(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Calculate cited CSR securitisation CTP delta risk-class capital."""

    batch = build_csr_sec_ctp_delta_batch_from_sensitivities(sensitivities)
    return calculate_csr_sec_ctp_delta_risk_class_capital_from_batch(
        batch,
        profile_id=profile_id,
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def calculate_csr_sec_ctp_delta_risk_class_capital_from_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Calculate cited CSR securitisation CTP delta risk-class capital from a batch."""

    weighted = weight_csr_sec_ctp_delta_sensitivity_batch(
        batch,
        profile_id=profile_id,
    )
    return aggregate_csr_sec_ctp_delta_measure_capital(
        weighted,
        profile_id=profile_id,
        name_by_id=_batch_text_by_id(batch, batch.qualifiers, field="qualifier"),
        tenor_by_id=_batch_text_by_id(batch, batch.tenors, field="tenor"),
        risk_factor_by_id=_batch_text_by_id(batch, batch.risk_factors, field="risk_factor"),
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def aggregate_csr_sec_ctp_delta_measure_capital(
    weighted: tuple[WeightedSensitivity, ...],
    *,
    profile_id: str,
    name_by_id: Mapping[str, str],
    tenor_by_id: Mapping[str, str],
    risk_factor_by_id: Mapping[str, str],
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Aggregate weighted CSR securitisation CTP delta sensitivities."""

    grouped = group_weighted_sensitivities_by_bucket(weighted)
    intra_specs: list[IntraBucketScenarioSpec] = []
    for (_risk_class, _risk_measure, bucket_id), bucket_weighted in sorted(grouped.items()):
        matrix = build_csr_sec_ctp_delta_intra_bucket_correlation_matrix(
            bucket_weighted,
            profile_id=profile_id,
            bucket_id=bucket_id,
            name_by_id=name_by_id,
            tenor_by_id=tenor_by_id,
            risk_factor_by_id=risk_factor_by_id,
        )
        intra_specs.append(
            IntraBucketScenarioSpec(
                bucket_id=bucket_id,
                weighted_sensitivities=tuple(bucket_weighted),
                base_correlation_matrix=matrix,
            )
        )

    bucket_ids = tuple(spec.bucket_id for spec in intra_specs)
    inter_bucket_correlations = build_csr_nonsec_inter_bucket_correlation_map(
        bucket_ids,
        profile_id=profile_id,
    )
    return aggregate_risk_class_with_scenarios(
        tuple(intra_specs),
        inter_bucket_correlations,
        risk_class=SbmRiskClass.CSR_SEC_CTP,
        risk_measure=SbmRiskMeasure.DELTA,
        intra_bucket_citation_ids=_MAR21_CSR_CTP_INTRA_CITATION,
        inter_bucket_citation_ids=_MAR21_CSR_CTP_INTER_CITATION,
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def build_csr_sec_ctp_delta_intra_bucket_correlation_matrix(
    ordered: Sequence[WeightedSensitivity],
    *,
    profile_id: str,
    bucket_id: str,
    name_by_id: Mapping[str, str],
    tenor_by_id: Mapping[str, str],
    risk_factor_by_id: Mapping[str, str],
) -> npt.NDArray[np.float64]:
    """Return the cited CSR securitisation CTP delta intra-bucket correlation matrix."""

    size = len(ordered)
    matrix = np.eye(size, dtype=np.float64)
    for row_index, sensitivity_a in enumerate(ordered):
        for col_index in range(row_index + 1, size):
            sensitivity_b = ordered[col_index]
            correlation, _ = csr_sec_ctp_delta_intra_bucket_correlation(
                profile_id,
                bucket_id=bucket_id,
                name_a=name_by_id[sensitivity_a.sensitivity_id],
                name_b=name_by_id[sensitivity_b.sensitivity_id],
                tenor_a=tenor_by_id[sensitivity_a.sensitivity_id],
                tenor_b=tenor_by_id[sensitivity_b.sensitivity_id],
                risk_factor_a=risk_factor_by_id[sensitivity_a.sensitivity_id],
                risk_factor_b=risk_factor_by_id[sensitivity_b.sensitivity_id],
            )
            matrix[row_index, col_index] = correlation
            matrix[col_index, row_index] = correlation
    return matrix


__all__ = [
    "aggregate_csr_sec_ctp_delta_measure_capital",
    "build_csr_sec_ctp_delta_intra_bucket_correlation_matrix",
    "calculate_csr_sec_ctp_delta_risk_class_capital",
    "calculate_csr_sec_ctp_delta_risk_class_capital_from_batch",
]
