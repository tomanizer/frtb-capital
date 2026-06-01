"""
Curvature contract parsing, branch selection, and cited capital aggregation.

Regulatory traceability:
    Basel MAR21.5 — curvature risk capital, up/down branch selection, floors.
    U.S. NPR 2.0 section V.A.7.a footnote 328.
    SBM-CURV-001, SBM-FUNC-012.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.aggregation import (
    adjust_correlation_for_scenario,
    adjust_correlation_matrix_for_scenario,
    select_max_correlation_scenario,
)
from frtb_sbm.batch import SbmSensitivityBatch, sorted_girr_curvature_batch_indices
from frtb_sbm.data_models import (
    BucketCapital,
    CurvatureBranchRecord,
    CurvatureBucketBranchRecord,
    CurvatureInput,
    IntraBucketScenarioRecord,
    PairwiseCorrelationRecord,
    PairwiseCorrelationSummary,
    RiskClassCapital,
    RiskClassScenarioDetail,
    SbmPairwiseEvidenceMode,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmScenarioLabel,
    SbmSensitivity,
    SbmUnsupportedFeature,
    WeightedSensitivity,
)
from frtb_sbm.reference_data import (
    curvature_citation_ids,
    girr_delta_intra_bucket_correlation,
    girr_inter_bucket_correlation,
)
from frtb_sbm.regimes import ensure_profile_supports_risk_class_measure
from frtb_sbm.validation import (
    SbmInputError,
    ensure_sbm_profile_known,
    normalise_sensitivity_amount,
    sensitivity_sort_key,
    validate_sbm_sensitivities,
)

CURVATURE_CAPITAL_REQUIREMENT_ID = "SBM-CURV-001"

_MAR21_CURVATURE_INTRA_CITATION = (
    "basel_mar21_4_intra_bucket",
    "basel_mar21_41",
    "basel_mar21_curvature",
)
_MAR21_CURVATURE_INTER_CITATION = (
    "basel_mar21_4_inter_bucket",
    "basel_mar21_42",
    "basel_mar21_curvature",
)
_MAR21_CURVATURE_FLOOR_CITATION = ("basel_mar21_curvature",)
_MAR21_CURVATURE_SCENARIO_CITATION = (
    "basel_mar21_6_correlation_scenarios",
    "basel_mar21_7_scenario_selection",
)
_GIRR_CURVATURE_PARALLEL_TENOR = "3m"
_CURVATURE_UP_BRANCH = "up"
_CURVATURE_DOWN_BRANCH = "down"
_DEFAULT_SCENARIOS: tuple[SbmScenarioLabel, ...] = (
    SbmScenarioLabel.LOW,
    SbmScenarioLabel.MEDIUM,
    SbmScenarioLabel.HIGH,
)


@dataclass(frozen=True)
class _CurvatureFactor:
    bucket_id: str
    factor_id: str
    risk_factor: str
    up_cvr: float
    down_cvr: float
    sensitivity_ids: tuple[str, ...]
    source_row_ids: tuple[str, ...]
    citation_ids: tuple[str, ...]


@dataclass(frozen=True)
class _CurvatureBranchEvaluation:
    branch: str
    bucket_capital: float
    branch_sum: float
    variance_before_floor: float
    floor_applied: bool
    psi_zero_count: int


@dataclass(frozen=True)
class _CurvatureBucketScenario:
    bucket_id: str
    scenario: SbmScenarioLabel
    selected: _CurvatureBranchEvaluation
    rejected: _CurvatureBranchEvaluation
    up: _CurvatureBranchEvaluation
    down: _CurvatureBranchEvaluation
    factors: tuple[_CurvatureFactor, ...]
    correlation_matrix: npt.NDArray[np.float64]
    citation_ids: tuple[str, ...]


def parse_curvature_input(
    sensitivity: SbmSensitivity,
    *,
    profile_id: str,
) -> CurvatureInput:
    """Build a canonical curvature input from one validated CURVATURE sensitivity."""

    ensure_sbm_profile_known(profile_id)
    if sensitivity.risk_measure is not SbmRiskMeasure.CURVATURE:
        raise SbmInputError(
            "parse_curvature_input requires risk_measure=CURVATURE",
            field="risk_measure",
            sensitivity_id=sensitivity.sensitivity_id,
        )
    up_shock_amount = sensitivity.up_shock_amount
    down_shock_amount = sensitivity.down_shock_amount
    if up_shock_amount is None or down_shock_amount is None:
        raise SbmInputError(
            "curvature inputs require up_shock_amount and down_shock_amount",
            field="up_shock_amount",
            sensitivity_id=sensitivity.sensitivity_id,
        )
    return CurvatureInput(
        sensitivity_id=sensitivity.sensitivity_id,
        risk_class=sensitivity.risk_class,
        bucket=sensitivity.bucket,
        risk_factor=sensitivity.risk_factor,
        amount_currency=sensitivity.amount_currency,
        up_shock_amount=normalise_sensitivity_amount(
            up_shock_amount,
            sensitivity_id=sensitivity.sensitivity_id,
        ),
        down_shock_amount=normalise_sensitivity_amount(
            down_shock_amount,
            sensitivity_id=sensitivity.sensitivity_id,
        ),
        citation_ids=curvature_citation_ids(profile_id),
    )


def validate_curvature_sensitivities(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
) -> tuple[CurvatureInput, ...]:
    """Validate curvature-only sensitivities and return canonical curvature inputs."""

    ensure_sbm_profile_known(profile_id)
    if not sensitivities:
        raise SbmInputError("sensitivities must not be empty", field="sensitivities")
    for sensitivity in sensitivities:
        if sensitivity.risk_measure is not SbmRiskMeasure.CURVATURE:
            raise SbmInputError(
                "validate_curvature_sensitivities accepts only CURVATURE rows",
                field="risk_measure",
                sensitivity_id=sensitivity.sensitivity_id,
            )
    validated = validate_sbm_sensitivities(sensitivities)
    ordered = sorted(validated, key=sensitivity_sort_key)
    return tuple(
        parse_curvature_input(sensitivity, profile_id=profile_id) for sensitivity in ordered
    )


def curvature_worst_branch(up_shock_amount: float, down_shock_amount: float) -> str:
    """Return the profile-prescribed worst-side branch label for up/down shocks."""

    up = normalise_sensitivity_amount(up_shock_amount)
    down = normalise_sensitivity_amount(down_shock_amount)
    if down < up:
        return "down"
    return "up"


def selected_curvature_shock_amount(up_shock_amount: float, down_shock_amount: float) -> float:
    """Return the more negative up/down shock amount for curvature weighting."""

    up = normalise_sensitivity_amount(up_shock_amount)
    down = normalise_sensitivity_amount(down_shock_amount)
    branch = curvature_worst_branch(up, down)
    return down if branch == "down" else up


def validate_girr_curvature_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
) -> SbmSensitivityBatch:
    """
    Validate a GIRR curvature batch without enabling curvature capital.

    This helper checks the package-owned batch contract and the separate
    up/down shock arrays needed by MAR21.5. It intentionally does not call the
    public capital support gate because GIRR curvature capital remains
    fail-closed until the cited aggregation path is implemented.
    """

    _validate_and_get_girr_curvature_shocks(batch, profile_id=profile_id)
    return batch


def select_girr_curvature_branches_from_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
) -> tuple[CurvatureBranchRecord, ...]:
    """
    Return deterministic GIRR curvature branch records from batch columns.

    The returned records match the row-wise branch-selection rule while reading
    directly from the package-owned batch arrays.
    """

    up_shocks, down_shocks = _validate_and_get_girr_curvature_shocks(
        batch,
        profile_id=profile_id,
    )
    citations = curvature_citation_ids(profile_id)
    records: list[CurvatureBranchRecord] = []
    for row_index in sorted_girr_curvature_batch_indices(batch):
        up_shock = float(up_shocks[row_index])
        down_shock = float(down_shocks[row_index])
        branch = curvature_worst_branch(up_shock, down_shock)
        records.append(
            CurvatureBranchRecord(
                sensitivity_id=str(batch.sensitivity_ids[row_index]),
                selected_branch=branch,
                up_shock_amount=up_shock,
                down_shock_amount=down_shock,
                citation_ids=citations,
            )
        )
    return tuple(records)


def weight_girr_curvature_sensitivities(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
    reporting_currency: str,
) -> tuple[tuple[WeightedSensitivity, ...], tuple[CurvatureBranchRecord, ...]]:
    """Reject the obsolete row-wise weighted curvature shortcut."""

    del sensitivities, reporting_currency
    ensure_profile_supports_risk_class_measure(
        profile_id,
        SbmRiskClass.GIRR,
        SbmRiskMeasure.CURVATURE,
    )
    raise UnsupportedRegulatoryFeatureError(
        "frtb-sbm GIRR curvature cannot be represented as one weighted sensitivity "
        "per input row; use calculate_girr_curvature_risk_class_capital for the "
        "MAR21.5 CVR+/CVR- branch engine"
    )


def calculate_girr_curvature_risk_class_capital(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
    reporting_currency: str,
) -> RiskClassCapital:
    """Calculate cited GIRR curvature risk-class capital."""

    del reporting_currency
    validated = _validate_girr_curvature_capital_sensitivities(
        sensitivities,
        profile_id=profile_id,
    )
    factors = _build_girr_curvature_factors(validated, profile_id=profile_id)
    branches = _curvature_input_branch_records(validated, profile_id=profile_id)
    return _aggregate_girr_curvature_factors(
        factors,
        profile_id=profile_id,
        curvature_branches=branches,
    )


def aggregate_girr_curvature_measure_capital(
    weighted: tuple[WeightedSensitivity, ...],
    *,
    profile_id: str,
    tenor_by_id: Mapping[str, str],
    risk_factor_by_id: Mapping[str, str],
    curvature_branches: tuple[CurvatureBranchRecord, ...],
) -> RiskClassCapital:
    """Reject weighted-input curvature aggregation because it loses CVR branch state."""

    del weighted, profile_id, tenor_by_id, risk_factor_by_id, curvature_branches
    raise UnsupportedRegulatoryFeatureError(
        "frtb-sbm GIRR curvature aggregation requires separate CVR+/CVR- factor "
        "amounts and bucket-level MAR21.5 branch selection"
    )


def calculate_curvature_risk_class_capital(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
    reporting_currency: str,
) -> RiskClassCapital:
    """Calculate cited curvature capital for supported risk classes."""

    if not sensitivities:
        raise SbmInputError("sensitivities must not be empty", field="sensitivities")
    risk_classes = {item.risk_class for item in sensitivities}
    if len(risk_classes) != 1:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm curvature capital requires a homogeneous risk class"
        )
    risk_class = next(iter(risk_classes))
    if risk_class is SbmRiskClass.GIRR:
        return calculate_girr_curvature_risk_class_capital(
            sensitivities,
            profile_id=profile_id,
            reporting_currency=reporting_currency,
        )
    raise UnsupportedRegulatoryFeatureError(
        "frtb-sbm curvature capital is unsupported for "
        f"risk_class={risk_class.value}; GIRR curvature is supported on BASEL_MAR21"
    )


def curvature_capital_unsupported_feature(profile_id: str) -> SbmUnsupportedFeature:
    """Return structured metadata for unsupported curvature paths on a profile."""

    ensure_sbm_profile_known(profile_id)
    return SbmUnsupportedFeature(
        feature_key="sbm_curvature_capital",
        dimension="risk_measure",
        reason=(
            "Curvature capital is unsupported for the requested risk class or profile "
            f"({CURVATURE_CAPITAL_REQUIREMENT_ID})."
        ),
        requirement_id=CURVATURE_CAPITAL_REQUIREMENT_ID,
    )


def _validate_girr_curvature_capital_sensitivities(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
) -> tuple[SbmSensitivity, ...]:
    ensure_sbm_profile_known(profile_id)
    if not sensitivities:
        raise SbmInputError("sensitivities must not be empty", field="sensitivities")
    validated = tuple(sorted(validate_sbm_sensitivities(sensitivities), key=sensitivity_sort_key))
    for sensitivity in validated:
        if sensitivity.risk_class is not SbmRiskClass.GIRR:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm GIRR curvature capital does not support "
                f"risk_class={sensitivity.risk_class.value}"
            )
        if sensitivity.risk_measure is not SbmRiskMeasure.CURVATURE:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm GIRR curvature capital does not support "
                f"risk_measure={sensitivity.risk_measure.value}"
            )
        if sensitivity.up_shock_amount is None or sensitivity.down_shock_amount is None:
            raise SbmInputError(
                "curvature inputs require up_shock_amount and down_shock_amount",
                field="up_shock_amount",
                sensitivity_id=sensitivity.sensitivity_id,
            )
    return validated


def _curvature_input_branch_records(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
) -> tuple[CurvatureBranchRecord, ...]:
    citations = curvature_citation_ids(profile_id)
    records: list[CurvatureBranchRecord] = []
    for sensitivity in sensitivities:
        up_shock = _required_curvature_shock(sensitivity, field="up_shock_amount")
        down_shock = _required_curvature_shock(sensitivity, field="down_shock_amount")
        records.append(
            CurvatureBranchRecord(
                sensitivity_id=sensitivity.sensitivity_id,
                selected_branch=curvature_worst_branch(up_shock, down_shock),
                up_shock_amount=up_shock,
                down_shock_amount=down_shock,
                citation_ids=citations,
            )
        )
    return tuple(records)


def _build_girr_curvature_factors(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
) -> tuple[_CurvatureFactor, ...]:
    citations = curvature_citation_ids(profile_id)
    grouped: dict[tuple[str, str], list[SbmSensitivity]] = {}
    for sensitivity in sensitivities:
        grouped.setdefault((sensitivity.bucket, sensitivity.risk_factor), []).append(sensitivity)

    factors: list[_CurvatureFactor] = []
    for (bucket_id, risk_factor), items in sorted(grouped.items()):
        ordered = tuple(sorted(items, key=sensitivity_sort_key))
        up_cvr = sum(
            (_required_curvature_shock(item, field="up_shock_amount") for item in ordered),
            0.0,
        )
        down_cvr = sum(
            (_required_curvature_shock(item, field="down_shock_amount") for item in ordered),
            0.0,
        )
        factors.append(
            _CurvatureFactor(
                bucket_id=bucket_id,
                factor_id=f"{bucket_id}|{risk_factor}",
                risk_factor=risk_factor,
                up_cvr=up_cvr,
                down_cvr=down_cvr,
                sensitivity_ids=tuple(item.sensitivity_id for item in ordered),
                source_row_ids=tuple(item.source_row_id for item in ordered),
                citation_ids=citations,
            )
        )
    return tuple(factors)


def _required_curvature_shock(sensitivity: SbmSensitivity, *, field: str) -> float:
    value = (
        sensitivity.up_shock_amount if field == "up_shock_amount" else sensitivity.down_shock_amount
    )
    if value is None:
        raise SbmInputError(
            "curvature inputs require up_shock_amount and down_shock_amount",
            field=field,
            sensitivity_id=sensitivity.sensitivity_id,
        )
    return normalise_sensitivity_amount(value, sensitivity_id=sensitivity.sensitivity_id)


def _aggregate_girr_curvature_factors(
    factors: tuple[_CurvatureFactor, ...],
    *,
    profile_id: str,
    curvature_branches: tuple[CurvatureBranchRecord, ...],
) -> RiskClassCapital:
    grouped: dict[str, list[_CurvatureFactor]] = {}
    for factor in factors:
        grouped.setdefault(factor.bucket_id, []).append(factor)
    if not grouped:
        raise SbmInputError("curvature factors must not be empty", field="sensitivities")

    bucket_ids = tuple(sorted(grouped))
    inter_bucket_correlations = _build_girr_curvature_inter_bucket_correlation_map(
        bucket_ids,
        profile_id=profile_id,
    )
    scenario_details: list[RiskClassScenarioDetail] = []
    scenario_buckets: dict[SbmScenarioLabel, tuple[_CurvatureBucketScenario, ...]] = {}
    scenario_totals: dict[SbmScenarioLabel, float] = {}
    bucket_branch_records: list[CurvatureBucketBranchRecord] = []

    for scenario in _DEFAULT_SCENARIOS:
        bucket_scenarios = tuple(
            _evaluate_curvature_bucket_scenario(
                bucket_id,
                tuple(sorted(grouped[bucket_id], key=lambda item: item.factor_id)),
                profile_id=profile_id,
                scenario=scenario,
            )
            for bucket_id in bucket_ids
        )
        scenario_buckets[scenario] = bucket_scenarios
        bucket_branch_records.extend(
            _curvature_bucket_branch_record(bucket_scenario) for bucket_scenario in bucket_scenarios
        )
        capital, inter_correlations = _aggregate_curvature_inter_bucket(
            bucket_scenarios,
            inter_bucket_correlations,
            scenario=scenario,
        )
        scenario_totals[scenario] = capital
        scenario_details.append(
            RiskClassScenarioDetail(
                scenario=scenario,
                capital=capital,
                inter_bucket_correlations=inter_correlations,
                alternative_sb_used=False,
                intra_buckets=tuple(
                    _curvature_bucket_to_intra_record(bucket_scenario)
                    for bucket_scenario in bucket_scenarios
                ),
                citation_ids=_merge_citation_ids(
                    _MAR21_CURVATURE_SCENARIO_CITATION,
                    _MAR21_CURVATURE_INTRA_CITATION,
                    _MAR21_CURVATURE_INTER_CITATION,
                ),
            )
        )

    selection = select_max_correlation_scenario(
        scenario_totals,
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.CURVATURE,
        branch_id="girr_curvature_scenario_selection",
        citation_ids=_MAR21_CURVATURE_SCENARIO_CITATION,
    )
    selected_bucket_scenarios = scenario_buckets[selection.selected_scenario]
    selected_buckets = tuple(
        _curvature_bucket_to_bucket_capital(bucket_scenario)
        for bucket_scenario in selected_bucket_scenarios
    )
    citations = _merge_citation_ids(
        _MAR21_CURVATURE_SCENARIO_CITATION,
        _MAR21_CURVATURE_INTRA_CITATION,
        _MAR21_CURVATURE_INTER_CITATION,
        _MAR21_CURVATURE_FLOOR_CITATION,
        selection.citation_ids,
    )
    return RiskClassCapital(
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.CURVATURE,
        selected_capital=selection.selected_capital,
        buckets=selected_buckets,
        citation_ids=citations,
        scenario_totals=selection.scenario_totals,
        selected_scenario=selection.selected_scenario,
        scenario_details=tuple(scenario_details),
        scenario_selection=selection.branch_metadata,
        curvature_branches=curvature_branches,
        curvature_bucket_branches=tuple(bucket_branch_records),
    )


def _evaluate_curvature_bucket_scenario(
    bucket_id: str,
    factors: tuple[_CurvatureFactor, ...],
    *,
    profile_id: str,
    scenario: SbmScenarioLabel,
) -> _CurvatureBucketScenario:
    base_matrix = _build_girr_curvature_intra_bucket_correlation_matrix(
        factors,
        profile_id=profile_id,
    )
    adjusted_matrix = adjust_correlation_matrix_for_scenario(
        base_matrix,
        scenario,
        profile_id=profile_id,
    )
    up = _evaluate_curvature_branch(
        tuple(factor.up_cvr for factor in factors),
        adjusted_matrix,
        branch=_CURVATURE_UP_BRANCH,
    )
    down = _evaluate_curvature_branch(
        tuple(factor.down_cvr for factor in factors),
        adjusted_matrix,
        branch=_CURVATURE_DOWN_BRANCH,
    )
    selected, rejected = _select_curvature_bucket_branch(up, down)
    return _CurvatureBucketScenario(
        bucket_id=bucket_id,
        scenario=scenario,
        selected=selected,
        rejected=rejected,
        up=up,
        down=down,
        factors=factors,
        correlation_matrix=adjusted_matrix,
        citation_ids=_MAR21_CURVATURE_INTRA_CITATION,
    )


def _evaluate_curvature_branch(
    values: Sequence[float],
    correlation_matrix: npt.NDArray[np.float64],
    *,
    branch: str,
) -> _CurvatureBranchEvaluation:
    cvr = np.asarray(values, dtype=np.float64)
    positive_diagonal = float(np.dot(np.maximum(cvr, 0.0), np.maximum(cvr, 0.0)))
    if len(cvr) <= 1:
        pair_contribution = 0.0
        psi_zero_count = 0
    else:
        row_indices, col_indices = np.triu_indices(len(cvr), k=1)
        left = cvr[row_indices]
        right = cvr[col_indices]
        psi = ~((left < 0.0) & (right < 0.0))
        psi_zero_count = int(np.count_nonzero(~psi))
        pair_contribution = float(
            2.0 * np.sum(correlation_matrix[row_indices, col_indices] * left * right * psi)
        )
    variance = positive_diagonal + pair_contribution
    return _CurvatureBranchEvaluation(
        branch=branch,
        bucket_capital=math.sqrt(max(0.0, variance)),
        branch_sum=float(np.sum(cvr)),
        variance_before_floor=variance,
        floor_applied=variance < 0.0,
        psi_zero_count=psi_zero_count,
    )


def _select_curvature_bucket_branch(
    up: _CurvatureBranchEvaluation,
    down: _CurvatureBranchEvaluation,
) -> tuple[_CurvatureBranchEvaluation, _CurvatureBranchEvaluation]:
    if not math.isclose(up.bucket_capital, down.bucket_capital, rel_tol=1e-12, abs_tol=1e-12):
        return (up, down) if up.bucket_capital > down.bucket_capital else (down, up)
    return (up, down) if up.branch_sum > down.branch_sum else (down, up)


def _aggregate_curvature_inter_bucket(
    bucket_scenarios: tuple[_CurvatureBucketScenario, ...],
    inter_bucket_correlations: Mapping[tuple[str, str], float],
    *,
    scenario: SbmScenarioLabel,
) -> tuple[float, tuple[tuple[str, str, float], ...]]:
    bucket_ids = tuple(bucket.bucket_id for bucket in bucket_scenarios)
    kb_values = np.array([bucket.selected.bucket_capital for bucket in bucket_scenarios])
    sb_values = np.array([bucket.selected.branch_sum for bucket in bucket_scenarios])
    gamma = _build_curvature_inter_bucket_gamma_matrix(
        bucket_ids,
        inter_bucket_correlations,
        scenario=scenario,
    )
    psi = _curvature_psi_matrix(sb_values)
    variance = float(np.dot(kb_values, kb_values) + sb_values @ (gamma * psi) @ sb_values)
    capital = math.sqrt(max(0.0, variance))
    return capital, _curvature_inter_bucket_correlation_audit(
        bucket_ids,
        inter_bucket_correlations,
        scenario=scenario,
    )


def _curvature_psi_matrix(values: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
    size = len(values)
    psi = np.ones((size, size), dtype=np.float64)
    if size:
        np.fill_diagonal(psi, 0.0)
    if size <= 1:
        return psi
    row_indices, col_indices = np.triu_indices(size, k=1)
    zero_mask = (values[row_indices] < 0.0) & (values[col_indices] < 0.0)
    psi[row_indices[zero_mask], col_indices[zero_mask]] = 0.0
    psi[col_indices[zero_mask], row_indices[zero_mask]] = 0.0
    return psi


def _build_curvature_inter_bucket_gamma_matrix(
    bucket_ids: Sequence[str],
    inter_bucket_correlations: Mapping[tuple[str, str], float],
    *,
    scenario: SbmScenarioLabel,
) -> npt.NDArray[np.float64]:
    size = len(bucket_ids)
    gamma = np.zeros((size, size), dtype=np.float64)
    index = {bucket_id: position for position, bucket_id in enumerate(bucket_ids)}
    for (bucket_a, bucket_b), base_gamma in sorted(inter_bucket_correlations.items()):
        if bucket_a not in index or bucket_b not in index:
            continue
        applied = adjust_correlation_for_scenario(base_gamma, scenario)
        row = index[bucket_a]
        col = index[bucket_b]
        gamma[row, col] = applied
        gamma[col, row] = applied
    return gamma


def _curvature_inter_bucket_correlation_audit(
    bucket_ids: Sequence[str],
    inter_bucket_correlations: Mapping[tuple[str, str], float],
    *,
    scenario: SbmScenarioLabel,
) -> tuple[tuple[str, str, float], ...]:
    return tuple(
        (bucket_a, bucket_b, adjust_correlation_for_scenario(base_gamma, scenario))
        for (bucket_a, bucket_b), base_gamma in sorted(inter_bucket_correlations.items())
        if bucket_a in bucket_ids and bucket_b in bucket_ids
    )


def _curvature_bucket_to_intra_record(
    bucket_scenario: _CurvatureBucketScenario,
) -> IntraBucketScenarioRecord:
    pairwise_records, summary = _curvature_pairwise_audit(bucket_scenario)
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
    return BucketCapital(
        bucket_id=bucket_scenario.bucket_id,
        risk_class=SbmRiskClass.GIRR,
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
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.CURVATURE,
        bucket=factor.bucket_id,
        raw_amount=cvr,
        risk_weight=1.0,
        scaled_amount=cvr,
        citation_ids=factor.citation_ids,
        qualifier=f"{factor.risk_factor}:{selected_branch}:{scenario.value}",
        factor_key=(factor.bucket_id, factor.risk_factor),
        contributing_sensitivity_ids=factor.sensitivity_ids,
        contributing_source_row_ids=factor.source_row_ids,
    )


def _curvature_pairwise_audit(
    bucket_scenario: _CurvatureBucketScenario,
) -> tuple[tuple[PairwiseCorrelationRecord, ...], PairwiseCorrelationSummary]:
    factors = bucket_scenario.factors
    records: list[PairwiseCorrelationRecord] = []
    for row_index, factor_a in enumerate(factors):
        for col_index in range(row_index, len(factors)):
            factor_b = factors[col_index]
            records.append(
                PairwiseCorrelationRecord(
                    sensitivity_a=factor_a.factor_id,
                    sensitivity_b=factor_b.factor_id,
                    correlation=float(bucket_scenario.correlation_matrix[row_index, col_index]),
                )
            )
    total_count = len(factors) * (len(factors) + 1) // 2
    summary = PairwiseCorrelationSummary(
        evidence_mode=SbmPairwiseEvidenceMode.FULL,
        total_count=total_count,
        materialized_count=len(records),
        omitted_count=0,
        factor_ids=tuple(factor.factor_id for factor in factors),
    )
    return tuple(records), summary


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


def _build_girr_curvature_intra_bucket_correlation_matrix(
    ordered: Sequence[_CurvatureFactor],
    *,
    profile_id: str,
) -> npt.NDArray[np.float64]:
    size = len(ordered)
    matrix = np.eye(size, dtype=np.float64)
    for row_index, factor_a in enumerate(ordered):
        for col_index in range(row_index + 1, size):
            factor_b = ordered[col_index]
            same_curve = factor_a.risk_factor == factor_b.risk_factor
            correlation, _ = girr_delta_intra_bucket_correlation(
                profile_id,
                tenor1=_GIRR_CURVATURE_PARALLEL_TENOR,
                tenor2=_GIRR_CURVATURE_PARALLEL_TENOR,
                same_curve=same_curve,
            )
            curvature_correlation = correlation**2
            matrix[row_index, col_index] = curvature_correlation
            matrix[col_index, row_index] = curvature_correlation
    return matrix


def _build_girr_curvature_inter_bucket_correlation_map(
    bucket_ids: Sequence[str],
    *,
    profile_id: str,
) -> dict[tuple[str, str], float]:
    correlations: dict[tuple[str, str], float] = {}
    ordered_ids = tuple(sorted(bucket_ids))
    for left_index, bucket_a in enumerate(ordered_ids):
        for bucket_b in ordered_ids[left_index + 1 :]:
            gamma, _ = girr_inter_bucket_correlation(
                profile_id,
                bucket1=bucket_a,
                bucket2=bucket_b,
            )
            correlations[(bucket_a, bucket_b)] = gamma**2
    return correlations


def _merge_citation_ids(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for citation_id in group:
            if citation_id not in seen:
                merged.append(citation_id)
                seen.add(citation_id)
    return tuple(merged)


def _require_girr_curvature_batch(batch: SbmSensitivityBatch) -> None:
    if not isinstance(batch, SbmSensitivityBatch):
        raise SbmInputError("batch must be SbmSensitivityBatch", field="batch")
    if batch.risk_class is not SbmRiskClass.GIRR:
        raise SbmInputError("GIRR curvature batch only accepts GIRR sensitivities")
    if batch.risk_measure is not SbmRiskMeasure.CURVATURE:
        raise SbmInputError("GIRR curvature batch only accepts CURVATURE sensitivities")
    if batch.up_shock_amounts is None or batch.down_shock_amounts is None:
        raise SbmInputError(
            "curvature inputs require up_shock_amount and down_shock_amount",
            field="up_shock_amount",
        )


def _validate_and_get_girr_curvature_shocks(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    ensure_sbm_profile_known(profile_id)
    _require_girr_curvature_batch(batch)
    return (
        _curvature_shock_float_array(batch, batch.up_shock_amounts, field="up_shock_amount"),
        _curvature_shock_float_array(batch, batch.down_shock_amounts, field="down_shock_amount"),
    )


def _curvature_shock_float_array(
    batch: SbmSensitivityBatch,
    values: npt.NDArray[np.object_] | None,
    *,
    field: str,
) -> npt.NDArray[np.float64]:
    if values is None:
        raise SbmInputError(
            "curvature inputs require up_shock_amount and down_shock_amount",
            field=field,
        )
    shocks = np.empty(batch.row_count, dtype=np.float64)
    for row_index, value in enumerate(values):
        sensitivity_id = str(batch.sensitivity_ids[row_index])
        if value is None:
            raise SbmInputError(
                "curvature inputs require up_shock_amount and down_shock_amount",
                field=field,
                sensitivity_id=sensitivity_id,
            )
        try:
            shocks[row_index] = float(value)
        except (TypeError, ValueError) as exc:
            raise SbmInputError(
                "value must be numeric",
                field=field,
                sensitivity_id=sensitivity_id,
            ) from exc
        if not np.isfinite(shocks[row_index]):
            raise SbmInputError(
                "value must be finite",
                field=field,
                sensitivity_id=sensitivity_id,
            )
    shocks.setflags(write=False)
    return shocks


__all__ = [
    "CURVATURE_CAPITAL_REQUIREMENT_ID",
    "aggregate_girr_curvature_measure_capital",
    "calculate_curvature_risk_class_capital",
    "calculate_girr_curvature_risk_class_capital",
    "curvature_capital_unsupported_feature",
    "curvature_worst_branch",
    "parse_curvature_input",
    "select_girr_curvature_branches_from_batch",
    "selected_curvature_shock_amount",
    "validate_curvature_sensitivities",
    "validate_girr_curvature_batch",
    "weight_girr_curvature_sensitivities",
]
