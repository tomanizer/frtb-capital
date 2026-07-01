"""Package-owned RRAO batches for high-volume residual-risk kernels."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, cast

import frtb_common.batch_arrays as _batch_arrays
import numpy as np
from frtb_common import CalculationScope

from frtb_rrao._batch_columns import (
    BoolArray,
    ColumnInput,
    FloatArray,
    NullableColumnInput,
    ObjectArray,
    _bool_array,
    _enum_array,
    _freeze_citations,
    _freeze_source_column_maps,
    _optional_bool_object_array,
    _optional_enum_array,
    _optional_float_array,
    _optional_int_array,
    _optional_text_array,
    _require_lengths,
    _required_float_array,
    _required_text_array,
    _text_array_with_default,
)
from frtb_rrao._citations import merged_citation_ids
from frtb_rrao.assembly.hashes import (
    INPUT_HASH_ALGORITHM_JSON_ROW_V1,
    input_hash_for_rrao_batch,
)
from frtb_rrao.assembly.results import (
    collect_line_citations,
    partition_lines,
    profile_warnings,
    validate_context,
)
from frtb_rrao.audit import validate_rrao_result_reconciliation
from frtb_rrao.batch_registry import materialize_rrao_positions, rrao_position_column_kwargs
from frtb_rrao.capital import build_rrao_subtotals, included_rrao_total
from frtb_rrao.data_models import (
    RraoCalculationContext,
    RraoCapitalLine,
    RraoCapitalResult,
    RraoClassification,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoInvestmentFundExposureType,
    RraoInvestmentFundMethod,
    RraoPosition,
    RraoRegulatoryProfile,
)
from frtb_rrao.kernel.classification import RraoDecisionArrays, decision_arrays_for_batch
from frtb_rrao.org_scope import scope_at, validate_scope_metadata
from frtb_rrao.reference_data import risk_weight_rules_for_profile
from frtb_rrao.regimes import get_rrao_rule_profile
from frtb_rrao.validation._batch_common import position_id_at_first
from frtb_rrao.validation._errors import RraoInputError
from frtb_rrao.validation.batch import validate_rrao_batch


@dataclass(frozen=True)
class RraoPositionBatch:
    """Kernel-facing canonical RRAO input batch."""

    position_ids: ObjectArray
    source_row_ids: ObjectArray
    desk_ids: ObjectArray
    legal_entities: ObjectArray
    gross_effective_notionals: FloatArray
    currencies: ObjectArray
    evidence_types: ObjectArray
    evidence_labels: ObjectArray
    classification_hints: ObjectArray
    exclusion_reasons: ObjectArray
    exclusion_evidence_ids: ObjectArray
    back_to_back_match_group_ids: ObjectArray
    back_to_back_matched_position_ids: ObjectArray
    supervisor_directive_ids: ObjectArray
    underlying_counts: ObjectArray
    is_path_dependents: ObjectArray
    has_maturities: ObjectArray
    has_strike_or_barriers: ObjectArray
    has_multiple_strikes_or_barriers: ObjectArray
    is_ctp_hedges: BoolArray
    is_investment_fund_exposures: BoolArray
    investment_fund_ids: ObjectArray
    investment_fund_section_205_methods: ObjectArray
    investment_fund_included_exposure_types: ObjectArray
    investment_fund_mandate_evidence_ids: ObjectArray
    investment_fund_section_205_evidence_ids: ObjectArray
    investment_fund_gross_effective_notionals: FloatArray
    investment_fund_included_exposure_ratios: FloatArray
    investment_fund_look_through_availables: BoolArray
    investment_fund_mandate_allows_rrao_exposures: BoolArray
    notional_sources: ObjectArray
    lineage_source_systems: ObjectArray
    lineage_source_files: ObjectArray
    lineage_source_row_ids: ObjectArray
    lineage_present: BoolArray
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...]
    citations: tuple[tuple[str, ...], ...]
    input_hash: str
    input_hash_algorithm: str = INPUT_HASH_ALGORITHM_JSON_ROW_V1
    source_hash: str | None = None
    handoff_hash: str | None = None
    diagnostics: tuple[Mapping[str, object], ...] = ()
    org_scopes: tuple[CalculationScope | None, ...] | None = None

    @property
    def row_count(self) -> int:
        return int(self.position_ids.shape[0])


@dataclass(frozen=True)
class RraoBatchCapitalCalculation:
    """RRAO batch calculation with array intermediates and public capital."""

    result: RraoCapitalResult
    classifications: ObjectArray
    risk_weights: FloatArray
    add_ons: FloatArray


def build_rrao_batch_from_positions(
    positions: Iterable[RraoPosition],
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> RraoPositionBatch:
    """Build an RRAO batch from existing canonical position rows.

    This compatibility bridge is for callers that already hold dataclasses.
    High-volume adapters should build from Arrow batches or columns.
    Parameters
    ----------
    positions : Iterable[RraoPosition]
        Positions.
    source_hash : str | None, optional
        Source hash.
    handoff_hash : str | None, optional
        Handoff hash.
    diagnostics : Sequence[Mapping[str, object]], optional
        Diagnostics.

    Returns
    -------
    RraoPositionBatch
        Result of the operation.
    """

    materialized = materialize_rrao_positions(positions)
    if not materialized:
        raise RraoInputError("RRAO batch requires at least one position", field="positions")
    return _build_rrao_batch_from_materialized_positions(
        materialized,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def _build_rrao_batch_from_materialized_positions(
    positions: tuple[RraoPosition, ...],
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> RraoPositionBatch:
    """Build a validated RRAO batch after row container/type checks."""

    column_kwargs = cast(Any, rrao_position_column_kwargs(positions))
    return build_rrao_batch_from_columns(
        **column_kwargs,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
        copy_arrays=False,
    )


def build_rrao_batch_from_columns(
    *,
    position_ids: ColumnInput,
    source_row_ids: ColumnInput,
    desk_ids: ColumnInput,
    legal_entities: ColumnInput,
    gross_effective_notionals: ColumnInput,
    currencies: ColumnInput,
    evidence_types: ColumnInput,
    evidence_labels: ColumnInput,
    classification_hints: NullableColumnInput | None = None,
    exclusion_reasons: NullableColumnInput | None = None,
    exclusion_evidence_ids: NullableColumnInput | None = None,
    back_to_back_match_group_ids: NullableColumnInput | None = None,
    back_to_back_matched_position_ids: NullableColumnInput | None = None,
    supervisor_directive_ids: NullableColumnInput | None = None,
    underlying_counts: NullableColumnInput | None = None,
    is_path_dependents: NullableColumnInput | None = None,
    has_maturities: NullableColumnInput | None = None,
    has_strike_or_barriers: NullableColumnInput | None = None,
    has_multiple_strikes_or_barriers: NullableColumnInput | None = None,
    is_ctp_hedges: ColumnInput | None = None,
    is_investment_fund_exposures: ColumnInput | None = None,
    investment_fund_ids: NullableColumnInput | None = None,
    investment_fund_section_205_methods: NullableColumnInput | None = None,
    investment_fund_included_exposure_types: NullableColumnInput | None = None,
    investment_fund_mandate_evidence_ids: NullableColumnInput | None = None,
    investment_fund_section_205_evidence_ids: NullableColumnInput | None = None,
    investment_fund_gross_effective_notionals: NullableColumnInput | None = None,
    investment_fund_included_exposure_ratios: NullableColumnInput | None = None,
    investment_fund_look_through_availables: ColumnInput | None = None,
    investment_fund_mandate_allows_rrao_exposures: ColumnInput | None = None,
    notional_sources: ColumnInput | None = None,
    lineage_source_systems: ColumnInput | None = None,
    lineage_source_files: ColumnInput | None = None,
    lineage_source_row_ids: ColumnInput | None = None,
    lineage_present: ColumnInput | None = None,
    source_column_maps: Sequence[Sequence[tuple[str, str]]] | None = None,
    citations: Sequence[Sequence[str]] | None = None,
    org_scopes: Sequence[CalculationScope | None] | None = None,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    copy_arrays: bool = True,
) -> RraoPositionBatch:
    """Build a validated canonical RRAO batch from columnar inputs.
    Parameters
    ----------
    position_ids : ColumnInput
        Position ids.
    source_row_ids : ColumnInput
        Source row ids.
    desk_ids : ColumnInput
        Desk ids.
    legal_entities : ColumnInput
        Legal entities.
    gross_effective_notionals : ColumnInput
        Gross effective notionals.
    currencies : ColumnInput
        Currencies.
    evidence_types : ColumnInput
        Evidence types.
    evidence_labels : ColumnInput
        Evidence labels.
    classification_hints : NullableColumnInput | None, optional
        Classification hints.
    exclusion_reasons : NullableColumnInput | None, optional
        Exclusion reasons.
    exclusion_evidence_ids : NullableColumnInput | None, optional
        Exclusion evidence ids.
    back_to_back_match_group_ids : NullableColumnInput | None, optional
        Back to back match group ids.
    back_to_back_matched_position_ids : NullableColumnInput | None, optional
        Back to back matched position ids.
    supervisor_directive_ids : NullableColumnInput | None, optional
        Supervisor directive ids.
    underlying_counts : NullableColumnInput | None, optional
        Underlying counts.
    is_path_dependents : NullableColumnInput | None, optional
        Is path dependents.
    has_maturities : NullableColumnInput | None, optional
        Has maturities.
    has_strike_or_barriers : NullableColumnInput | None, optional
        Has strike or barriers.
    has_multiple_strikes_or_barriers : NullableColumnInput | None, optional
        Has multiple strikes or barriers.
    is_ctp_hedges : ColumnInput | None, optional
        Is ctp hedges.
    is_investment_fund_exposures : ColumnInput | None, optional
        Is investment fund exposures.
    investment_fund_ids : NullableColumnInput | None, optional
        Investment fund ids.
    investment_fund_section_205_methods : NullableColumnInput | None, optional
        Investment fund section 205 methods.
    investment_fund_included_exposure_types : NullableColumnInput | None, optional
        Investment fund included exposure types.
    investment_fund_mandate_evidence_ids : NullableColumnInput | None, optional
        Investment fund mandate evidence ids.
    investment_fund_section_205_evidence_ids : NullableColumnInput | None, optional
        Investment fund section 205 evidence ids.
    investment_fund_gross_effective_notionals : NullableColumnInput | None, optional
        Investment fund gross effective notionals.
    investment_fund_included_exposure_ratios : NullableColumnInput | None, optional
        Investment fund included exposure ratios.
    investment_fund_look_through_availables : ColumnInput | None, optional
        Investment fund look through availables.
    investment_fund_mandate_allows_rrao_exposures : ColumnInput | None, optional
        Investment fund mandate allows rrao exposures.
    notional_sources : ColumnInput | None, optional
        Notional sources.
    lineage_source_systems : ColumnInput | None, optional
        Lineage source systems.
    lineage_source_files : ColumnInput | None, optional
        Lineage source files.
    lineage_source_row_ids : ColumnInput | None, optional
        Lineage source row ids.
    lineage_present : ColumnInput | None, optional
        Lineage present.
    source_column_maps : Sequence[Sequence[tuple[str, str]]] | None, optional
        Source column maps.
    citations : Sequence[Sequence[str]] | None, optional
        Citations.
    source_hash : str | None, optional
        Source hash.
    handoff_hash : str | None, optional
        Handoff hash.
    diagnostics : Sequence[Mapping[str, object]], optional
        Diagnostics.
    copy_arrays : bool, optional
        Copy arrays.

    Returns
    -------
    RraoPositionBatch
        Result of the operation.
    """

    row_count = len(position_ids)
    if row_count == 0:
        raise RraoInputError("RRAO batch requires at least one position", field="positions")
    _require_lengths(
        row_count,
        source_row_ids=source_row_ids,
        desk_ids=desk_ids,
        legal_entities=legal_entities,
        gross_effective_notionals=gross_effective_notionals,
        currencies=currencies,
        evidence_types=evidence_types,
        evidence_labels=evidence_labels,
    )
    optional_lengths = {
        "classification_hints": classification_hints,
        "exclusion_reasons": exclusion_reasons,
        "exclusion_evidence_ids": exclusion_evidence_ids,
        "back_to_back_match_group_ids": back_to_back_match_group_ids,
        "back_to_back_matched_position_ids": back_to_back_matched_position_ids,
        "supervisor_directive_ids": supervisor_directive_ids,
        "underlying_counts": underlying_counts,
        "is_path_dependents": is_path_dependents,
        "has_maturities": has_maturities,
        "has_strike_or_barriers": has_strike_or_barriers,
        "has_multiple_strikes_or_barriers": has_multiple_strikes_or_barriers,
        "is_ctp_hedges": is_ctp_hedges,
        "is_investment_fund_exposures": is_investment_fund_exposures,
        "investment_fund_ids": investment_fund_ids,
        "investment_fund_section_205_methods": investment_fund_section_205_methods,
        "investment_fund_included_exposure_types": investment_fund_included_exposure_types,
        "investment_fund_mandate_evidence_ids": investment_fund_mandate_evidence_ids,
        "investment_fund_section_205_evidence_ids": investment_fund_section_205_evidence_ids,
        "investment_fund_gross_effective_notionals": investment_fund_gross_effective_notionals,
        "investment_fund_included_exposure_ratios": investment_fund_included_exposure_ratios,
        "investment_fund_look_through_availables": investment_fund_look_through_availables,
        "investment_fund_mandate_allows_rrao_exposures": (
            investment_fund_mandate_allows_rrao_exposures
        ),
        "notional_sources": notional_sources,
        "lineage_source_systems": lineage_source_systems,
        "lineage_source_files": lineage_source_files,
        "lineage_source_row_ids": lineage_source_row_ids,
        "lineage_present": lineage_present,
        "source_column_maps": source_column_maps,
        "citations": citations,
        "org_scopes": org_scopes,
    }
    for name, values in optional_lengths.items():
        if values is not None and len(values) != row_count:
            raise RraoInputError(f"{name} length does not match position_ids", field=name)

    lineage_present_default = (
        lineage_source_systems is not None
        or lineage_source_files is not None
        or lineage_source_row_ids is not None
        or source_column_maps is not None
    )
    batch = RraoPositionBatch(
        position_ids=_required_text_array(position_ids, "position_id", copy=copy_arrays),
        source_row_ids=_required_text_array(source_row_ids, "source_row_id", copy=copy_arrays),
        desk_ids=_required_text_array(desk_ids, "desk_id", copy=copy_arrays),
        legal_entities=_required_text_array(legal_entities, "legal_entity", copy=copy_arrays),
        gross_effective_notionals=_required_float_array(
            gross_effective_notionals,
            "gross_effective_notional",
            copy=copy_arrays,
        ),
        currencies=_required_text_array(currencies, "currency", copy=copy_arrays),
        evidence_types=_enum_array(
            evidence_types,
            RraoEvidenceType,
            "evidence_type",
            copy=copy_arrays,
        ),
        evidence_labels=_required_text_array(
            evidence_labels,
            "evidence_label",
            copy=copy_arrays,
        ),
        classification_hints=_optional_enum_array(
            classification_hints,
            row_count,
            RraoClassification,
            "classification_hint",
            copy=copy_arrays,
        ),
        exclusion_reasons=_optional_enum_array(
            exclusion_reasons,
            row_count,
            RraoExclusionReason,
            "exclusion_reason",
            copy=copy_arrays,
        ),
        exclusion_evidence_ids=_optional_text_array(
            exclusion_evidence_ids,
            row_count,
            copy=copy_arrays,
        ),
        back_to_back_match_group_ids=_optional_text_array(
            back_to_back_match_group_ids,
            row_count,
            copy=copy_arrays,
        ),
        back_to_back_matched_position_ids=_optional_text_array(
            back_to_back_matched_position_ids,
            row_count,
            copy=copy_arrays,
        ),
        supervisor_directive_ids=_optional_text_array(
            supervisor_directive_ids,
            row_count,
            copy=copy_arrays,
        ),
        underlying_counts=_optional_int_array(underlying_counts, row_count, copy=copy_arrays),
        is_path_dependents=_optional_bool_object_array(
            is_path_dependents,
            row_count,
            copy=copy_arrays,
        ),
        has_maturities=_optional_bool_object_array(
            has_maturities,
            row_count,
            copy=copy_arrays,
        ),
        has_strike_or_barriers=_optional_bool_object_array(
            has_strike_or_barriers,
            row_count,
            copy=copy_arrays,
        ),
        has_multiple_strikes_or_barriers=_optional_bool_object_array(
            has_multiple_strikes_or_barriers,
            row_count,
            copy=copy_arrays,
        ),
        is_ctp_hedges=_bool_array(is_ctp_hedges, row_count, default=False, copy=copy_arrays),
        is_investment_fund_exposures=_bool_array(
            is_investment_fund_exposures,
            row_count,
            default=False,
            copy=copy_arrays,
        ),
        investment_fund_ids=_optional_text_array(
            investment_fund_ids,
            row_count,
            copy=copy_arrays,
        ),
        investment_fund_section_205_methods=_optional_enum_array(
            investment_fund_section_205_methods,
            row_count,
            RraoInvestmentFundMethod,
            "investment_fund_descriptor.section_205_method",
            copy=copy_arrays,
        ),
        investment_fund_included_exposure_types=_optional_enum_array(
            investment_fund_included_exposure_types,
            row_count,
            RraoInvestmentFundExposureType,
            "investment_fund_descriptor.included_exposure_type",
            copy=copy_arrays,
        ),
        investment_fund_mandate_evidence_ids=_optional_text_array(
            investment_fund_mandate_evidence_ids,
            row_count,
            copy=copy_arrays,
        ),
        investment_fund_section_205_evidence_ids=_optional_text_array(
            investment_fund_section_205_evidence_ids,
            row_count,
            copy=copy_arrays,
        ),
        investment_fund_gross_effective_notionals=_optional_float_array(
            investment_fund_gross_effective_notionals,
            row_count,
            copy=copy_arrays,
        ),
        investment_fund_included_exposure_ratios=_optional_float_array(
            investment_fund_included_exposure_ratios,
            row_count,
            copy=copy_arrays,
        ),
        investment_fund_look_through_availables=_bool_array(
            investment_fund_look_through_availables,
            row_count,
            default=False,
            copy=copy_arrays,
        ),
        investment_fund_mandate_allows_rrao_exposures=_bool_array(
            investment_fund_mandate_allows_rrao_exposures,
            row_count,
            default=True,
            copy=copy_arrays,
        ),
        notional_sources=_text_array_with_default(
            notional_sources,
            row_count,
            default="reported",
            copy=copy_arrays,
        ),
        lineage_source_systems=_text_array_with_default(
            lineage_source_systems,
            row_count,
            default="",
            copy=copy_arrays,
        ),
        lineage_source_files=_text_array_with_default(
            lineage_source_files,
            row_count,
            default="",
            copy=copy_arrays,
        ),
        lineage_source_row_ids=_text_array_with_default(
            source_row_ids if lineage_source_row_ids is None else lineage_source_row_ids,
            row_count,
            default="",
            copy=copy_arrays,
        ),
        lineage_present=_bool_array(
            lineage_present,
            row_count,
            default=lineage_present_default,
            copy=copy_arrays,
        ),
        source_column_maps=_freeze_source_column_maps(source_column_maps, row_count),
        citations=_freeze_citations(citations, row_count),
        org_scopes=_scope_metadata_from_columns(org_scopes, row_count),
        input_hash="",
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=tuple(dict(item) for item in diagnostics),
    )
    validate_rrao_batch(batch)
    return replace(
        batch,
        input_hash=input_hash_for_rrao_batch(batch),
        input_hash_algorithm=INPUT_HASH_ALGORITHM_JSON_ROW_V1,
    )


def calculate_rrao_capital_from_batch(
    batch: RraoPositionBatch,
    *,
    context: RraoCalculationContext,
) -> RraoBatchCapitalCalculation:
    """Calculate supported RRAO capital from a columnar batch.
    Parameters
    ----------
    batch : RraoPositionBatch
        Batch.
    context : RraoCalculationContext
        Context.

    Returns
    -------
    RraoBatchCapitalCalculation
        Result of the operation.
    """

    if not isinstance(batch, RraoPositionBatch):
        raise RraoInputError("batch must be RraoPositionBatch", field="batch")
    validate_context(context)
    rule_profile = get_rrao_rule_profile(context.profile)

    lines, classifications, risk_weights, add_ons = _capital_lines_from_batch(
        batch,
        profile=rule_profile.profile,
    )
    included_lines, excluded_lines = partition_lines(lines)
    result_lines = included_lines + excluded_lines
    result = RraoCapitalResult(
        run_id=context.run_id,
        calculation_date=context.calculation_date,
        base_currency=context.base_currency,
        profile_id=rule_profile.profile.value,
        profile_hash=rule_profile.content_hash,
        input_hash=batch.input_hash,
        input_hash_algorithm=batch.input_hash_algorithm,
        lines=included_lines,
        excluded_lines=excluded_lines,
        subtotals=build_rrao_subtotals(result_lines),
        total_rrao=included_rrao_total(result_lines),
        citations=collect_line_citations(result_lines),
        warnings=profile_warnings(rule_profile.profile),
        calculation_scope=context.calculation_scope,
    )
    validate_rrao_result_reconciliation(result)
    return RraoBatchCapitalCalculation(
        result=result,
        classifications=_batch_arrays.readonly_array(
            np.asarray(classifications, dtype=object).copy(),
            copy=False,
        ),
        risk_weights=_batch_arrays.readonly_array(
            np.asarray(risk_weights, dtype=np.float64).copy(),
            copy=False,
        ),
        add_ons=_batch_arrays.readonly_array(
            np.asarray(add_ons, dtype=np.float64).copy(),
            copy=False,
        ),
    )


def _capital_lines_from_batch(
    batch: RraoPositionBatch,
    *,
    profile: RraoRegulatoryProfile,
) -> tuple[tuple[RraoCapitalLine, ...], ObjectArray, FloatArray, FloatArray]:
    decisions = decision_arrays_for_batch(batch, profile=profile)
    risk_weights, risk_weight_citations = _risk_weight_arrays_for_decisions(
        batch,
        decisions,
        profile=profile,
    )
    add_ons = batch.gross_effective_notionals * risk_weights
    lines = tuple(
        _capital_line_from_decision(
            batch,
            decisions,
            risk_weights=risk_weights,
            risk_weight_citations=risk_weight_citations,
            add_ons=add_ons,
            index=index,
        )
        for index in range(batch.row_count)
    )
    return (lines, decisions.classifications, risk_weights, add_ons)


def _risk_weight_arrays_for_decisions(
    batch: RraoPositionBatch,
    decisions: RraoDecisionArrays,
    *,
    profile: RraoRegulatoryProfile,
) -> tuple[FloatArray, tuple[str, ...]]:
    risk_weights = np.empty(batch.row_count, dtype=np.float64)
    risk_weight_citations: list[str] = [""] * batch.row_count
    assigned = np.zeros(batch.row_count, dtype=np.bool_)
    for rule in risk_weight_rules_for_profile(profile):
        mask = decisions.risk_weight_keys == rule.key
        if not bool(np.any(mask)):
            continue
        mismatch = mask & (decisions.classifications != rule.classification.value)
        if bool(np.any(mismatch)):
            raise RraoInputError(
                "risk-weight classification does not match decision",
                field="risk_weight_key",
                position_id=position_id_at_first(batch, mismatch),
            )
        risk_weights[mask] = rule.risk_weight
        for index in np.nonzero(mask)[0]:
            risk_weight_citations[int(index)] = rule.citation_id
        assigned |= mask
    if bool(np.any(~assigned)):
        missing_index = int(np.nonzero(~assigned)[0][0])
        raise RraoInputError(
            f"no RRAO risk-weight rule for {decisions.risk_weight_keys[missing_index]}",
            field="risk_weight_key",
            position_id=cast(str, batch.position_ids[missing_index]),
        )
    return _batch_arrays.readonly_array(risk_weights, copy=False), tuple(risk_weight_citations)


def _capital_line_from_decision(
    batch: RraoPositionBatch,
    decisions: RraoDecisionArrays,
    *,
    risk_weights: FloatArray,
    risk_weight_citations: tuple[str, ...],
    add_ons: FloatArray,
    index: int,
) -> RraoCapitalLine:
    classification = RraoClassification(cast(str, decisions.classifications[index]))
    return RraoCapitalLine(
        position_id=cast(str, batch.position_ids[index]),
        classification=classification,
        evidence_type=RraoEvidenceType(cast(str, batch.evidence_types[index])),
        gross_effective_notional=float(batch.gross_effective_notionals[index]),
        risk_weight=float(risk_weights[index]),
        add_on=float(add_ons[index]),
        currency=cast(str, batch.currencies[index]),
        is_excluded=classification is RraoClassification.EXCLUDED,
        reason_code=cast(str, decisions.reason_codes[index]),
        citations=merged_citation_ids(
            decisions.decision_citations[index],
            batch.citations[index],
            (risk_weight_citations[index],),
        ),
        desk_id=cast(str, batch.desk_ids[index]),
        legal_entity=cast(str, batch.legal_entities[index]),
        source_row_id=cast(str, batch.source_row_ids[index]),
        exclusion_reason=(
            None
            if batch.exclusion_reasons[index] is None
            else RraoExclusionReason(cast(str, batch.exclusion_reasons[index]))
        ),
        exclusion_evidence_id=cast(str | None, batch.exclusion_evidence_ids[index]),
        org_scope=scope_at(batch.org_scopes, index),
    )


def _scope_metadata_from_columns(
    org_scopes: Sequence[CalculationScope | None] | None,
    row_count: int,
) -> tuple[CalculationScope | None, ...] | None:
    if org_scopes is None:
        return None
    if len(org_scopes) != row_count:
        raise RraoInputError("org_scopes length does not match position_ids", field="org_scopes")
    rows = tuple(
        validate_scope_metadata(scope, field=f"org_scopes[{index}]")
        for index, scope in enumerate(org_scopes)
    )
    if not any(scope is not None for scope in rows):
        return None
    return rows


__all__ = [
    "RraoBatchCapitalCalculation",
    "RraoPositionBatch",
    "build_rrao_batch_from_columns",
    "build_rrao_batch_from_positions",
    "calculate_rrao_capital_from_batch",
    "input_hash_for_rrao_batch",
]
