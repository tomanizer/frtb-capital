"""
Public SBM capital calculation for supported SBM phase-1 delta/vega/curvature inputs.

Regulatory traceability:
    Basel MAR21.4-MAR21.7 — delta aggregation and scenario selection.
    Basel MAR21.14, MAR21.86-MAR21.89 — FX delta buckets, weights, correlations.
    Basel MAR21.90-MAR21.95 — vega buckets, weights, and correlations.
    U.S. NPR 2.0 section V.A.7.a steps three through six.
    SBM-WS-001, SBM-AGG-001, SBM-AGG-002, SBM-FUNC-014, SBM-FUNC-015,
    SBM-FUNC-016, SBM-FUNC-017, SBM-FUNC-018.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass, replace
from typing import Any, TypedDict

import numpy as np
from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm.aggregation import (
    select_portfolio_correlation_scenario,
)
from frtb_sbm.assembly.hashes import input_hash_for_validated_sensitivities
from frtb_sbm.audit import validate_sbm_result_reconciliation
from frtb_sbm.batch import SbmSensitivityBatch
from frtb_sbm.curvature import (
    calculate_curvature_risk_class_capital,
    calculate_curvature_risk_class_capital_from_batch,
)
from frtb_sbm.data_models import (
    RiskClassCapital,
    SbmBranchMetadata,
    SbmCalculationContext,
    SbmCapitalResult,
    SbmPairwiseEvidenceMode,
    SbmReconciliationMetadata,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmRuleProfile,
    SbmRunContextSummary,
    SbmRunControls,
    SbmSensitivity,
)
from frtb_sbm.reference_citations_eu_crr3 import translate_basel_citation_ids_to_eu
from frtb_sbm.regimes import get_sbm_rule_profile
from frtb_sbm.registry import SBM_BATCH_PATH_ORDER, sbm_batch_spec
from frtb_sbm.risk_classes.commodity import (
    calculate_commodity_delta_risk_class_capital,
    calculate_commodity_delta_risk_class_capital_from_batch,
)
from frtb_sbm.risk_classes.csr_nonsec import (
    calculate_csr_nonsec_delta_risk_class_capital,
    calculate_csr_nonsec_delta_risk_class_capital_from_batch,
)
from frtb_sbm.risk_classes.csr_sec_ctp import (
    calculate_csr_sec_ctp_delta_risk_class_capital,
    calculate_csr_sec_ctp_delta_risk_class_capital_from_batch,
)
from frtb_sbm.risk_classes.csr_sec_nonctp import (
    calculate_csr_sec_nonctp_delta_risk_class_capital,
    calculate_csr_sec_nonctp_delta_risk_class_capital_from_batch,
)
from frtb_sbm.risk_classes.equity import (
    calculate_equity_delta_risk_class_capital,
    calculate_equity_delta_risk_class_capital_from_batch,
)
from frtb_sbm.risk_classes.fx import (
    calculate_fx_delta_risk_class_capital,
    calculate_fx_delta_risk_class_capital_from_batch,
)
from frtb_sbm.risk_classes.girr import (
    _ensure_girr_delta_batch_run_supported,
    _ensure_girr_vega_batch_run_supported,
    calculate_girr_delta_risk_class_capital,
    calculate_girr_delta_risk_class_capital_from_batch,
    calculate_girr_vega_risk_class_capital,
    calculate_girr_vega_risk_class_capital_from_batch,
)
from frtb_sbm.risk_classes.vega import (
    calculate_non_girr_vega_risk_class_capital,
    calculate_non_girr_vega_risk_class_capital_from_batch,
)
from frtb_sbm.validation import (
    SbmInputError,
    ensure_sbm_capital_paths_supported,
    ensure_sbm_risk_class_measure_supported,
    ensure_sbm_run_supported,
    phase1_capital_supported_paths,
    validate_sbm_calculation_context,
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
    "SBM-FUNC-015",
    "SBM-FUNC-016",
    "SBM-CURV-001",
)

_PROFILE_PORTFOLIO_SCENARIO_CITATIONS = {
    SbmRegulatoryProfile.BASEL_MAR21.value: ("basel_mar21_7_scenario_selection",),
    SbmRegulatoryProfile.US_NPR_2_0.value: ("us_npr_91_fr_14952_va7a_correlation_scenarios",),
    SbmRegulatoryProfile.EU_CRR3.value: (
        translate_basel_citation_ids_to_eu(("basel_mar21_7_scenario_selection",))[0],
    ),
}
_SBM_CAPITAL_PATH_ORDER = SBM_BATCH_PATH_ORDER


class _PairwiseEvidenceKwargs(TypedDict):
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str
    pairwise_evidence_limit: int


def calculate_sbm_capital(
    sensitivities: object | None = None,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate supported SBM capital for Basel MAR21 delta, vega, and curvature.
    Parameters
    ----------
    sensitivities : object | None, optional
        See signature.
    context : SbmCalculationContext | None, optional
        See signature.

    Returns
    -------
    SbmCapitalResult
    """

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
    ensure_sbm_capital_paths_supported(context.profile_id, validated)
    run_controls = context.run_controls or SbmRunControls()

    risk_class_results: list[RiskClassCapital] = []
    for risk_class, risk_measure in _ordered_supported_paths(
        validated,
        profile_id=context.profile_id,
    ):
        measure_sensitivities = tuple(
            item
            for item in validated
            if item.risk_class is risk_class and item.risk_measure is risk_measure
        )
        if risk_measure is SbmRiskMeasure.CURVATURE:
            risk_class_results.append(
                calculate_curvature_risk_class_capital(
                    measure_sensitivities,
                    profile_id=rule_profile.profile_id,
                    reporting_currency=context.reporting_currency,
                    pairwise_evidence_mode=run_controls.pairwise_evidence_mode,
                    pairwise_evidence_limit=run_controls.pairwise_evidence_limit,
                )
            )
        elif risk_class is SbmRiskClass.GIRR and risk_measure is SbmRiskMeasure.DELTA:
            risk_class_results.append(
                calculate_girr_delta_risk_class_capital(
                    measure_sensitivities,
                    profile_id=rule_profile.profile_id,
                    reporting_currency=context.reporting_currency,
                    pairwise_evidence_mode=run_controls.pairwise_evidence_mode,
                    pairwise_evidence_limit=run_controls.pairwise_evidence_limit,
                )
            )
        elif risk_class is SbmRiskClass.GIRR and risk_measure is SbmRiskMeasure.VEGA:
            risk_class_results.append(
                calculate_girr_vega_risk_class_capital(
                    measure_sensitivities,
                    profile_id=rule_profile.profile_id,
                    pairwise_evidence_mode=run_controls.pairwise_evidence_mode,
                    pairwise_evidence_limit=run_controls.pairwise_evidence_limit,
                )
            )
        elif risk_measure is SbmRiskMeasure.VEGA:
            risk_class_results.append(
                calculate_non_girr_vega_risk_class_capital(
                    measure_sensitivities,
                    profile_id=rule_profile.profile_id,
                    pairwise_evidence_mode=run_controls.pairwise_evidence_mode,
                    pairwise_evidence_limit=run_controls.pairwise_evidence_limit,
                )
            )
        elif risk_class is SbmRiskClass.FX and risk_measure is SbmRiskMeasure.DELTA:
            risk_class_results.append(
                calculate_fx_delta_risk_class_capital(
                    measure_sensitivities,
                    profile_id=rule_profile.profile_id,
                    reporting_currency=context.reporting_currency,
                    pairwise_evidence_mode=run_controls.pairwise_evidence_mode,
                    pairwise_evidence_limit=run_controls.pairwise_evidence_limit,
                )
            )
        elif risk_class is SbmRiskClass.EQUITY and risk_measure is SbmRiskMeasure.DELTA:
            risk_class_results.append(
                calculate_equity_delta_risk_class_capital(
                    measure_sensitivities,
                    profile_id=rule_profile.profile_id,
                    pairwise_evidence_mode=run_controls.pairwise_evidence_mode,
                    pairwise_evidence_limit=run_controls.pairwise_evidence_limit,
                )
            )
        elif risk_class is SbmRiskClass.COMMODITY and risk_measure is SbmRiskMeasure.DELTA:
            risk_class_results.append(
                calculate_commodity_delta_risk_class_capital(
                    measure_sensitivities,
                    profile_id=rule_profile.profile_id,
                    pairwise_evidence_mode=run_controls.pairwise_evidence_mode,
                    pairwise_evidence_limit=run_controls.pairwise_evidence_limit,
                )
            )
        elif risk_class is SbmRiskClass.CSR_NONSEC and risk_measure is SbmRiskMeasure.DELTA:
            risk_class_results.append(
                calculate_csr_nonsec_delta_risk_class_capital(
                    measure_sensitivities,
                    profile_id=rule_profile.profile_id,
                    pairwise_evidence_mode=run_controls.pairwise_evidence_mode,
                    pairwise_evidence_limit=run_controls.pairwise_evidence_limit,
                )
            )
        elif risk_class is SbmRiskClass.CSR_SEC_NONCTP and risk_measure is SbmRiskMeasure.DELTA:
            risk_class_results.append(
                calculate_csr_sec_nonctp_delta_risk_class_capital(
                    measure_sensitivities,
                    profile_id=rule_profile.profile_id,
                    pairwise_evidence_mode=run_controls.pairwise_evidence_mode,
                    pairwise_evidence_limit=run_controls.pairwise_evidence_limit,
                )
            )
        elif risk_class is SbmRiskClass.CSR_SEC_CTP and risk_measure is SbmRiskMeasure.DELTA:
            risk_class_results.append(
                calculate_csr_sec_ctp_delta_risk_class_capital(
                    measure_sensitivities,
                    profile_id=rule_profile.profile_id,
                    pairwise_evidence_mode=run_controls.pairwise_evidence_mode,
                    pairwise_evidence_limit=run_controls.pairwise_evidence_limit,
                )
            )
        else:
            raise UnsupportedRegulatoryFeatureError(
                "frtb-sbm phase-1 capital does not support "
                f"risk_class={risk_class.value}, risk_measure={risk_measure.value}"
            )

    return _build_sbm_capital_result(
        risk_class_results,
        rule_profile=rule_profile,
        context=context,
        input_hash=input_hash_for_validated_sensitivities(validated),
        input_count=len(validated),
    )


def calculate_sbm_capital_from_batch(
    batch: SbmSensitivityBatch,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital for a pre-built batch via the path registry.

    Parameters
    ----------
    batch
        Homogeneous SBM sensitivity batch.
    context
        Calculation context for supported profile and scope validation.

    Returns
    -------
    SbmCapitalResult
    """

    if context is None:
        raise SbmInputError("calculation context is required", field="context")
    if not isinstance(context, SbmCalculationContext):
        raise SbmInputError(
            "calculation context must be SbmCalculationContext",
            field="context",
        )
    if not isinstance(batch, SbmSensitivityBatch):
        raise SbmInputError("batch must be SbmSensitivityBatch", field="batch")

    validate_sbm_calculation_context(context)
    rule_profile = get_sbm_rule_profile(context.profile_id)
    risk_class = _calculate_batch_risk_class_capital(batch, context=context)
    return _build_sbm_capital_result(
        (risk_class,),
        rule_profile=rule_profile,
        context=context,
        input_hash=batch.input_hash,
        input_count=batch.row_count,
        input_hash_algorithm=batch.input_hash_algorithm,
    )


def _calculate_batch_risk_class_capital(
    batch: SbmSensitivityBatch,
    *,
    context: SbmCalculationContext,
) -> RiskClassCapital:
    if not isinstance(batch, SbmSensitivityBatch):
        raise SbmInputError("batch must be SbmSensitivityBatch", field="batch")
    if batch.row_count == 0:
        raise SbmInputError("batch must not be empty", field="batch")

    risk_class = batch.risk_class
    risk_measure = batch.risk_measure
    ensure_sbm_risk_class_measure_supported(context.profile_id, risk_class, risk_measure)
    spec = sbm_batch_spec(risk_class, risk_measure)
    _ensure_batch_run_supported(context, batch, label=spec.label)

    rule_profile = get_sbm_rule_profile(context.profile_id)
    run_controls = context.run_controls or SbmRunControls()
    pairwise_kwargs: _PairwiseEvidenceKwargs = {
        "pairwise_evidence_mode": run_controls.pairwise_evidence_mode,
        "pairwise_evidence_limit": run_controls.pairwise_evidence_limit,
    }
    if risk_class is SbmRiskClass.GIRR and risk_measure is SbmRiskMeasure.DELTA:
        return calculate_girr_delta_risk_class_capital_from_batch(
            batch,
            profile_id=rule_profile.profile_id,
            reporting_currency=context.reporting_currency,
            **pairwise_kwargs,
        )
    if risk_class is SbmRiskClass.GIRR and risk_measure is SbmRiskMeasure.VEGA:
        return calculate_girr_vega_risk_class_capital_from_batch(
            batch,
            profile_id=rule_profile.profile_id,
            **pairwise_kwargs,
        )
    if risk_measure is SbmRiskMeasure.VEGA:
        return calculate_non_girr_vega_risk_class_capital_from_batch(
            batch,
            profile_id=rule_profile.profile_id,
            **pairwise_kwargs,
        )
    if risk_measure is SbmRiskMeasure.CURVATURE:
        return calculate_curvature_risk_class_capital_from_batch(
            batch,
            profile_id=rule_profile.profile_id,
            reporting_currency=context.reporting_currency,
            expected_risk_class=risk_class,
            **pairwise_kwargs,
        )
    if risk_class is SbmRiskClass.FX and risk_measure is SbmRiskMeasure.DELTA:
        return calculate_fx_delta_risk_class_capital_from_batch(
            batch,
            profile_id=rule_profile.profile_id,
            reporting_currency=context.reporting_currency,
            **pairwise_kwargs,
        )
    if risk_class is SbmRiskClass.EQUITY and risk_measure is SbmRiskMeasure.DELTA:
        return calculate_equity_delta_risk_class_capital_from_batch(
            batch,
            profile_id=rule_profile.profile_id,
            **pairwise_kwargs,
        )
    if risk_class is SbmRiskClass.COMMODITY and risk_measure is SbmRiskMeasure.DELTA:
        return calculate_commodity_delta_risk_class_capital_from_batch(
            batch,
            profile_id=rule_profile.profile_id,
            **pairwise_kwargs,
        )
    if risk_class is SbmRiskClass.CSR_NONSEC and risk_measure is SbmRiskMeasure.DELTA:
        return calculate_csr_nonsec_delta_risk_class_capital_from_batch(
            batch,
            profile_id=rule_profile.profile_id,
            **pairwise_kwargs,
        )
    if risk_class is SbmRiskClass.CSR_SEC_NONCTP and risk_measure is SbmRiskMeasure.DELTA:
        return calculate_csr_sec_nonctp_delta_risk_class_capital_from_batch(
            batch,
            profile_id=rule_profile.profile_id,
            **pairwise_kwargs,
        )
    if risk_class is SbmRiskClass.CSR_SEC_CTP and risk_measure is SbmRiskMeasure.DELTA:
        return calculate_csr_sec_ctp_delta_risk_class_capital_from_batch(
            batch,
            profile_id=rule_profile.profile_id,
            **pairwise_kwargs,
        )
    raise UnsupportedRegulatoryFeatureError(
        "frtb-sbm batch capital does not support "
        f"risk_class={risk_class.value}, risk_measure={risk_measure.value}"
    )


def _ensure_batch_run_supported(
    context: SbmCalculationContext,
    batch: SbmSensitivityBatch,
    *,
    label: str,
) -> None:
    risk_class = batch.risk_class
    risk_measure = batch.risk_measure
    if risk_class is SbmRiskClass.GIRR and risk_measure is SbmRiskMeasure.DELTA:
        _ensure_girr_delta_batch_run_supported(context, batch)
        return
    if risk_class is SbmRiskClass.GIRR and risk_measure is SbmRiskMeasure.VEGA:
        _ensure_girr_vega_batch_run_supported(context, batch)
        return
    if risk_measure is SbmRiskMeasure.DELTA:
        _ensure_delta_batch_run_supported(
            context,
            batch,
            expected_risk_class=risk_class,
            label=label,
        )
        return
    if risk_measure is SbmRiskMeasure.VEGA:
        _ensure_vega_batch_run_supported(
            context,
            batch,
            expected_risk_class=risk_class,
            label=label,
        )
        return
    if risk_measure is SbmRiskMeasure.CURVATURE:
        _ensure_curvature_batch_run_supported(
            context,
            batch,
            expected_risk_class=risk_class,
            label=label,
        )
        return

    raise UnsupportedRegulatoryFeatureError(
        "frtb-sbm batch capital does not support "
        f"risk_class={risk_class.value}, risk_measure={risk_measure.value}"
    )


def _ensure_delta_batch_run_supported(
    context: SbmCalculationContext,
    batch: SbmSensitivityBatch,
    *,
    expected_risk_class: SbmRiskClass,
    label: str,
) -> None:
    if batch.row_count == 0:
        raise SbmInputError(f"{label} batch must not be empty", field="batch")
    if batch.risk_class is not expected_risk_class:
        raise SbmInputError(
            f"{label} batch only accepts {expected_risk_class.value} sensitivities",
            field="risk_class",
        )
    if batch.risk_measure is not SbmRiskMeasure.DELTA:
        raise SbmInputError(
            f"{label} batch only accepts delta sensitivities",
            field="risk_measure",
        )
    scoped_desk_id = (context.desk_id or "").strip()
    scoped_legal_entity = (context.legal_entity or "").strip()
    if scoped_desk_id:
        mismatches = batch.desk_ids != scoped_desk_id
        if np.any(mismatches):
            row_index = int(np.flatnonzero(mismatches)[0])
            raise SbmInputError(
                f"desk_id {batch.desk_ids[row_index]} does not match "
                f"context desk_id {scoped_desk_id}",
                field="desk_id",
                sensitivity_id=batch.sensitivity_ids[row_index],
            )
    if scoped_legal_entity:
        mismatches = batch.legal_entities != scoped_legal_entity
        if np.any(mismatches):
            row_index = int(np.flatnonzero(mismatches)[0])
            raise SbmInputError(
                f"legal_entity {batch.legal_entities[row_index]} does not match "
                f"context legal_entity {scoped_legal_entity}",
                field="legal_entity",
                sensitivity_id=batch.sensitivity_ids[row_index],
            )


def _ensure_vega_batch_run_supported(
    context: SbmCalculationContext,
    batch: SbmSensitivityBatch,
    *,
    expected_risk_class: SbmRiskClass,
    label: str,
) -> None:
    if batch.row_count == 0:
        raise SbmInputError(f"{label} batch must not be empty", field="batch")
    if batch.risk_class is not expected_risk_class:
        raise SbmInputError(
            f"{label} batch only accepts {expected_risk_class.value} sensitivities",
            field="risk_class",
        )
    if batch.risk_measure is not SbmRiskMeasure.VEGA:
        raise SbmInputError(
            f"{label} batch only accepts vega sensitivities",
            field="risk_measure",
        )
    scoped_desk_id = (context.desk_id or "").strip()
    scoped_legal_entity = (context.legal_entity or "").strip()
    if scoped_desk_id:
        mismatches = batch.desk_ids != scoped_desk_id
        if np.any(mismatches):
            row_index = int(np.flatnonzero(mismatches)[0])
            raise SbmInputError(
                f"desk_id {batch.desk_ids[row_index]} does not match "
                f"context desk_id {scoped_desk_id}",
                field="desk_id",
                sensitivity_id=batch.sensitivity_ids[row_index],
            )
    if scoped_legal_entity:
        mismatches = batch.legal_entities != scoped_legal_entity
        if np.any(mismatches):
            row_index = int(np.flatnonzero(mismatches)[0])
            raise SbmInputError(
                f"legal_entity {batch.legal_entities[row_index]} does not match "
                f"context legal_entity {scoped_legal_entity}",
                field="legal_entity",
                sensitivity_id=batch.sensitivity_ids[row_index],
            )


def _ensure_curvature_batch_run_supported(
    context: SbmCalculationContext,
    batch: SbmSensitivityBatch,
    *,
    expected_risk_class: SbmRiskClass,
    label: str,
) -> None:
    if batch.row_count == 0:
        raise SbmInputError(f"{label} batch must not be empty", field="batch")
    if batch.risk_class is not expected_risk_class:
        raise SbmInputError(
            f"{label} batch only accepts {expected_risk_class.value} sensitivities",
            field="risk_class",
        )
    if batch.risk_measure is not SbmRiskMeasure.CURVATURE:
        raise SbmInputError(
            f"{label} batch only accepts curvature sensitivities",
            field="risk_measure",
        )
    scoped_desk_id = (context.desk_id or "").strip()
    scoped_legal_entity = (context.legal_entity or "").strip()
    if scoped_desk_id:
        mismatches = batch.desk_ids != scoped_desk_id
        if np.any(mismatches):
            row_index = int(np.flatnonzero(mismatches)[0])
            raise SbmInputError(
                f"desk_id {batch.desk_ids[row_index]} does not match "
                f"context desk_id {scoped_desk_id}",
                field="desk_id",
                sensitivity_id=batch.sensitivity_ids[row_index],
            )
    if scoped_legal_entity:
        mismatches = batch.legal_entities != scoped_legal_entity
        if np.any(mismatches):
            row_index = int(np.flatnonzero(mismatches)[0])
            raise SbmInputError(
                f"legal_entity {batch.legal_entities[row_index]} does not match "
                f"context legal_entity {scoped_legal_entity}",
                field="legal_entity",
                sensitivity_id=batch.sensitivity_ids[row_index],
            )


def _build_sbm_capital_result(
    risk_class_results: Sequence[RiskClassCapital],
    *,
    rule_profile: SbmRuleProfile,
    context: SbmCalculationContext,
    input_hash: str,
    input_count: int,
    input_hash_algorithm: str = "json-row-v1",
) -> SbmCapitalResult:
    (
        aligned_risk_classes,
        total_capital,
        portfolio_scenario_totals,
        selected_portfolio_scenario,
        portfolio_scenario_selection,
    ) = select_portfolio_correlation_scenario(
        risk_class_results,
        citation_ids=_portfolio_scenario_citations(rule_profile.profile_id),
    )
    if rule_profile.profile_id == SbmRegulatoryProfile.EU_CRR3.value:
        aligned_risk_classes = _translate_eu_crr3_result_citations(aligned_risk_classes)
        if portfolio_scenario_selection is not None:
            portfolio_scenario_selection = _translate_eu_crr3_result_citations(
                portfolio_scenario_selection
            )
    citation_ids = _collect_citation_ids(
        aligned_risk_classes,
        portfolio_scenario_selection=portfolio_scenario_selection,
    )
    result = SbmCapitalResult(
        total_capital=total_capital,
        risk_classes=aligned_risk_classes,
        profile_id=rule_profile.profile_id,
        profile_hash=rule_profile.content_hash,
        input_hash=input_hash,
        input_hash_algorithm=input_hash_algorithm,
        warnings=_profile_warnings(rule_profile.profile_id),
        reconciliation=SbmReconciliationMetadata(
            input_count=input_count,
            rejected_input_count=0,
            requirement_ids=_SBM_REQUIREMENT_IDS,
            citation_ids=citation_ids,
        ),
        run_context=SbmRunContextSummary(
            run_id=context.run_id,
            calculation_date=context.calculation_date,
            base_currency=context.base_currency,
            reporting_currency=context.reporting_currency,
            calculation_scope=context.calculation_scope,
        ),
        portfolio_scenario_totals=portfolio_scenario_totals,
        selected_portfolio_scenario=selected_portfolio_scenario,
        portfolio_scenario_selection=portfolio_scenario_selection,
    )
    validate_sbm_result_reconciliation(result)
    return result


def _portfolio_scenario_citations(profile_id: str) -> tuple[str, ...]:
    try:
        return _PROFILE_PORTFOLIO_SCENARIO_CITATIONS[profile_id]
    except KeyError as exc:
        raise UnsupportedRegulatoryFeatureError(
            f"Portfolio scenario citations are unsupported for profile={profile_id}"
        ) from exc


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


def _translate_eu_crr3_result_citations(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        changes: dict[str, object] = {}
        for field in fields(value):
            field_value = getattr(value, field.name)
            if field.name == "citation_ids":
                if isinstance(field_value, (tuple, list)):
                    try:
                        translated = translate_basel_citation_ids_to_eu(field_value)
                    except KeyError as exc:
                        raise UnsupportedRegulatoryFeatureError(
                            "EU_CRR3 result contains an unsupported Basel citation id: "
                            f"{field_value!r}"
                        ) from exc
                else:
                    translated = field_value
            else:
                if isinstance(field_value, (tuple, list)):
                    translated = _translate_eu_crr3_result_citations_in_collection(field_value)
                elif is_dataclass(field_value):
                    translated = _translate_eu_crr3_result_citations(field_value)
                elif isinstance(field_value, Mapping):
                    translated = _translate_eu_crr3_result_citations_in_mapping(field_value)
                else:
                    translated = field_value
            if translated != field_value:
                changes[field.name] = translated
        if not changes:
            return value
        return replace(value, **changes)
    return value


def _translate_eu_crr3_result_citations_in_collection(values: Sequence[Any]) -> Sequence[Any]:
    if not values:
        return values

    first = values[0]
    if not (is_dataclass(first) or isinstance(first, (tuple, list, Mapping))):
        return values

    translated = []
    changed = False
    for item in values:
        if is_dataclass(item) or isinstance(item, (tuple, list, Mapping)):
            translated_item = _translate_eu_crr3_result_citations(item)
            changed = changed or (translated_item is not item)
            translated.append(translated_item)
        else:
            translated.append(item)
    if not changed:
        return values
    if isinstance(values, tuple):
        return tuple(translated)
    return translated


def _translate_eu_crr3_result_citations_in_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    translated = {}
    changed = False
    for key, item in value.items():
        if is_dataclass(item) or isinstance(item, (tuple, list, Mapping)):
            translated_item = _translate_eu_crr3_result_citations(item)
            changed = changed or (translated_item is not item)
            translated[key] = translated_item
        else:
            translated[key] = item
    if not changed:
        return dict(value)
    return translated


def _ordered_supported_paths(
    sensitivities: Sequence[SbmSensitivity],
    *,
    profile_id: str,
) -> tuple[tuple[SbmRiskClass, SbmRiskMeasure], ...]:
    supported = phase1_capital_supported_paths(profile_id)
    present = {
        (item.risk_class, item.risk_measure)
        for item in sensitivities
        if (item.risk_class, item.risk_measure) in supported
    }
    ordered = tuple(path for path in _SBM_CAPITAL_PATH_ORDER if path in present)
    remaining = tuple(
        sorted(
            present - set(_SBM_CAPITAL_PATH_ORDER),
            key=lambda p: (p[0].value, p[1].value),
        )
    )
    return ordered + remaining


def _coerce_sensitivities(sensitivities: object) -> tuple[SbmSensitivity, ...]:
    from frtb_sbm.validation import validate_sbm_sensitivities

    return validate_sbm_sensitivities(sensitivities)


def _profile_warnings(profile_id: str) -> tuple[str, ...]:
    del profile_id
    return ()


from frtb_sbm.kernel.portfolio import calculate_sbm_portfolio_capital_from_batches  # noqa: E402

__all__ = [
    "calculate_sbm_capital",
    "calculate_sbm_capital_from_batch",
    "calculate_sbm_portfolio_capital_from_batches",
]
