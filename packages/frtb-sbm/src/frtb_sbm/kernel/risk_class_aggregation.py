"""
Risk-class scenario aggregation and selection for SBM capital kernels.

Regulatory traceability:
    Basel MAR21.6 — low, medium, and high correlation scenarios.
    Basel MAR21.7(2) — select the largest risk-class capital across scenarios.
    U.S. NPR 2.0 section V.A.7.a steps four through six.
    SBM-REQ-006.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import cast

from frtb_sbm._citations import merge_citation_ids as _merge_citation_ids
from frtb_sbm.data_models import (
    DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
    BucketCapital,
    RiskClassCapital,
    RiskClassScenarioDetail,
    SbmBranchMetadata,
    SbmBranchType,
    SbmPairwiseEvidenceMode,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmScenarioLabel,
)
from frtb_sbm.kernel.bucket_aggregation import (
    IntraBucketAggregationResult,
    IntraBucketScenarioSpec,
)
from frtb_sbm.kernel.inter_bucket_aggregation import (
    InterBucketScenarioResult,
    _as_bucket_capital,
    aggregate_inter_bucket,
)
from frtb_sbm.kernel.scenario_bucket_aggregation import (
    _aggregate_intra_buckets_for_scenario,
    _intra_bucket_to_scenario_record,
)
from frtb_sbm.validation import SbmInputError

_MAR21_INTRA_BUCKET_CITATION = ("basel_mar21_4_intra_bucket",)
_MAR21_INTER_BUCKET_CITATION = ("basel_mar21_4_inter_bucket",)
_MAR21_SCENARIO_CITATION = (
    "basel_mar21_6_correlation_scenarios",
    "basel_mar21_7_scenario_selection",
)
_MAR21_SCENARIO_SELECTION_CITATION = ("basel_mar21_7_scenario_selection",)

_DEFAULT_SCENARIOS: tuple[SbmScenarioLabel, ...] = (
    SbmScenarioLabel.LOW,
    SbmScenarioLabel.MEDIUM,
    SbmScenarioLabel.HIGH,
)


@dataclass(frozen=True)
class ScenarioSelectionResult:
    """Selected scenario outcome for a risk class."""

    scenario_totals: Mapping[SbmScenarioLabel, float]
    selected_scenario: SbmScenarioLabel
    selected_capital: float
    branch_metadata: SbmBranchMetadata
    citation_ids: tuple[str, ...]


def select_max_correlation_scenario(
    scenario_totals: Mapping[SbmScenarioLabel, float],
    *,
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure | None = None,
    branch_id: str | None = None,
    citation_ids: tuple[str, ...] = _MAR21_SCENARIO_SELECTION_CITATION,
) -> ScenarioSelectionResult:
    """Select the maximum risk-class capital across correlation scenarios.

    GIRR delta capital uses the largest scenario total per MAR21.7(2).
    Parameters
    ----------
    scenario_totals, risk_class, risk_measure, branch_id, citation_ids :
        See function signature for types and defaults.

    Returns
    -------
    ScenarioSelectionResult
    """
    if not scenario_totals:
        raise SbmInputError("scenario_totals must not be empty", field="scenario_totals")

    selected_scenario = max(
        scenario_totals,
        key=lambda label: (scenario_totals[label], _scenario_rank(label)),
    )
    selected_capital = float(scenario_totals[selected_scenario])
    resolved_branch_id = branch_id
    if resolved_branch_id is None:
        measure_suffix = f"_{risk_measure.value.lower()}" if risk_measure is not None else ""
        resolved_branch_id = f"{risk_class.value.lower()}{measure_suffix}_scenario_selection"
    branch = SbmBranchMetadata(
        branch_id=resolved_branch_id,
        branch_type=SbmBranchType.SCENARIO_SELECTION,
        source_id="mar21_7_2",
        selected=True,
        reason=(
            f"selected {selected_scenario.value} scenario with capital "
            f"{selected_capital} as the maximum across correlation scenarios"
        ),
        citation_ids=citation_ids,
    )
    return ScenarioSelectionResult(
        scenario_totals=dict(scenario_totals),
        selected_scenario=selected_scenario,
        selected_capital=selected_capital,
        branch_metadata=branch,
        citation_ids=citation_ids,
    )


def aggregate_risk_class_with_scenarios(
    bucket_inputs: Sequence[IntraBucketScenarioSpec | IntraBucketAggregationResult | BucketCapital],
    inter_bucket_correlations: Mapping[tuple[str, str], float],
    *,
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
    scenarios: Sequence[SbmScenarioLabel] = _DEFAULT_SCENARIOS,
    apply_scenario_adjustment: bool = True,
    citation_ids: tuple[str, ...] = _MAR21_SCENARIO_CITATION,
    intra_bucket_citation_ids: tuple[str, ...] = _MAR21_INTRA_BUCKET_CITATION,
    inter_bucket_citation_ids: tuple[str, ...] = _MAR21_INTER_BUCKET_CITATION,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Evaluate low/medium/high scenarios with intra- and inter-bucket recomputation.

    Parameters
    ----------
    bucket_inputs, inter_bucket_correlations, risk_class, risk_measure, scenarios,
    apply_scenario_adjustment, citation_ids, intra_bucket_citation_ids,
    inter_bucket_citation_ids, pairwise_evidence_mode, pairwise_evidence_limit :
        Same contract as the compatibility export in ``frtb_sbm.aggregation``.

    Returns
    -------
    RiskClassCapital
        Selected risk-class capital with scenario totals, selected buckets, citations,
        and branch metadata preserved.
    """
    if not bucket_inputs:
        raise SbmInputError("bucket_inputs must not be empty", field="bucket_inputs")
    if not scenarios:
        raise SbmInputError("scenarios must not be empty", field="scenarios")

    specs = _coerce_scenario_specs(bucket_inputs)
    scenario_results, scenario_details, intra_by_scenario = _evaluate_risk_class_scenarios(
        bucket_inputs,
        specs=specs,
        inter_bucket_correlations=inter_bucket_correlations,
        risk_class=risk_class,
        risk_measure=risk_measure,
        scenarios=scenarios,
        apply_scenario_adjustment=apply_scenario_adjustment,
        citation_ids=citation_ids,
        intra_bucket_citation_ids=intra_bucket_citation_ids,
        inter_bucket_citation_ids=inter_bucket_citation_ids,
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )
    scenario_totals = {label: result.capital for label, result in sorted(scenario_results.items())}
    selection = select_max_correlation_scenario(
        scenario_totals,
        risk_class=risk_class,
        risk_measure=risk_measure,
        citation_ids=citation_ids,
    )
    buckets = _selected_buckets_for_risk_class(bucket_inputs, specs, intra_by_scenario, selection)
    return RiskClassCapital(
        risk_class=risk_class,
        risk_measure=risk_measure,
        selected_capital=selection.selected_capital,
        buckets=buckets,
        citation_ids=_merge_citation_ids(
            citation_ids,
            intra_bucket_citation_ids,
            inter_bucket_citation_ids,
        ),
        scenario_totals=selection.scenario_totals,
        selected_scenario=selection.selected_scenario,
        scenario_details=tuple(scenario_details),
        scenario_selection=selection.branch_metadata,
    )


def _coerce_scenario_specs(
    bucket_inputs: Sequence[IntraBucketScenarioSpec | IntraBucketAggregationResult | BucketCapital],
) -> tuple[IntraBucketScenarioSpec, ...] | None:
    has_specs = any(isinstance(item, IntraBucketScenarioSpec) for item in bucket_inputs)
    if not has_specs:
        return None
    specs = tuple(item for item in bucket_inputs if isinstance(item, IntraBucketScenarioSpec))
    if len(specs) != len(bucket_inputs):
        raise SbmInputError(
            "bucket_inputs must be homogeneous IntraBucketScenarioSpec records",
            field="bucket_inputs",
        )
    return tuple(sorted(specs, key=lambda spec: spec.bucket_id))


def _evaluate_risk_class_scenarios(
    bucket_inputs: Sequence[IntraBucketScenarioSpec | IntraBucketAggregationResult | BucketCapital],
    *,
    specs: tuple[IntraBucketScenarioSpec, ...] | None,
    inter_bucket_correlations: Mapping[tuple[str, str], float],
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
    scenarios: Sequence[SbmScenarioLabel],
    apply_scenario_adjustment: bool,
    citation_ids: tuple[str, ...],
    intra_bucket_citation_ids: tuple[str, ...],
    inter_bucket_citation_ids: tuple[str, ...],
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str,
    pairwise_evidence_limit: int,
) -> tuple[
    dict[SbmScenarioLabel, InterBucketScenarioResult],
    list[RiskClassScenarioDetail],
    dict[SbmScenarioLabel, tuple[IntraBucketAggregationResult, ...]],
]:
    scenario_details: list[RiskClassScenarioDetail] = []
    scenario_results: dict[SbmScenarioLabel, InterBucketScenarioResult] = {}
    intra_by_scenario: dict[SbmScenarioLabel, tuple[IntraBucketAggregationResult, ...]] = {}
    for scenario in scenarios:
        inter_input = _inter_bucket_input_for_scenario(
            bucket_inputs,
            specs=specs,
            scenario=scenario,
            risk_class=risk_class,
            risk_measure=risk_measure,
            intra_bucket_citation_ids=intra_bucket_citation_ids,
            pairwise_evidence_mode=pairwise_evidence_mode,
            pairwise_evidence_limit=pairwise_evidence_limit,
            intra_by_scenario=intra_by_scenario,
        )
        inter_result = aggregate_inter_bucket(
            inter_input,
            inter_bucket_correlations,
            scenario=scenario,
            apply_scenario_adjustment=apply_scenario_adjustment,
            citation_ids=inter_bucket_citation_ids,
        )
        scenario_results[scenario] = inter_result
        if specs is not None:
            scenario_details.append(
                _risk_class_scenario_detail(scenario, inter_result, citation_ids, intra_by_scenario)
            )
    return scenario_results, scenario_details, intra_by_scenario


def _inter_bucket_input_for_scenario(
    bucket_inputs: Sequence[IntraBucketScenarioSpec | IntraBucketAggregationResult | BucketCapital],
    *,
    specs: tuple[IntraBucketScenarioSpec, ...] | None,
    scenario: SbmScenarioLabel,
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
    intra_bucket_citation_ids: tuple[str, ...],
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str,
    pairwise_evidence_limit: int,
    intra_by_scenario: dict[SbmScenarioLabel, tuple[IntraBucketAggregationResult, ...]],
) -> Sequence[IntraBucketAggregationResult | BucketCapital]:
    if specs is None:
        return cast(Sequence[IntraBucketAggregationResult | BucketCapital], bucket_inputs)
    intra_results = _aggregate_intra_buckets_for_scenario(
        specs,
        scenario=scenario,
        risk_class=risk_class,
        risk_measure=risk_measure,
        intra_bucket_citation_ids=intra_bucket_citation_ids,
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )
    intra_by_scenario[scenario] = intra_results
    return intra_results


def _risk_class_scenario_detail(
    scenario: SbmScenarioLabel,
    inter_result: InterBucketScenarioResult,
    citation_ids: tuple[str, ...],
    intra_by_scenario: Mapping[SbmScenarioLabel, tuple[IntraBucketAggregationResult, ...]],
) -> RiskClassScenarioDetail:
    return RiskClassScenarioDetail(
        scenario=scenario,
        capital=inter_result.capital,
        inter_bucket_correlations=inter_result.inter_bucket_correlations,
        alternative_sb_used=inter_result.alternative_sb_used,
        intra_buckets=tuple(
            _intra_bucket_to_scenario_record(result) for result in intra_by_scenario[scenario]
        ),
        citation_ids=citation_ids,
    )


def _selected_buckets_for_risk_class(
    bucket_inputs: Sequence[IntraBucketScenarioSpec | IntraBucketAggregationResult | BucketCapital],
    specs: tuple[IntraBucketScenarioSpec, ...] | None,
    intra_by_scenario: Mapping[SbmScenarioLabel, tuple[IntraBucketAggregationResult, ...]],
    selection: ScenarioSelectionResult,
) -> tuple[BucketCapital, ...]:
    if specs is None:
        legacy_inputs = cast(Sequence[IntraBucketAggregationResult | BucketCapital], bucket_inputs)
        return tuple(_as_bucket_capital(item) for item in legacy_inputs)
    selected_intra = intra_by_scenario[selection.selected_scenario]
    weighted_by_bucket = {spec.bucket_id: spec.weighted_sensitivities for spec in specs}
    return tuple(
        replace(
            result.bucket_capital,
            scenario=selection.selected_scenario,
            weighted_sensitivities=weighted_by_bucket[result.bucket_capital.bucket_id],
        )
        for result in selected_intra
    )


def _scenario_rank(label: SbmScenarioLabel) -> int:
    order = {
        SbmScenarioLabel.LOW: 0,
        SbmScenarioLabel.MEDIUM: 1,
        SbmScenarioLabel.HIGH: 2,
    }
    return order[label]


__all__ = [
    "ScenarioSelectionResult",
    "aggregate_risk_class_with_scenarios",
    "select_max_correlation_scenario",
]
