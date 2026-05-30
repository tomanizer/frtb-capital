"""
Shared intra-bucket and inter-bucket SBM aggregation primitives.

Regulatory traceability:
    Basel MAR21.4(4)-(5) — within-bucket and across-bucket delta/vega aggregation.
    Basel MAR21.6 — low, medium, and high correlation scenarios.
    Basel MAR21.7(2) — select the largest risk-class capital across scenarios.
    U.S. NPR 2.0 section V.A.7.a steps four through six.
    SBM-REQ-005, SBM-REQ-006.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import cast

import numpy as np
import numpy.typing as npt

from frtb_sbm.data_models import (
    BucketCapital,
    IntraBucketScenarioRecord,
    PairwiseCorrelationRecord,
    RiskClassCapital,
    RiskClassScenarioDetail,
    SbmBranchMetadata,
    SbmBranchType,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmScenarioLabel,
    WeightedSensitivity,
)
from frtb_sbm.validation import SbmInputError

_MAR21_INTRA_BUCKET_CITATION = ("basel_mar21_4_intra_bucket",)
_MAR21_INTER_BUCKET_CITATION = ("basel_mar21_4_inter_bucket",)
_MAR21_SCENARIO_CITATION = (
    "basel_mar21_6_correlation_scenarios",
    "basel_mar21_7_scenario_selection",
)


@dataclass(frozen=True)
class IntraBucketScenarioSpec:
    """Inputs required to recompute intra-bucket capital under each scenario."""

    bucket_id: str
    weighted_sensitivities: tuple[WeightedSensitivity, ...]
    base_correlation_matrix: npt.NDArray[np.float64]
    sb_correlation_floor: float | None = None
    absolute_weight_intra: bool = False
    absolute_weight_citation_ids: tuple[str, ...] = ()


_MAR21_SCENARIO_SELECTION_CITATION = ("basel_mar21_7_scenario_selection",)

_DEFAULT_SCENARIOS: tuple[SbmScenarioLabel, ...] = (
    SbmScenarioLabel.LOW,
    SbmScenarioLabel.MEDIUM,
    SbmScenarioLabel.HIGH,
)


@dataclass(frozen=True)
class PairwiseCorrelationEvidence:
    """Audit record for one pairwise intra-bucket correlation."""

    sensitivity_id_a: str
    sensitivity_id_b: str
    correlation: float
    citation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class IntraBucketAggregationResult:
    """Intra-bucket capital with full audit evidence."""

    bucket_capital: BucketCapital
    pairwise_correlations: tuple[PairwiseCorrelationEvidence, ...]
    variance_before_floor: float
    zero_variance_floor_applied: bool
    sb_correlation_floor_applied: bool


@dataclass(frozen=True)
class InterBucketScenarioResult:
    """Risk-class capital for one correlation scenario."""

    scenario: SbmScenarioLabel
    capital: float
    capital_variance_sum: float
    alternative_sb_used: bool
    bucket_ids: tuple[str, ...]
    bucket_kb_values: tuple[float, ...]
    bucket_sb_values: tuple[float, ...]
    inter_bucket_correlations: tuple[tuple[str, str, float], ...]
    citation_ids: tuple[str, ...]


@dataclass(frozen=True)
class ScenarioSelectionResult:
    """Selected scenario outcome for a risk class."""

    scenario_totals: Mapping[SbmScenarioLabel, float]
    selected_scenario: SbmScenarioLabel
    selected_capital: float
    branch_metadata: SbmBranchMetadata
    citation_ids: tuple[str, ...]


def adjust_correlation_for_scenario(
    base_correlation: float,
    scenario: SbmScenarioLabel,
) -> float:
    """
    Apply MAR21.6 correlation-scenario adjustments to one parameter.

    Medium scenario uses the base value unchanged. High scenario multiplies by
    1.25 and caps at 100%. Low scenario uses max(2 * rho - 100%, 75% * rho).
    """
    _validate_finite_correlation(base_correlation, field="base_correlation")
    if scenario is SbmScenarioLabel.MEDIUM:
        return base_correlation
    if scenario is SbmScenarioLabel.HIGH:
        return min(base_correlation * 1.25, 1.0)
    if scenario is SbmScenarioLabel.LOW:
        return max(2.0 * base_correlation - 1.0, 0.75 * base_correlation)
    raise SbmInputError(
        f"unsupported correlation scenario: {scenario!r}",
        field="scenario",
    )


def adjust_correlation_matrix_for_scenario(
    base_matrix: npt.NDArray[np.float64],
    scenario: SbmScenarioLabel,
) -> npt.NDArray[np.float64]:
    """Return a copy of ``base_matrix`` with off-diagonal entries scenario-adjusted."""

    matrix = np.array(base_matrix, dtype=np.float64, copy=True)
    size = matrix.shape[0]
    for row_index in range(size):
        for col_index in range(row_index + 1, size):
            base_rho = float(matrix[row_index, col_index])
            adjusted = adjust_correlation_for_scenario(base_rho, scenario)
            matrix[row_index, col_index] = adjusted
            matrix[col_index, row_index] = adjusted
    return matrix


def aggregate_intra_bucket(
    bucket_id: str,
    weighted_sensitivities: Sequence[WeightedSensitivity],
    correlation_matrix: npt.NDArray[np.float64],
    *,
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
    sb_correlation_floor: float | None = None,
    citation_ids: tuple[str, ...] = _MAR21_INTRA_BUCKET_CITATION,
) -> IntraBucketAggregationResult:
    """
    Aggregate weighted sensitivities within one bucket (MAR21.4 step 4).

    Computes the signed bucket aggregate ``Sb = sum_k WS_k`` and bucket capital
    ``Kb = sqrt(max(0, sum_k sum_l rho_kl WS_k WS_l))``. When ``sb_correlation_floor``
    is supplied, ``Kb`` is additionally floored at ``abs(sb_correlation_floor * Sb)``.
    """
    ordered = _sort_weighted_sensitivities(weighted_sensitivities)
    _validate_bucket_scope(bucket_id, ordered, risk_class, risk_measure)
    matrix = _validate_correlation_matrix(correlation_matrix, n_factors=len(ordered))

    ws = np.array([item.scaled_amount for item in ordered], dtype=np.float64)
    sb = float(np.sum(ws))
    variance = float(ws @ matrix @ ws)

    zero_floor_applied = variance < 0.0
    variance_floored = max(0.0, variance)

    kb_squared = variance_floored
    sb_floor_applied = False
    if sb_correlation_floor is not None:
        if not math.isfinite(sb_correlation_floor) or sb_correlation_floor < 0.0:
            raise SbmInputError(
                "sb_correlation_floor must be a finite non-negative number",
                field="sb_correlation_floor",
            )
        sb_floor_value = (sb_correlation_floor * sb) ** 2
        if sb_floor_value > kb_squared:
            kb_squared = sb_floor_value
            sb_floor_applied = True

    kb = math.sqrt(kb_squared)
    pairwise = _pairwise_correlation_evidence(ordered, matrix, citation_ids)

    bucket_capital = BucketCapital(
        bucket_id=bucket_id,
        risk_class=risk_class,
        risk_measure=risk_measure,
        kb=kb,
        weighted_sensitivities=tuple(ordered),
        citation_ids=citation_ids,
        sb=sb,
        floor_applied=zero_floor_applied or sb_floor_applied,
    )
    return IntraBucketAggregationResult(
        bucket_capital=bucket_capital,
        pairwise_correlations=pairwise,
        variance_before_floor=variance,
        zero_variance_floor_applied=zero_floor_applied,
        sb_correlation_floor_applied=sb_floor_applied,
    )


def aggregate_inter_bucket(
    bucket_results: Sequence[IntraBucketAggregationResult | BucketCapital],
    inter_bucket_correlations: Mapping[tuple[str, str], float],
    *,
    scenario: SbmScenarioLabel = SbmScenarioLabel.MEDIUM,
    apply_scenario_adjustment: bool = True,
    citation_ids: tuple[str, ...] = _MAR21_INTER_BUCKET_CITATION,
) -> InterBucketScenarioResult:
    """
    Aggregate bucket-level positions across buckets for one scenario (MAR21.4 step 5).

    Uses ``K^2 = sum_b Kb^2 + sum_b sum_c gamma_bc Sb Sc`` with ``gamma_bb = 0``.
    When the summed variance is negative, applies the alternative ``Sb`` specification
    from MAR21.4(5)(b).
    """
    buckets = [_as_bucket_capital(item) for item in bucket_results]
    if not buckets:
        raise SbmInputError("bucket_results must not be empty", field="bucket_results")

    bucket_ids = tuple(sorted({bucket.bucket_id for bucket in buckets}, key=str))
    if len(bucket_ids) != len(buckets):
        raise SbmInputError(
            "duplicate bucket_id values are not permitted in inter-bucket aggregation",
            field="bucket_results",
        )

    kb_values = np.array([bucket.kb for bucket in buckets], dtype=np.float64)
    sb_values = np.array([_bucket_sb(bucket) for bucket in buckets], dtype=np.float64)
    gamma = _build_inter_bucket_gamma_matrix(
        bucket_ids=bucket_ids,
        inter_bucket_correlations=inter_bucket_correlations,
        scenario=scenario,
        apply_scenario_adjustment=apply_scenario_adjustment,
    )

    capital_variance, alternative_sb_used = _inter_bucket_variance(
        kb_values=kb_values,
        sb_values=sb_values,
        gamma=gamma,
    )
    capital = math.sqrt(max(0.0, capital_variance))
    adjusted_correlations = _inter_bucket_correlation_audit(
        bucket_ids=bucket_ids,
        inter_bucket_correlations=inter_bucket_correlations,
        scenario=scenario,
        apply_scenario_adjustment=apply_scenario_adjustment,
    )

    return InterBucketScenarioResult(
        scenario=scenario,
        capital=capital,
        capital_variance_sum=capital_variance,
        alternative_sb_used=alternative_sb_used,
        bucket_ids=bucket_ids,
        bucket_kb_values=tuple(float(value) for value in kb_values),
        bucket_sb_values=tuple(float(value) for value in sb_values),
        inter_bucket_correlations=adjusted_correlations,
        citation_ids=citation_ids,
    )


def select_max_correlation_scenario(
    scenario_totals: Mapping[SbmScenarioLabel, float],
    *,
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure | None = None,
    branch_id: str | None = None,
    citation_ids: tuple[str, ...] = _MAR21_SCENARIO_SELECTION_CITATION,
) -> ScenarioSelectionResult:
    """
    Select the maximum risk-class capital across correlation scenarios.

    GIRR delta capital uses the largest scenario total per MAR21.7(2).
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
    )


def _aggregate_intra_buckets_for_scenario(
    specs: Sequence[IntraBucketScenarioSpec],
    *,
    scenario: SbmScenarioLabel,
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
    intra_bucket_citation_ids: tuple[str, ...] = _MAR21_INTRA_BUCKET_CITATION,
) -> tuple[IntraBucketAggregationResult, ...]:
    results: list[IntraBucketAggregationResult] = []
    for spec in specs:
        if spec.absolute_weight_intra:
            results.append(_aggregate_absolute_weight_intra_bucket(spec, risk_class, risk_measure))
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
                citation_ids=intra_bucket_citation_ids,
            )
        )
    return tuple(results)


def _aggregate_absolute_weight_intra_bucket(
    spec: IntraBucketScenarioSpec,
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
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
        variance_before_floor=float(np.dot(ws, ws)),
        zero_variance_floor_applied=False,
        sb_correlation_floor_applied=False,
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
) -> RiskClassCapital:
    """
    Evaluate low/medium/high scenarios with full intra- and inter-bucket recomputation.

    When ``IntraBucketScenarioSpec`` inputs are supplied, intra-bucket capital is
    recomputed under scenario-adjusted pairwise correlations per MAR21.6 before
    inter-bucket aggregation. Pre-aggregated ``BucketCapital`` inputs skip intra-bucket
    scenario recomputation and vary only inter-bucket correlations.
    """
    if not bucket_inputs:
        raise SbmInputError("bucket_inputs must not be empty", field="bucket_inputs")
    if not scenarios:
        raise SbmInputError("scenarios must not be empty", field="scenarios")

    specs: tuple[IntraBucketScenarioSpec, ...] | None = None
    has_specs = any(isinstance(item, IntraBucketScenarioSpec) for item in bucket_inputs)
    if has_specs:
        specs = tuple(item for item in bucket_inputs if isinstance(item, IntraBucketScenarioSpec))
        if len(specs) != len(bucket_inputs):
            raise SbmInputError(
                "bucket_inputs must be homogeneous IntraBucketScenarioSpec records",
                field="bucket_inputs",
            )
        specs = tuple(sorted(specs, key=lambda spec: spec.bucket_id))

    scenario_details: list[RiskClassScenarioDetail] = []
    scenario_results: dict[SbmScenarioLabel, InterBucketScenarioResult] = {}
    intra_by_scenario: dict[SbmScenarioLabel, tuple[IntraBucketAggregationResult, ...]] = {}

    for scenario in scenarios:
        if specs is not None:
            intra_results = _aggregate_intra_buckets_for_scenario(
                specs,
                scenario=scenario,
                risk_class=risk_class,
                risk_measure=risk_measure,
                intra_bucket_citation_ids=intra_bucket_citation_ids,
            )
            intra_by_scenario[scenario] = intra_results
            inter_input: Sequence[IntraBucketAggregationResult | BucketCapital] = intra_results
        else:
            inter_input = cast(
                Sequence[IntraBucketAggregationResult | BucketCapital],
                bucket_inputs,
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
                RiskClassScenarioDetail(
                    scenario=scenario,
                    capital=inter_result.capital,
                    inter_bucket_correlations=inter_result.inter_bucket_correlations,
                    alternative_sb_used=inter_result.alternative_sb_used,
                    intra_buckets=tuple(
                        _intra_bucket_to_scenario_record(result) for result in intra_results
                    ),
                    citation_ids=citation_ids,
                )
            )

    scenario_totals = {label: result.capital for label, result in sorted(scenario_results.items())}
    selection = select_max_correlation_scenario(
        scenario_totals,
        risk_class=risk_class,
        risk_measure=risk_measure,
        citation_ids=_MAR21_SCENARIO_SELECTION_CITATION,
    )

    if specs is not None:
        selected_intra = intra_by_scenario[selection.selected_scenario]
        weighted_by_bucket = {spec.bucket_id: spec.weighted_sensitivities for spec in specs}
        buckets = tuple(
            replace(
                result.bucket_capital,
                scenario=selection.selected_scenario,
                weighted_sensitivities=weighted_by_bucket[result.bucket_capital.bucket_id],
            )
            for result in selected_intra
        )
    else:
        legacy_inputs = cast(
            Sequence[IntraBucketAggregationResult | BucketCapital],
            bucket_inputs,
        )
        buckets = tuple(_as_bucket_capital(item) for item in legacy_inputs)

    merged_citation_ids = _merge_citation_ids(
        citation_ids,
        intra_bucket_citation_ids,
        inter_bucket_citation_ids,
    )
    return RiskClassCapital(
        risk_class=risk_class,
        risk_measure=risk_measure,
        selected_capital=selection.selected_capital,
        buckets=buckets,
        citation_ids=merged_citation_ids,
        scenario_totals=selection.scenario_totals,
        selected_scenario=selection.selected_scenario,
        scenario_details=tuple(scenario_details),
        scenario_selection=selection.branch_metadata,
    )


def group_weighted_sensitivities_by_bucket(
    weighted_sensitivities: Sequence[WeightedSensitivity],
) -> dict[tuple[SbmRiskClass, SbmRiskMeasure, str], tuple[WeightedSensitivity, ...]]:
    """Group weighted sensitivities by risk class, measure, and bucket id."""
    grouped: dict[tuple[SbmRiskClass, SbmRiskMeasure, str], list[WeightedSensitivity]] = {}
    for item in weighted_sensitivities:
        key = (item.risk_class, item.risk_measure, item.bucket)
        grouped.setdefault(key, []).append(item)
    return {
        key: tuple(_sort_weighted_sensitivities(values)) for key, values in sorted(grouped.items())
    }


def _inter_bucket_variance(
    *,
    kb_values: npt.NDArray[np.float64],
    sb_values: npt.NDArray[np.float64],
    gamma: npt.NDArray[np.float64],
) -> tuple[float, bool]:
    variance = float(np.dot(kb_values, kb_values) + sb_values @ gamma @ sb_values)
    if variance >= 0.0:
        return variance, False

    adjusted_sb = np.array(
        [max(min(sb, kb), -kb) for sb, kb in zip(sb_values, kb_values, strict=True)],
        dtype=np.float64,
    )
    adjusted_variance = float(np.dot(kb_values, kb_values) + adjusted_sb @ gamma @ adjusted_sb)
    return adjusted_variance, True


def _build_inter_bucket_gamma_matrix(
    *,
    bucket_ids: Sequence[str],
    inter_bucket_correlations: Mapping[tuple[str, str], float],
    scenario: SbmScenarioLabel,
    apply_scenario_adjustment: bool,
) -> npt.NDArray[np.float64]:
    size = len(bucket_ids)
    gamma = np.zeros((size, size), dtype=np.float64)
    index = {bucket_id: position for position, bucket_id in enumerate(bucket_ids)}

    for (bucket_a, bucket_b), base_gamma in sorted(inter_bucket_correlations.items()):
        if bucket_a not in index or bucket_b not in index:
            continue
        applied = (
            adjust_correlation_for_scenario(base_gamma, scenario)
            if apply_scenario_adjustment
            else base_gamma
        )
        row = index[bucket_a]
        col = index[bucket_b]
        gamma[row, col] = applied
        if row != col:
            gamma[col, row] = applied
    return gamma


def _inter_bucket_correlation_audit(
    *,
    bucket_ids: Sequence[str],
    inter_bucket_correlations: Mapping[tuple[str, str], float],
    scenario: SbmScenarioLabel,
    apply_scenario_adjustment: bool,
) -> tuple[tuple[str, str, float], ...]:
    audit: list[tuple[str, str, float]] = []
    for (bucket_a, bucket_b), base_gamma in sorted(inter_bucket_correlations.items()):
        if bucket_a not in bucket_ids or bucket_b not in bucket_ids:
            continue
        applied = (
            adjust_correlation_for_scenario(base_gamma, scenario)
            if apply_scenario_adjustment
            else base_gamma
        )
        audit.append((bucket_a, bucket_b, applied))
    return tuple(audit)


def _pairwise_correlation_evidence(
    ordered: Sequence[WeightedSensitivity],
    matrix: npt.NDArray[np.float64],
    citation_ids: tuple[str, ...],
) -> tuple[PairwiseCorrelationEvidence, ...]:
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
    return tuple(records)


def _sort_weighted_sensitivities(
    weighted_sensitivities: Sequence[WeightedSensitivity],
) -> tuple[WeightedSensitivity, ...]:
    return tuple(
        sorted(
            weighted_sensitivities,
            key=lambda item: (item.sensitivity_id, item.bucket, item.qualifier or ""),
        )
    )


def _validate_bucket_scope(
    bucket_id: str,
    weighted_sensitivities: Sequence[WeightedSensitivity],
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
) -> None:
    if not bucket_id.strip():
        raise SbmInputError("bucket_id must be non-empty", field="bucket_id")
    if not weighted_sensitivities:
        raise SbmInputError(
            "weighted_sensitivities must not be empty",
            field="weighted_sensitivities",
        )
    for item in weighted_sensitivities:
        if item.bucket != bucket_id:
            raise SbmInputError(
                "weighted sensitivity bucket does not match bucket_id",
                field="bucket",
                sensitivity_id=item.sensitivity_id,
            )
        if item.risk_class is not risk_class:
            raise SbmInputError(
                "weighted sensitivity risk_class does not match aggregation scope",
                field="risk_class",
                sensitivity_id=item.sensitivity_id,
            )
        if item.risk_measure is not risk_measure:
            raise SbmInputError(
                "weighted sensitivity risk_measure does not match aggregation scope",
                field="risk_measure",
                sensitivity_id=item.sensitivity_id,
            )
        if not math.isfinite(item.scaled_amount):
            raise SbmInputError(
                "scaled_amount must be finite",
                field="scaled_amount",
                sensitivity_id=item.sensitivity_id,
            )


def _validate_correlation_matrix(
    correlation_matrix: npt.NDArray[np.float64],
    *,
    n_factors: int,
) -> npt.NDArray[np.float64]:
    matrix = np.asarray(correlation_matrix, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape != (n_factors, n_factors):
        raise SbmInputError(
            "correlation_matrix shape must match weighted_sensitivities count",
            field="correlation_matrix",
        )
    if not np.all(np.isfinite(matrix)):
        raise SbmInputError(
            "correlation_matrix must contain finite values",
            field="correlation_matrix",
        )
    if not np.allclose(matrix, matrix.T):
        raise SbmInputError("correlation_matrix must be symmetric", field="correlation_matrix")
    if not np.allclose(np.diag(matrix), 1.0):
        raise SbmInputError("correlation_matrix diagonal must be 1.0", field="correlation_matrix")
    return matrix


def _validate_finite_correlation(value: float, *, field: str) -> None:
    if not math.isfinite(value):
        raise SbmInputError(f"{field} must be finite", field=field)


def _as_bucket_capital(
    item: IntraBucketAggregationResult | BucketCapital,
) -> BucketCapital:
    if isinstance(item, IntraBucketAggregationResult):
        return item.bucket_capital
    return item


def _bucket_sb(bucket: BucketCapital) -> float:
    if bucket.sb is not None:
        return bucket.sb
    return float(sum(item.scaled_amount for item in bucket.weighted_sensitivities))


def _scenario_rank(label: SbmScenarioLabel) -> int:
    order = {
        SbmScenarioLabel.LOW: 0,
        SbmScenarioLabel.MEDIUM: 1,
        SbmScenarioLabel.HIGH: 2,
    }
    return order[label]


def _merge_citation_ids(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for citation_id in group:
            if citation_id not in seen:
                merged.append(citation_id)
                seen.add(citation_id)
    return tuple(merged)


def compute_portfolio_scenario_totals(
    risk_class_results: Sequence[RiskClassCapital],
) -> dict[SbmScenarioLabel, float]:
    """Sum risk-class scenario totals across supported measures per MAR21.7."""

    if not risk_class_results:
        raise SbmInputError(
            "risk_class_results must not be empty",
            field="risk_class_results",
        )
    portfolio_totals: dict[SbmScenarioLabel, float] = {}
    for risk_class_result in risk_class_results:
        if risk_class_result.scenario_totals is None:
            raise SbmInputError(
                "risk-class capital must include scenario totals for portfolio selection",
                field="scenario_totals",
            )
        for scenario, total in risk_class_result.scenario_totals.items():
            portfolio_totals[scenario] = portfolio_totals.get(scenario, 0.0) + float(total)
    if not portfolio_totals:
        raise SbmInputError(
            "portfolio scenario totals must not be empty",
            field="portfolio_scenario_totals",
        )
    return portfolio_totals


def select_portfolio_correlation_scenario(
    risk_class_results: Sequence[RiskClassCapital],
    *,
    citation_ids: tuple[str, ...] = _MAR21_SCENARIO_SELECTION_CITATION,
) -> tuple[
    tuple[RiskClassCapital, ...],
    float,
    dict[SbmScenarioLabel, float],
    SbmScenarioLabel,
    SbmBranchMetadata,
]:
    """
    Apply MAR21.7 portfolio-level scenario selection across risk classes.

    Sums delta, vega, and curvature capital by scenario across present risk
    classes, selects the largest portfolio total, and aligns each risk-class
    result to that scenario for reconciliation.
    """
    if not risk_class_results:
        raise SbmInputError(
            "risk_class_results must not be empty",
            field="risk_class_results",
        )

    portfolio_totals = compute_portfolio_scenario_totals(risk_class_results)
    selection = select_max_correlation_scenario(
        portfolio_totals,
        risk_class=SbmRiskClass.GIRR,
        branch_id="portfolio_scenario_selection",
        citation_ids=citation_ids,
    )
    aligned = tuple(
        align_risk_class_to_scenario(
            risk_class_result,
            selection.selected_scenario,
        )
        for risk_class_result in risk_class_results
    )
    return (
        aligned,
        selection.selected_capital,
        portfolio_totals,
        selection.selected_scenario,
        selection.branch_metadata,
    )


def align_risk_class_to_scenario(
    risk_class_result: RiskClassCapital,
    scenario: SbmScenarioLabel,
) -> RiskClassCapital:
    """Return a risk-class result whose selected buckets match ``scenario``."""

    if risk_class_result.scenario_totals is None:
        raise SbmInputError(
            "risk-class capital must include scenario totals",
            field="scenario_totals",
        )
    if scenario not in risk_class_result.scenario_totals:
        raise SbmInputError(
            "risk-class scenario totals do not include requested scenario",
            field="selected_scenario",
        )
    if risk_class_result.selected_scenario is scenario:
        return risk_class_result

    selected_capital = float(risk_class_result.scenario_totals[scenario])
    detail = next(
        (item for item in risk_class_result.scenario_details if item.scenario is scenario),
        None,
    )
    if detail is None:
        raise SbmInputError(
            "risk-class scenario details must include requested scenario",
            field="scenario_details",
        )
    risk_measure = _risk_measure_for_alignment(risk_class_result)
    weighted_by_bucket = {
        bucket.bucket_id: bucket.weighted_sensitivities for bucket in risk_class_result.buckets
    }
    buckets = tuple(
        BucketCapital(
            bucket_id=intra.bucket_id,
            risk_class=risk_class_result.risk_class,
            risk_measure=risk_measure,
            kb=intra.kb,
            weighted_sensitivities=weighted_by_bucket.get(intra.bucket_id, ()),
            citation_ids=intra.citation_ids,
            sb=intra.sb,
            floor_applied=intra.floor_applied,
            scenario=scenario,
        )
        for intra in detail.intra_buckets
    )

    scenario_selection = risk_class_result.scenario_selection
    if scenario_selection is not None:
        scenario_selection = replace(
            scenario_selection,
            reason=(
                f"aligned to portfolio {scenario.value} scenario with capital {selected_capital}"
            ),
        )

    return replace(
        risk_class_result,
        selected_capital=selected_capital,
        selected_scenario=scenario,
        buckets=buckets,
        scenario_selection=scenario_selection,
    )


def _risk_measure_for_alignment(risk_class_result: RiskClassCapital) -> SbmRiskMeasure:
    if risk_class_result.risk_measure is not None:
        return risk_class_result.risk_measure
    if risk_class_result.buckets:
        return risk_class_result.buckets[0].risk_measure
    raise SbmInputError(
        "risk-class capital must include a risk measure for scenario alignment",
        field="risk_measure",
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
    "select_max_correlation_scenario",
    "select_portfolio_correlation_scenario",
]
