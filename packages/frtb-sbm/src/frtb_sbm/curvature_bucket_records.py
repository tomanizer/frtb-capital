"""Curvature bucket scenario record conversion helpers.

Regulatory traceability:
    Basel MAR21.5, MAR21.6-MAR21.7, and SBM-CURV-001.
"""

from __future__ import annotations

from frtb_sbm.aggregation import pairwise_correlation_audit_from_matrix
from frtb_sbm.curvature_bucket_scenarios import (
    _CURVATURE_UP_BRANCH,
    _CurvatureBucketScenario,
)
from frtb_sbm.curvature_factors import _CurvatureFactor
from frtb_sbm.data_models import (
    BucketCapital,
    CurvatureBucketBranchRecord,
    IntraBucketScenarioRecord,
    PairwiseCorrelationRecord,
    PairwiseCorrelationSummary,
    SbmPairwiseEvidenceMode,
    SbmRiskMeasure,
    SbmScenarioLabel,
    WeightedSensitivity,
)


def _curvature_bucket_to_intra_record(
    bucket_scenario: _CurvatureBucketScenario,
    *,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str,
    pairwise_evidence_limit: int,
) -> IntraBucketScenarioRecord:
    pairwise_records, summary = _curvature_pairwise_audit(
        bucket_scenario,
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )
    return IntraBucketScenarioRecord(
        bucket_id=bucket_scenario.bucket_id,
        kb=bucket_scenario.selected.bucket_capital,
        sb=bucket_scenario.selected.branch_sum,
        floor_applied=bucket_scenario.selected.floor_applied,
        pairwise_correlations=pairwise_records,
        citation_ids=bucket_scenario.citation_ids,
        pairwise_correlation_summary=summary,
    )


def _curvature_bucket_to_bucket_capital(
    bucket_scenario: _CurvatureBucketScenario,
) -> BucketCapital:
    risk_class = bucket_scenario.factors[0].risk_class
    return BucketCapital(
        bucket_id=bucket_scenario.bucket_id,
        risk_class=risk_class,
        risk_measure=SbmRiskMeasure.CURVATURE,
        kb=bucket_scenario.selected.bucket_capital,
        weighted_sensitivities=tuple(
            _curvature_factor_to_weighted_sensitivity(
                factor,
                selected_branch=bucket_scenario.selected.branch,
                scenario=bucket_scenario.scenario,
            )
            for factor in bucket_scenario.factors
        ),
        citation_ids=bucket_scenario.citation_ids,
        scenario=bucket_scenario.scenario,
        sb=bucket_scenario.selected.branch_sum,
        floor_applied=bucket_scenario.selected.floor_applied,
    )


def _curvature_factor_to_weighted_sensitivity(
    factor: _CurvatureFactor,
    *,
    selected_branch: str,
    scenario: SbmScenarioLabel,
) -> WeightedSensitivity:
    cvr = factor.up_cvr if selected_branch == _CURVATURE_UP_BRANCH else factor.down_cvr
    return WeightedSensitivity(
        sensitivity_id=factor.factor_id,
        risk_class=factor.risk_class,
        risk_measure=SbmRiskMeasure.CURVATURE,
        bucket=factor.bucket_id,
        raw_amount=cvr,
        risk_weight=1.0,
        scaled_amount=cvr,
        citation_ids=factor.citation_ids,
        qualifier=_curvature_weighted_qualifier(factor, selected_branch, scenario),
        factor_key=tuple(factor.factor_id.split("|")),
        contributing_sensitivity_ids=factor.sensitivity_ids,
        contributing_source_row_ids=factor.source_row_ids,
        org_scope=factor.org_scope,
        contributing_org_scopes=factor.contributing_org_scopes,
        up_shock_ids=factor.up_shock_ids,
        down_shock_ids=factor.down_shock_ids,
        surface_id=_single_optional_value(factor.surface_ids),
        surface_point_id=_single_optional_value(factor.surface_point_ids),
    )


def _curvature_pairwise_audit(
    bucket_scenario: _CurvatureBucketScenario,
    *,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str,
    pairwise_evidence_limit: int,
) -> tuple[tuple[PairwiseCorrelationRecord, ...], PairwiseCorrelationSummary]:
    factors = bucket_scenario.factors
    return pairwise_correlation_audit_from_matrix(
        tuple(factor.factor_id for factor in factors),
        bucket_scenario.correlation_matrix,
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def _curvature_bucket_branch_record(
    bucket_scenario: _CurvatureBucketScenario,
) -> CurvatureBucketBranchRecord:
    return CurvatureBucketBranchRecord(
        bucket_id=bucket_scenario.bucket_id,
        scenario=bucket_scenario.scenario,
        selected_branch=bucket_scenario.selected.branch,
        rejected_branch=bucket_scenario.rejected.branch,
        selected_bucket_capital=bucket_scenario.selected.bucket_capital,
        rejected_bucket_capital=bucket_scenario.rejected.bucket_capital,
        up_bucket_capital=bucket_scenario.up.bucket_capital,
        down_bucket_capital=bucket_scenario.down.bucket_capital,
        selected_sum=bucket_scenario.selected.branch_sum,
        up_sum=bucket_scenario.up.branch_sum,
        down_sum=bucket_scenario.down.branch_sum,
        selected_psi_zero_count=bucket_scenario.selected.psi_zero_count,
        up_psi_zero_count=bucket_scenario.up.psi_zero_count,
        down_psi_zero_count=bucket_scenario.down.psi_zero_count,
        floor_applied=bucket_scenario.selected.floor_applied,
        citation_ids=bucket_scenario.citation_ids,
    )


def _curvature_weighted_qualifier(
    factor: _CurvatureFactor,
    selected_branch: str,
    scenario: SbmScenarioLabel,
) -> str:
    parts = [factor.risk_factor]
    if factor.qualifier:
        parts.append(factor.qualifier)
    parts.extend([selected_branch, scenario.value])
    return ":".join(parts)


def _single_optional_value(values: tuple[str, ...]) -> str | None:
    if len(values) == 1:
        return values[0]
    return None


__all__ = [
    "_curvature_bucket_branch_record",
    "_curvature_bucket_to_bucket_capital",
    "_curvature_bucket_to_intra_record",
    "_curvature_factor_to_weighted_sensitivity",
    "_curvature_pairwise_audit",
    "_curvature_weighted_qualifier",
]
