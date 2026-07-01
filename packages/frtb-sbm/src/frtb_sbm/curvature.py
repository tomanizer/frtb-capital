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

from frtb_sbm._citations import merge_citation_ids as _merge_citation_ids
from frtb_sbm.aggregation import (
    select_max_correlation_scenario,
)
from frtb_sbm.batch import (
    SbmSensitivityBatch,
    sorted_curvature_batch_indices,
    sorted_girr_curvature_batch_indices,
)
from frtb_sbm.curvature_batch_inputs import (
    _curvature_input_branch_records_from_batch,
    _optional_text_at,
    _scaled_curvature_batch_shock,
    _text_at,
    _validate_and_get_curvature_shocks,
    _validate_and_get_girr_curvature_shocks,
    _validate_curvature_batch_for_capital,
    validate_curvature_batch,
    validate_girr_curvature_batch,
)
from frtb_sbm.curvature_bucket_records import (
    _curvature_bucket_branch_record,
    _curvature_bucket_to_bucket_capital,
    _curvature_bucket_to_intra_record,
)
from frtb_sbm.curvature_bucket_scenarios import (
    _CurvatureBucketScenario,
    _evaluate_curvature_bucket_scenario,
)
from frtb_sbm.curvature_correlations import (
    _bucket_sort_key,
    _build_curvature_inter_bucket_correlation_map,
    _curvature_inter_citation_ids,
    _curvature_intra_citation_ids,
)
from frtb_sbm.curvature_correlations import (
    _build_curvature_intra_bucket_correlation_matrix as _intra_matrix_compat,
)
from frtb_sbm.curvature_correlations import (
    _build_vectorized_curvature_intra_bucket_correlation_matrix as _build_vectorized_intra_matrix,
)
from frtb_sbm.curvature_correlations import (
    _curvature_inter_bucket_correlation as _inter_bucket_correlation,
)
from frtb_sbm.curvature_correlations import (
    _curvature_intra_bucket_correlation as _intra_bucket_correlation,
)
from frtb_sbm.curvature_correlations import (
    _required_factor_qualifier as _factor_qualifier,
)
from frtb_sbm.curvature_factors import (
    FX_CURVATURE_SCALAR_1_5_FLAG,
    _curvature_factor_citation_ids,
    _curvature_factor_key,
    _curvature_factor_qualifier,
    _curvature_factor_risk_factor,
    _CurvatureFactor,
    _scaled_curvature_shock,
)
from frtb_sbm.curvature_factors import (
    _required_curvature_shock as _required_curvature_shock,
)
from frtb_sbm.curvature_inputs import (
    _curvature_input_branch_records,
    _validate_curvature_capital_sensitivities,
    curvature_worst_branch,
    parse_curvature_input,
    selected_curvature_shock_amount,
    validate_curvature_sensitivities,
)
from frtb_sbm.curvature_inter_bucket_aggregation import _aggregate_curvature_inter_bucket
from frtb_sbm.data_models import (
    DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
    CurvatureBranchRecord,
    CurvatureBucketBranchRecord,
    RiskClassCapital,
    RiskClassScenarioDetail,
    SbmPairwiseEvidenceMode,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmScenarioLabel,
    SbmSensitivity,
    SbmUnsupportedFeature,
    WeightedSensitivity,
)
from frtb_sbm.equity_reference_data import (
    EQUITY_SPOT_RISK_FACTOR,
)
from frtb_sbm.girr_reference_tables import PROFILE_GIRR_CURVATURE_SCENARIO_CITATION_IDS
from frtb_sbm.org_scope import scope_at, single_scope_metadata, unique_scope_metadata
from frtb_sbm.reference_data import (
    curvature_citation_ids,
    normalise_fx_delta_currency_code,
)
from frtb_sbm.reference_profiles import _resolve_supported_profile
from frtb_sbm.regimes import ensure_profile_supports_risk_class_measure
from frtb_sbm.validation import (
    SbmInputError,
    ensure_sbm_profile_known,
    sensitivity_sort_key,
)

CURVATURE_CAPITAL_REQUIREMENT_ID = "SBM-CURV-001"

_MAR21_CURVATURE_FLOOR_CITATION = ("basel_mar21_curvature",)
_MAR21_CURVATURE_SCENARIO_CITATION = (
    "basel_mar21_6_correlation_scenarios",
    "basel_mar21_7_scenario_selection",
)
_DEFAULT_SCENARIOS: tuple[SbmScenarioLabel, ...] = (
    SbmScenarioLabel.LOW,
    SbmScenarioLabel.MEDIUM,
    SbmScenarioLabel.HIGH,
)
_SUPPORTED_CURVATURE_RISK_CLASSES: frozenset[SbmRiskClass] = frozenset(SbmRiskClass)

_build_vectorized_curvature_intra_bucket_correlation_matrix = _build_vectorized_intra_matrix
_build_curvature_intra_bucket_correlation_matrix = _intra_matrix_compat
_curvature_inter_bucket_correlation = _inter_bucket_correlation
_curvature_intra_bucket_correlation = _intra_bucket_correlation
_required_factor_qualifier = _factor_qualifier


def select_girr_curvature_branches_from_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
) -> tuple[CurvatureBranchRecord, ...]:
    """Return deterministic GIRR curvature branch records from batch columns.

    The returned records match the row-wise branch-selection rule while reading
    directly from the package-owned batch arrays.
    Parameters
    ----------
    batch : SbmSensitivityBatch
        See signature.
    profile_id : str
        See signature.

    Returns
    -------
    tuple[CurvatureBranchRecord, ...]
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
    """Return deterministic curvature branch records from batch columns.
    Parameters
    ----------
    batch : SbmSensitivityBatch
        See signature.
    profile_id : str
        See signature.

    Returns
    -------
    tuple[CurvatureBranchRecord, ...]
    """

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
    """Reject the obsolete row-wise weighted curvature shortcut.
    Parameters
    ----------
    sensitivities : Sequence[SbmSensitivity]
        See signature.
    profile_id : str
        See signature.
    reporting_currency : str
        See signature.

    Returns
    -------
    tuple[tuple[WeightedSensitivity, ...], tuple[CurvatureBranchRecord, ...]]
    """

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
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Calculate cited GIRR curvature risk-class capital.
    Parameters
    ----------
    sensitivities, profile_id, reporting_currency, pairwise_evidence_mode, pairwise_evidence_limit :
        See function signature for types and defaults.

    Returns
    -------
    RiskClassCapital
    """

    return _calculate_curvature_risk_class_capital(
        sensitivities,
        profile_id=profile_id,
        reporting_currency=reporting_currency,
        expected_risk_class=SbmRiskClass.GIRR,
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def aggregate_girr_curvature_measure_capital(
    weighted: tuple[WeightedSensitivity, ...],
    *,
    profile_id: str,
    tenor_by_id: Mapping[str, str],
    risk_factor_by_id: Mapping[str, str],
    curvature_branches: tuple[CurvatureBranchRecord, ...],
) -> RiskClassCapital:
    """Reject weighted-input curvature aggregation because it loses CVR branch state.
    Parameters
    ----------
    weighted, profile_id, tenor_by_id, risk_factor_by_id, curvature_branches :
        See function signature for types and defaults.

    Returns
    -------
    RiskClassCapital
    """

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
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Calculate cited curvature capital for supported risk classes.
    Parameters
    ----------
    sensitivities, profile_id, reporting_currency, pairwise_evidence_mode, pairwise_evidence_limit :
        See function signature for types and defaults.

    Returns
    -------
    RiskClassCapital
    """

    return _calculate_curvature_risk_class_capital(
        sensitivities,
        profile_id=profile_id,
        reporting_currency=reporting_currency,
        expected_risk_class=None,
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def calculate_girr_curvature_risk_class_capital_from_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
    reporting_currency: str,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Calculate cited GIRR curvature capital directly from a sensitivity batch.
    Parameters
    ----------
    batch, profile_id, reporting_currency, pairwise_evidence_mode, pairwise_evidence_limit :
        See function signature for types and defaults.

    Returns
    -------
    RiskClassCapital
    """

    return calculate_curvature_risk_class_capital_from_batch(
        batch,
        profile_id=profile_id,
        reporting_currency=reporting_currency,
        expected_risk_class=SbmRiskClass.GIRR,
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def calculate_curvature_risk_class_capital_from_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
    reporting_currency: str,
    expected_risk_class: SbmRiskClass | None = None,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    """Calculate cited curvature capital directly from package-owned batch arrays.
    Parameters
    ----------
    batch, profile_id, reporting_currency, expected_risk_class, pairwise_evidence_mode,
    pairwise_evidence_limit :
        See function signature for types and defaults.

    Returns
    -------
    RiskClassCapital
    """

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
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def _calculate_curvature_risk_class_capital(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
    reporting_currency: str,
    expected_risk_class: SbmRiskClass | None,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
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
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def curvature_capital_unsupported_feature(profile_id: str) -> SbmUnsupportedFeature:
    """Return structured metadata for unsupported curvature paths on a profile.
    Parameters
    ----------
    profile_id : str
        See signature.

    Returns
    -------
    SbmUnsupportedFeature
    """

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
                org_scope=single_scope_metadata(item.org_scope for item in ordered),
                contributing_org_scopes=unique_scope_metadata(item.org_scope for item in ordered),
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
                org_scope=single_scope_metadata(
                    scope_at(batch.org_scopes, index) for index in row_indices
                ),
                contributing_org_scopes=unique_scope_metadata(
                    scope_at(batch.org_scopes, index) for index in row_indices
                ),
            )
        )
    return tuple(factors)


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


def _aggregate_curvature_factors(
    factors: tuple[_CurvatureFactor, ...],
    *,
    profile_id: str,
    risk_class: SbmRiskClass,
    curvature_branches: tuple[CurvatureBranchRecord, ...],
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
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
                    _curvature_bucket_to_intra_record(
                        bucket_scenario,
                        pairwise_evidence_mode=pairwise_evidence_mode,
                        pairwise_evidence_limit=pairwise_evidence_limit,
                    )
                    for bucket_scenario in bucket_scenarios
                ),
                citation_ids=_merge_citation_ids(
                    _curvature_scenario_citation_ids(profile_id, risk_class),
                    _curvature_intra_citation_ids(risk_class, profile_id),
                    _curvature_inter_citation_ids(risk_class, profile_id),
                ),
            )
        )

    selection = select_max_correlation_scenario(
        scenario_totals,
        risk_class=risk_class,
        risk_measure=SbmRiskMeasure.CURVATURE,
        branch_id=f"{risk_class.value.lower()}_curvature_scenario_selection",
        citation_ids=_curvature_scenario_citation_ids(profile_id, risk_class),
    )
    selected_bucket_scenarios = scenario_buckets[selection.selected_scenario]
    selected_buckets = tuple(
        _curvature_bucket_to_bucket_capital(bucket_scenario)
        for bucket_scenario in selected_bucket_scenarios
    )
    citations = _merge_citation_ids(
        _curvature_scenario_citation_ids(profile_id, risk_class),
        _curvature_intra_citation_ids(risk_class, profile_id),
        _curvature_inter_citation_ids(risk_class, profile_id),
        _curvature_floor_citation_ids(profile_id, risk_class),
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


def _curvature_scenario_citation_ids(
    profile_id: str,
    risk_class: SbmRiskClass,
) -> tuple[str, ...]:
    if risk_class is SbmRiskClass.GIRR:
        return PROFILE_GIRR_CURVATURE_SCENARIO_CITATION_IDS[_resolve_supported_profile(profile_id)]
    if (
        _resolve_supported_profile(profile_id) is SbmRegulatoryProfile.US_NPR_2_0
        and risk_class is SbmRiskClass.FX
    ):
        return ("us_npr_91_fr_14952_va7a_fx_curvature_scenarios",)
    return _MAR21_CURVATURE_SCENARIO_CITATION


def _curvature_floor_citation_ids(
    profile_id: str,
    risk_class: SbmRiskClass,
) -> tuple[str, ...]:
    profile = _resolve_supported_profile(profile_id)
    if profile is SbmRegulatoryProfile.US_NPR_2_0:
        return curvature_citation_ids(profile_id, risk_class)
    if profile in {SbmRegulatoryProfile.EU_CRR3, SbmRegulatoryProfile.PRA_UK_CRR}:
        return curvature_citation_ids(profile_id, risk_class)[:1]
    if risk_class is SbmRiskClass.GIRR:
        return ()
    return _MAR21_CURVATURE_FLOOR_CITATION


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
