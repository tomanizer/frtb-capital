"""
Scenario-specific intra-bucket recomputation helpers for SBM risk-class aggregation.

Regulatory traceability:
    Basel MAR21.6 — recompute intra-bucket capital under correlation scenarios.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from frtb_sbm.data_models import (
    DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
    BucketCapital,
    IntraBucketScenarioRecord,
    PairwiseCorrelationRecord,
    SbmPairwiseEvidenceMode,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmScenarioLabel,
)
from frtb_sbm.kernel.bucket_aggregation import (
    IntraBucketAggregationResult,
    IntraBucketScenarioSpec,
    _sort_weighted_sensitivities,
    _validate_bucket_scope,
    aggregate_intra_bucket,
)
from frtb_sbm.kernel.correlation_scenarios import adjust_correlation_matrix_for_scenario
from frtb_sbm.kernel.pairwise_evidence import (
    _coerce_pairwise_evidence_mode,
    _pairwise_correlation_summary,
)

_MAR21_INTRA_BUCKET_CITATION = ("basel_mar21_4_intra_bucket",)


def _intra_bucket_to_scenario_record(
    result: IntraBucketAggregationResult,
) -> IntraBucketScenarioRecord:
    return IntraBucketScenarioRecord(
        bucket_id=result.bucket_capital.bucket_id,
        kb=result.bucket_capital.kb,
        sb=result.bucket_capital.sb or 0.0,
        floor_applied=result.bucket_capital.floor_applied,
        pairwise_correlations=tuple(
            PairwiseCorrelationRecord(
                sensitivity_a=evidence.sensitivity_id_a,
                sensitivity_b=evidence.sensitivity_id_b,
                correlation=evidence.correlation,
            )
            for evidence in result.pairwise_correlations
        ),
        citation_ids=result.bucket_capital.citation_ids,
        pairwise_correlation_summary=result.pairwise_correlation_summary,
    )


def _aggregate_intra_buckets_for_scenario(
    specs: Sequence[IntraBucketScenarioSpec],
    *,
    scenario: SbmScenarioLabel,
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
    intra_bucket_citation_ids: tuple[str, ...] = _MAR21_INTRA_BUCKET_CITATION,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> tuple[IntraBucketAggregationResult, ...]:
    results: list[IntraBucketAggregationResult] = []
    for spec in specs:
        if spec.absolute_weight_intra:
            results.append(
                _aggregate_absolute_weight_intra_bucket(
                    spec,
                    risk_class,
                    risk_measure,
                    pairwise_evidence_mode=pairwise_evidence_mode,
                )
            )
            continue
        adjusted_matrix = adjust_correlation_matrix_for_scenario(
            spec.base_correlation_matrix,
            scenario,
        )
        results.append(
            aggregate_intra_bucket(
                spec.bucket_id,
                spec.weighted_sensitivities,
                adjusted_matrix,
                risk_class=risk_class,
                risk_measure=risk_measure,
                sb_correlation_floor=spec.sb_correlation_floor,
                curvature_absolute_floor=spec.curvature_absolute_floor,
                citation_ids=intra_bucket_citation_ids,
                pairwise_evidence_mode=pairwise_evidence_mode,
                pairwise_evidence_limit=pairwise_evidence_limit,
            )
        )
    return tuple(results)


def _aggregate_absolute_weight_intra_bucket(
    spec: IntraBucketScenarioSpec,
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
    *,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
) -> IntraBucketAggregationResult:
    """MAR21.79: other-sector equity bucket capital equals sum of absolute weighted WS."""

    ordered = _sort_weighted_sensitivities(spec.weighted_sensitivities)
    _validate_bucket_scope(
        spec.bucket_id,
        ordered,
        risk_class,
        risk_measure,
    )
    ws = np.array([item.scaled_amount for item in ordered], dtype=np.float64)
    sb = float(np.sum(ws))
    kb = float(np.sum(np.abs(ws)))
    citation_ids = spec.absolute_weight_citation_ids or _MAR21_INTRA_BUCKET_CITATION
    bucket_capital = BucketCapital(
        bucket_id=spec.bucket_id,
        risk_class=risk_class,
        risk_measure=risk_measure,
        kb=kb,
        weighted_sensitivities=tuple(ordered),
        citation_ids=citation_ids,
        sb=sb,
        floor_applied=False,
    )
    return IntraBucketAggregationResult(
        bucket_capital=bucket_capital,
        pairwise_correlations=(),
        pairwise_correlation_summary=_pairwise_correlation_summary(
            ordered,
            mode=_coerce_pairwise_evidence_mode(pairwise_evidence_mode),
            materialized_count=0,
            total_count=0,
        ),
        variance_before_floor=float(np.dot(ws, ws)),
        zero_variance_floor_applied=False,
        sb_correlation_floor_applied=False,
    )


__all__ = [
    "_aggregate_intra_buckets_for_scenario",
    "_intra_bucket_to_scenario_record",
]
