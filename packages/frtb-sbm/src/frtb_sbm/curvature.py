"""
Curvature contract parsing, branch selection, and cited capital aggregation.

Regulatory traceability:
    Basel MAR21.5 — curvature risk capital, up/down branch selection, floors.
    U.S. NPR 2.0 section V.A.7.a footnote 328.
    SBM-CURV-001, SBM-FUNC-012.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import numpy.typing as npt
from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.aggregation import (
    IntraBucketScenarioSpec,
    aggregate_risk_class_with_scenarios,
    group_weighted_sensitivities_by_bucket,
)
from frtb_sbm.batch import SbmSensitivityBatch, sorted_girr_curvature_batch_indices
from frtb_sbm.data_models import (
    CurvatureBranchRecord,
    CurvatureInput,
    RiskClassCapital,
    SbmBranchMetadata,
    SbmBranchType,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmUnsupportedFeature,
    WeightedSensitivity,
)
from frtb_sbm.reference_data import (
    curvature_citation_ids,
    girr_delta_intra_bucket_correlation,
    girr_delta_risk_weight,
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
    """Return cited weighted GIRR curvature sensitivities and branch audit records."""

    ensure_profile_supports_risk_class_measure(
        profile_id,
        SbmRiskClass.GIRR,
        SbmRiskMeasure.CURVATURE,
    )
    weighted: list[WeightedSensitivity] = []
    branches: list[CurvatureBranchRecord] = []
    curvature_citations = curvature_citation_ids(profile_id)
    for sensitivity in sorted(sensitivities, key=sensitivity_sort_key):
        if sensitivity.risk_class is not SbmRiskClass.GIRR:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm GIRR curvature weighting does not support "
                f"risk_class={sensitivity.risk_class.value}"
            )
        if sensitivity.risk_measure is not SbmRiskMeasure.CURVATURE:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm GIRR curvature weighting does not support "
                f"risk_measure={sensitivity.risk_measure.value}"
            )
        if not sensitivity.tenor:
            raise SbmInputError(
                "GIRR curvature inputs require tenor",
                field="tenor",
                sensitivity_id=sensitivity.sensitivity_id,
            )
        up_shock = sensitivity.up_shock_amount
        down_shock = sensitivity.down_shock_amount
        if up_shock is None or down_shock is None:
            raise SbmInputError(
                "curvature inputs require up_shock_amount and down_shock_amount",
                field="up_shock_amount",
                sensitivity_id=sensitivity.sensitivity_id,
            )
        branch = curvature_worst_branch(up_shock, down_shock)
        raw_amount = selected_curvature_shock_amount(up_shock, down_shock)
        risk_weight, rw_citations = girr_delta_risk_weight(
            profile_id,
            tenor=sensitivity.tenor,
            currency=sensitivity.risk_factor,
            reporting_currency=reporting_currency,
        )
        citation_ids = tuple(dict.fromkeys((*rw_citations, *curvature_citations)))
        scaled_amount = raw_amount * risk_weight
        weighted.append(
            WeightedSensitivity(
                sensitivity_id=sensitivity.sensitivity_id,
                risk_class=SbmRiskClass.GIRR,
                risk_measure=SbmRiskMeasure.CURVATURE,
                bucket=sensitivity.bucket,
                raw_amount=raw_amount,
                risk_weight=risk_weight,
                scaled_amount=scaled_amount,
                citation_ids=citation_ids,
                qualifier=sensitivity.tenor,
            )
        )
        branches.append(
            CurvatureBranchRecord(
                sensitivity_id=sensitivity.sensitivity_id,
                selected_branch=branch,
                up_shock_amount=normalise_sensitivity_amount(
                    up_shock,
                    sensitivity_id=sensitivity.sensitivity_id,
                ),
                down_shock_amount=normalise_sensitivity_amount(
                    down_shock,
                    sensitivity_id=sensitivity.sensitivity_id,
                ),
                citation_ids=curvature_citations,
            )
        )
    return tuple(weighted), tuple(branches)


def calculate_girr_curvature_risk_class_capital(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
    reporting_currency: str,
) -> RiskClassCapital:
    """Calculate cited GIRR curvature risk-class capital."""

    weighted, branches = weight_girr_curvature_sensitivities(
        sensitivities,
        profile_id=profile_id,
        reporting_currency=reporting_currency,
    )
    tenor_by_id = {item.sensitivity_id: item.tenor or "" for item in sensitivities}
    risk_factor_by_id = {item.sensitivity_id: item.risk_factor for item in sensitivities}
    return aggregate_girr_curvature_measure_capital(
        weighted,
        profile_id=profile_id,
        tenor_by_id=tenor_by_id,
        risk_factor_by_id=risk_factor_by_id,
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
    """Aggregate weighted GIRR curvature sensitivities with cited floors."""

    grouped = group_weighted_sensitivities_by_bucket(weighted)
    intra_specs: list[IntraBucketScenarioSpec] = []
    for (_risk_class, _risk_measure, bucket_id), bucket_weighted in sorted(grouped.items()):
        matrix = _build_girr_curvature_intra_bucket_correlation_matrix(
            bucket_weighted,
            profile_id=profile_id,
            tenor_by_id=tenor_by_id,
            risk_factor_by_id=risk_factor_by_id,
        )
        intra_specs.append(
            IntraBucketScenarioSpec(
                bucket_id=bucket_id,
                weighted_sensitivities=tuple(bucket_weighted),
                base_correlation_matrix=matrix,
                sb_correlation_floor=None,
                curvature_absolute_floor=True,
            )
        )

    bucket_ids = tuple(sorted(spec.bucket_id for spec in intra_specs))
    inter_bucket_correlations = _build_girr_curvature_inter_bucket_correlation_map(
        bucket_ids,
        profile_id=profile_id,
    )
    result = aggregate_risk_class_with_scenarios(
        tuple(intra_specs),
        inter_bucket_correlations,
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.CURVATURE,
        intra_bucket_citation_ids=_MAR21_CURVATURE_INTRA_CITATION,
        inter_bucket_citation_ids=_MAR21_CURVATURE_INTER_CITATION,
    )
    return _with_curvature_branch_metadata(result, curvature_branches)


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


def _with_curvature_branch_metadata(
    result: RiskClassCapital,
    curvature_branches: tuple[CurvatureBranchRecord, ...],
) -> RiskClassCapital:
    branch_metadata = SbmBranchMetadata(
        branch_id="girr_curvature_branch_selection",
        branch_type=SbmBranchType.CURVATURE_BRANCH,
        source_id="mar21_5",
        selected=True,
        reason="selected worst-side up/down shock per sensitivity before weighting",
        citation_ids=_MAR21_CURVATURE_FLOOR_CITATION,
    )
    existing_selection = result.scenario_selection
    citation_ids = tuple(
        dict.fromkeys(
            (
                *result.citation_ids,
                *branch_metadata.citation_ids,
                *(existing_selection.citation_ids if existing_selection else ()),
            )
        )
    )
    return RiskClassCapital(
        risk_class=result.risk_class,
        selected_capital=result.selected_capital,
        buckets=result.buckets,
        citation_ids=citation_ids,
        risk_measure=result.risk_measure,
        scenario_totals=result.scenario_totals,
        selected_scenario=result.selected_scenario,
        scenario_details=result.scenario_details,
        scenario_selection=existing_selection or branch_metadata,
        curvature_branches=curvature_branches,
    )


def _build_girr_curvature_intra_bucket_correlation_matrix(
    ordered: Sequence[WeightedSensitivity],
    *,
    profile_id: str,
    tenor_by_id: Mapping[str, str],
    risk_factor_by_id: Mapping[str, str],
) -> npt.NDArray[np.float64]:
    size = len(ordered)
    matrix = np.eye(size, dtype=np.float64)
    for row_index, sensitivity_a in enumerate(ordered):
        for col_index in range(row_index + 1, size):
            sensitivity_b = ordered[col_index]
            same_curve = (
                risk_factor_by_id[sensitivity_a.sensitivity_id]
                == risk_factor_by_id[sensitivity_b.sensitivity_id]
            )
            correlation, _ = girr_delta_intra_bucket_correlation(
                profile_id,
                tenor1=tenor_by_id[sensitivity_a.sensitivity_id],
                tenor2=tenor_by_id[sensitivity_b.sensitivity_id],
                same_curve=same_curve,
            )
            matrix[row_index, col_index] = correlation
            matrix[col_index, row_index] = correlation
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
            correlations[(bucket_a, bucket_b)] = gamma
    return correlations


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
