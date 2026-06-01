"""Package-owned RRAO batches for high-volume residual-risk kernels."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum
from typing import Any, TypeVar, cast

import numpy as np
import numpy.typing as npt
from frtb_common import jsonable

from frtb_rrao.audit import validate_rrao_result_reconciliation
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
from frtb_rrao.reference_data import (
    evidence_rule_for,
    exclusion_rule_for,
    investment_fund_rule_for,
    risk_weight_rule_for,
)
from frtb_rrao.regimes import RraoRuleProfile, get_rrao_rule_profile
from frtb_rrao.validation import RraoInputError, validate_rrao_positions

ObjectArray = npt.NDArray[np.object_]
FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]
EnumT = TypeVar("EnumT", bound=StrEnum)


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
    source_hash: str | None = None
    handoff_hash: str | None = None
    diagnostics: tuple[Mapping[str, object], ...] = ()

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
    accepted_row_dataclasses_materialized: int = 0


def build_rrao_batch_from_positions(
    positions: Iterable[RraoPosition],
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> RraoPositionBatch:
    """
    Build an RRAO batch from existing canonical position rows.

    This compatibility bridge is for callers that already hold dataclasses.
    High-volume adapters should build from Arrow handoffs or columns.
    """

    validated = validate_rrao_positions(positions)
    if not validated:
        raise RraoInputError("RRAO batch requires at least one position", field="positions")
    return build_rrao_batch_from_columns(
        position_ids=[position.position_id for position in validated],
        source_row_ids=[position.source_row_id for position in validated],
        desk_ids=[position.desk_id for position in validated],
        legal_entities=[position.legal_entity for position in validated],
        gross_effective_notionals=[position.gross_effective_notional for position in validated],
        currencies=[position.currency for position in validated],
        evidence_types=[position.evidence_type.value for position in validated],
        evidence_labels=[position.evidence_label for position in validated],
        classification_hints=[
            None if position.classification_hint is None else position.classification_hint.value
            for position in validated
        ],
        exclusion_reasons=[
            None if position.exclusion_reason is None else position.exclusion_reason.value
            for position in validated
        ],
        exclusion_evidence_ids=[position.exclusion_evidence_id for position in validated],
        back_to_back_match_group_ids=[
            None
            if position.back_to_back_match is None
            else position.back_to_back_match.match_group_id
            for position in validated
        ],
        back_to_back_matched_position_ids=[
            None
            if position.back_to_back_match is None
            else position.back_to_back_match.matched_position_id
            for position in validated
        ],
        supervisor_directive_ids=[position.supervisor_directive_id for position in validated],
        underlying_counts=[position.underlying_count for position in validated],
        is_path_dependents=[position.is_path_dependent for position in validated],
        has_maturities=[position.has_maturity for position in validated],
        has_strike_or_barriers=[position.has_strike_or_barrier for position in validated],
        has_multiple_strikes_or_barriers=[
            position.has_multiple_strikes_or_barriers for position in validated
        ],
        is_ctp_hedges=[position.is_ctp_hedge for position in validated],
        is_investment_fund_exposures=[
            position.is_investment_fund_exposure for position in validated
        ],
        investment_fund_ids=[
            None
            if position.investment_fund_descriptor is None
            else position.investment_fund_descriptor.fund_id
            for position in validated
        ],
        investment_fund_section_205_methods=[
            None
            if position.investment_fund_descriptor is None
            else position.investment_fund_descriptor.section_205_method.value
            for position in validated
        ],
        investment_fund_included_exposure_types=[
            None
            if position.investment_fund_descriptor is None
            else position.investment_fund_descriptor.included_exposure_type.value
            for position in validated
        ],
        investment_fund_mandate_evidence_ids=[
            None
            if position.investment_fund_descriptor is None
            else position.investment_fund_descriptor.mandate_evidence_id
            for position in validated
        ],
        investment_fund_section_205_evidence_ids=[
            None
            if position.investment_fund_descriptor is None
            else position.investment_fund_descriptor.section_205_evidence_id
            for position in validated
        ],
        investment_fund_gross_effective_notionals=[
            None
            if position.investment_fund_descriptor is None
            else position.investment_fund_descriptor.fund_gross_effective_notional
            for position in validated
        ],
        investment_fund_included_exposure_ratios=[
            None
            if position.investment_fund_descriptor is None
            else position.investment_fund_descriptor.included_exposure_ratio
            for position in validated
        ],
        investment_fund_look_through_availables=[
            False
            if position.investment_fund_descriptor is None
            else position.investment_fund_descriptor.look_through_available
            for position in validated
        ],
        investment_fund_mandate_allows_rrao_exposures=[
            True
            if position.investment_fund_descriptor is None
            else position.investment_fund_descriptor.mandate_allows_rrao_exposures
            for position in validated
        ],
        notional_sources=[position.notional_source for position in validated],
        lineage_source_systems=[
            "" if position.lineage is None else position.lineage.source_system
            for position in validated
        ],
        lineage_source_files=[
            "" if position.lineage is None else position.lineage.source_file
            for position in validated
        ],
        lineage_source_row_ids=[
            "" if position.lineage is None else position.lineage.source_row_id
            for position in validated
        ],
        lineage_present=[position.lineage is not None for position in validated],
        source_column_maps=[
            () if position.lineage is None else tuple(position.lineage.source_column_map)
            for position in validated
        ],
        citations=[position.citations for position in validated],
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_rrao_batch_from_columns(
    *,
    position_ids: Sequence[object],
    source_row_ids: Sequence[object],
    desk_ids: Sequence[object],
    legal_entities: Sequence[object],
    gross_effective_notionals: Sequence[object],
    currencies: Sequence[object],
    evidence_types: Sequence[object],
    evidence_labels: Sequence[object],
    classification_hints: Sequence[object | None] | None = None,
    exclusion_reasons: Sequence[object | None] | None = None,
    exclusion_evidence_ids: Sequence[object | None] | None = None,
    back_to_back_match_group_ids: Sequence[object | None] | None = None,
    back_to_back_matched_position_ids: Sequence[object | None] | None = None,
    supervisor_directive_ids: Sequence[object | None] | None = None,
    underlying_counts: Sequence[object | None] | None = None,
    is_path_dependents: Sequence[object | None] | None = None,
    has_maturities: Sequence[object | None] | None = None,
    has_strike_or_barriers: Sequence[object | None] | None = None,
    has_multiple_strikes_or_barriers: Sequence[object | None] | None = None,
    is_ctp_hedges: Sequence[object] | None = None,
    is_investment_fund_exposures: Sequence[object] | None = None,
    investment_fund_ids: Sequence[object | None] | None = None,
    investment_fund_section_205_methods: Sequence[object | None] | None = None,
    investment_fund_included_exposure_types: Sequence[object | None] | None = None,
    investment_fund_mandate_evidence_ids: Sequence[object | None] | None = None,
    investment_fund_section_205_evidence_ids: Sequence[object | None] | None = None,
    investment_fund_gross_effective_notionals: Sequence[object | None] | None = None,
    investment_fund_included_exposure_ratios: Sequence[object | None] | None = None,
    investment_fund_look_through_availables: Sequence[object] | None = None,
    investment_fund_mandate_allows_rrao_exposures: Sequence[object] | None = None,
    notional_sources: Sequence[object] | None = None,
    lineage_source_systems: Sequence[object] | None = None,
    lineage_source_files: Sequence[object] | None = None,
    lineage_source_row_ids: Sequence[object] | None = None,
    lineage_present: Sequence[object] | None = None,
    source_column_maps: Sequence[Sequence[tuple[str, str]]] | None = None,
    citations: Sequence[Sequence[str]] | None = None,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    copy_arrays: bool = True,
) -> RraoPositionBatch:
    """Build a validated canonical RRAO batch from columnar inputs."""

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
        input_hash="",
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=tuple(dict(item) for item in diagnostics),
    )
    _validate_batch(batch)
    return replace(batch, input_hash=input_hash_for_rrao_batch(batch))


def input_hash_for_rrao_batch(batch: RraoPositionBatch) -> str:
    """Hash canonical RRAO batch inputs in deterministic input order."""

    return _hash_payload(
        {"positions": [_position_payload(batch, index) for index in range(batch.row_count)]}
    )


def calculate_rrao_capital_from_batch(
    batch: RraoPositionBatch,
    *,
    context: RraoCalculationContext,
) -> RraoBatchCapitalCalculation:
    """Calculate supported RRAO capital from a columnar batch."""

    if not isinstance(batch, RraoPositionBatch):
        raise RraoInputError("batch must be RraoPositionBatch", field="batch")
    _validate_context(context)
    rule_profile = get_rrao_rule_profile(context.profile)

    lines, classifications, risk_weights, add_ons = _capital_lines_from_batch(
        batch,
        profile=rule_profile.profile,
    )
    included_lines, excluded_lines = _partition_lines(lines)
    result_lines = included_lines + excluded_lines
    result = RraoCapitalResult(
        run_id=context.run_id,
        calculation_date=context.calculation_date,
        base_currency=context.base_currency,
        profile_id=rule_profile.profile.value,
        profile_hash=rule_profile.content_hash,
        input_hash=batch.input_hash,
        lines=included_lines,
        excluded_lines=excluded_lines,
        subtotals=build_rrao_subtotals(result_lines),
        total_rrao=included_rrao_total(result_lines),
        citations=_collect_line_citations(result_lines),
        warnings=_profile_warnings(rule_profile),
    )
    validate_rrao_result_reconciliation(result)
    return RraoBatchCapitalCalculation(
        result=result,
        classifications=_immutable_object_array(classifications),
        risk_weights=_immutable_float_array(risk_weights),
        add_ons=_immutable_float_array(add_ons),
        accepted_row_dataclasses_materialized=0,
    )


def _validate_context(context: RraoCalculationContext) -> None:
    if not isinstance(context, RraoCalculationContext):
        raise RraoInputError("calculation context must be RraoCalculationContext", field="context")
    _required_text(context.run_id, "run_id")
    _required_text(context.base_currency, "base_currency")
    if not isinstance(context.calculation_date, date):
        raise RraoInputError("calculation date must be a date", field="calculation_date")
    try:
        RraoRegulatoryProfile(context.profile)
    except ValueError as exc:
        raise RraoInputError("invalid regulatory profile", field="profile") from exc
    if context.desk_id:
        _required_text(context.desk_id, "desk_id")
    if context.legal_entity:
        _required_text(context.legal_entity, "legal_entity")
    _required_text(context.citation_policy, "citation_policy")


def _validate_batch(batch: RraoPositionBatch) -> None:
    _require_unique(batch.position_ids)
    if not np.all(np.isfinite(batch.gross_effective_notionals)):
        raise RraoInputError(
            "gross effective notional values must be finite",
            field="gross_effective_notional",
        )
    if bool(np.any(batch.gross_effective_notionals < 0.0)):
        raise RraoInputError(
            "gross effective notional must be non-negative",
            field="gross_effective_notional",
        )
    if bool(np.any(batch.classification_hints == RraoClassification.UNSUPPORTED.value)):
        raise RraoInputError(
            "unsupported classification path",
            field="classification_hint",
            position_id=_position_id_at_first(
                batch,
                batch.classification_hints == RraoClassification.UNSUPPORTED.value,
            ),
        )
    if bool(np.any(~batch.lineage_present)):
        raise RraoInputError(
            "source lineage is required",
            field="lineage",
            position_id=_position_id_at_first(batch, ~batch.lineage_present),
        )
    _require_non_empty_object_column(
        batch,
        batch.lineage_source_systems,
        field="lineage.source_system",
    )
    _require_non_empty_object_column(
        batch,
        batch.lineage_source_files,
        field="lineage.source_file",
    )
    _require_non_empty_object_column(
        batch,
        batch.lineage_source_row_ids,
        field="lineage.source_row_id",
    )
    _validate_evidence_requirements(batch)
    _validate_back_to_back_match_groups(batch)
    _validate_investment_fund_fields(batch)


def _validate_evidence_requirements(batch: RraoPositionBatch) -> None:
    supervisor_mask = (batch.evidence_types == RraoEvidenceType.SUPERVISOR_DIRECTIVE.value) | (
        batch.classification_hints == RraoClassification.SUPERVISOR_DIRECTED.value
    )
    _require_text_where(
        batch,
        batch.supervisor_directive_ids,
        supervisor_mask,
        field="supervisor_directive_id",
    )

    excluded_hint_mask = batch.classification_hints == RraoClassification.EXCLUDED.value
    missing_exclusion_reason = excluded_hint_mask & (batch.exclusion_reasons == None)  # noqa: E711
    if bool(np.any(missing_exclusion_reason)):
        raise RraoInputError(
            "excluded classification requires an exclusion reason",
            field="exclusion_reason",
            position_id=_position_id_at_first(batch, missing_exclusion_reason),
        )

    has_exclusion_reason = batch.exclusion_reasons != None  # noqa: E711
    wrong_exclusion_evidence = has_exclusion_reason & (
        batch.evidence_types != RraoEvidenceType.EXPLICIT_EXCLUSION.value
    )
    if bool(np.any(wrong_exclusion_evidence)):
        raise RraoInputError(
            "exclusion reason requires explicit exclusion evidence type",
            field="evidence_type",
            position_id=_position_id_at_first(batch, wrong_exclusion_evidence),
        )
    _require_text_where(
        batch,
        batch.exclusion_evidence_ids,
        has_exclusion_reason,
        field="exclusion_evidence_id",
    )

    explicit_exclusion = batch.evidence_types == RraoEvidenceType.EXPLICIT_EXCLUSION.value
    missing_reason_for_explicit = explicit_exclusion & (batch.exclusion_reasons == None)  # noqa: E711
    if bool(np.any(missing_reason_for_explicit)):
        raise RraoInputError(
            "explicit exclusion evidence requires an exclusion reason",
            field="exclusion_reason",
            position_id=_position_id_at_first(batch, missing_reason_for_explicit),
        )
    _require_text_where(
        batch,
        batch.exclusion_evidence_ids,
        explicit_exclusion,
        field="exclusion_evidence_id",
    )

    exact_back_to_back = (
        batch.exclusion_reasons == RraoExclusionReason.EXACT_THIRD_PARTY_BACK_TO_BACK.value
    )
    match_present = (batch.back_to_back_match_group_ids != None) | (  # noqa: E711
        batch.back_to_back_matched_position_ids != None  # noqa: E711
    )
    missing_match = exact_back_to_back & ~match_present
    if bool(np.any(missing_match)):
        raise RraoInputError(
            "exact back-to-back exclusion requires match evidence",
            field="back_to_back_match",
            position_id=_position_id_at_first(batch, missing_match),
        )
    invalid_match_context = match_present & ~exact_back_to_back
    if bool(np.any(invalid_match_context)):
        raise RraoInputError(
            "back-to-back match evidence is only valid for exact back-to-back exclusions",
            field="back_to_back_match",
            position_id=_position_id_at_first(batch, invalid_match_context),
        )
    _require_text_where(
        batch,
        batch.back_to_back_match_group_ids,
        match_present,
        field="back_to_back_match.match_group_id",
    )
    _require_text_where(
        batch,
        batch.back_to_back_matched_position_ids,
        match_present,
        field="back_to_back_match.matched_position_id",
    )


def _validate_back_to_back_match_groups(batch: RraoPositionBatch) -> None:
    positions_by_id = {
        cast(str, batch.position_ids[index]): index for index in range(batch.row_count)
    }
    match_groups: dict[str, list[int]] = {}
    for index in range(batch.row_count):
        match_group_id = batch.back_to_back_match_group_ids[index]
        if match_group_id is None:
            continue
        matched_position_id = cast(str, batch.back_to_back_matched_position_ids[index])
        position_id = cast(str, batch.position_ids[index])
        if matched_position_id == position_id:
            raise RraoInputError(
                "back-to-back match must reference the opposite transaction",
                field="back_to_back_match.matched_position_id",
                position_id=position_id,
            )
        if matched_position_id not in positions_by_id:
            raise RraoInputError(
                "back-to-back matched position is missing from input",
                field="back_to_back_match.matched_position_id",
                position_id=position_id,
            )
        match_groups.setdefault(cast(str, match_group_id), []).append(index)

    for match_group_id in sorted(match_groups):
        indices = match_groups[match_group_id]
        if len(indices) != 2:
            joined = ", ".join(cast(str, batch.position_ids[index]) for index in indices)
            raise RraoInputError(
                f"exact back-to-back match group must contain exactly two transactions: {joined}",
                field="back_to_back_match.match_group_id",
                position_id=cast(str, batch.position_ids[indices[0]]),
            )
        left, right = indices
        _validate_exact_back_to_back_pair(batch, left, right)


def _validate_exact_back_to_back_pair(
    batch: RraoPositionBatch,
    left: int,
    right: int,
) -> None:
    left_id = cast(str, batch.position_ids[left])
    right_id = cast(str, batch.position_ids[right])
    if batch.back_to_back_matched_position_ids[left] != right_id:
        raise RraoInputError(
            "back-to-back match group does not cross-reference the paired transaction",
            field="back_to_back_match.matched_position_id",
            position_id=left_id,
        )
    if batch.back_to_back_matched_position_ids[right] != left_id:
        raise RraoInputError(
            "back-to-back match group does not cross-reference the paired transaction",
            field="back_to_back_match.matched_position_id",
            position_id=right_id,
        )
    if batch.exclusion_evidence_ids[left] != batch.exclusion_evidence_ids[right]:
        raise RraoInputError(
            "exact back-to-back pair must share the same exclusion evidence id",
            field="exclusion_evidence_id",
            position_id=right_id,
        )
    if batch.currencies[left] != batch.currencies[right]:
        raise RraoInputError(
            "exact back-to-back pair must have matching currency",
            field="currency",
            position_id=right_id,
        )
    if not math.isclose(
        float(batch.gross_effective_notionals[left]),
        float(batch.gross_effective_notionals[right]),
        rel_tol=1e-12,
        abs_tol=1e-9,
    ):
        raise RraoInputError(
            "exact back-to-back pair must have matching gross effective notional",
            field="gross_effective_notional",
            position_id=right_id,
        )


def _validate_investment_fund_fields(batch: RraoPositionBatch) -> None:
    descriptor_present = (
        (batch.investment_fund_ids != None)  # noqa: E711
        | (batch.investment_fund_section_205_methods != None)  # noqa: E711
        | (batch.investment_fund_included_exposure_types != None)  # noqa: E711
        | (batch.investment_fund_mandate_evidence_ids != None)  # noqa: E711
        | (batch.investment_fund_section_205_evidence_ids != None)  # noqa: E711
        | ~np.isnan(batch.investment_fund_gross_effective_notionals)
        | ~np.isnan(batch.investment_fund_included_exposure_ratios)
    )
    is_fund_path = (
        batch.is_investment_fund_exposures
        | (batch.evidence_types == RraoEvidenceType.INVESTMENT_FUND_EXPOSURE.value)
        | descriptor_present
    )
    missing_flag = is_fund_path & ~batch.is_investment_fund_exposures
    if bool(np.any(missing_flag)):
        raise RraoInputError(
            "investment fund exposure flag is required",
            field="is_investment_fund_exposure",
            position_id=_position_id_at_first(batch, missing_flag),
        )
    wrong_evidence = is_fund_path & (
        batch.evidence_types != RraoEvidenceType.INVESTMENT_FUND_EXPOSURE.value
    )
    if bool(np.any(wrong_evidence)):
        raise RraoInputError(
            "investment fund exposure requires investment-fund evidence type",
            field="evidence_type",
            position_id=_position_id_at_first(batch, wrong_evidence),
        )
    missing_descriptor = is_fund_path & ~descriptor_present
    if bool(np.any(missing_descriptor)):
        raise RraoInputError(
            "investment fund descriptor is required",
            field="investment_fund_descriptor",
            position_id=_position_id_at_first(batch, missing_descriptor),
        )
    if not bool(np.any(is_fund_path)):
        return

    _require_text_where(
        batch,
        batch.investment_fund_ids,
        is_fund_path,
        field="investment_fund_descriptor.fund_id",
    )
    _require_text_where(
        batch,
        batch.investment_fund_mandate_evidence_ids,
        is_fund_path,
        field="investment_fund_descriptor.mandate_evidence_id",
    )
    _require_text_where(
        batch,
        batch.investment_fund_section_205_evidence_ids,
        is_fund_path,
        field="investment_fund_descriptor.section_205_evidence_id",
    )
    wrong_method = is_fund_path & (
        batch.investment_fund_section_205_methods
        != RraoInvestmentFundMethod.BACKSTOP_FUND_METHOD.value
    )
    if bool(np.any(wrong_method)):
        raise RraoInputError(
            "investment fund RRAO inclusion requires the __.205(e)(3)(iii) backstop method",
            field="investment_fund_descriptor.section_205_method",
            position_id=_position_id_at_first(batch, wrong_method),
        )
    missing_exposure_type = is_fund_path & (
        batch.investment_fund_included_exposure_types == None  # noqa: E711
    )
    if bool(np.any(missing_exposure_type)):
        raise RraoInputError(
            "invalid investment fund exposure type",
            field="investment_fund_descriptor.included_exposure_type",
            position_id=_position_id_at_first(batch, missing_exposure_type),
        )
    if bool(np.any(is_fund_path & batch.investment_fund_look_through_availables)):
        raise RraoInputError(
            "investment fund RRAO inclusion requires a non-look-through portion",
            field="investment_fund_descriptor.look_through_available",
            position_id=_position_id_at_first(
                batch,
                is_fund_path & batch.investment_fund_look_through_availables,
            ),
        )
    mandate_disallowed = is_fund_path & ~batch.investment_fund_mandate_allows_rrao_exposures
    if bool(np.any(mandate_disallowed)):
        raise RraoInputError(
            "investment fund mandate evidence must permit RRAO exposure types",
            field="investment_fund_descriptor.mandate_allows_rrao_exposures",
            position_id=_position_id_at_first(batch, mandate_disallowed),
        )
    missing_fund_notional = is_fund_path & np.isnan(batch.investment_fund_gross_effective_notionals)
    if bool(np.any(missing_fund_notional)):
        raise RraoInputError(
            "fund gross effective notional must be positive",
            field="investment_fund_descriptor.fund_gross_effective_notional",
            position_id=_position_id_at_first(batch, missing_fund_notional),
        )
    non_positive_fund = is_fund_path & (batch.investment_fund_gross_effective_notionals <= 0.0)
    if bool(np.any(non_positive_fund)):
        raise RraoInputError(
            "fund gross effective notional must be positive",
            field="investment_fund_descriptor.fund_gross_effective_notional",
            position_id=_position_id_at_first(batch, non_positive_fund),
        )
    ratio = batch.investment_fund_included_exposure_ratios
    invalid_ratio = is_fund_path & (np.isnan(ratio) | (ratio <= 0.0) | (ratio > 1.0))
    if bool(np.any(invalid_ratio)):
        raise RraoInputError(
            "included exposure ratio must be greater than zero and no more than one",
            field="investment_fund_descriptor.included_exposure_ratio",
            position_id=_position_id_at_first(batch, invalid_ratio),
        )
    expected_notionals = batch.investment_fund_gross_effective_notionals * ratio
    mismatch = is_fund_path & ~np.isclose(
        batch.gross_effective_notionals,
        expected_notionals,
        rtol=1e-12,
        atol=1e-9,
    )
    if bool(np.any(mismatch)):
        raise RraoInputError(
            "gross effective notional must equal the cited investment-fund included portion",
            field="gross_effective_notional",
            position_id=_position_id_at_first(batch, mismatch),
        )


def _capital_lines_from_batch(
    batch: RraoPositionBatch,
    *,
    profile: RraoRegulatoryProfile,
) -> tuple[tuple[RraoCapitalLine, ...], ObjectArray, FloatArray, FloatArray]:
    lines: list[RraoCapitalLine] = []
    classifications: list[str] = []
    risk_weights: list[float] = []
    add_ons: list[float] = []
    for index in range(batch.row_count):
        line = _capital_line_for_index(batch, index, profile=profile)
        lines.append(line)
        classifications.append(line.classification.value)
        risk_weights.append(line.risk_weight)
        add_ons.append(line.add_on)
    return (
        tuple(lines),
        _object_array(classifications, copy=True),
        np.asarray(risk_weights, dtype=np.float64),
        np.asarray(add_ons, dtype=np.float64),
    )


def _capital_line_for_index(
    batch: RraoPositionBatch,
    index: int,
    *,
    profile: RraoRegulatoryProfile,
) -> RraoCapitalLine:
    classification, risk_weight_key, reason_code, decision_citations = _decision_for_index(
        batch,
        index,
        profile=profile,
    )
    risk_weight_rule = risk_weight_rule_for(profile, risk_weight_key)
    if risk_weight_rule.classification is not classification:
        raise RraoInputError(
            "risk-weight classification does not match decision",
            field="risk_weight_key",
            position_id=cast(str, batch.position_ids[index]),
        )
    risk_weight = risk_weight_rule.risk_weight
    add_on = float(batch.gross_effective_notionals[index]) * risk_weight
    is_excluded = classification is RraoClassification.EXCLUDED
    return RraoCapitalLine(
        position_id=cast(str, batch.position_ids[index]),
        classification=classification,
        evidence_type=RraoEvidenceType(cast(str, batch.evidence_types[index])),
        gross_effective_notional=float(batch.gross_effective_notionals[index]),
        risk_weight=risk_weight,
        add_on=add_on,
        currency=cast(str, batch.currencies[index]),
        is_excluded=is_excluded,
        reason_code=reason_code,
        citations=_merged_citation_ids(decision_citations, (risk_weight_rule.citation_id,)),
        desk_id=cast(str, batch.desk_ids[index]),
        legal_entity=cast(str, batch.legal_entities[index]),
        source_row_id=cast(str, batch.source_row_ids[index]),
        exclusion_reason=(
            None
            if batch.exclusion_reasons[index] is None
            else RraoExclusionReason(cast(str, batch.exclusion_reasons[index]))
        ),
        exclusion_evidence_id=cast(str | None, batch.exclusion_evidence_ids[index]),
    )


def _decision_for_index(
    batch: RraoPositionBatch,
    index: int,
    *,
    profile: RraoRegulatoryProfile,
) -> tuple[RraoClassification, str, str, tuple[str, ...]]:
    if _is_exclusion_path(batch, index):
        exclusion_reason = RraoExclusionReason(cast(str, batch.exclusion_reasons[index]))
        exclusion_rule = exclusion_rule_for(profile, exclusion_reason)
        return (
            RraoClassification.EXCLUDED,
            exclusion_rule.risk_weight_key,
            exclusion_rule.reason_code,
            _merged_citation_ids((exclusion_rule.citation_id,), batch.citations[index]),
        )

    evidence_type = RraoEvidenceType(cast(str, batch.evidence_types[index]))
    if evidence_type is RraoEvidenceType.INVESTMENT_FUND_EXPOSURE:
        investment_fund_rule = investment_fund_rule_for(
            profile,
            RraoInvestmentFundExposureType(
                cast(str, batch.investment_fund_included_exposure_types[index])
            ),
        )
        _check_hint_compatibility(batch, index, investment_fund_rule.classification)
        return (
            investment_fund_rule.classification,
            investment_fund_rule.risk_weight_key,
            investment_fund_rule.reason_code,
            _merged_citation_ids(investment_fund_rule.citation_ids, batch.citations[index]),
        )

    evidence_rule = evidence_rule_for(profile, evidence_type)
    _check_hint_compatibility(batch, index, evidence_rule.classification)
    return (
        evidence_rule.classification,
        evidence_rule.risk_weight_key,
        evidence_rule.reason_code,
        _merged_citation_ids((evidence_rule.citation_id,), batch.citations[index]),
    )


def _check_hint_compatibility(
    batch: RraoPositionBatch,
    index: int,
    classification: RraoClassification,
) -> None:
    hint = batch.classification_hints[index]
    if hint is None:
        return
    if RraoClassification(cast(str, hint)) is classification:
        return
    raise RraoInputError(
        (
            "classification hint conflicts with profile evidence rule: "
            f"{hint} != {classification.value}"
        ),
        field="classification_hint",
        position_id=cast(str, batch.position_ids[index]),
    )


def _is_exclusion_path(batch: RraoPositionBatch, index: int) -> bool:
    return (
        batch.classification_hints[index] == RraoClassification.EXCLUDED.value
        or batch.exclusion_reasons[index] is not None
        or batch.evidence_types[index] == RraoEvidenceType.EXPLICIT_EXCLUSION.value
    )


def _partition_lines(
    lines: tuple[RraoCapitalLine, ...],
) -> tuple[tuple[RraoCapitalLine, ...], tuple[RraoCapitalLine, ...]]:
    included = tuple(line for line in lines if not line.is_excluded)
    excluded = tuple(line for line in lines if line.is_excluded)
    return included, excluded


def _collect_line_citations(lines: tuple[RraoCapitalLine, ...]) -> tuple[str, ...]:
    citation_ids: list[str] = []
    seen: set[str] = set()
    for line in lines:
        for citation_id in line.citations:
            if citation_id not in seen:
                citation_ids.append(citation_id)
                seen.add(citation_id)
    return tuple(citation_ids)


def _profile_warnings(rule_profile: RraoRuleProfile) -> tuple[str, ...]:
    if rule_profile.profile is RraoRegulatoryProfile.US_NPR_2_0:
        return (
            "US_NPR_2_0 is proposed-rule material; do not present outputs as final "
            "regulatory capital.",
        )
    return ()


def _position_payload(batch: RraoPositionBatch, index: int) -> dict[str, object]:
    payload: dict[str, object] = {
        "position_id": batch.position_ids[index],
        "source_row_id": batch.source_row_ids[index],
        "desk_id": batch.desk_ids[index],
        "legal_entity": batch.legal_entities[index],
        "gross_effective_notional": float(batch.gross_effective_notionals[index]),
        "currency": batch.currencies[index],
        "evidence_type": batch.evidence_types[index],
        "evidence_label": batch.evidence_labels[index],
        "lineage": {
            "source_system": batch.lineage_source_systems[index],
            "source_file": batch.lineage_source_files[index],
            "source_row_id": batch.lineage_source_row_ids[index],
            "source_column_map": [list(pair) for pair in batch.source_column_maps[index]],
        },
        "classification_hint": batch.classification_hints[index],
        "exclusion_reason": batch.exclusion_reasons[index],
        "exclusion_evidence_id": batch.exclusion_evidence_ids[index],
        "supervisor_directive_id": batch.supervisor_directive_ids[index],
        "underlying_count": batch.underlying_counts[index],
        "is_path_dependent": batch.is_path_dependents[index],
        "has_maturity": batch.has_maturities[index],
        "has_strike_or_barrier": batch.has_strike_or_barriers[index],
        "has_multiple_strikes_or_barriers": batch.has_multiple_strikes_or_barriers[index],
        "is_ctp_hedge": bool(batch.is_ctp_hedges[index]),
        "is_investment_fund_exposure": bool(batch.is_investment_fund_exposures[index]),
        "investment_fund_descriptor": _investment_fund_descriptor_payload(batch, index),
        "notional_source": batch.notional_sources[index],
        "citations": list(batch.citations[index]),
    }
    if batch.back_to_back_match_group_ids[index] is not None:
        payload["back_to_back_match"] = {
            "match_group_id": batch.back_to_back_match_group_ids[index],
            "matched_position_id": batch.back_to_back_matched_position_ids[index],
        }
    return payload


def _investment_fund_descriptor_payload(
    batch: RraoPositionBatch,
    index: int,
) -> dict[str, object] | None:
    if not bool(batch.is_investment_fund_exposures[index]):
        return None
    return {
        "fund_id": batch.investment_fund_ids[index],
        "section_205_method": batch.investment_fund_section_205_methods[index],
        "included_exposure_type": batch.investment_fund_included_exposure_types[index],
        "mandate_evidence_id": batch.investment_fund_mandate_evidence_ids[index],
        "section_205_evidence_id": batch.investment_fund_section_205_evidence_ids[index],
        "fund_gross_effective_notional": float(
            batch.investment_fund_gross_effective_notionals[index]
        ),
        "included_exposure_ratio": float(batch.investment_fund_included_exposure_ratios[index]),
        "look_through_available": bool(batch.investment_fund_look_through_availables[index]),
        "mandate_allows_rrao_exposures": bool(
            batch.investment_fund_mandate_allows_rrao_exposures[index]
        ),
    }


def _hash_payload(payload: object) -> str:
    encoded = bytes(json.dumps(jsonable(payload), sort_keys=True, separators=(",", ":")), "utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _merged_citation_ids(*citation_groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in citation_groups:
        for citation_id in group:
            if citation_id not in seen:
                merged.append(citation_id)
                seen.add(citation_id)
    return tuple(merged)


def _require_lengths(row_count: int, **columns: Sequence[object]) -> None:
    for name, values in columns.items():
        if len(values) != row_count:
            raise RraoInputError(f"{name} length does not match position_ids", field=name)


def _require_unique(values: ObjectArray) -> None:
    unique_values, counts = np.unique(values, return_counts=True)
    duplicate_mask = counts > 1
    if bool(np.any(duplicate_mask)):
        duplicate = str(unique_values[np.nonzero(duplicate_mask)[0][0]])
        raise RraoInputError(
            "duplicate position id",
            field="position_id",
            position_id=duplicate,
        )


def _position_id_at_first(batch: RraoPositionBatch, mask: npt.NDArray[np.bool_]) -> str:
    index = int(np.nonzero(mask)[0][0])
    return cast(str, batch.position_ids[index])


def _require_non_empty_object_column(
    batch: RraoPositionBatch,
    values: ObjectArray,
    *,
    field: str,
) -> None:
    mask = values == ""
    if bool(np.any(mask)):
        raise RraoInputError(
            "non-empty text is required",
            field=field,
            position_id=_position_id_at_first(batch, mask),
        )


def _require_text_where(
    batch: RraoPositionBatch,
    values: ObjectArray,
    mask: npt.NDArray[np.bool_],
    *,
    field: str,
) -> None:
    missing = mask & (values == None)  # noqa: E711
    if bool(np.any(missing)):
        raise RraoInputError(
            "non-empty text is required",
            field=field,
            position_id=_position_id_at_first(batch, missing),
        )


def _required_text_array(
    values: Sequence[object | None],
    field_name: str,
    *,
    copy: bool,
) -> ObjectArray:
    return _object_array([_required_text(value, field_name) for value in values], copy=copy)


def _optional_text_array(
    values: Sequence[object | None] | None,
    row_count: int,
    *,
    copy: bool,
) -> ObjectArray:
    if values is None:
        return _object_array([None] * row_count, copy=copy)
    return _object_array([_optional_text(value) for value in values], copy=copy)


def _text_array_with_default(
    values: Sequence[object] | None,
    row_count: int,
    *,
    default: str,
    copy: bool,
) -> ObjectArray:
    if values is None:
        return _object_array([default] * row_count, copy=copy)
    return _object_array([_optional_text(value) or default for value in values], copy=copy)


def _enum_array(
    values: Sequence[object | None],
    enum_type: type[EnumT],
    field_name: str,
    *,
    copy: bool,
) -> ObjectArray:
    return _object_array(
        [_coerce_enum_value(value, enum_type, field_name) for value in values],
        copy=copy,
    )


def _optional_enum_array(
    values: Sequence[object | None] | None,
    row_count: int,
    enum_type: type[EnumT],
    field_name: str,
    *,
    copy: bool,
) -> ObjectArray:
    if values is None:
        return _object_array([None] * row_count, copy=copy)
    return _object_array(
        [
            None
            if _optional_text(value) is None
            else _coerce_enum_value(value, enum_type, field_name)
            for value in values
        ],
        copy=copy,
    )


def _required_float_array(
    values: Sequence[object],
    field_name: str,
    *,
    copy: bool,
) -> FloatArray:
    array = np.asarray([_required_float(value, field_name) for value in values], dtype=np.float64)
    if copy:
        array = array.copy()
    array.setflags(write=False)
    return array


def _optional_float_array(
    values: Sequence[object | None] | None,
    row_count: int,
    *,
    copy: bool,
) -> FloatArray:
    if values is None:
        array = np.full(row_count, np.nan, dtype=np.float64)
    else:
        array = np.asarray([_optional_float(value) for value in values], dtype=np.float64)
    if copy:
        array = array.copy()
    array.setflags(write=False)
    return array


def _optional_int_array(
    values: Sequence[object | None] | None,
    row_count: int,
    *,
    copy: bool,
) -> ObjectArray:
    if values is None:
        return _object_array([None] * row_count, copy=copy)
    return _object_array([_optional_int(value) for value in values], copy=copy)


def _bool_array(
    values: Sequence[object] | None,
    row_count: int,
    *,
    default: bool,
    copy: bool,
) -> BoolArray:
    if values is None:
        array = np.full(row_count, default, dtype=np.bool_)
    else:
        array = np.asarray([_bool_value(value) for value in values], dtype=np.bool_)
    if copy:
        array = array.copy()
    array.setflags(write=False)
    return array


def _optional_bool_object_array(
    values: Sequence[object | None] | None,
    row_count: int,
    *,
    copy: bool,
) -> ObjectArray:
    if values is None:
        return _object_array([None] * row_count, copy=copy)
    return _object_array([_optional_bool_value(value) for value in values], copy=copy)


def _object_array(values: Sequence[object | None], *, copy: bool) -> ObjectArray:
    array = np.asarray(values, dtype=object)
    if copy:
        array = array.copy()
    array.setflags(write=False)
    return array


def _immutable_object_array(values: ObjectArray) -> ObjectArray:
    array = np.asarray(values, dtype=object).copy()
    array.setflags(write=False)
    return array


def _immutable_float_array(values: FloatArray) -> FloatArray:
    array = np.asarray(values, dtype=np.float64).copy()
    array.setflags(write=False)
    return array


def _required_text(value: object | None, field_name: str) -> str:
    text = _optional_text(value)
    if text is None:
        raise RraoInputError("non-empty text is required", field=field_name)
    return text


def _optional_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _required_float(value: object, field_name: str) -> float:
    if value is None:
        raise RraoInputError("value must be numeric", field=field_name)
    try:
        number = float(cast(Any, value))
    except (TypeError, ValueError) as exc:
        raise RraoInputError("value must be numeric", field=field_name) from exc
    if not math.isfinite(number):
        raise RraoInputError("value must be finite", field=field_name)
    return number


def _optional_float(value: object | None) -> float:
    if value is None:
        return math.nan
    if isinstance(value, float) and math.isnan(value):
        return math.nan
    if isinstance(value, str) and not value.strip():
        return math.nan
    return _required_float(value, "optional numeric field")


def _optional_int(value: object | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    if isinstance(value, (bool, np.bool_)):
        raise RraoInputError("underlying count must be an integer", field="underlying_count")
    if isinstance(value, (int, np.integer)):
        if value < 0:
            raise RraoInputError(
                "underlying count must be non-negative",
                field="underlying_count",
            )
        return int(value)
    raise RraoInputError("underlying count must be an integer", field="underlying_count")


def _bool_value(value: object) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n", ""}:
        return False
    raise RraoInputError(f"boolean field contains unsupported value: {value!r}")


def _optional_bool_value(value: object | None) -> bool | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return _bool_value(value)


def _coerce_enum_value(
    value: object | None,
    enum_type: type[EnumT],
    field_name: str,
) -> str:
    text = _required_text(value, field_name)
    try:
        return enum_type(text).value
    except ValueError as exc:
        raise RraoInputError(f"invalid {field_name}", field=field_name) from exc


def _freeze_source_column_maps(
    values: Sequence[Sequence[tuple[str, str]]] | None,
    row_count: int,
) -> tuple[tuple[tuple[str, str], ...], ...]:
    if values is None:
        return tuple(() for _ in range(row_count))
    frozen: list[tuple[tuple[str, str], ...]] = []
    for row in values:
        pairs: list[tuple[str, str]] = []
        for source, target in row:
            pairs.append(
                (
                    _required_text(source, "lineage.source_column_map.source"),
                    _required_text(target, "lineage.source_column_map.canonical"),
                )
            )
        frozen.append(tuple(pairs))
    return tuple(frozen)


def _freeze_citations(
    values: Sequence[Sequence[str]] | None,
    row_count: int,
) -> tuple[tuple[str, ...], ...]:
    if values is None:
        return tuple(() for _ in range(row_count))
    frozen: list[tuple[str, ...]] = []
    for row in values:
        citations: list[str] = []
        for item in row:
            if not isinstance(item, str):
                raise RraoInputError("non-empty text is required", field="citations")
            citation = item.strip()
            if citation == "":
                raise RraoInputError("non-empty text is required", field="citations")
            citations.append(citation)
        frozen.append(tuple(citations))
    return tuple(frozen)


__all__ = [
    "RraoBatchCapitalCalculation",
    "RraoPositionBatch",
    "build_rrao_batch_from_columns",
    "build_rrao_batch_from_positions",
    "calculate_rrao_capital_from_batch",
    "input_hash_for_rrao_batch",
]
