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
from frtb_sbm.batch import (
    SbmSensitivityBatch,
    sorted_curvature_batch_indices,
    sorted_girr_curvature_batch_indices,
)
from frtb_sbm.commodity_reference_data import (
    _require_commodity_bucket_number,
    commodity_bucket_definition,
    commodity_delta_intra_bucket_correlation,
    commodity_inter_bucket_correlation,
)
from frtb_sbm.csr_nonsec_reference_data import (
    CSR_BOND_RISK_FACTOR,
    CSR_CDS_RISK_FACTOR,
    CSR_HY_INDEX_BUCKET,
    CSR_IG_INDEX_BUCKET,
    CSR_INDEX_NAME_CORRELATION,
    CSR_NAME_CORRELATION,
    CSR_OTHER_SECTOR_BUCKET,
    csr_nonsec_bucket_definition,
    csr_nonsec_inter_bucket_correlation,
)
from frtb_sbm.csr_sec_ctp_reference_data import (
    csr_sec_ctp_bucket_definition,
    csr_sec_ctp_inter_bucket_correlation,
)
from frtb_sbm.csr_sec_nonctp_reference_data import (
    CSR_SEC_BOND_RISK_FACTOR,
    CSR_SEC_CDS_RISK_FACTOR,
    CSR_SEC_OTHER_SECTOR_BUCKET,
    CSR_SEC_TRANCHE_DIFFERENT_CORRELATION,
    csr_sec_nonctp_bucket_definition,
    csr_sec_nonctp_inter_bucket_correlation,
)
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
from frtb_sbm.equity_reference_data import (
    EQUITY_OTHER_SECTOR_BUCKET,
    EQUITY_SPOT_RISK_FACTOR,
    _require_equity_bucket_number,
    equity_bucket_definition,
    equity_delta_intra_bucket_correlation,
    equity_inter_bucket_correlation,
)
from frtb_sbm.reference_data import (
    curvature_citation_ids,
    curvature_risk_weight,
    fx_delta_intra_bucket_correlation,
    fx_inter_bucket_correlation,
    girr_bucket_definition,
    girr_delta_intra_bucket_correlation,
    girr_inter_bucket_correlation,
    normalise_fx_delta_currency_code,
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
FX_CURVATURE_SCALAR_1_5_FLAG = "fx_curvature_scalar_1_5"

_MAR21_CURVATURE_INTRA_CITATION = (
    "basel_mar21_curvature",
    "basel_mar21_100",
)
_MAR21_CURVATURE_INTER_CITATION = (
    "basel_mar21_curvature",
    "basel_mar21_101",
)
_MAR21_CURVATURE_FLOOR_CITATION = ("basel_mar21_curvature",)
_MAR21_CURVATURE_SCENARIO_CITATION = (
    "basel_mar21_6_correlation_scenarios",
    "basel_mar21_7_scenario_selection",
)
_GIRR_CURVATURE_PARALLEL_TENOR = "3m"
_COMMODITY_CURVATURE_PARALLEL_TENOR = "parallel"
_CURVATURE_UP_BRANCH = "up"
_CURVATURE_DOWN_BRANCH = "down"
_DEFAULT_SCENARIOS: tuple[SbmScenarioLabel, ...] = (
    SbmScenarioLabel.LOW,
    SbmScenarioLabel.MEDIUM,
    SbmScenarioLabel.HIGH,
)
_SUPPORTED_CURVATURE_RISK_CLASSES: frozenset[SbmRiskClass] = frozenset(SbmRiskClass)


@dataclass(frozen=True)
class _CurvatureFactor:
    risk_class: SbmRiskClass
    bucket_id: str
    factor_id: str
    risk_factor: str
    qualifier: str | None
    tenor: str | None
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
    """Validate a GIRR curvature batch and its separate MAR21.5 shock arrays."""

    _validate_and_get_girr_curvature_shocks(batch, profile_id=profile_id)
    return batch


def validate_curvature_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
    reporting_currency: str,
    expected_risk_class: SbmRiskClass | None = None,
) -> SbmSensitivityBatch:
    """Validate a curvature batch without materialising row dataclasses."""

    _validate_curvature_batch_for_capital(
        batch,
        profile_id=profile_id,
        reporting_currency=reporting_currency,
        expected_risk_class=expected_risk_class,
    )
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


def select_curvature_branches_from_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
) -> tuple[CurvatureBranchRecord, ...]:
    """Return deterministic curvature branch records from batch columns."""

    up_shocks, down_shocks = _validate_and_get_curvature_shocks(
        batch,
        profile_id=profile_id,
    )
    return _curvature_input_branch_records_from_batch(
        batch,
        up_shocks=up_shocks,
        down_shocks=down_shocks,
        profile_id=profile_id,
    )


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

    return _calculate_curvature_risk_class_capital(
        sensitivities,
        profile_id=profile_id,
        reporting_currency=reporting_currency,
        expected_risk_class=SbmRiskClass.GIRR,
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

    return _calculate_curvature_risk_class_capital(
        sensitivities,
        profile_id=profile_id,
        reporting_currency=reporting_currency,
        expected_risk_class=None,
    )


def calculate_girr_curvature_risk_class_capital_from_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
    reporting_currency: str,
) -> RiskClassCapital:
    """Calculate cited GIRR curvature capital directly from a sensitivity batch."""

    return calculate_curvature_risk_class_capital_from_batch(
        batch,
        profile_id=profile_id,
        reporting_currency=reporting_currency,
        expected_risk_class=SbmRiskClass.GIRR,
    )


def calculate_curvature_risk_class_capital_from_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
    reporting_currency: str,
    expected_risk_class: SbmRiskClass | None = None,
) -> RiskClassCapital:
    """Calculate cited curvature capital directly from package-owned batch arrays."""

    risk_class, up_shocks, down_shocks = _validate_curvature_batch_for_capital(
        batch,
        profile_id=profile_id,
        reporting_currency=reporting_currency,
        expected_risk_class=expected_risk_class,
    )
    factors = _build_curvature_factors_from_batch(
        batch,
        up_shocks=up_shocks,
        down_shocks=down_shocks,
        profile_id=profile_id,
    )
    branches = _curvature_input_branch_records_from_batch(
        batch,
        up_shocks=up_shocks,
        down_shocks=down_shocks,
        profile_id=profile_id,
    )
    return _aggregate_curvature_factors(
        factors,
        profile_id=profile_id,
        risk_class=risk_class,
        curvature_branches=branches,
    )


def _calculate_curvature_risk_class_capital(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
    reporting_currency: str,
    expected_risk_class: SbmRiskClass | None,
) -> RiskClassCapital:
    if not sensitivities:
        raise SbmInputError("sensitivities must not be empty", field="sensitivities")
    risk_classes = {item.risk_class for item in sensitivities}
    if len(risk_classes) != 1:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm curvature capital requires a homogeneous risk class"
        )
    risk_class = next(iter(risk_classes))
    if expected_risk_class is not None and risk_class is not expected_risk_class:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm curvature capital expected "
            f"risk_class={expected_risk_class.value}; received risk_class={risk_class.value}"
        )
    if risk_class not in _SUPPORTED_CURVATURE_RISK_CLASSES:
        raise UnsupportedRegulatoryFeatureError(
            f"frtb-sbm curvature capital is unsupported for risk_class={risk_class.value}"
        )
    validated = _validate_curvature_capital_sensitivities(
        sensitivities,
        profile_id=profile_id,
        reporting_currency=reporting_currency,
    )
    factors = _build_curvature_factors(
        validated,
        profile_id=profile_id,
        reporting_currency=reporting_currency,
    )
    branches = _curvature_input_branch_records(validated, profile_id=profile_id)
    return _aggregate_curvature_factors(
        factors,
        profile_id=profile_id,
        risk_class=risk_class,
        curvature_branches=branches,
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


def _validate_curvature_capital_sensitivities(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
    reporting_currency: str,
) -> tuple[SbmSensitivity, ...]:
    ensure_sbm_profile_known(profile_id)
    if not sensitivities:
        raise SbmInputError("sensitivities must not be empty", field="sensitivities")
    validated = tuple(sorted(validate_sbm_sensitivities(sensitivities), key=sensitivity_sort_key))
    risk_classes = {item.risk_class for item in validated}
    if len(risk_classes) != 1:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm curvature capital requires a homogeneous risk class"
        )
    risk_class = next(iter(risk_classes))
    ensure_profile_supports_risk_class_measure(
        profile_id,
        risk_class,
        SbmRiskMeasure.CURVATURE,
    )
    for sensitivity in validated:
        if sensitivity.risk_measure is not SbmRiskMeasure.CURVATURE:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm curvature capital does not support "
                f"risk_measure={sensitivity.risk_measure.value}"
            )
        if sensitivity.up_shock_amount is None or sensitivity.down_shock_amount is None:
            raise SbmInputError(
                "curvature inputs require up_shock_amount and down_shock_amount",
                field="up_shock_amount",
                sensitivity_id=sensitivity.sensitivity_id,
            )
        _validate_curvature_mapping(
            sensitivity,
            profile_id=profile_id,
            reporting_currency=reporting_currency,
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


def _build_curvature_factors(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
    reporting_currency: str,
) -> tuple[_CurvatureFactor, ...]:
    del reporting_currency
    grouped: dict[tuple[str, ...], list[SbmSensitivity]] = {}
    for sensitivity in sensitivities:
        grouped.setdefault(_curvature_factor_key(sensitivity), []).append(sensitivity)

    factors: list[_CurvatureFactor] = []
    for key, items in sorted(grouped.items()):
        ordered = tuple(sorted(items, key=sensitivity_sort_key))
        first = ordered[0]
        risk_class = first.risk_class
        bucket_id = key[0]
        risk_factor = _curvature_factor_risk_factor(risk_class, key, first)
        qualifier = _curvature_factor_qualifier(risk_class, key, first)
        citations = _curvature_factor_citation_ids(
            profile_id,
            risk_class=risk_class,
            bucket_id=bucket_id,
            risk_factor=risk_factor,
        )
        up_cvr = sum(_scaled_curvature_shock(item, field="up_shock_amount") for item in ordered)
        down_cvr = sum(_scaled_curvature_shock(item, field="down_shock_amount") for item in ordered)
        factors.append(
            _CurvatureFactor(
                risk_class=risk_class,
                bucket_id=bucket_id,
                factor_id="|".join(key),
                risk_factor=risk_factor,
                qualifier=qualifier,
                tenor=None,
                up_cvr=up_cvr,
                down_cvr=down_cvr,
                sensitivity_ids=tuple(item.sensitivity_id for item in ordered),
                source_row_ids=tuple(item.source_row_id for item in ordered),
                citation_ids=citations,
            )
        )
    return tuple(factors)


def _build_curvature_factors_from_batch(
    batch: SbmSensitivityBatch,
    *,
    up_shocks: npt.NDArray[np.float64],
    down_shocks: npt.NDArray[np.float64],
    profile_id: str,
) -> tuple[_CurvatureFactor, ...]:
    grouped: dict[tuple[str, ...], list[int]] = {}
    risk_class = batch.risk_class
    for row_index in sorted_curvature_batch_indices(batch):
        key = _curvature_factor_key_from_batch(batch, int(row_index), risk_class=risk_class)
        grouped.setdefault(key, []).append(int(row_index))

    factors: list[_CurvatureFactor] = []
    for key, row_indices in sorted(grouped.items()):
        first_index = row_indices[0]
        bucket_id = key[0]
        risk_factor = _curvature_factor_risk_factor_from_key(
            risk_class,
            key,
            _text_at(batch.risk_factors, first_index),
        )
        qualifier = _curvature_factor_qualifier_from_key(
            risk_class,
            key,
            _optional_text_at(batch.qualifiers, first_index),
        )
        citations = _curvature_factor_citation_ids(
            profile_id,
            risk_class=risk_class,
            bucket_id=bucket_id,
            risk_factor=risk_factor,
        )
        up_cvr = sum(
            _scaled_curvature_batch_shock(batch, row_index, up_shocks[row_index])
            for row_index in row_indices
        )
        down_cvr = sum(
            _scaled_curvature_batch_shock(batch, row_index, down_shocks[row_index])
            for row_index in row_indices
        )
        factors.append(
            _CurvatureFactor(
                risk_class=risk_class,
                bucket_id=bucket_id,
                factor_id="|".join(key),
                risk_factor=risk_factor,
                qualifier=qualifier,
                tenor=None,
                up_cvr=up_cvr,
                down_cvr=down_cvr,
                sensitivity_ids=tuple(
                    _text_at(batch.sensitivity_ids, index) for index in row_indices
                ),
                source_row_ids=tuple(
                    _text_at(batch.source_row_ids, index) for index in row_indices
                ),
                citation_ids=citations,
            )
        )
    return tuple(factors)


def _validate_curvature_mapping(
    sensitivity: SbmSensitivity,
    *,
    profile_id: str,
    reporting_currency: str,
) -> None:
    risk_class = sensitivity.risk_class
    if risk_class is SbmRiskClass.GIRR:
        girr_bucket_definition(profile_id, sensitivity.bucket)
        if sensitivity.risk_factor.strip().upper() in {"INFL", "XCCY"}:
            raise UnsupportedRegulatoryFeatureError(
                "GIRR curvature has no capital requirement for inflation or "
                "cross-currency basis risk factors (MAR21.8(5)(b))"
            )
        return
    if risk_class is SbmRiskClass.FX:
        bucket = normalise_fx_delta_currency_code(sensitivity.bucket)
        risk_factor = normalise_fx_delta_currency_code(sensitivity.risk_factor)
        reporting = normalise_fx_delta_currency_code(reporting_currency)
        if bucket != risk_factor:
            raise SbmInputError(
                "FX curvature bucket must match risk_factor currency",
                field="bucket",
                sensitivity_id=sensitivity.sensitivity_id,
            )
        curvature_risk_weight(
            profile_id,
            risk_class=risk_class,
            currency=risk_factor,
            reporting_currency=reporting,
        )
        _validate_fx_curvature_scalar_flag(sensitivity, reporting_currency=reporting)
        return
    if risk_class is SbmRiskClass.EQUITY:
        equity_bucket_definition(profile_id, sensitivity.bucket)
        if sensitivity.risk_factor.strip().upper() != EQUITY_SPOT_RISK_FACTOR:
            raise UnsupportedRegulatoryFeatureError(
                "equity curvature has no capital requirement for equity repo rates (MAR21.12(3))"
            )
        return
    if risk_class is SbmRiskClass.COMMODITY:
        commodity_bucket_definition(profile_id, sensitivity.bucket)
        return
    if risk_class is SbmRiskClass.CSR_NONSEC:
        csr_nonsec_bucket_definition(profile_id, sensitivity.bucket)
        _normalise_csr_basis(sensitivity.risk_factor)
        return
    if risk_class is SbmRiskClass.CSR_SEC_CTP:
        csr_sec_ctp_bucket_definition(profile_id, sensitivity.bucket)
        _normalise_csr_basis(sensitivity.risk_factor)
        return
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        csr_sec_nonctp_bucket_definition(profile_id, sensitivity.bucket)
        _normalise_csr_sec_basis(sensitivity.risk_factor)
        return
    raise UnsupportedRegulatoryFeatureError(
        f"frtb-sbm curvature capital is unsupported for risk_class={risk_class.value}"
    )


def _curvature_factor_key(sensitivity: SbmSensitivity) -> tuple[str, ...]:
    risk_class = sensitivity.risk_class
    bucket = sensitivity.bucket
    risk_factor = sensitivity.risk_factor.strip()
    qualifier = sensitivity.qualifier.strip() if sensitivity.qualifier else ""
    if risk_class is SbmRiskClass.GIRR:
        return (bucket, risk_factor)
    if risk_class is SbmRiskClass.FX:
        currency = normalise_fx_delta_currency_code(risk_factor)
        return (currency, currency)
    if risk_class is SbmRiskClass.EQUITY:
        return (bucket, EQUITY_SPOT_RISK_FACTOR, qualifier)
    if risk_class is SbmRiskClass.COMMODITY:
        return (bucket, risk_factor, qualifier)
    if risk_class in {
        SbmRiskClass.CSR_NONSEC,
        SbmRiskClass.CSR_SEC_CTP,
        SbmRiskClass.CSR_SEC_NONCTP,
    }:
        return (bucket, qualifier)
    return (bucket, risk_factor, qualifier)


def _curvature_factor_key_from_batch(
    batch: SbmSensitivityBatch,
    row_index: int,
    *,
    risk_class: SbmRiskClass,
) -> tuple[str, ...]:
    bucket = _text_at(batch.buckets, row_index)
    risk_factor = _text_at(batch.risk_factors, row_index).strip()
    qualifier = (_optional_text_at(batch.qualifiers, row_index) or "").strip()
    if risk_class is SbmRiskClass.GIRR:
        return (bucket, risk_factor)
    if risk_class is SbmRiskClass.FX:
        currency = normalise_fx_delta_currency_code(risk_factor)
        return (currency, currency)
    if risk_class is SbmRiskClass.EQUITY:
        return (bucket, EQUITY_SPOT_RISK_FACTOR, qualifier)
    if risk_class is SbmRiskClass.COMMODITY:
        return (bucket, risk_factor, qualifier)
    if risk_class in {
        SbmRiskClass.CSR_NONSEC,
        SbmRiskClass.CSR_SEC_CTP,
        SbmRiskClass.CSR_SEC_NONCTP,
    }:
        return (bucket, qualifier)
    return (bucket, risk_factor, qualifier)


def _curvature_factor_risk_factor(
    risk_class: SbmRiskClass,
    key: tuple[str, ...],
    sensitivity: SbmSensitivity,
) -> str:
    if risk_class is SbmRiskClass.GIRR:
        return key[1]
    if risk_class is SbmRiskClass.FX:
        return key[1]
    if risk_class is SbmRiskClass.EQUITY:
        return EQUITY_SPOT_RISK_FACTOR
    if risk_class is SbmRiskClass.COMMODITY:
        return key[1]
    if risk_class in {
        SbmRiskClass.CSR_NONSEC,
        SbmRiskClass.CSR_SEC_CTP,
        SbmRiskClass.CSR_SEC_NONCTP,
    }:
        del sensitivity
        return "CREDIT_SPREAD_CURVE"
    return sensitivity.risk_factor


def _curvature_factor_risk_factor_from_key(
    risk_class: SbmRiskClass,
    key: tuple[str, ...],
    fallback_risk_factor: str,
) -> str:
    if risk_class is SbmRiskClass.GIRR:
        return key[1]
    if risk_class is SbmRiskClass.FX:
        return key[1]
    if risk_class is SbmRiskClass.EQUITY:
        return EQUITY_SPOT_RISK_FACTOR
    if risk_class is SbmRiskClass.COMMODITY:
        return key[1]
    if risk_class in {
        SbmRiskClass.CSR_NONSEC,
        SbmRiskClass.CSR_SEC_CTP,
        SbmRiskClass.CSR_SEC_NONCTP,
    }:
        return "CREDIT_SPREAD_CURVE"
    return fallback_risk_factor


def _curvature_factor_qualifier(
    risk_class: SbmRiskClass,
    key: tuple[str, ...],
    sensitivity: SbmSensitivity,
) -> str | None:
    if risk_class is SbmRiskClass.EQUITY:
        return key[2]
    if risk_class is SbmRiskClass.COMMODITY:
        return key[2]
    if risk_class in {
        SbmRiskClass.CSR_NONSEC,
        SbmRiskClass.CSR_SEC_CTP,
        SbmRiskClass.CSR_SEC_NONCTP,
    }:
        return key[1]
    return sensitivity.qualifier


def _curvature_factor_qualifier_from_key(
    risk_class: SbmRiskClass,
    key: tuple[str, ...],
    fallback_qualifier: str | None,
) -> str | None:
    if risk_class is SbmRiskClass.EQUITY:
        return key[2]
    if risk_class is SbmRiskClass.COMMODITY:
        return key[2]
    if risk_class in {
        SbmRiskClass.CSR_NONSEC,
        SbmRiskClass.CSR_SEC_CTP,
        SbmRiskClass.CSR_SEC_NONCTP,
    }:
        return key[1]
    return fallback_qualifier


def _curvature_factor_citation_ids(
    profile_id: str,
    *,
    risk_class: SbmRiskClass,
    bucket_id: str,
    risk_factor: str,
) -> tuple[str, ...]:
    del bucket_id, risk_factor
    return _merge_citation_ids(
        curvature_citation_ids(profile_id),
        _curvature_definition_citation_ids(risk_class),
        _curvature_weight_rule_citation_ids(risk_class),
    )


def _curvature_definition_citation_ids(risk_class: SbmRiskClass) -> tuple[str, ...]:
    if risk_class is SbmRiskClass.GIRR:
        return ("basel_mar21_8", "basel_mar21_96", "basel_mar21_97")
    if risk_class is SbmRiskClass.FX:
        return ("basel_mar21_14", "basel_mar21_96", "basel_mar21_97")
    if risk_class is SbmRiskClass.EQUITY:
        return ("basel_mar21_12", "basel_mar21_96", "basel_mar21_97")
    if risk_class is SbmRiskClass.COMMODITY:
        return ("basel_mar21_13", "basel_mar21_96", "basel_mar21_97")
    if risk_class is SbmRiskClass.CSR_NONSEC:
        return ("basel_mar21_9", "basel_mar21_96", "basel_mar21_97")
    if risk_class is SbmRiskClass.CSR_SEC_CTP:
        return ("basel_mar21_11", "basel_mar21_96", "basel_mar21_97")
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        return ("basel_mar21_10", "basel_mar21_96", "basel_mar21_97")
    return ("basel_mar21_96", "basel_mar21_97")


def _curvature_weight_rule_citation_ids(risk_class: SbmRiskClass) -> tuple[str, ...]:
    if risk_class is SbmRiskClass.GIRR:
        return ("basel_mar21_99", "basel_mar21_39")
    if risk_class is SbmRiskClass.FX:
        return ("basel_mar21_98", "basel_mar21_87", "basel_mar21_88")
    if risk_class is SbmRiskClass.EQUITY:
        return ("basel_mar21_98", "basel_mar21_77")
    if risk_class is SbmRiskClass.COMMODITY:
        return ("basel_mar21_99", "basel_mar21_82")
    if risk_class is SbmRiskClass.CSR_NONSEC:
        return ("basel_mar21_99", "basel_mar21_53")
    if risk_class is SbmRiskClass.CSR_SEC_CTP:
        return ("basel_mar21_99", "basel_mar21_59")
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        return ("basel_mar21_99", "basel_mar21_65", "basel_mar21_66")
    return ("basel_mar21_99",)


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


def _scaled_curvature_shock(sensitivity: SbmSensitivity, *, field: str) -> float:
    shock = _required_curvature_shock(sensitivity, field=field)
    if (
        sensitivity.risk_class is SbmRiskClass.FX
        and FX_CURVATURE_SCALAR_1_5_FLAG in sensitivity.mapping_citation_ids
    ):
        return shock / 1.5
    return shock


def _validate_fx_curvature_scalar_flag(
    sensitivity: SbmSensitivity,
    *,
    reporting_currency: str,
) -> None:
    if FX_CURVATURE_SCALAR_1_5_FLAG not in sensitivity.mapping_citation_ids:
        return
    qualifier = sensitivity.qualifier.strip().upper() if sensitivity.qualifier else ""
    if qualifier:
        tokens = tuple(
            token for token in qualifier.replace("/", " ").replace("-", " ").split() if token
        )
        if len(tokens) == 2 and all(len(token) == 3 and token.isalpha() for token in tokens):
            if reporting_currency in tokens:
                raise UnsupportedRegulatoryFeatureError(
                    "FX curvature MAR21.98 scalar applies only when the option does not "
                    "reference the reporting currency"
                )
            return
    raise UnsupportedRegulatoryFeatureError(
        "FX curvature MAR21.98 scalar requires a two-currency qualifier such as "
        "'EUR/GBP' so audit evidence identifies the non-reporting-currency pair"
    )


def _aggregate_curvature_factors(
    factors: tuple[_CurvatureFactor, ...],
    *,
    profile_id: str,
    risk_class: SbmRiskClass,
    curvature_branches: tuple[CurvatureBranchRecord, ...],
) -> RiskClassCapital:
    grouped: dict[str, list[_CurvatureFactor]] = {}
    for factor in factors:
        grouped.setdefault(factor.bucket_id, []).append(factor)
    if not grouped:
        raise SbmInputError("curvature factors must not be empty", field="sensitivities")

    bucket_ids = tuple(sorted(grouped, key=lambda item: _bucket_sort_key(risk_class, item)))
    inter_bucket_correlations = _build_curvature_inter_bucket_correlation_map(
        bucket_ids,
        profile_id=profile_id,
        risk_class=risk_class,
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
                risk_class=risk_class,
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
                    _curvature_intra_citation_ids(risk_class),
                    _curvature_inter_citation_ids(risk_class),
                ),
            )
        )

    selection = select_max_correlation_scenario(
        scenario_totals,
        risk_class=risk_class,
        risk_measure=SbmRiskMeasure.CURVATURE,
        branch_id=f"{risk_class.value.lower()}_curvature_scenario_selection",
        citation_ids=_MAR21_CURVATURE_SCENARIO_CITATION,
    )
    selected_bucket_scenarios = scenario_buckets[selection.selected_scenario]
    selected_buckets = tuple(
        _curvature_bucket_to_bucket_capital(bucket_scenario)
        for bucket_scenario in selected_bucket_scenarios
    )
    citations = _merge_citation_ids(
        _MAR21_CURVATURE_SCENARIO_CITATION,
        _curvature_intra_citation_ids(risk_class),
        _curvature_inter_citation_ids(risk_class),
        _MAR21_CURVATURE_FLOOR_CITATION,
        selection.citation_ids,
    )
    return RiskClassCapital(
        risk_class=risk_class,
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
    risk_class: SbmRiskClass,
    scenario: SbmScenarioLabel,
) -> _CurvatureBucketScenario:
    base_matrix = _build_curvature_intra_bucket_correlation_matrix(
        factors,
        profile_id=profile_id,
        risk_class=risk_class,
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
        citation_ids=_curvature_intra_citation_ids(risk_class),
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


def _build_curvature_intra_bucket_correlation_matrix(
    ordered: Sequence[_CurvatureFactor],
    *,
    profile_id: str,
    risk_class: SbmRiskClass,
) -> npt.NDArray[np.float64]:
    size = len(ordered)
    matrix = np.eye(size, dtype=np.float64)
    for row_index, factor_a in enumerate(ordered):
        for col_index in range(row_index + 1, size):
            factor_b = ordered[col_index]
            curvature_correlation = _curvature_intra_bucket_correlation(
                profile_id,
                risk_class=risk_class,
                factor_a=factor_a,
                factor_b=factor_b,
            )
            matrix[row_index, col_index] = curvature_correlation
            matrix[col_index, row_index] = curvature_correlation
    return matrix


def _curvature_intra_bucket_correlation(
    profile_id: str,
    *,
    risk_class: SbmRiskClass,
    factor_a: _CurvatureFactor,
    factor_b: _CurvatureFactor,
) -> float:
    if risk_class is SbmRiskClass.GIRR:
        same_curve = factor_a.risk_factor == factor_b.risk_factor
        correlation, _ = girr_delta_intra_bucket_correlation(
            profile_id,
            tenor1=_GIRR_CURVATURE_PARALLEL_TENOR,
            tenor2=_GIRR_CURVATURE_PARALLEL_TENOR,
            same_curve=same_curve,
        )
        return correlation**2
    if risk_class is SbmRiskClass.FX:
        correlation, _ = fx_delta_intra_bucket_correlation(
            profile_id,
            bucket1=factor_a.bucket_id,
            bucket2=factor_b.bucket_id,
        )
        return correlation**2
    if risk_class is SbmRiskClass.EQUITY:
        if factor_a.bucket_id == EQUITY_OTHER_SECTOR_BUCKET:
            return 0.0
        correlation, _ = equity_delta_intra_bucket_correlation(
            profile_id,
            bucket_id=factor_a.bucket_id,
            risk_factor_a=EQUITY_SPOT_RISK_FACTOR,
            risk_factor_b=EQUITY_SPOT_RISK_FACTOR,
            issuer_a=_required_factor_qualifier(factor_a),
            issuer_b=_required_factor_qualifier(factor_b),
        )
        return correlation**2
    if risk_class is SbmRiskClass.COMMODITY:
        correlation, _ = commodity_delta_intra_bucket_correlation(
            profile_id,
            bucket_id=factor_a.bucket_id,
            commodity_a=factor_a.risk_factor,
            commodity_b=factor_b.risk_factor,
            tenor_a=_COMMODITY_CURVATURE_PARALLEL_TENOR,
            tenor_b=_COMMODITY_CURVATURE_PARALLEL_TENOR,
            location_a=_required_factor_qualifier(factor_a),
            location_b=_required_factor_qualifier(factor_b),
        )
        return correlation**2
    if risk_class is SbmRiskClass.CSR_NONSEC:
        if factor_a.bucket_id == CSR_OTHER_SECTOR_BUCKET:
            return 0.0
        nonsec_bucket = csr_nonsec_bucket_definition(profile_id, factor_a.bucket_id)
        if _required_factor_qualifier(factor_a) == _required_factor_qualifier(factor_b):
            return 1.0
        name_rho = (
            CSR_INDEX_NAME_CORRELATION
            if nonsec_bucket.bucket_id in {CSR_IG_INDEX_BUCKET, CSR_HY_INDEX_BUCKET}
            else CSR_NAME_CORRELATION
        )
        return name_rho**2
    if risk_class is SbmRiskClass.CSR_SEC_CTP:
        if _required_factor_qualifier(factor_a) == _required_factor_qualifier(factor_b):
            return 1.0
        return CSR_NAME_CORRELATION**2
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        nonctp_bucket = csr_sec_nonctp_bucket_definition(profile_id, factor_a.bucket_id)
        if nonctp_bucket.bucket_id == CSR_SEC_OTHER_SECTOR_BUCKET:
            return 0.0
        if _required_factor_qualifier(factor_a) == _required_factor_qualifier(factor_b):
            return 1.0
        return CSR_SEC_TRANCHE_DIFFERENT_CORRELATION**2
    raise UnsupportedRegulatoryFeatureError(
        f"curvature intra-bucket correlation is unsupported for risk_class={risk_class.value}"
    )


def _build_curvature_inter_bucket_correlation_map(
    bucket_ids: Sequence[str],
    *,
    profile_id: str,
    risk_class: SbmRiskClass,
) -> dict[tuple[str, str], float]:
    correlations: dict[tuple[str, str], float] = {}
    ordered_ids = tuple(sorted(bucket_ids, key=lambda item: _bucket_sort_key(risk_class, item)))
    for left_index, bucket_a in enumerate(ordered_ids):
        for bucket_b in ordered_ids[left_index + 1 :]:
            gamma = _curvature_inter_bucket_correlation(
                profile_id,
                risk_class=risk_class,
                bucket_a=bucket_a,
                bucket_b=bucket_b,
            )
            correlations[(bucket_a, bucket_b)] = gamma**2
    return correlations


def _curvature_inter_bucket_correlation(
    profile_id: str,
    *,
    risk_class: SbmRiskClass,
    bucket_a: str,
    bucket_b: str,
) -> float:
    if risk_class is SbmRiskClass.GIRR:
        gamma, _ = girr_inter_bucket_correlation(profile_id, bucket1=bucket_a, bucket2=bucket_b)
        return gamma
    if risk_class is SbmRiskClass.FX:
        gamma, _ = fx_inter_bucket_correlation(profile_id, bucket1=bucket_a, bucket2=bucket_b)
        return gamma
    if risk_class is SbmRiskClass.EQUITY:
        gamma, _ = equity_inter_bucket_correlation(profile_id, bucket1=bucket_a, bucket2=bucket_b)
        return gamma
    if risk_class is SbmRiskClass.COMMODITY:
        gamma, _ = commodity_inter_bucket_correlation(
            profile_id,
            bucket1=bucket_a,
            bucket2=bucket_b,
        )
        return gamma
    if risk_class is SbmRiskClass.CSR_NONSEC:
        gamma, _ = csr_nonsec_inter_bucket_correlation(
            profile_id,
            bucket1=bucket_a,
            bucket2=bucket_b,
        )
        return gamma
    if risk_class is SbmRiskClass.CSR_SEC_CTP:
        gamma, _ = csr_sec_ctp_inter_bucket_correlation(
            profile_id,
            bucket1=bucket_a,
            bucket2=bucket_b,
        )
        return gamma
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        gamma, _ = csr_sec_nonctp_inter_bucket_correlation(
            profile_id,
            bucket1=bucket_a,
            bucket2=bucket_b,
        )
        return gamma
    raise UnsupportedRegulatoryFeatureError(
        f"curvature inter-bucket correlation is unsupported for risk_class={risk_class.value}"
    )


def _curvature_intra_citation_ids(risk_class: SbmRiskClass) -> tuple[str, ...]:
    if risk_class is SbmRiskClass.GIRR:
        return (*_MAR21_CURVATURE_INTRA_CITATION, "basel_mar21_45_49")
    if risk_class is SbmRiskClass.FX:
        return (*_MAR21_CURVATURE_INTRA_CITATION, "basel_mar21_86")
    if risk_class is SbmRiskClass.EQUITY:
        return (*_MAR21_CURVATURE_INTRA_CITATION, "basel_mar21_78", "basel_mar21_79")
    if risk_class is SbmRiskClass.COMMODITY:
        return (*_MAR21_CURVATURE_INTRA_CITATION, "basel_mar21_83")
    if risk_class is SbmRiskClass.CSR_NONSEC:
        return (*_MAR21_CURVATURE_INTRA_CITATION, "basel_mar21_54", "basel_mar21_55")
    if risk_class is SbmRiskClass.CSR_SEC_CTP:
        return (*_MAR21_CURVATURE_INTRA_CITATION, "basel_mar21_58")
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        return (*_MAR21_CURVATURE_INTRA_CITATION, "basel_mar21_67", "basel_mar21_68")
    return _MAR21_CURVATURE_INTRA_CITATION


def _curvature_inter_citation_ids(risk_class: SbmRiskClass) -> tuple[str, ...]:
    if risk_class is SbmRiskClass.GIRR:
        return (*_MAR21_CURVATURE_INTER_CITATION, "basel_mar21_50")
    if risk_class is SbmRiskClass.FX:
        return (*_MAR21_CURVATURE_INTER_CITATION, "basel_mar21_89")
    if risk_class is SbmRiskClass.EQUITY:
        return (*_MAR21_CURVATURE_INTER_CITATION, "basel_mar21_80")
    if risk_class is SbmRiskClass.COMMODITY:
        return (*_MAR21_CURVATURE_INTER_CITATION, "basel_mar21_85")
    if risk_class in {SbmRiskClass.CSR_NONSEC, SbmRiskClass.CSR_SEC_CTP}:
        return (*_MAR21_CURVATURE_INTER_CITATION, "basel_mar21_57")
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        return (*_MAR21_CURVATURE_INTER_CITATION, "basel_mar21_70")
    return _MAR21_CURVATURE_INTER_CITATION


def _bucket_sort_key(risk_class: SbmRiskClass, bucket_id: str) -> tuple[int, str]:
    if risk_class is SbmRiskClass.EQUITY:
        return (_require_equity_bucket_number(bucket_id), bucket_id)
    if risk_class is SbmRiskClass.COMMODITY:
        return (_require_commodity_bucket_number(bucket_id), bucket_id)
    try:
        return (int(bucket_id), bucket_id)
    except ValueError:
        return (10_000, bucket_id)


def _required_factor_qualifier(factor: _CurvatureFactor) -> str:
    if factor.qualifier is None or not factor.qualifier.strip():
        raise SbmInputError("curvature factor qualifier is required", field="qualifier")
    return factor.qualifier.strip()


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


def _normalise_csr_basis(risk_factor: str) -> str:
    normalised = risk_factor.strip().upper()
    if normalised not in {CSR_BOND_RISK_FACTOR, CSR_CDS_RISK_FACTOR}:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm CSR curvature supports BOND and CDS risk factors only; "
            f"received risk_factor={normalised!r}"
        )
    return normalised


def _normalise_csr_sec_basis(risk_factor: str) -> str:
    normalised = risk_factor.strip().upper()
    if normalised not in {CSR_SEC_BOND_RISK_FACTOR, CSR_SEC_CDS_RISK_FACTOR}:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm CSR securitisation curvature supports BOND and CDS risk factors only; "
            f"received risk_factor={normalised!r}"
        )
    return normalised


def _merge_citation_ids(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for citation_id in group:
            if citation_id not in seen:
                merged.append(citation_id)
                seen.add(citation_id)
    return tuple(merged)


def _validate_curvature_batch_for_capital(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
    reporting_currency: str,
    expected_risk_class: SbmRiskClass | None,
) -> tuple[SbmRiskClass, npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    ensure_sbm_profile_known(profile_id)
    if not isinstance(batch, SbmSensitivityBatch):
        raise SbmInputError("batch must be SbmSensitivityBatch", field="batch")
    if batch.row_count == 0:
        raise SbmInputError("curvature batch must not be empty", field="batch")
    risk_class = batch.risk_class
    if expected_risk_class is not None and risk_class is not expected_risk_class:
        raise UnsupportedRegulatoryFeatureError(
            "frtb-sbm curvature capital expected "
            f"risk_class={expected_risk_class.value}; received risk_class={risk_class.value}"
        )
    if risk_class not in _SUPPORTED_CURVATURE_RISK_CLASSES:
        raise UnsupportedRegulatoryFeatureError(
            f"frtb-sbm curvature capital is unsupported for risk_class={risk_class.value}"
        )
    if batch.risk_measure is not SbmRiskMeasure.CURVATURE:
        raise UnsupportedRegulatoryFeatureError(
            f"frtb-sbm curvature capital does not support risk_measure={batch.risk_measure.value}"
        )
    ensure_profile_supports_risk_class_measure(
        profile_id,
        risk_class,
        SbmRiskMeasure.CURVATURE,
    )
    up_shocks, down_shocks = _validate_and_get_curvature_shocks(
        batch,
        profile_id=profile_id,
    )
    reporting = normalise_fx_delta_currency_code(reporting_currency)
    for row_index in sorted_curvature_batch_indices(batch):
        _validate_curvature_mapping_from_batch(
            batch,
            int(row_index),
            profile_id=profile_id,
            reporting_currency=reporting,
            risk_class=risk_class,
        )
    return risk_class, up_shocks, down_shocks


def _validate_curvature_mapping_from_batch(
    batch: SbmSensitivityBatch,
    row_index: int,
    *,
    profile_id: str,
    reporting_currency: str,
    risk_class: SbmRiskClass,
) -> None:
    sensitivity_id = _text_at(batch.sensitivity_ids, row_index)
    bucket = _text_at(batch.buckets, row_index)
    risk_factor = _text_at(batch.risk_factors, row_index)
    qualifier = _optional_text_at(batch.qualifiers, row_index)
    if risk_class is SbmRiskClass.GIRR:
        girr_bucket_definition(profile_id, bucket)
        if risk_factor.strip().upper() in {"INFL", "XCCY"}:
            raise UnsupportedRegulatoryFeatureError(
                "GIRR curvature has no capital requirement for inflation or "
                "cross-currency basis risk factors (MAR21.8(5)(b))"
            )
        return
    if risk_class is SbmRiskClass.FX:
        normalised_bucket = normalise_fx_delta_currency_code(bucket)
        normalised_risk_factor = normalise_fx_delta_currency_code(risk_factor)
        if normalised_bucket != normalised_risk_factor:
            raise SbmInputError(
                "FX curvature bucket must match risk_factor currency",
                field="bucket",
                sensitivity_id=sensitivity_id,
            )
        curvature_risk_weight(
            profile_id,
            risk_class=risk_class,
            currency=normalised_risk_factor,
            reporting_currency=reporting_currency,
        )
        _validate_fx_curvature_scalar_flag_from_values(
            qualifier,
            _mapping_citation_ids_from_batch(batch, row_index),
            reporting_currency=reporting_currency,
        )
        return
    if risk_class is SbmRiskClass.EQUITY:
        equity_bucket_definition(profile_id, bucket)
        if risk_factor.strip().upper() != EQUITY_SPOT_RISK_FACTOR:
            raise UnsupportedRegulatoryFeatureError(
                "equity curvature has no capital requirement for equity repo rates (MAR21.12(3))"
            )
        return
    if risk_class is SbmRiskClass.COMMODITY:
        commodity_bucket_definition(profile_id, bucket)
        return
    if risk_class is SbmRiskClass.CSR_NONSEC:
        csr_nonsec_bucket_definition(profile_id, bucket)
        _normalise_csr_basis(risk_factor)
        return
    if risk_class is SbmRiskClass.CSR_SEC_CTP:
        csr_sec_ctp_bucket_definition(profile_id, bucket)
        _normalise_csr_basis(risk_factor)
        return
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP:
        csr_sec_nonctp_bucket_definition(profile_id, bucket)
        _normalise_csr_sec_basis(risk_factor)
        return
    raise UnsupportedRegulatoryFeatureError(
        f"frtb-sbm curvature capital is unsupported for risk_class={risk_class.value}"
    )


def _curvature_input_branch_records_from_batch(
    batch: SbmSensitivityBatch,
    *,
    up_shocks: npt.NDArray[np.float64],
    down_shocks: npt.NDArray[np.float64],
    profile_id: str,
) -> tuple[CurvatureBranchRecord, ...]:
    citations = curvature_citation_ids(profile_id)
    records: list[CurvatureBranchRecord] = []
    for row_index in sorted_curvature_batch_indices(batch):
        up_shock = float(up_shocks[row_index])
        down_shock = float(down_shocks[row_index])
        records.append(
            CurvatureBranchRecord(
                sensitivity_id=_text_at(batch.sensitivity_ids, int(row_index)),
                selected_branch=curvature_worst_branch(up_shock, down_shock),
                up_shock_amount=up_shock,
                down_shock_amount=down_shock,
                citation_ids=citations,
            )
        )
    return tuple(records)


def _scaled_curvature_batch_shock(
    batch: SbmSensitivityBatch,
    row_index: int,
    shock: float,
) -> float:
    if (
        batch.risk_class is SbmRiskClass.FX
        and FX_CURVATURE_SCALAR_1_5_FLAG in _mapping_citation_ids_from_batch(batch, row_index)
    ):
        return float(shock) / 1.5
    return float(shock)


def _validate_fx_curvature_scalar_flag_from_values(
    qualifier: str | None,
    mapping_citation_ids: tuple[str, ...],
    *,
    reporting_currency: str,
) -> None:
    if FX_CURVATURE_SCALAR_1_5_FLAG not in mapping_citation_ids:
        return
    qualifier_text = qualifier.strip().upper() if qualifier else ""
    if qualifier_text:
        tokens = tuple(
            token for token in qualifier_text.replace("/", " ").replace("-", " ").split() if token
        )
        if len(tokens) == 2 and all(len(token) == 3 and token.isalpha() for token in tokens):
            if reporting_currency in tokens:
                raise UnsupportedRegulatoryFeatureError(
                    "FX curvature MAR21.98 scalar applies only when the option does not "
                    "reference the reporting currency"
                )
            return
    raise UnsupportedRegulatoryFeatureError(
        "FX curvature MAR21.98 scalar requires a two-currency qualifier such as "
        "'EUR/GBP' so audit evidence identifies the non-reporting-currency pair"
    )


def _text_at(values: npt.NDArray[np.object_], row_index: int) -> str:
    return str(values[row_index])


def _optional_text_at(values: npt.NDArray[np.object_] | None, row_index: int) -> str | None:
    if values is None:
        return None
    value = values[row_index]
    if value is None:
        return None
    return str(value)


def _mapping_citation_ids_from_batch(
    batch: SbmSensitivityBatch,
    row_index: int,
) -> tuple[str, ...]:
    if batch.mapping_citation_ids is None:
        return ()
    return batch.mapping_citation_ids[row_index]


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
    return _validate_and_get_curvature_shocks(batch, profile_id=profile_id)


def _validate_and_get_curvature_shocks(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    ensure_sbm_profile_known(profile_id)
    if not isinstance(batch, SbmSensitivityBatch):
        raise SbmInputError("batch must be SbmSensitivityBatch", field="batch")
    if batch.risk_measure is not SbmRiskMeasure.CURVATURE:
        raise SbmInputError("curvature batch only accepts CURVATURE sensitivities")
    if batch.up_shock_amounts is None or batch.down_shock_amounts is None:
        raise SbmInputError(
            "curvature inputs require up_shock_amount and down_shock_amount",
            field="up_shock_amount",
        )
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
    "FX_CURVATURE_SCALAR_1_5_FLAG",
    "aggregate_girr_curvature_measure_capital",
    "calculate_curvature_risk_class_capital",
    "calculate_curvature_risk_class_capital_from_batch",
    "calculate_girr_curvature_risk_class_capital",
    "calculate_girr_curvature_risk_class_capital_from_batch",
    "curvature_capital_unsupported_feature",
    "curvature_worst_branch",
    "parse_curvature_input",
    "select_curvature_branches_from_batch",
    "select_girr_curvature_branches_from_batch",
    "selected_curvature_shock_amount",
    "validate_curvature_batch",
    "validate_curvature_sensitivities",
    "validate_girr_curvature_batch",
    "weight_girr_curvature_sensitivities",
]
