"""
Pairwise correlation evidence helpers for SBM aggregation audit records.

Regulatory traceability:
    Basel MAR21.4(4) — within-bucket aggregation correlation evidence.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from frtb_sbm.data_models import (
    PairwiseCorrelationRecord,
    PairwiseCorrelationSummary,
    SbmPairwiseEvidenceMode,
    WeightedSensitivity,
)
from frtb_sbm.validation import SbmInputError


@dataclass(frozen=True)
class PairwiseCorrelationEvidence:
    """Audit record for one pairwise intra-bucket correlation."""

    sensitivity_id_a: str
    sensitivity_id_b: str
    correlation: float
    citation_ids: tuple[str, ...] = ()


def pairwise_correlation_audit_from_matrix(
    factor_ids: Sequence[str],
    matrix: npt.NDArray[np.float64],
    *,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str,
    pairwise_evidence_limit: int,
) -> tuple[tuple[PairwiseCorrelationRecord, ...], PairwiseCorrelationSummary]:
    """Build pairwise correlation audit records honoring evidence mode controls.
    Parameters
    ----------
    factor_ids, matrix, pairwise_evidence_mode, pairwise_evidence_limit :
        See function signature for types and defaults.

    Returns
    -------
    tuple[tuple[PairwiseCorrelationRecord, ...], PairwiseCorrelationSummary]
    """

    mode = _coerce_pairwise_evidence_mode(pairwise_evidence_mode)
    size = len(factor_ids)
    total_count = _upper_triangle_count(size)
    if (
        isinstance(pairwise_evidence_limit, bool)
        or not isinstance(pairwise_evidence_limit, int)
        or pairwise_evidence_limit < 0
    ):
        raise SbmInputError(
            "pairwise_evidence_limit must be a non-negative integer",
            field="pairwise_evidence_limit",
        )
    materialize = mode is SbmPairwiseEvidenceMode.FULL or (
        mode is SbmPairwiseEvidenceMode.AUTO and total_count <= pairwise_evidence_limit
    )
    if not materialize:
        return (), _pairwise_correlation_summary_from_factor_ids(
            factor_ids,
            mode=mode,
            materialized_count=0,
            total_count=total_count,
        )

    records: list[PairwiseCorrelationRecord] = []
    for row_index, factor_a in enumerate(factor_ids):
        for col_index in range(row_index, size):
            factor_b = factor_ids[col_index]
            records.append(
                PairwiseCorrelationRecord(
                    sensitivity_a=factor_a,
                    sensitivity_b=factor_b,
                    correlation=float(matrix[row_index, col_index]),
                )
            )
    pairwise = tuple(records)
    return pairwise, _pairwise_correlation_summary_from_factor_ids(
        factor_ids,
        mode=mode,
        materialized_count=len(pairwise),
        total_count=total_count,
    )


def _pairwise_correlation_audit(
    ordered: Sequence[WeightedSensitivity],
    matrix: npt.NDArray[np.float64],
    citation_ids: tuple[str, ...],
    *,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str,
    pairwise_evidence_limit: int,
) -> tuple[tuple[PairwiseCorrelationEvidence, ...], PairwiseCorrelationSummary]:
    mode = _coerce_pairwise_evidence_mode(pairwise_evidence_mode)
    total_count = _upper_triangle_count(len(ordered))
    if (
        isinstance(pairwise_evidence_limit, bool)
        or not isinstance(pairwise_evidence_limit, int)
        or pairwise_evidence_limit < 0
    ):
        raise SbmInputError(
            "pairwise_evidence_limit must be a non-negative integer",
            field="pairwise_evidence_limit",
        )
    materialize = mode is SbmPairwiseEvidenceMode.FULL or (
        mode is SbmPairwiseEvidenceMode.AUTO and total_count <= pairwise_evidence_limit
    )
    if not materialize:
        return (), _pairwise_correlation_summary(
            ordered,
            mode=mode,
            materialized_count=0,
            total_count=total_count,
        )

    records: list[PairwiseCorrelationEvidence] = []
    for row_index, sensitivity_a in enumerate(ordered):
        for col_index in range(row_index, len(ordered)):
            sensitivity_b = ordered[col_index]
            records.append(
                PairwiseCorrelationEvidence(
                    sensitivity_id_a=sensitivity_a.sensitivity_id,
                    sensitivity_id_b=sensitivity_b.sensitivity_id,
                    correlation=float(matrix[row_index, col_index]),
                    citation_ids=citation_ids,
                )
            )
    pairwise = tuple(records)
    return pairwise, _pairwise_correlation_summary(
        ordered,
        mode=mode,
        materialized_count=len(pairwise),
        total_count=total_count,
    )


def _pairwise_correlation_summary(
    ordered: Sequence[WeightedSensitivity],
    *,
    mode: SbmPairwiseEvidenceMode,
    materialized_count: int,
    total_count: int,
) -> PairwiseCorrelationSummary:
    return _pairwise_correlation_summary_from_factor_ids(
        tuple(item.sensitivity_id for item in ordered),
        mode=mode,
        materialized_count=materialized_count,
        total_count=total_count,
    )


def _pairwise_correlation_summary_from_factor_ids(
    factor_ids: Sequence[str],
    *,
    mode: SbmPairwiseEvidenceMode,
    materialized_count: int,
    total_count: int,
) -> PairwiseCorrelationSummary:
    return PairwiseCorrelationSummary(
        evidence_mode=mode,
        total_count=total_count,
        materialized_count=materialized_count,
        omitted_count=total_count - materialized_count,
        factor_ids=tuple(factor_ids),
    )


def _upper_triangle_count(size: int) -> int:
    return size * (size + 1) // 2


def _coerce_pairwise_evidence_mode(
    mode: SbmPairwiseEvidenceMode | str,
) -> SbmPairwiseEvidenceMode:
    from frtb_sbm.validation import coerce_pairwise_evidence_mode

    return coerce_pairwise_evidence_mode(mode)


__all__ = [
    "PairwiseCorrelationEvidence",
    "pairwise_correlation_audit_from_matrix",
]
