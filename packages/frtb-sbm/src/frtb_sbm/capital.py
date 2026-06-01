"""
Public SBM capital calculation for supported SBM phase-1 delta/vega inputs.

Regulatory traceability:
    Basel MAR21.4-MAR21.7 — delta aggregation and scenario selection.
    Basel MAR21.14, MAR21.86-MAR21.89 — FX delta buckets, weights, correlations.
    Basel MAR21.90-MAR21.95 — GIRR vega buckets and inter-bucket gamma.
    U.S. NPR 2.0 section V.A.7.a steps three through six.
    SBM-WS-001, SBM-AGG-001, SBM-AGG-002, SBM-FUNC-014, SBM-FUNC-015,
    SBM-FUNC-016, SBM-FUNC-017, SBM-FUNC-018.
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
from frtb_sbm.batch import (
    SbmSensitivityBatch,
    build_girr_delta_batch_from_sensitivities,
    build_girr_vega_batch_from_sensitivities,
)
from frtb_sbm.data_models import (
    DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
    RiskClassCapital,
    SbmBranchMetadata,
    SbmCalculationContext,
    SbmCapitalResult,
    SbmPairwiseEvidenceMode,
    SbmReconciliationMetadata,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmRuleProfile,
    SbmRunContextSummary,
    SbmRunControls,
    SbmSensitivity,
    WeightedSensitivity,
)
from frtb_sbm.factor_grid import net_girr_delta_sensitivity_batch
from frtb_sbm.reference_data import (
    GIRR_DELTA_INTRA_BUCKET_CONSTANT,
    GIRR_DIFFERENT_CURVE_CORRELATION,
    GIRR_INFLATION_DIFFERENT_TENOR_CORRELATION,
    GIRR_INFLATION_SAME_TENOR_CORRELATION,
    GIRR_INTRA_BUCKET_CORRELATION_FLOOR,
    GIRR_SAME_CURVE_CORRELATION,
    girr_inter_bucket_correlation,
    girr_tenor_definition,
    girr_vega_intra_bucket_correlation,
)
from frtb_sbm.regimes import get_sbm_rule_profile
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
from frtb_sbm.validation import (
    SbmInputError,
    ensure_sbm_capital_paths_supported,
    ensure_sbm_risk_class_measure_supported,
    ensure_sbm_run_supported,
    normalise_currency_code,
    phase1_capital_supported_paths,
    validate_sbm_calculation_context,
)
from frtb_sbm.weighted_sensitivity import (
    weight_girr_vega_sensitivity_batch,
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
        if risk_class is SbmRiskClass.GIRR and risk_measure is SbmRiskMeasure.DELTA:
            risk_class_results.append(
                _calculate_girr_delta_risk_class_capital(
                    measure_sensitivities,
                    profile_id=rule_profile.profile_id,
                    reporting_currency=context.reporting_currency,
                    pairwise_evidence_mode=run_controls.pairwise_evidence_mode,
                    pairwise_evidence_limit=run_controls.pairwise_evidence_limit,
                )
            )
        elif risk_class is SbmRiskClass.GIRR and risk_measure is SbmRiskMeasure.VEGA:
            risk_class_results.append(
                _calculate_girr_vega_risk_class_capital(
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
        input_hash=_input_hash_for_validated_sensitivities(validated),
        input_count=len(validated),
    )


def calculate_sbm_capital_from_girr_delta_batch(
    batch: SbmSensitivityBatch,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital for a pre-built GIRR delta sensitivity batch."""

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
    ensure_sbm_risk_class_measure_supported(
        context.profile_id,
        SbmRiskClass.GIRR,
        SbmRiskMeasure.DELTA,
    )
    _ensure_girr_delta_batch_run_supported(context, batch)
    rule_profile = get_sbm_rule_profile(context.profile_id)
    run_controls = context.run_controls or SbmRunControls()
    risk_class = _calculate_girr_delta_risk_class_capital_from_batch(
        batch,
        profile_id=rule_profile.profile_id,
        reporting_currency=context.reporting_currency,
        pairwise_evidence_mode=run_controls.pairwise_evidence_mode,
        pairwise_evidence_limit=run_controls.pairwise_evidence_limit,
    )
    return _build_sbm_capital_result(
        (risk_class,),
        rule_profile=rule_profile,
        context=context,
        input_hash=batch.input_hash,
        input_count=batch.row_count,
    )


def calculate_sbm_capital_from_girr_vega_batch(
    batch: SbmSensitivityBatch,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital for a pre-built GIRR vega sensitivity batch."""

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
    ensure_sbm_risk_class_measure_supported(
        context.profile_id,
        SbmRiskClass.GIRR,
        SbmRiskMeasure.VEGA,
    )
    _ensure_girr_vega_batch_run_supported(context, batch)
    rule_profile = get_sbm_rule_profile(context.profile_id)
    run_controls = context.run_controls or SbmRunControls()
    risk_class = _calculate_girr_vega_risk_class_capital_from_batch(
        batch,
        profile_id=rule_profile.profile_id,
        pairwise_evidence_mode=run_controls.pairwise_evidence_mode,
        pairwise_evidence_limit=run_controls.pairwise_evidence_limit,
    )
    return _build_sbm_capital_result(
        (risk_class,),
        rule_profile=rule_profile,
        context=context,
        input_hash=batch.input_hash,
        input_count=batch.row_count,
    )


def calculate_sbm_capital_from_fx_delta_batch(
    batch: SbmSensitivityBatch,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital for a pre-built FX delta sensitivity batch."""

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
    ensure_sbm_risk_class_measure_supported(
        context.profile_id,
        SbmRiskClass.FX,
        SbmRiskMeasure.DELTA,
    )
    _ensure_delta_batch_run_supported(
        context,
        batch,
        expected_risk_class=SbmRiskClass.FX,
        label="FX delta",
    )
    rule_profile = get_sbm_rule_profile(context.profile_id)
    run_controls = context.run_controls or SbmRunControls()
    risk_class = calculate_fx_delta_risk_class_capital_from_batch(
        batch,
        profile_id=rule_profile.profile_id,
        reporting_currency=context.reporting_currency,
        pairwise_evidence_mode=run_controls.pairwise_evidence_mode,
        pairwise_evidence_limit=run_controls.pairwise_evidence_limit,
    )
    return _build_sbm_capital_result(
        (risk_class,),
        rule_profile=rule_profile,
        context=context,
        input_hash=batch.input_hash,
        input_count=batch.row_count,
    )


def calculate_sbm_capital_from_equity_delta_batch(
    batch: SbmSensitivityBatch,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital for a pre-built equity delta sensitivity batch."""

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
    ensure_sbm_risk_class_measure_supported(
        context.profile_id,
        SbmRiskClass.EQUITY,
        SbmRiskMeasure.DELTA,
    )
    _ensure_delta_batch_run_supported(
        context,
        batch,
        expected_risk_class=SbmRiskClass.EQUITY,
        label="equity delta",
    )
    rule_profile = get_sbm_rule_profile(context.profile_id)
    run_controls = context.run_controls or SbmRunControls()
    risk_class = calculate_equity_delta_risk_class_capital_from_batch(
        batch,
        profile_id=rule_profile.profile_id,
        pairwise_evidence_mode=run_controls.pairwise_evidence_mode,
        pairwise_evidence_limit=run_controls.pairwise_evidence_limit,
    )
    return _build_sbm_capital_result(
        (risk_class,),
        rule_profile=rule_profile,
        context=context,
        input_hash=batch.input_hash,
        input_count=batch.row_count,
    )


def calculate_sbm_capital_from_commodity_delta_batch(
    batch: SbmSensitivityBatch,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital for a pre-built commodity delta sensitivity batch."""

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
    ensure_sbm_risk_class_measure_supported(
        context.profile_id,
        SbmRiskClass.COMMODITY,
        SbmRiskMeasure.DELTA,
    )
    _ensure_delta_batch_run_supported(
        context,
        batch,
        expected_risk_class=SbmRiskClass.COMMODITY,
        label="commodity delta",
    )
    rule_profile = get_sbm_rule_profile(context.profile_id)
    run_controls = context.run_controls or SbmRunControls()
    risk_class = calculate_commodity_delta_risk_class_capital_from_batch(
        batch,
        profile_id=rule_profile.profile_id,
        pairwise_evidence_mode=run_controls.pairwise_evidence_mode,
        pairwise_evidence_limit=run_controls.pairwise_evidence_limit,
    )
    return _build_sbm_capital_result(
        (risk_class,),
        rule_profile=rule_profile,
        context=context,
        input_hash=batch.input_hash,
        input_count=batch.row_count,
    )


def calculate_sbm_capital_from_csr_nonsec_delta_batch(
    batch: SbmSensitivityBatch,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital for a pre-built CSR non-securitisation delta batch."""

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
    ensure_sbm_risk_class_measure_supported(
        context.profile_id,
        SbmRiskClass.CSR_NONSEC,
        SbmRiskMeasure.DELTA,
    )
    _ensure_delta_batch_run_supported(
        context,
        batch,
        expected_risk_class=SbmRiskClass.CSR_NONSEC,
        label="CSR non-securitisation delta",
    )
    rule_profile = get_sbm_rule_profile(context.profile_id)
    run_controls = context.run_controls or SbmRunControls()
    risk_class = calculate_csr_nonsec_delta_risk_class_capital_from_batch(
        batch,
        profile_id=rule_profile.profile_id,
        pairwise_evidence_mode=run_controls.pairwise_evidence_mode,
        pairwise_evidence_limit=run_controls.pairwise_evidence_limit,
    )
    return _build_sbm_capital_result(
        (risk_class,),
        rule_profile=rule_profile,
        context=context,
        input_hash=batch.input_hash,
        input_count=batch.row_count,
    )


def calculate_sbm_capital_from_csr_sec_nonctp_delta_batch(
    batch: SbmSensitivityBatch,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital for a pre-built CSR securitisation non-CTP delta batch."""

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
    ensure_sbm_risk_class_measure_supported(
        context.profile_id,
        SbmRiskClass.CSR_SEC_NONCTP,
        SbmRiskMeasure.DELTA,
    )
    _ensure_delta_batch_run_supported(
        context,
        batch,
        expected_risk_class=SbmRiskClass.CSR_SEC_NONCTP,
        label="CSR securitisation non-CTP delta",
    )
    rule_profile = get_sbm_rule_profile(context.profile_id)
    run_controls = context.run_controls or SbmRunControls()
    risk_class = calculate_csr_sec_nonctp_delta_risk_class_capital_from_batch(
        batch,
        profile_id=rule_profile.profile_id,
        pairwise_evidence_mode=run_controls.pairwise_evidence_mode,
        pairwise_evidence_limit=run_controls.pairwise_evidence_limit,
    )
    return _build_sbm_capital_result(
        (risk_class,),
        rule_profile=rule_profile,
        context=context,
        input_hash=batch.input_hash,
        input_count=batch.row_count,
    )


def calculate_sbm_capital_from_csr_sec_ctp_delta_batch(
    batch: SbmSensitivityBatch,
    *,
    context: SbmCalculationContext | None = None,
) -> SbmCapitalResult:
    """Calculate SBM capital for a pre-built CSR securitisation CTP delta batch."""

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
    ensure_sbm_risk_class_measure_supported(
        context.profile_id,
        SbmRiskClass.CSR_SEC_CTP,
        SbmRiskMeasure.DELTA,
    )
    _ensure_delta_batch_run_supported(
        context,
        batch,
        expected_risk_class=SbmRiskClass.CSR_SEC_CTP,
        label="CSR securitisation CTP delta",
    )
    rule_profile = get_sbm_rule_profile(context.profile_id)
    run_controls = context.run_controls or SbmRunControls()
    risk_class = calculate_csr_sec_ctp_delta_risk_class_capital_from_batch(
        batch,
        profile_id=rule_profile.profile_id,
        pairwise_evidence_mode=run_controls.pairwise_evidence_mode,
        pairwise_evidence_limit=run_controls.pairwise_evidence_limit,
    )
    return _build_sbm_capital_result(
        (risk_class,),
        rule_profile=rule_profile,
        context=context,
        input_hash=batch.input_hash,
        input_count=batch.row_count,
    )


def _calculate_girr_delta_risk_class_capital(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
    reporting_currency: str,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    batch = build_girr_delta_batch_from_sensitivities(sensitivities)
    return _calculate_girr_delta_risk_class_capital_from_batch(
        batch,
        profile_id=profile_id,
        reporting_currency=reporting_currency,
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def _calculate_girr_delta_risk_class_capital_from_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
    reporting_currency: str,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    factor_grid = net_girr_delta_sensitivity_batch(
        batch,
        profile_id=profile_id,
        reporting_currency=reporting_currency,
    )
    return _aggregate_girr_measure_capital(
        factor_grid.weighted_sensitivities,
        profile_id=profile_id,
        risk_measure=SbmRiskMeasure.DELTA,
        tenor_by_id=factor_grid.tenor_by_id,
        risk_factor_by_id=factor_grid.risk_factor_by_id,
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def _ensure_girr_delta_batch_run_supported(
    context: SbmCalculationContext,
    batch: SbmSensitivityBatch,
) -> None:
    if batch.row_count == 0:
        raise SbmInputError("GIRR delta batch must not be empty", field="batch")
    normalise_currency_code(context.reporting_currency, field="reporting_currency")
    scoped_desk_id = (context.desk_id or "").strip()
    scoped_legal_entity = (context.legal_entity or "").strip()
    for row_index in range(batch.row_count):
        sensitivity_id = batch.sensitivity_ids[row_index]
        if scoped_desk_id and batch.desk_ids[row_index] != scoped_desk_id:
            raise SbmInputError(
                f"desk_id {batch.desk_ids[row_index]} does not match "
                f"context desk_id {scoped_desk_id}",
                field="desk_id",
                sensitivity_id=sensitivity_id,
            )
        if scoped_legal_entity and batch.legal_entities[row_index] != scoped_legal_entity:
            raise SbmInputError(
                f"legal_entity {batch.legal_entities[row_index]} does not match "
                f"context legal_entity {scoped_legal_entity}",
                field="legal_entity",
                sensitivity_id=sensitivity_id,
            )


def _ensure_girr_vega_batch_run_supported(
    context: SbmCalculationContext,
    batch: SbmSensitivityBatch,
) -> None:
    if batch.row_count == 0:
        raise SbmInputError("GIRR vega batch must not be empty", field="batch")
    if batch.risk_class is not SbmRiskClass.GIRR:
        raise SbmInputError(
            "GIRR vega batch only accepts GIRR sensitivities",
            field="risk_class",
        )
    if batch.risk_measure is not SbmRiskMeasure.VEGA:
        raise SbmInputError(
            "GIRR vega batch only accepts vega sensitivities",
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


def _build_sbm_capital_result(
    risk_class_results: Sequence[RiskClassCapital],
    *,
    rule_profile: SbmRuleProfile,
    context: SbmCalculationContext,
    input_hash: str,
    input_count: int,
) -> SbmCapitalResult:
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
        input_hash=input_hash,
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
        ),
        portfolio_scenario_totals=portfolio_scenario_totals,
        selected_portfolio_scenario=selected_portfolio_scenario,
        portfolio_scenario_selection=portfolio_scenario_selection,
    )
    validate_sbm_result_reconciliation(result)
    return result


def _calculate_girr_vega_risk_class_capital(
    sensitivities: tuple[SbmSensitivity, ...],
    *,
    profile_id: str,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    batch = build_girr_vega_batch_from_sensitivities(sensitivities)
    return _calculate_girr_vega_risk_class_capital_from_batch(
        batch,
        profile_id=profile_id,
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def _calculate_girr_vega_risk_class_capital_from_batch(
    batch: SbmSensitivityBatch,
    *,
    profile_id: str,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
) -> RiskClassCapital:
    weighted = weight_girr_vega_sensitivity_batch(
        batch,
        profile_id=profile_id,
    )
    option_tenor_by_id = _batch_optional_text_by_id(batch, batch.option_tenors, "option_tenor")
    tenor_by_id = _batch_text_by_id(batch, batch.tenors, "tenor")
    return _aggregate_girr_measure_capital(
        weighted,
        profile_id=profile_id,
        risk_measure=SbmRiskMeasure.VEGA,
        tenor_by_id=tenor_by_id,
        option_tenor_by_id=option_tenor_by_id,
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def _batch_text_by_id(
    batch: SbmSensitivityBatch,
    values: npt.NDArray[np.object_],
    _field: str,
) -> Mapping[str, str]:
    return {
        str(batch.sensitivity_ids[row_index]): str(values[row_index])
        for row_index in range(batch.row_count)
    }


def _batch_optional_text_by_id(
    batch: SbmSensitivityBatch,
    values: npt.NDArray[np.object_] | None,
    field: str,
) -> Mapping[str, str]:
    if values is None:
        raise SbmInputError(f"{field} is required", field=field)
    return _batch_text_by_id(batch, values, field)


def _aggregate_girr_measure_capital(
    weighted: tuple[WeightedSensitivity, ...],
    *,
    profile_id: str,
    risk_measure: SbmRiskMeasure,
    tenor_by_id: Mapping[str, str],
    risk_factor_by_id: Mapping[str, str] | None = None,
    option_tenor_by_id: Mapping[str, str] | None = None,
    pairwise_evidence_mode: SbmPairwiseEvidenceMode | str = SbmPairwiseEvidenceMode.AUTO,
    pairwise_evidence_limit: int = DEFAULT_PAIRWISE_EVIDENCE_LIMIT,
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
        pairwise_evidence_mode=pairwise_evidence_mode,
        pairwise_evidence_limit=pairwise_evidence_limit,
    )


def _build_girr_delta_intra_bucket_correlation_matrix(
    ordered: Sequence[WeightedSensitivity],
    *,
    profile_id: str,
    tenor_by_id: Mapping[str, str],
    risk_factor_by_id: Mapping[str, str],
) -> npt.NDArray[np.float64]:
    tenors = _girr_delta_tenor_array(ordered, tenor_by_id=tenor_by_id)
    risk_factors = _girr_delta_risk_factor_array(ordered, risk_factor_by_id=risk_factor_by_id)
    maturities = _girr_delta_maturity_array(tenors, profile_id=profile_id)

    same_curve = risk_factors[:, np.newaxis] == risk_factors[np.newaxis, :]
    minimum_tenor = np.minimum(maturities[:, np.newaxis], maturities[np.newaxis, :])
    tenor_difference = np.abs(maturities[:, np.newaxis] - maturities[np.newaxis, :])
    with np.errstate(divide="ignore", invalid="ignore"):
        tenor_correlation = np.exp(
            -GIRR_DELTA_INTRA_BUCKET_CONSTANT * tenor_difference / minimum_tenor
        )
    tenor_correlation = np.where(minimum_tenor <= 0.0, 1.0, tenor_correlation)
    tenor_correlation = np.maximum(tenor_correlation, GIRR_INTRA_BUCKET_CORRELATION_FLOOR)
    curve_correlation = np.where(
        same_curve,
        GIRR_SAME_CURVE_CORRELATION,
        GIRR_DIFFERENT_CURVE_CORRELATION,
    )
    matrix = curve_correlation * tenor_correlation

    xccy = tenors == "XCCY"
    xccy_any = xccy[:, np.newaxis] | xccy[np.newaxis, :]
    if np.any(xccy_any):
        xccy_both = xccy[:, np.newaxis] & xccy[np.newaxis, :]
        matrix = np.where(xccy_any, np.where(xccy_both, GIRR_SAME_CURVE_CORRELATION, 0.0), matrix)

    inflation = tenors == "INFL"
    inflation_any = inflation[:, np.newaxis] | inflation[np.newaxis, :]
    if np.any(inflation_any):
        inflation_both = inflation[:, np.newaxis] & inflation[np.newaxis, :]
        matrix = np.where(
            inflation_any & ~xccy_any,
            np.where(
                inflation_both,
                GIRR_INFLATION_SAME_TENOR_CORRELATION,
                GIRR_INFLATION_DIFFERENT_TENOR_CORRELATION,
            ),
            matrix,
        )

    np.fill_diagonal(matrix, GIRR_SAME_CURVE_CORRELATION)
    return matrix


def _girr_delta_tenor_array(
    ordered: Sequence[WeightedSensitivity],
    *,
    tenor_by_id: Mapping[str, str],
) -> npt.NDArray[np.object_]:
    tenors: list[str] = []
    for sensitivity in ordered:
        try:
            tenor = tenor_by_id[sensitivity.sensitivity_id]
        except KeyError as exc:
            raise SbmInputError(
                "missing GIRR delta tenor for weighted sensitivity",
                field="tenor_by_id",
                sensitivity_id=sensitivity.sensitivity_id,
            ) from exc
        if not isinstance(tenor, str) or not tenor.strip():
            raise SbmInputError(
                "non-empty text is required",
                field="tenor",
                sensitivity_id=sensitivity.sensitivity_id,
            )
        tenors.append(tenor.strip())
    return np.asarray(tenors, dtype=object)


def _girr_delta_risk_factor_array(
    ordered: Sequence[WeightedSensitivity],
    *,
    risk_factor_by_id: Mapping[str, str],
) -> npt.NDArray[np.object_]:
    risk_factors: list[str] = []
    for sensitivity in ordered:
        try:
            risk_factor = risk_factor_by_id[sensitivity.sensitivity_id]
        except KeyError as exc:
            raise SbmInputError(
                "missing GIRR delta risk factor for weighted sensitivity",
                field="risk_factor_by_id",
                sensitivity_id=sensitivity.sensitivity_id,
            ) from exc
        risk_factors.append(risk_factor)
    return np.asarray(risk_factors, dtype=object)


def _girr_delta_maturity_array(
    tenors: npt.NDArray[np.object_],
    *,
    profile_id: str,
) -> npt.NDArray[np.float64]:
    maturity_by_tenor: dict[str, float] = {}
    for tenor in sorted(str(value) for value in set(tenors) if value not in {"INFL", "XCCY"}):
        maturity_by_tenor[tenor] = girr_tenor_definition(profile_id, tenor).maturity_years
    return np.asarray(
        [maturity_by_tenor.get(str(tenor), 0.0) for tenor in tenors],
        dtype=np.float64,
    )


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
    ordering = (
        (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA),
        (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA),
        (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE),
        (SbmRiskClass.FX, SbmRiskMeasure.DELTA),
        (SbmRiskClass.EQUITY, SbmRiskMeasure.DELTA),
        (SbmRiskClass.COMMODITY, SbmRiskMeasure.DELTA),
        (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA),
        (SbmRiskClass.CSR_SEC_NONCTP, SbmRiskMeasure.DELTA),
        (SbmRiskClass.CSR_SEC_CTP, SbmRiskMeasure.DELTA),
    )
    ordered = tuple(path for path in ordering if path in present)
    remaining = tuple(sorted(present - set(ordering), key=lambda p: (p[0].value, p[1].value)))
    return ordered + remaining


def _coerce_sensitivities(sensitivities: object) -> tuple[SbmSensitivity, ...]:
    from frtb_sbm.validation import validate_sbm_sensitivities

    return validate_sbm_sensitivities(sensitivities)


def _profile_warnings(profile_id: str) -> tuple[str, ...]:
    del profile_id
    return ()


__all__ = [
    "calculate_sbm_capital",
    "calculate_sbm_capital_from_commodity_delta_batch",
    "calculate_sbm_capital_from_csr_nonsec_delta_batch",
    "calculate_sbm_capital_from_csr_sec_ctp_delta_batch",
    "calculate_sbm_capital_from_csr_sec_nonctp_delta_batch",
    "calculate_sbm_capital_from_equity_delta_batch",
    "calculate_sbm_capital_from_fx_delta_batch",
    "calculate_sbm_capital_from_girr_delta_batch",
    "calculate_sbm_capital_from_girr_vega_batch",
]
