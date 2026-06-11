"""Compatibility exports for SBM aggregation kernel modules."""

from __future__ import annotations

from frtb_sbm.kernel.bucket_aggregation import (
    IntraBucketAggregationResult,
    IntraBucketScenarioSpec,
    aggregate_intra_bucket,
    group_weighted_sensitivities_by_bucket,
)
from frtb_sbm.kernel.inter_bucket_aggregation import (
    InterBucketScenarioResult,
    aggregate_inter_bucket,
)
from frtb_sbm.kernel.risk_class_aggregation import (
    ScenarioSelectionResult,
    aggregate_risk_class_with_scenarios,
    select_max_correlation_scenario,
)

__all__ = [
    "InterBucketScenarioResult",
    "IntraBucketAggregationResult",
    "IntraBucketScenarioSpec",
    "ScenarioSelectionResult",
    "aggregate_inter_bucket",
    "aggregate_intra_bucket",
    "aggregate_risk_class_with_scenarios",
    "group_weighted_sensitivities_by_bucket",
    "select_max_correlation_scenario",
]
