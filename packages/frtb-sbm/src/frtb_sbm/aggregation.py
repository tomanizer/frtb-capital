"""Compatibility exports for shared SBM aggregation primitives."""

from __future__ import annotations

from frtb_sbm.kernel.aggregation import (
    InterBucketScenarioResult,
    IntraBucketAggregationResult,
    IntraBucketScenarioSpec,
    ScenarioSelectionResult,
    aggregate_inter_bucket,
    aggregate_intra_bucket,
    aggregate_risk_class_with_scenarios,
    group_weighted_sensitivities_by_bucket,
    select_max_correlation_scenario,
)
from frtb_sbm.kernel.correlation_scenarios import (
    adjust_correlation_for_scenario,
    adjust_correlation_matrix_for_scenario,
)
from frtb_sbm.kernel.pairwise_evidence import (
    PairwiseCorrelationEvidence,
    pairwise_correlation_audit_from_matrix,
)
from frtb_sbm.kernel.scenario_alignment import (
    align_risk_class_to_scenario,
    compute_portfolio_scenario_totals,
    select_portfolio_correlation_scenario,
)

__all__ = [
    "InterBucketScenarioResult",
    "IntraBucketAggregationResult",
    "IntraBucketScenarioSpec",
    "PairwiseCorrelationEvidence",
    "ScenarioSelectionResult",
    "adjust_correlation_for_scenario",
    "adjust_correlation_matrix_for_scenario",
    "aggregate_inter_bucket",
    "aggregate_intra_bucket",
    "aggregate_risk_class_with_scenarios",
    "align_risk_class_to_scenario",
    "compute_portfolio_scenario_totals",
    "group_weighted_sensitivities_by_bucket",
    "pairwise_correlation_audit_from_matrix",
    "select_max_correlation_scenario",
    "select_portfolio_correlation_scenario",
]
