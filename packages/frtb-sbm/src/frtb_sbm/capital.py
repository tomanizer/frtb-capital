"""
Public SBM capital calculation for supported GIRR and FX delta/vega inputs.

Regulatory traceability:
    Basel MAR21.4-MAR21.7 — delta aggregation and scenario selection.
    Basel MAR21.14, MAR21.86-MAR21.89 — FX delta buckets, weights, correlations.
    Basel MAR21.90-MAR21.95 — GIRR vega buckets and inter-bucket gamma.
    U.S. NPR 2.0 section V.A.7.a steps three through six.
    SBM-WS-001, SBM-AGG-001, SBM-AGG-002, SBM-FUNC-017, SBM-FUNC-018.
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
    select_portfolio_correlation_scenario,
)
from frtb_sbm.audit import (
    _input_hash_for_validated_sensitivities,
    validate_sbm_result_reconciliation,
)
from frtb_sbm.data_models import (
    RiskClassCapital,
    SbmBranchMetadata,
    SbmCalculationContext,
    SbmCapitalResult,
    SbmReconciliationMetadata,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmRunContextSummary,
    SbmSensitivity,
    WeightedSensitivity,
)
from frtb_sbm.reference_data import (
    GIRR_INTRA_BUCKET_CORRELATION_FLOOR,
    girr_delta_intra_bucket_correlation,
    girr_inter_bucket_correlation,
    girr_vega_intra_bucket_correlation,
)
from frtb_sbm.regimes import get_sbm_rule_profile
from frtb_sbm.risk_classes.commodity import calculate_commodity_delta_risk_class_capital
from frtb_sbm.risk_classes.csr_nonsec import calculate_csr_nonsec_delta_risk_class_capital
from frtb_sbm.risk_classes.equity import calculate_equity_delta_risk_class_capital
from frtb_sbm.risk_classes.fx import calculate_fx_delta_risk_class_capital
from frtb_sbm.validation import SbmInputError, ensure_sbm_run_supported
from frtb_sbm.weighted_sensitivity import (
    weight_girr_delta_sensitivities,
    weight_girr_vega_sensitivities,
)

_SBM_REQUIREMENT_IDS = (
    "SBM-WS-001",
    "SBM-AGG-001",
    "SBM-AGG-002",
    "SBM-AUDIT-001",
    "SBM-FUNC-017",
    "SBM-FUNC-018",
    "SBM-FUNC-019",
    "SBM-FUNC-014",
)

_PHASE1_SUPPORTED_PATHS: frozenset[tuple[SbmRiskClass, SbmRiskMeasure]] = frozenset(
    {
        (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA),
        (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA),
        (SbmRiskClass.FX, SbmRiskMeasure.DELTA),
        (SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA),
        (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA),
        (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA),
    }
)

_MAR21_INTRA_BUCKET_CITATION = ("basel_mar21_4_intra_bucket",)
_MAR21_INTER_BUCKET_CITATION = ("basel_mar21_4_inter_bucket",)
_GIRR_DELTA_INTRA_CITATIONS = (*_MAR21_INTRA_BUCKET_CITATION, "basel_mar21_41")
_GIRR_DELTA_INTER_CITATIONS = (*_MAR21_INTER_BUCKET_CITATION, "basel_mar21_42")
_GIRR_VEGA_INTRA_CITATIONS = (*_MAR21_INTRA_BUCKET_CITATION, "basel_mar21_93")
_GIRR_VEGA_INTER_CITATIONS = (*_MAR21_INTER_BUCKET_CITATION, "basel_mar21_42")


def calculate_sbm_capital(
    sensitivities: object | None = None,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate supported SBM capital for GIRR, FX, equity, commodity, and CSR non-sec delta."""

    if sensitivities is None:
        raise SbmInputError("sensitivities are required", field="sensitivities")
    if context is None:
        raise SbmInputError("calculation context is required", field="context")
    if not isinstance(context, SbmCalculationContext):
        raise SbmInputError(
            "calculation context must be SbmCalculationContext",
            field="context",
        )

    validated = _coerce_sensitivities(sensitivities)
    rule_profile = get_sbm_rule_profile(context.profile_id)
    ensure_sbm_run_supported(context, validated)
    _ensure_phase1_supported(validated)

    risk_class_results: list[RiskClassCapital] = []
    for risk_class, risk_measure in _ordered_supported_paths(validated):
        measure_sensitivities = tuple(
            item
            for item in validated
            if item.risk_class is risk_class and item.risk_measure is risk_measure
        )
        if risk_class is SbmRiskClass.GIRR and risk_measure is SbmRiskMeasure.DELTA:
            risk_class_results.append(
                _calculate_girr_delta_risk_class_capital(
                    measure_sensitivities,
                    profile_id=rule_profile.profile_id,
                    reporting_currency=context.reporting_currency,
                )
            )
        elif risk_class is SbmRiskClass.GIRR and risk_measure is SbmRiskMeasure.VEGA:
            risk_class_results.append(
                _calculate_girr_vega_risk_class_capital(
                    measure_sensitivities,
                    profile_id=rule_profile.profile_id,
                )
            )
        elif risk_class is SbmRiskClass.FX and risk_measure is SbmRiskMeasure.DELTA:
            risk_class_results.append(
                calculate_fx_delta_risk_class_capital(
                    measure_sensitivities,
                    profile_id=rule_profile.profile_id,
                    reporting_currency=context.reporting_currency,
                )
            )
        elif risk_class is SbmRiskClass.EQUITY and risk_measure is SbmRiskMeasure.DELTA:
            risk_class_results.append(
                calculate_equity_delta_risk_class_capital(
                    measure_sensitivities,
                    profile_id=rule_profile.profile_id,
                )
            )
        elif risk_class is SbmRiskClass.COMMODITY and risk_measure is SbmRiskMeasure.DELTA:
            risk_class_results.append(
                calculate_commodity_delta_risk_class_capital(
                    measure_sensitivities,
                    profile_id=rule_profile.profile_id,
                )
            )
        elif risk_class is SbmRiskClass.CSR_NONSEC and risk_measure is SbmRiskMeasure.DELTA:
            risk_class_results.append(
                calculate_csr_nonsec_delta_risk_class_capital(
                    measure_sensitivities,
                    profile_id=rule_profile.profile_id,
                )
            )
        else:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm phase-1 capital does not support "
                f"risk_class={risk_class.value}, risk_measure={risk_measure.value}"
            )

    (
        aligned_risk_classes,
        total_capital,
        portfolio_scenario_totals,
        selected_portfolio_scenario,
        portfolio_scenario_selection,
    ) = select_portfolio_correlation_scenario(risk_class_results)
    citation_ids = _collect_citation_ids(
        aligned_risk_classes,
        portfolio_scenario_selection=portfolio_scenario_selection,
    )
    result = SbmCapitalResult(
        total_capital=total_capital,
        risk_classes=aligned_risk_classes,
        profile_id=rule_profile.profile_id,
        profile_hash=rule_profile.content_hash,
        input_hash=_input_hash_for_validated_sensitivities(validated),
        warnings=_profile_warnings(rule_profile.profile_id),
        reconciliation=SbmReconciliationMetadata(
            input_count=len(validated),
            rejected_input_count=0,
            requirement_ids=_SBM_REQUIREMENT_IDS,
            citation_ids=citation_ids,
        ),
        run_context=SbmRunContextSummary(
            run_id=context.run_id,
            calculation_date=context.calculation_date,
            base_currency=context.base_currency,
            reporting_currency=context.reporting_currency,
        ),
        portfolio_scenario_totals=portfolio_scenario_totals,
        selected_portfolio_scenario=selected_portfolio_scenario,
        portfolio_scenario_selection=portfolio_scenario_selection,
    )
    validate_sbm_result_reconciliation(result)
    return result


def _calculate_girr_delta_risk_class_capital(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
    reporting_currency: str,
) -> RiskClassCapital:
    weighted = weight_girr_delta_sensitivities(
        sensitivities,
        profile_id=profile_id,
        reporting_currency=reporting_currency,
    )
    tenor_by_id = {item.sensitivity_id: item.tenor or "" for item in sensitivities}
    risk_factor_by_id = {item.sensitivity_id: item.risk_factor for item in sensitivities}
    return _aggregate_girr_measure_capital(
        weighted,
        profile_id=profile_id,
        risk_measure=SbmRiskMeasure.DELTA,
        tenor_by_id=tenor_by_id,
        risk_factor_by_id=risk_factor_by_id,
    )


def _calculate_girr_vega_risk_class_capital(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
) -> RiskClassCapital:
    weighted = weight_girr_vega_sensitivities(
        sensitivities,
        profile_id=profile_id,
    )
    option_tenor_by_id = {item.sensitivity_id: item.option_tenor or "" for item in sensitivities}
    tenor_by_id = {item.sensitivity_id: item.tenor or "" for item in sensitivities}
    return _aggregate_girr_measure_capital(
        weighted,
        profile_id=profile_id,
        risk_measure=SbmRiskMeasure.VEGA,
        tenor_by_id=tenor_by_id,
        option_tenor_by_id=option_tenor_by_id,
    )


def _aggregate_girr_measure_capital(
    weighted: tuple[WeightedSensitivity, ...],
    *,
    profile_id: str,
    risk_measure: SbmRiskMeasure,
    tenor_by_id: Mapping[str, str],
    risk_factor_by_id: Mapping[str, str] | None = None,
    option_tenor_by_id: Mapping[str, str] | None = None,
) -> RiskClassCapital:
    grouped = group_weighted_sensitivities_by_bucket(weighted)

    intra_specs: list[IntraBucketScenarioSpec] = []
    for (_risk_class, _risk_measure, bucket_id), bucket_weighted in sorted(grouped.items()):
        if risk_measure is SbmRiskMeasure.DELTA:
            matrix = _build_girr_delta_intra_bucket_correlation_matrix(
                bucket_weighted,
                profile_id=profile_id,
                tenor_by_id=tenor_by_id,
                risk_factor_by_id=risk_factor_by_id or {},
            )
        else:
            matrix = _build_girr_vega_intra_bucket_correlation_matrix(
                bucket_weighted,
                profile_id=profile_id,
                option_tenor_by_id=option_tenor_by_id or {},
                tenor_by_id=tenor_by_id,
            )
        intra_specs.append(
            IntraBucketScenarioSpec(
                bucket_id=bucket_id,
                weighted_sensitivities=tuple(bucket_weighted),
                base_correlation_matrix=matrix,
                sb_correlation_floor=GIRR_INTRA_BUCKET_CORRELATION_FLOOR
                if risk_measure is SbmRiskMeasure.DELTA
                else None,
            )
        )

    bucket_ids = tuple(sorted(spec.bucket_id for spec in intra_specs))
    inter_bucket_correlations = _build_inter_bucket_correlation_map(
        bucket_ids,
        profile_id=profile_id,
    )
    return aggregate_risk_class_with_scenarios(
        tuple(intra_specs),
        inter_bucket_correlations,
        risk_class=SbmRiskClass.GIRR,
        risk_measure=risk_measure,
        intra_bucket_citation_ids=(
            _GIRR_DELTA_INTRA_CITATIONS
            if risk_measure is SbmRiskMeasure.DELTA
            else _GIRR_VEGA_INTRA_CITATIONS
        ),
        inter_bucket_citation_ids=(
            _GIRR_DELTA_INTER_CITATIONS
            if risk_measure is SbmRiskMeasure.DELTA
            else _GIRR_VEGA_INTER_CITATIONS
        ),
    )


def _build_girr_delta_intra_bucket_correlation_matrix(
    ordered: Sequence[WeightedSensitivity],
    *,
    profile_id: str,
    tenor_by_id: Mapping[str, str],
    risk_factor_by_id: Mapping[str, str],
) -> npt.NDArray[np.float64]:
    size = len(ordered)
    matrix = np.eye(size, dtype=np.float64)
    for row_index, sensitivity_a in enumerate(ordered):
        for col_index in range(row_index, size):
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


def _build_girr_vega_intra_bucket_correlation_matrix(
    ordered: Sequence[WeightedSensitivity],
    *,
    profile_id: str,
    option_tenor_by_id: Mapping[str, str],
    tenor_by_id: Mapping[str, str],
) -> npt.NDArray[np.float64]:
    size = len(ordered)
    matrix = np.eye(size, dtype=np.float64)
    for row_index, sensitivity_a in enumerate(ordered):
        for col_index in range(row_index, size):
            sensitivity_b = ordered[col_index]
            correlation, _ = girr_vega_intra_bucket_correlation(
                profile_id,
                option_tenor1=option_tenor_by_id[sensitivity_a.sensitivity_id],
                option_tenor2=option_tenor_by_id[sensitivity_b.sensitivity_id],
                tenor1=tenor_by_id[sensitivity_a.sensitivity_id],
                tenor2=tenor_by_id[sensitivity_b.sensitivity_id],
            )
            matrix[row_index, col_index] = correlation
            matrix[col_index, row_index] = correlation
    return matrix


def _build_inter_bucket_correlation_map(
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


def _collect_citation_ids(
    risk_class_capitals: Sequence[RiskClassCapital],
    *,
    portfolio_scenario_selection: SbmBranchMetadata | None = None,
) -> tuple[str, ...]:
    citation_ids: list[str] = []
    seen: set[str] = set()
    for risk_class_capital in risk_class_capitals:
        for citation_id in risk_class_capital.citation_ids:
            _append_citation(citation_ids, seen, citation_id)
        for bucket in risk_class_capital.buckets:
            for citation_id in bucket.citation_ids:
                _append_citation(citation_ids, seen, citation_id)
            for weighted in bucket.weighted_sensitivities:
                for citation_id in weighted.citation_ids:
                    _append_citation(citation_ids, seen, citation_id)
        for detail in risk_class_capital.scenario_details:
            for citation_id in detail.citation_ids:
                _append_citation(citation_ids, seen, citation_id)
            for intra_bucket in detail.intra_buckets:
                for citation_id in intra_bucket.citation_ids:
                    _append_citation(citation_ids, seen, citation_id)
        if risk_class_capital.scenario_selection is not None:
            for citation_id in risk_class_capital.scenario_selection.citation_ids:
                _append_citation(citation_ids, seen, citation_id)
    if portfolio_scenario_selection is not None:
        for citation_id in portfolio_scenario_selection.citation_ids:
            _append_citation(citation_ids, seen, citation_id)
    return tuple(citation_ids)


def _append_citation(citation_ids: list[str], seen: set[str], citation_id: str) -> None:
    if citation_id not in seen:
        citation_ids.append(citation_id)
        seen.add(citation_id)


def _ensure_phase1_supported(sensitivities: Sequence[SbmSensitivity]) -> None:
    if not sensitivities:
        raise SbmInputError("sensitivities must not be empty", field="sensitivities")
    for sensitivity in sensitivities:
        path = (sensitivity.risk_class, sensitivity.risk_measure)
        if path not in _PHASE1_SUPPORTED_PATHS:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm phase-1 capital supports GIRR delta/vega, FX delta, "
                "equity delta, commodity delta, and CSR non-securitisation delta inputs; "
                f"received risk_class={sensitivity.risk_class.value}, "
                f"risk_measure={sensitivity.risk_measure.value}"
            )


def _ordered_supported_paths(
    sensitivities: Sequence[SbmSensitivity],
) -> tuple[tuple[SbmRiskClass, SbmRiskMeasure], ...]:
    present = {
        (item.risk_class, item.risk_measure)
        for item in sensitivities
        if (item.risk_class, item.risk_measure) in _PHASE1_SUPPORTED_PATHS
    }
    ordering = (
        (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA),
        (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA),
        (SbmRiskClass.FX, SbmRiskMeasure.DELTA),
        (SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA),
        (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA),
        (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA),
    )
    return tuple(path for path in ordering if path in present)


def _coerce_sensitivities(sensitivities: object) -> tuple[SbmSensitivity, ...]:
    from frtb_sbm.validation import validate_sbm_sensitivities

    return validate_sbm_sensitivities(sensitivities)


def _profile_warnings(profile_id: str) -> tuple[str, ...]:
    del profile_id
    return ()


__all__ = ["calculate_sbm_capital"]
