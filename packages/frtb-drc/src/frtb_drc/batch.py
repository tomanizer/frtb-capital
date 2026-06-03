"""Package-owned DRC batches for high-volume DRC kernels."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from itertools import count
from typing import Any, cast

import frtb_common.batch_arrays as _batch_arrays
import numpy as np
from frtb_common import jsonable

from frtb_drc._batch_columns import (
    BoolArray,
    ColumnInput,
    FloatArray,
    NullableColumnInput,
    ObjectArray,
    _bool_array,
    _enum_array,
    _freeze_citation_ids,
    _freeze_source_column_maps,
    _nullable_enum_array,
    _optional_float_array,
    _optional_text_array,
    _require_lengths,
    _required_float_array,
    _required_text_array,
    _text_array_with_default,
)
from frtb_drc._identifiers import slug_path as _slug
from frtb_drc._netting_helpers import (
    bounded_rejected_group_offsets as _bounded_rejected_group_offsets,
)
from frtb_drc._netting_helpers import (
    risk_weights_for_net_jtd as _risk_weights_for_net_jtd,
)
from frtb_drc._validation_utils import optional_text as _optional_text
from frtb_drc._validation_utils import require_text as _required_text
from frtb_drc._version import __version__
from frtb_drc.attribution import calculate_drc_attribution
from frtb_drc.audit import validate_reconciliation
from frtb_drc.capital import CapitalInput, calculate_category_drc
from frtb_drc.ctp import CtpCapitalInput, calculate_ctp_category_drc
from frtb_drc.data_models import (
    BranchMetadata,
    BranchType,
    CategoryDrc,
    CreditQuality,
    DefaultDirection,
    DrcCalculationContext,
    DrcCapitalResult,
    DrcFxConversion,
    DrcFxRate,
    DrcInstrumentType,
    DrcPosition,
    DrcRiskClass,
    DrcSeniority,
    NetJtd,
    RejectedOffset,
)
from frtb_drc.fair_value_cap import (
    fair_value_cap_hash_payload,
    used_fair_value_cap_evidence_for_position_ids,
    validate_fair_value_cap_evidence,
)
from frtb_drc.fx import (
    fx_branch_metadata,
    fx_citation_ids,
    fx_conversion_records,
    input_hash_with_fx,
    require_fx_rate,
    validate_fx_rates,
)
from frtb_drc.reference_data import (
    get_lgd_rule,
    get_maturity_policy,
    get_risk_weight_rule,
    iter_lgd_rules,
)
from frtb_drc.regimes import DrcRuleProfile, ensure_risk_class_supported, get_rule_profile
from frtb_drc.risk_weight_evidence import (
    effective_risk_weights,
    risk_weight_evidence_hash_payload,
    used_risk_weight_evidence_for_position_ids,
)
from frtb_drc.securitisation import (
    SecuritisationNonCtpCapitalInput,
    calculate_securitisation_non_ctp_category_drc,
)
from frtb_drc.validation import (
    BASEL_MAR22_PROFILE_ID,
    US_NPR_2_0_PROFILE_ID,
    DrcInputError,
    chargeable_non_securitisation_bucket_keys,
    chargeable_securitisation_non_ctp_bucket_keys,
    ensure_chargeable_credit_quality,
    ensure_chargeable_non_securitisation_bucket,
    ensure_chargeable_securitisation_non_ctp_bucket,
    validate_positions,
)

_FORMULA_CITATIONS = ("BASEL_MAR22_11", "BASEL_MAR22_13")
_NETTING_CITATION = "US_NPR_210_B_2"
_ZERO_CATEGORY_CITATION = "US_NPR_210_B_3_III"
_SEC_NON_CTP_GROSS_CITATIONS = ("US_NPR_210_C_1", "BASEL_MAR22_27")
_SEC_NON_CTP_FAIR_VALUE_CAP_CITATIONS = ("US_NPR_210_C_3_III", "BASEL_MAR22_34")
_SEC_NON_CTP_NETTING_CITATIONS = (
    "US_NPR_210_C_2",
    "BASEL_MAR22_28",
    "BASEL_MAR22_29",
    "BASEL_MAR22_30",
)
_SEC_NON_CTP_BATCH_CITATIONS = (
    *_SEC_NON_CTP_GROSS_CITATIONS,
    *_SEC_NON_CTP_NETTING_CITATIONS,
    "US_NPR_210_C_3_I_II",
    "US_NPR_210_C_3_III",
    "US_NPR_210_C_3_IV",
    "BASEL_MAR22_31",
    "BASEL_MAR22_32",
    "BASEL_MAR22_33",
    "BASEL_MAR22_34",
    "BASEL_MAR22_35",
)
_BASEL_SEC_NON_CTP_GROSS_CITATIONS = ("BASEL_MAR22_27",)
_BASEL_SEC_NON_CTP_FAIR_VALUE_CAP_CITATIONS = ("BASEL_MAR22_34",)
_BASEL_SEC_NON_CTP_NETTING_CITATIONS = (
    "BASEL_MAR22_28",
    "BASEL_MAR22_29",
    "BASEL_MAR22_30",
)
_BASEL_SEC_NON_CTP_BATCH_CITATIONS = (
    *_BASEL_SEC_NON_CTP_GROSS_CITATIONS,
    *_BASEL_SEC_NON_CTP_NETTING_CITATIONS,
    "BASEL_MAR22_31",
    "BASEL_MAR22_32",
    "BASEL_MAR22_33",
    "BASEL_MAR22_34",
    "BASEL_MAR22_35",
)
_CTP_GROSS_CITATIONS = ("US_NPR_210_D_1", "BASEL_MAR22_36", "BASEL_MAR22_37")
_CTP_NETTING_CITATIONS = ("US_NPR_210_D_2", "BASEL_MAR22_39")
_CTP_BATCH_CITATIONS = (
    *_CTP_GROSS_CITATIONS,
    *_CTP_NETTING_CITATIONS,
    "US_NPR_210_D_3_I_III",
    "US_NPR_210_D_3_IV",
    "US_NPR_210_D_3_IV_D",
    "US_NPR_210_D_3_V",
    "BASEL_MAR22_40",
    "BASEL_MAR22_41",
    "BASEL_MAR22_44",
    "BASEL_MAR22_45",
)

_SENIORITY_RANK: dict[DrcSeniority, int] = {
    DrcSeniority.COVERED_BOND: 0,
    DrcSeniority.GSE_GUARANTEED: 0,
    DrcSeniority.SENIOR_DEBT: 1,
    DrcSeniority.GSE_ISSUED_NOT_GUARANTEED: 1,
    DrcSeniority.PSE: 1,
    DrcSeniority.NON_SENIOR_DEBT: 2,
    DrcSeniority.EQUITY: 3,
    DrcSeniority.NOT_RECOVERY_LINKED: 4,
}


@dataclass(frozen=True)
class DrcPositionBatch:
    """Kernel-facing non-securitisation DRC input batch."""

    position_ids: ObjectArray
    source_row_ids: ObjectArray
    desk_ids: ObjectArray
    legal_entities: ObjectArray
    risk_classes: ObjectArray
    instrument_types: ObjectArray
    default_directions: ObjectArray
    issuer_ids: ObjectArray
    tranche_ids: ObjectArray
    index_series_ids: ObjectArray
    bucket_keys: ObjectArray
    seniorities: ObjectArray
    credit_qualities: ObjectArray
    notionals: FloatArray
    market_values: FloatArray
    cumulative_pnls: FloatArray
    maturity_years: FloatArray
    currencies: ObjectArray
    lgd_overrides: FloatArray
    is_defaulted: BoolArray
    is_gse: BoolArray
    is_pse: BoolArray
    is_covered_bond: BoolArray
    lineage_source_systems: ObjectArray
    lineage_source_files: ObjectArray
    lineage_present: BoolArray
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...]
    citation_ids: tuple[tuple[str, ...], ...]
    input_hash: str
    source_hash: str | None = None
    handoff_hash: str | None = None
    diagnostics: tuple[Mapping[str, object], ...] = ()

    @property
    def row_count(self) -> int:
        return int(self.position_ids.shape[0])


@dataclass(frozen=True)
class DrcBatchCapitalCalculation:
    """DRC batch calculation with array intermediates and row API-compatible capital."""

    result: DrcCapitalResult
    gross_jtd: FloatArray
    maturity_weights: FloatArray
    scaled_jtd: FloatArray
    accepted_row_dataclasses_materialized: int = 0


def build_drc_nonsec_batch_from_positions(
    positions: Iterable[DrcPosition],
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> DrcPositionBatch:
    """
    Build a DRC batch from existing canonical position rows.

    This is a compatibility bridge for callers that already hold dataclasses.
    High-volume adapters should build from handoffs or columns.
    """

    validated = _sorted_positions(validate_positions(positions, profile_id=profile_id))
    if not validated:
        raise DrcInputError("DRC batch requires at least one position")
    return build_drc_nonsec_batch_from_columns(
        position_ids=[position.position_id for position in validated],
        source_row_ids=[position.source_row_id for position in validated],
        desk_ids=[position.desk_id for position in validated],
        legal_entities=[position.legal_entity for position in validated],
        risk_classes=[DrcRiskClass(position.risk_class).value for position in validated],
        instrument_types=[
            DrcInstrumentType(position.instrument_type).value for position in validated
        ],
        default_directions=[
            DefaultDirection(position.default_direction).value for position in validated
        ],
        issuer_ids=[position.issuer_id for position in validated],
        tranche_ids=[position.tranche_id for position in validated],
        index_series_ids=[position.index_series_id for position in validated],
        bucket_keys=[position.bucket_key for position in validated],
        seniorities=[
            None if position.seniority is None else DrcSeniority(position.seniority).value
            for position in validated
        ],
        credit_qualities=[
            None
            if position.credit_quality is None
            else CreditQuality(position.credit_quality).value
            for position in validated
        ],
        notionals=[position.notional for position in validated],
        market_values=[position.market_value for position in validated],
        cumulative_pnls=[position.cumulative_pnl for position in validated],
        maturity_years=[position.maturity_years for position in validated],
        currencies=[position.currency for position in validated],
        lgd_overrides=[position.lgd_override for position in validated],
        is_defaulted=[position.is_defaulted for position in validated],
        is_gse=[position.is_gse for position in validated],
        is_pse=[position.is_pse for position in validated],
        is_covered_bond=[position.is_covered_bond for position in validated],
        lineage_source_systems=[
            "" if position.lineage is None else position.lineage.source_system
            for position in validated
        ],
        lineage_source_files=[
            "" if position.lineage is None else position.lineage.source_file
            for position in validated
        ],
        lineage_present=[position.lineage is not None for position in validated],
        source_column_maps=[
            ()
            if position.lineage is None
            else tuple(sorted(position.lineage.source_column_map.items()))
            for position in validated
        ],
        citation_ids=[position.citation_ids for position in validated],
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
        profile_id=profile_id,
    )


def build_drc_nonsec_batch_from_columns(
    *,
    position_ids: ColumnInput,
    source_row_ids: ColumnInput,
    desk_ids: ColumnInput,
    legal_entities: ColumnInput,
    risk_classes: ColumnInput,
    instrument_types: ColumnInput,
    default_directions: ColumnInput,
    issuer_ids: NullableColumnInput | None,
    tranche_ids: NullableColumnInput | None = None,
    index_series_ids: NullableColumnInput | None = None,
    bucket_keys: NullableColumnInput,
    seniorities: NullableColumnInput | None,
    credit_qualities: NullableColumnInput | None,
    notionals: ColumnInput,
    market_values: NullableColumnInput | None = None,
    cumulative_pnls: NullableColumnInput | None = None,
    maturity_years: ColumnInput,
    currencies: ColumnInput,
    lgd_overrides: NullableColumnInput | None = None,
    is_defaulted: ColumnInput | None = None,
    is_gse: ColumnInput | None = None,
    is_pse: ColumnInput | None = None,
    is_covered_bond: ColumnInput | None = None,
    lineage_source_systems: ColumnInput | None = None,
    lineage_source_files: ColumnInput | None = None,
    lineage_present: ColumnInput | None = None,
    source_column_maps: Sequence[Sequence[tuple[str, str]]] | None = None,
    citation_ids: Sequence[Sequence[str]] | None = None,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    copy_arrays: bool = True,
    _expected_risk_class: DrcRiskClass = DrcRiskClass.NON_SECURITISATION,
    profile_id: str = US_NPR_2_0_PROFILE_ID,
) -> DrcPositionBatch:
    """Build a validated non-securitisation DRC batch from columnar inputs."""

    row_count = len(position_ids)
    if row_count == 0:
        raise DrcInputError("DRC batch requires at least one position")
    _require_lengths(
        row_count,
        source_row_ids=source_row_ids,
        desk_ids=desk_ids,
        legal_entities=legal_entities,
        risk_classes=risk_classes,
        instrument_types=instrument_types,
        default_directions=default_directions,
        bucket_keys=bucket_keys,
        notionals=notionals,
        maturity_years=maturity_years,
        currencies=currencies,
    )
    optional_lengths = {
        "tranche_ids": tranche_ids,
        "index_series_ids": index_series_ids,
        "issuer_ids": issuer_ids,
        "market_values": market_values,
        "cumulative_pnls": cumulative_pnls,
        "lgd_overrides": lgd_overrides,
        "seniorities": seniorities,
        "credit_qualities": credit_qualities,
        "is_defaulted": is_defaulted,
        "is_gse": is_gse,
        "is_pse": is_pse,
        "is_covered_bond": is_covered_bond,
        "lineage_source_systems": lineage_source_systems,
        "lineage_source_files": lineage_source_files,
        "lineage_present": lineage_present,
        "source_column_maps": source_column_maps,
        "citation_ids": citation_ids,
    }
    for name, values in optional_lengths.items():
        if values is not None and len(values) != row_count:
            raise DrcInputError(f"{name} length does not match position_ids")

    lineage_present_default = (
        lineage_source_systems is not None
        or lineage_source_files is not None
        or source_column_maps is not None
    )
    batch = DrcPositionBatch(
        position_ids=_required_text_array(position_ids, "position_id", copy=copy_arrays),
        source_row_ids=_required_text_array(source_row_ids, "source_row_id", copy=copy_arrays),
        desk_ids=_required_text_array(desk_ids, "desk_id", copy=copy_arrays),
        legal_entities=_required_text_array(legal_entities, "legal_entity", copy=copy_arrays),
        risk_classes=_enum_array(risk_classes, DrcRiskClass, "risk_class", copy=copy_arrays),
        instrument_types=_enum_array(
            instrument_types,
            DrcInstrumentType,
            "instrument_type",
            copy=copy_arrays,
        ),
        default_directions=_enum_array(
            default_directions,
            DefaultDirection,
            "default_direction",
            copy=copy_arrays,
        ),
        issuer_ids=_optional_text_array(issuer_ids, row_count, copy=copy_arrays),
        tranche_ids=_optional_text_array(tranche_ids, row_count, copy=copy_arrays),
        index_series_ids=_optional_text_array(index_series_ids, row_count, copy=copy_arrays),
        bucket_keys=_required_text_array(bucket_keys, "bucket_key", copy=copy_arrays),
        seniorities=_nullable_enum_array(
            seniorities,
            DrcSeniority,
            "seniority",
            row_count,
            copy=copy_arrays,
        ),
        credit_qualities=_nullable_enum_array(
            credit_qualities,
            CreditQuality,
            "credit_quality",
            row_count,
            copy=copy_arrays,
        ),
        notionals=_required_float_array(notionals, "notional", copy=copy_arrays),
        market_values=_optional_float_array(market_values, row_count, copy=copy_arrays),
        cumulative_pnls=_optional_float_array(cumulative_pnls, row_count, copy=copy_arrays),
        maturity_years=_required_float_array(maturity_years, "maturity_years", copy=copy_arrays),
        currencies=_required_text_array(currencies, "currency", copy=copy_arrays),
        lgd_overrides=_optional_float_array(lgd_overrides, row_count, copy=copy_arrays),
        is_defaulted=_bool_array(is_defaulted, row_count, copy=copy_arrays),
        is_gse=_bool_array(is_gse, row_count, copy=copy_arrays),
        is_pse=_bool_array(is_pse, row_count, copy=copy_arrays),
        is_covered_bond=_bool_array(is_covered_bond, row_count, copy=copy_arrays),
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
        lineage_present=_bool_array(
            lineage_present,
            row_count,
            default=lineage_present_default,
            copy=copy_arrays,
        ),
        source_column_maps=_freeze_source_column_maps(source_column_maps, row_count),
        citation_ids=_freeze_citation_ids(citation_ids, row_count),
        input_hash="",
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=tuple(dict(item) for item in diagnostics),
    )
    _validate_batch(batch, expected_risk_class=_expected_risk_class, profile_id=profile_id)
    return replace(batch, input_hash=input_hash_for_drc_batch(batch))


def build_drc_securitisation_non_ctp_batch_from_columns(
    *,
    position_ids: ColumnInput,
    source_row_ids: ColumnInput,
    desk_ids: ColumnInput,
    legal_entities: ColumnInput,
    risk_classes: ColumnInput,
    instrument_types: ColumnInput,
    default_directions: ColumnInput,
    issuer_ids: NullableColumnInput | None,
    tranche_ids: NullableColumnInput | None = None,
    index_series_ids: NullableColumnInput | None = None,
    bucket_keys: NullableColumnInput,
    seniorities: NullableColumnInput | None = None,
    credit_qualities: NullableColumnInput | None = None,
    notionals: ColumnInput,
    market_values: NullableColumnInput | None = None,
    cumulative_pnls: NullableColumnInput | None = None,
    maturity_years: ColumnInput,
    currencies: ColumnInput,
    lgd_overrides: NullableColumnInput | None = None,
    is_defaulted: ColumnInput | None = None,
    is_gse: ColumnInput | None = None,
    is_pse: ColumnInput | None = None,
    is_covered_bond: ColumnInput | None = None,
    lineage_source_systems: ColumnInput | None = None,
    lineage_source_files: ColumnInput | None = None,
    lineage_present: ColumnInput | None = None,
    source_column_maps: Sequence[Sequence[tuple[str, str]]] | None = None,
    citation_ids: Sequence[Sequence[str]] | None = None,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    copy_arrays: bool = True,
) -> DrcPositionBatch:
    """Build a validated securitisation non-CTP DRC batch from columnar inputs."""

    return build_drc_nonsec_batch_from_columns(
        position_ids=position_ids,
        source_row_ids=source_row_ids,
        desk_ids=desk_ids,
        legal_entities=legal_entities,
        risk_classes=risk_classes,
        instrument_types=instrument_types,
        default_directions=default_directions,
        issuer_ids=issuer_ids,
        tranche_ids=tranche_ids,
        index_series_ids=index_series_ids,
        bucket_keys=bucket_keys,
        seniorities=seniorities,
        credit_qualities=credit_qualities,
        notionals=notionals,
        market_values=market_values,
        cumulative_pnls=cumulative_pnls,
        maturity_years=maturity_years,
        currencies=currencies,
        lgd_overrides=lgd_overrides,
        is_defaulted=is_defaulted,
        is_gse=is_gse,
        is_pse=is_pse,
        is_covered_bond=is_covered_bond,
        lineage_source_systems=lineage_source_systems,
        lineage_source_files=lineage_source_files,
        lineage_present=lineage_present,
        source_column_maps=source_column_maps,
        citation_ids=citation_ids,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
        copy_arrays=copy_arrays,
        _expected_risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
        profile_id=US_NPR_2_0_PROFILE_ID,
    )


def build_drc_ctp_batch_from_columns(
    *,
    position_ids: ColumnInput,
    source_row_ids: ColumnInput,
    desk_ids: ColumnInput,
    legal_entities: ColumnInput,
    risk_classes: ColumnInput,
    instrument_types: ColumnInput,
    default_directions: ColumnInput,
    issuer_ids: NullableColumnInput | None,
    tranche_ids: NullableColumnInput | None = None,
    index_series_ids: NullableColumnInput | None = None,
    bucket_keys: NullableColumnInput,
    seniorities: NullableColumnInput | None = None,
    credit_qualities: NullableColumnInput | None = None,
    notionals: ColumnInput,
    market_values: NullableColumnInput | None = None,
    cumulative_pnls: NullableColumnInput | None = None,
    maturity_years: ColumnInput,
    currencies: ColumnInput,
    lgd_overrides: NullableColumnInput | None = None,
    is_defaulted: ColumnInput | None = None,
    is_gse: ColumnInput | None = None,
    is_pse: ColumnInput | None = None,
    is_covered_bond: ColumnInput | None = None,
    lineage_source_systems: ColumnInput | None = None,
    lineage_source_files: ColumnInput | None = None,
    lineage_present: ColumnInput | None = None,
    source_column_maps: Sequence[Sequence[tuple[str, str]]] | None = None,
    citation_ids: Sequence[Sequence[str]] | None = None,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    copy_arrays: bool = True,
) -> DrcPositionBatch:
    """Build a validated CTP DRC batch from columnar inputs."""

    return build_drc_nonsec_batch_from_columns(
        position_ids=position_ids,
        source_row_ids=source_row_ids,
        desk_ids=desk_ids,
        legal_entities=legal_entities,
        risk_classes=risk_classes,
        instrument_types=instrument_types,
        default_directions=default_directions,
        issuer_ids=issuer_ids,
        tranche_ids=tranche_ids,
        index_series_ids=index_series_ids,
        bucket_keys=bucket_keys,
        seniorities=seniorities,
        credit_qualities=credit_qualities,
        notionals=notionals,
        market_values=market_values,
        cumulative_pnls=cumulative_pnls,
        maturity_years=maturity_years,
        currencies=currencies,
        lgd_overrides=lgd_overrides,
        is_defaulted=is_defaulted,
        is_gse=is_gse,
        is_pse=is_pse,
        is_covered_bond=is_covered_bond,
        lineage_source_systems=lineage_source_systems,
        lineage_source_files=lineage_source_files,
        lineage_present=lineage_present,
        source_column_maps=source_column_maps,
        citation_ids=citation_ids,
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
        copy_arrays=copy_arrays,
        _expected_risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
    )


def input_hash_for_drc_batch(batch: DrcPositionBatch) -> str:
    """Hash canonical DRC batch inputs in deterministic position-id order."""

    payload = [_position_payload(batch, index) for index in _sorted_indices(batch)]
    return _hash_payload(payload)


def calculate_drc_capital_from_batch(
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
) -> DrcBatchCapitalCalculation:
    """Calculate supported DRC capital from a columnar batch."""

    if not isinstance(batch, DrcPositionBatch):
        raise DrcInputError("batch must be DrcPositionBatch")
    _validate_context(context)
    profile = get_rule_profile(context.profile_id)
    risk_class = _batch_risk_class(batch)
    _validate_supported_batch_run(batch, context=context, profile=profile)
    calculation_batch, fx_conversions = _convert_batch_to_base_currency(
        batch,
        context=context,
    )

    if risk_class is DrcRiskClass.NON_SECURITISATION:
        gross_jtd, lgd_citations = _gross_jtd_array(
            calculation_batch,
            profile_id=profile.profile_id,
        )
        maturity_weights, scaled_jtd, maturity_citation = _scaled_jtd_array(
            calculation_batch,
            gross_jtd,
            profile_id=profile.profile_id,
        )
        net_jtds = _calculate_net_jtds_from_arrays(calculation_batch, gross_jtd, scaled_jtd)
        capital_inputs = _capital_inputs(calculation_batch, net_jtds)
        category = (
            calculate_category_drc(capital_inputs, profile_id=profile.profile_id)
            if capital_inputs
            else _zero_nonsec_category()
        )
        formula_citations = (
            *_FORMULA_CITATIONS,
            maturity_citation,
            *lgd_citations,
            *((_NETTING_CITATION,) if net_jtds else ()),
        )
    elif risk_class is DrcRiskClass.SECURITISATION_NON_CTP:
        gross_jtd = _securitisation_non_ctp_gross_jtd_array(calculation_batch, context=context)
        maturity_weights, scaled_jtd, maturity_citation = _scaled_jtd_array(
            calculation_batch,
            gross_jtd,
            profile_id=profile.profile_id,
        )
        net_jtds = _calculate_securitisation_non_ctp_net_jtds_from_arrays(
            calculation_batch,
            gross_jtd,
            scaled_jtd,
            context=context,
        )
        sec_capital_inputs = _securitisation_non_ctp_capital_inputs_from_batch(
            net_jtds,
            risk_weights=effective_risk_weights(
                context,
                risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
            ),
        )
        category = calculate_securitisation_non_ctp_category_drc(
            sec_capital_inputs,
            profile_id=profile.profile_id,
        )
        formula_citations = (
            *_sec_non_ctp_batch_citations(profile.profile_id),
            *_batch_fair_value_cap_citations(calculation_batch, context=context),
            maturity_citation,
        )
    elif risk_class is DrcRiskClass.CORRELATION_TRADING_PORTFOLIO:
        gross_jtd = _market_value_gross_jtd_array(calculation_batch)
        maturity_weights, scaled_jtd, maturity_citation = _scaled_jtd_array(
            calculation_batch,
            gross_jtd,
            profile_id=profile.profile_id,
        )
        net_jtds = _calculate_ctp_net_jtds_from_arrays(
            calculation_batch,
            gross_jtd,
            scaled_jtd,
            context=context,
        )
        ctp_capital_inputs = _ctp_capital_inputs_from_batch(
            net_jtds,
            risk_weights=effective_risk_weights(
                context,
                risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
            ),
        )
        category = calculate_ctp_category_drc(ctp_capital_inputs, profile_id=profile.profile_id)
        formula_citations = (*_CTP_BATCH_CITATIONS, maturity_citation)
    else:  # pragma: no cover - _batch_risk_class only returns known enum values.
        raise DrcInputError(f"unsupported DRC batch risk_class: {risk_class.value}")

    input_hash = _context_input_hash_for_batch(
        calculation_batch.input_hash,
        calculation_batch,
        context=context,
        risk_class=risk_class,
    )
    result = DrcCapitalResult(
        result_id=f"drc-{_slug(context.run_id)}-{input_hash[:12]}",
        run_id=context.run_id,
        calculation_date=context.calculation_date,
        base_currency=context.base_currency,
        profile_id=profile.profile_id,
        profile_hash=profile.content_hash,
        input_hash=input_hash,
        categories=(category,),
        total_drc=category.capital,
        citations=_collect_batch_citations(
            calculation_batch,
            category=category,
            net_jtds=net_jtds,
            formula_citations=formula_citations,
            fx_citations=fx_citation_ids(fx_conversions),
            profile_id=profile.profile_id,
        ),
        warnings=(),
        branch_metadata=(
            BranchMetadata(
                branch_id=f"drc-{_slug(risk_class.value)}-batch-api",
                branch_type=BranchType.NORMAL,
                source_id=profile.profile_id,
                selected=True,
                reason=(
                    f"batch API executed supported {risk_class.value} path; "
                    "attribution records are calculated on API-compatible net JTDs"
                ),
                citations=_batch_api_citations(profile.profile_id, risk_class),
            ),
            *_fair_value_cap_branch_metadata_for_batch(
                calculation_batch,
                context=context,
                risk_class=risk_class,
            ),
            *fx_branch_metadata(fx_conversions),
        ),
        package_name="frtb-drc",
        package_version=__version__,
        input_count=calculation_batch.row_count,
        rejected_input_count=len(calculation_batch.diagnostics),
        input_positions=(),
        gross_jtds=(),
        maturity_scaled_jtds=(),
        net_jtds=net_jtds,
        fx_conversions=fx_conversions,
        risk_weight_evidence=used_risk_weight_evidence_for_position_ids(
            (cast(str, position_id) for position_id in calculation_batch.position_ids),
            context,
            risk_class=risk_class,
        )
        if risk_class
        in {
            DrcRiskClass.SECURITISATION_NON_CTP,
            DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
        }
        else (),
        fair_value_cap_evidence=used_fair_value_cap_evidence_for_position_ids(
            (cast(str, position_id) for position_id in calculation_batch.position_ids),
            context,
        )
        if risk_class is DrcRiskClass.SECURITISATION_NON_CTP
        else (),
    )
    result = replace(
        result,
        attribution_records=calculate_drc_attribution(
            result,
            risk_weights_by_position=_batch_risk_weights_by_position(
                calculation_batch,
                context=context,
                risk_class=risk_class,
            ),
        ),
    )
    validate_reconciliation(result)
    return DrcBatchCapitalCalculation(
        result=result,
        gross_jtd=_batch_arrays.readonly_array(
            np.asarray(gross_jtd, dtype=np.float64).copy(),
            copy=False,
        ),
        maturity_weights=_batch_arrays.readonly_array(
            np.asarray(maturity_weights, dtype=np.float64).copy(),
            copy=False,
        ),
        scaled_jtd=_batch_arrays.readonly_array(
            np.asarray(scaled_jtd, dtype=np.float64).copy(),
            copy=False,
        ),
        accepted_row_dataclasses_materialized=0,
    )


def _validate_context(context: DrcCalculationContext) -> None:
    if context.run_id.strip() == "":
        raise DrcInputError("run_id must be non-empty")
    if context.base_currency.strip() == "":
        raise DrcInputError("base_currency must be non-empty")
    if context.profile_id.strip() == "":
        raise DrcInputError("profile_id must be non-empty")
    if context.citation_policy.strip() == "":
        raise DrcInputError("citation_policy must be non-empty")
    if context.citation_policy.strip().lower() != "strict":
        raise DrcInputError(f"unsupported citation_policy: {context.citation_policy}")
    validate_fx_rates(context)
    effective_risk_weights(context, risk_class=DrcRiskClass.SECURITISATION_NON_CTP)
    validate_fair_value_cap_evidence(
        context.securitisation_non_ctp_fair_value_cap_evidence,
        context=context,
    )
    _validate_context_text_map(
        context.securitisation_non_ctp_offset_groups,
        field_name="context.securitisation_non_ctp_offset_groups",
    )
    effective_risk_weights(context, risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO)
    _validate_context_text_map(context.ctp_offset_groups, field_name="context.ctp_offset_groups")


def _validate_context_risk_weight_map(values: Mapping[str, float], *, field_name: str) -> None:
    for position_id, risk_weight in values.items():
        _required_text(position_id, f"{field_name} position_id")
        _coerce_finite_non_negative_float(
            risk_weight,
            field_name=f"{field_name}[{position_id!r}]",
        )


def _validate_context_text_map(values: Mapping[str, str], *, field_name: str) -> None:
    for position_id, value in values.items():
        _required_text(position_id, f"{field_name} position_id")
        _required_text(value, f"{field_name}[{position_id!r}]")


def _validate_supported_batch_run(
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
    profile: DrcRuleProfile,
) -> None:
    risk_class = _batch_risk_class(batch)
    ensure_risk_class_supported(profile, risk_class)
    scoped_desk_id = context.desk_id.strip()
    scoped_legal_entity = context.legal_entity.strip()
    if scoped_desk_id:
        _raise_first_mismatch(
            batch.desk_ids,
            scoped_desk_id,
            message=lambda index: (
                f"position {batch.position_ids[index]} desk_id {batch.desk_ids[index]} "
                f"does not match context desk_id {scoped_desk_id}"
            ),
        )
    if scoped_legal_entity:
        _raise_first_mismatch(
            batch.legal_entities,
            scoped_legal_entity,
            message=lambda index: (
                f"position {batch.position_ids[index]} legal_entity "
                f"{batch.legal_entities[index]} does not match context legal_entity "
                f"{scoped_legal_entity}"
            ),
        )
    if risk_class is DrcRiskClass.SECURITISATION_NON_CTP:
        risk_weights = effective_risk_weights(
            context,
            risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
        )
        _validate_context_position_map(
            batch,
            risk_weights,
            field_name="context.securitisation_non_ctp_risk_weights",
        )
        _validate_context_position_map(
            batch,
            context.securitisation_non_ctp_offset_groups,
            field_name="context.securitisation_non_ctp_offset_groups",
            require_all=False,
        )
        _validate_context_position_map(
            batch,
            context.securitisation_non_ctp_fair_value_cap_evidence,
            field_name="context.securitisation_non_ctp_fair_value_cap_evidence",
            require_all=False,
        )
    elif risk_class is DrcRiskClass.CORRELATION_TRADING_PORTFOLIO:
        risk_weights = effective_risk_weights(
            context,
            risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
        )
        _validate_context_position_map(
            batch,
            risk_weights,
            field_name="context.ctp_risk_weights",
        )
        _validate_context_position_map(
            batch,
            context.ctp_offset_groups,
            field_name="context.ctp_offset_groups",
            require_all=False,
        )


def _batch_risk_class(batch: DrcPositionBatch) -> DrcRiskClass:
    unique = tuple(sorted(np.unique(batch.risk_classes)))
    if len(unique) != 1:
        raise DrcInputError(
            "DRC batch calculation requires one risk_class; mixed risk classes must "
            "be split into class-specific batches"
        )
    return DrcRiskClass(cast(str, unique[0]))


def _validate_context_position_map(
    batch: DrcPositionBatch,
    values: Mapping[str, object],
    *,
    field_name: str,
    require_all: bool = True,
) -> None:
    position_ids = {cast(str, position_id) for position_id in batch.position_ids.tolist()}
    keys = {str(position_id) for position_id in values}
    if require_all:
        missing = sorted(position_ids - keys)
        if missing:
            raise DrcInputError(f"{field_name} is required for positions: " + ", ".join(missing))
    unused = sorted(keys - position_ids)
    if unused:
        raise DrcInputError(f"{field_name} contains unused position ids: " + ", ".join(unused))


def _convert_batch_to_base_currency(
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
) -> tuple[DrcPositionBatch, tuple[DrcFxConversion, ...]]:
    conversion_mask = batch.currencies != context.base_currency
    if not bool(np.any(conversion_mask)):
        return batch, ()

    rates = np.ones(batch.row_count, dtype=np.float64)
    used_rates: dict[str, DrcFxRate] = {}
    counts: dict[str, int] = {}
    for raw_currency in sorted(np.unique(batch.currencies[conversion_mask])):
        currency = cast(str, raw_currency)
        first_index = int(np.nonzero(batch.currencies == currency)[0][0])
        rate = require_fx_rate(
            context,
            source_currency=currency,
            position_id=cast(str, batch.position_ids[first_index]),
        )
        mask = batch.currencies == currency
        rates[mask] = rate.rate
        used_rates[currency] = rate
        counts[currency] = int(np.count_nonzero(mask))

    conversions = fx_conversion_records(used_rates, counts)
    converted_currencies = _batch_arrays.object_array(
        [context.base_currency] * batch.row_count,
        copy=True,
    )
    converted = replace(
        batch,
        notionals=_batch_arrays.readonly_array(
            np.asarray(batch.notionals * rates, dtype=np.float64).copy(),
            copy=False,
        ),
        market_values=_batch_arrays.readonly_array(
            np.asarray(batch.market_values * rates, dtype=np.float64).copy(),
            copy=False,
        ),
        cumulative_pnls=_batch_arrays.readonly_array(
            np.asarray(batch.cumulative_pnls * rates, dtype=np.float64).copy(),
            copy=False,
        ),
        currencies=converted_currencies,
        input_hash=input_hash_with_fx(batch.input_hash, conversions),
    )
    return converted, conversions


def _validate_batch(
    batch: DrcPositionBatch,
    *,
    expected_risk_class: DrcRiskClass,
    profile_id: str,
) -> None:
    if not np.all(batch.risk_classes == expected_risk_class.value):
        unique = ", ".join(str(value) for value in sorted(np.unique(batch.risk_classes)))
        raise DrcInputError(
            "DRC batch builder requires a single supported risk_class "
            f"{expected_risk_class.value}; received {unique}"
        )
    _validate_common_batch_fields(batch)
    if expected_risk_class is DrcRiskClass.NON_SECURITISATION:
        _validate_nonsec_batch(batch, profile_id=profile_id)
    elif expected_risk_class is DrcRiskClass.SECURITISATION_NON_CTP:
        _validate_securitisation_non_ctp_batch(batch)
    elif expected_risk_class is DrcRiskClass.CORRELATION_TRADING_PORTFOLIO:
        _validate_ctp_batch(batch)
    else:  # pragma: no cover - all enum values are handled above.
        raise DrcInputError(f"unsupported DRC batch risk_class: {expected_risk_class.value}")


def _validate_common_batch_fields(batch: DrcPositionBatch) -> None:
    if not np.all(np.isfinite(batch.notionals)):
        raise DrcInputError("notional values must be finite")
    if not np.all(np.isfinite(batch.maturity_years)):
        raise DrcInputError("maturity_years values must be finite")
    if np.any(batch.maturity_years < 0.0):
        raise DrcInputError("maturity_years values must be non-negative")
    for field_name, values in (
        ("market_value", batch.market_values),
        ("cumulative_pnl", batch.cumulative_pnls),
        ("lgd_override", batch.lgd_overrides),
    ):
        mask = ~np.isnan(values)
        if bool(np.any(mask & ~np.isfinite(values))):
            raise DrcInputError(f"{field_name} values must be finite when present")
    if bool(np.any(~batch.lineage_present)):
        raise DrcInputError("lineage is required")
    _raise_first_mismatch(
        batch.lineage_source_systems,
        "",
        mismatch_when_equal=True,
        message=lambda _index: "lineage.source_system must be non-empty",
    )
    _raise_first_mismatch(
        batch.lineage_source_files,
        "",
        mismatch_when_equal=True,
        message=lambda _index: "lineage.source_file must be non-empty",
    )


def _validate_nonsec_batch(batch: DrcPositionBatch, *, profile_id: str) -> None:
    if np.any(batch.issuer_ids == None):  # noqa: E711
        raise DrcInputError("issuer_id is required for non-securitisation DRC batch")
    if np.any(batch.seniorities == None):  # noqa: E711
        raise DrcInputError("seniority is required for non-securitisation DRC batch")
    if np.any(batch.credit_qualities == None):  # noqa: E711
        raise DrcInputError("credit_quality is required for non-securitisation DRC batch")
    bucket_mask = np.isin(
        batch.bucket_keys,
        chargeable_non_securitisation_bucket_keys(profile_id=profile_id),
    )
    if not bool(np.all(bucket_mask)):
        first = int(np.argmax(~bucket_mask))
        ensure_chargeable_non_securitisation_bucket(
            cast(str, batch.bucket_keys[first]),
            position_id=cast(str, batch.position_ids[first]),
            profile_id=profile_id,
        )
    for quality in sorted(set(cast(str, item) for item in batch.credit_qualities.tolist())):
        first = int(np.argmax(batch.credit_qualities == quality))
        ensure_chargeable_credit_quality(
            quality,
            position_id=cast(str, batch.position_ids[first]),
            profile_id=profile_id,
        )


def _validate_securitisation_non_ctp_batch(batch: DrcPositionBatch) -> None:
    if np.any(batch.tranche_ids == None):  # noqa: E711
        raise DrcInputError("tranche_id is required for securitisation non-CTP DRC batch")
    bucket_mask = np.isin(
        batch.bucket_keys,
        chargeable_securitisation_non_ctp_bucket_keys(),
    )
    if not bool(np.all(bucket_mask)):
        first = int(np.argmax(~bucket_mask))
        ensure_chargeable_securitisation_non_ctp_bucket(
            cast(str, batch.bucket_keys[first]),
            position_id=cast(str, batch.position_ids[first]),
        )
    _validate_market_value_default_exposure_batch(
        batch,
        risk_class_label="securitisation non-CTP",
    )


def _validate_ctp_batch(batch: DrcPositionBatch) -> None:
    missing_identity = (
        (batch.tranche_ids == None)  # noqa: E711
        & (batch.index_series_ids == None)  # noqa: E711
        & (batch.issuer_ids == None)  # noqa: E711
    )
    if bool(np.any(missing_identity)):
        first = int(np.nonzero(missing_identity)[0][0])
        raise DrcInputError(
            "CTP positions require tranche_id, index_series_id, or issuer_id: "
            f"{batch.position_ids[first]}"
        )
    _validate_market_value_default_exposure_batch(batch, risk_class_label="CTP")


def _validate_market_value_default_exposure_batch(
    batch: DrcPositionBatch,
    *,
    risk_class_label: str,
) -> None:
    missing_market_value = np.isnan(batch.market_values)
    if bool(np.any(missing_market_value)):
        first = int(np.nonzero(missing_market_value)[0][0])
        raise DrcInputError(
            f"{risk_class_label} position {batch.position_ids[first]} requires market_value"
        )
    if bool(np.any(~np.isnan(batch.lgd_overrides))):
        raise DrcInputError(
            f"{risk_class_label} gross JTD uses market value; lgd_override is not supported"
        )


def _gross_jtd_array(
    batch: DrcPositionBatch,
    *,
    profile_id: str,
) -> tuple[FloatArray, tuple[str, ...]]:
    if bool(np.any(~np.isnan(batch.lgd_overrides))):
        raise DrcInputError("explicit LGD overrides are not supported by the selected profile")

    lgd_rates, citations = _lgd_rate_array(batch, profile_id=profile_id)
    pnl_component = np.empty(batch.row_count, dtype=np.float64)
    has_cumulative = ~np.isnan(batch.cumulative_pnls)
    pnl_component[has_cumulative] = batch.cumulative_pnls[has_cumulative]
    missing_pnl = ~has_cumulative & np.isnan(batch.market_values)
    if bool(np.any(missing_pnl)):
        first = int(np.nonzero(missing_pnl)[0][0])
        raise DrcInputError(
            f"cumulative_pnl or market_value is required for gross JTD: {batch.position_ids[first]}"
        )
    market_indices = ~has_cumulative
    notionals_abs = np.abs(batch.notionals)
    long_mask = batch.default_directions == DefaultDirection.LONG.value
    pnl_component[market_indices & long_mask] = (
        batch.market_values[market_indices & long_mask] - notionals_abs[market_indices & long_mask]
    )
    pnl_component[market_indices & ~long_mask] = (
        notionals_abs[market_indices & ~long_mask]
        - batch.market_values[market_indices & ~long_mask]
    )

    signed_notional = np.where(long_mask, notionals_abs, -notionals_abs)
    raw_jtd = lgd_rates * signed_notional + pnl_component
    gross = np.where(long_mask, np.maximum(raw_jtd, 0.0), np.abs(np.minimum(raw_jtd, 0.0)))
    return gross.astype(np.float64), citations


def _lgd_rate_array(
    batch: DrcPositionBatch,
    *,
    profile_id: str,
) -> tuple[FloatArray, tuple[str, ...]]:
    rule_by_seniority = {
        rule.seniority.value: rule for rule in iter_lgd_rules(profile_id=profile_id)
    }

    lgd_rates = np.empty(batch.row_count, dtype=np.float64)
    citations: set[str] = set()

    defaulted_mask = batch.is_defaulted
    if bool(np.any(defaulted_mask)):
        defaulted_rule = get_lgd_rule(
            DrcSeniority.EQUITY,
            profile_id=profile_id,
            is_defaulted=True,
        )
        lgd_rates[defaulted_mask] = defaulted_rule.lgd_rate
        citations.add(defaulted_rule.citation_id)

    non_defaulted_mask = ~defaulted_mask
    for seniority_value in np.unique(batch.seniorities[non_defaulted_mask]):
        seniority_text = cast(str, seniority_value)
        try:
            rule = rule_by_seniority[seniority_text]
        except KeyError as exc:
            raise DrcInputError(f"missing DRC LGD rule: {profile_id}/{seniority_text}") from exc
        seniority_mask = non_defaulted_mask & (batch.seniorities == seniority_text)
        lgd_rates[seniority_mask] = rule.lgd_rate
        citations.add(rule.citation_id)

    return lgd_rates, tuple(sorted(citations))


def _scaled_jtd_array(
    batch: DrcPositionBatch,
    gross_jtd: FloatArray,
    *,
    profile_id: str,
) -> tuple[FloatArray, FloatArray, str]:
    policy = get_maturity_policy(profile_id)
    effective_maturity = np.maximum(batch.maturity_years, policy.floor_years)
    weights = np.where(
        batch.maturity_years >= policy.full_weight_years,
        1.0,
        effective_maturity / policy.full_weight_years,
    )
    return weights.astype(np.float64), (gross_jtd * weights).astype(np.float64), policy.citation_id


def _market_value_gross_jtd_array(batch: DrcPositionBatch) -> FloatArray:
    return np.abs(batch.market_values).astype(np.float64)


def _securitisation_non_ctp_gross_jtd_array(
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
) -> FloatArray:
    gross_jtd = _market_value_gross_jtd_array(batch)
    evidence = context.securitisation_non_ctp_fair_value_cap_evidence
    if not evidence:
        return gross_jtd
    capped = gross_jtd.copy()
    for index in range(batch.row_count):
        position_id = cast(str, batch.position_ids[index])
        record = evidence.get(position_id)
        if record is None or not record.eligible:
            continue
        if record.fair_value_cap_amount is None:  # pragma: no cover - context validation enforces.
            raise DrcInputError(
                f"fair_value_cap_evidence[{position_id}].fair_value_cap_amount is required"
            )
        capped[index] = min(float(capped[index]), record.fair_value_cap_amount)
    return capped.astype(np.float64)


def _calculate_net_jtds_from_arrays(
    batch: DrcPositionBatch,
    gross_jtd: FloatArray,
    scaled_jtd: FloatArray,
) -> tuple[NetJtd, ...]:
    grouped: dict[tuple[str, str], list[int]] = {}
    for index in _sorted_indices(batch):
        key = (
            cast(str, batch.bucket_keys[index]),
            cast(str, batch.issuer_ids[index]),
        )
        grouped.setdefault(key, []).append(index)

    net_records: list[NetJtd] = []
    for key in sorted(grouped):
        net_records.extend(_net_group(batch, grouped[key], gross_jtd, scaled_jtd, key=key))
    return tuple(net_records)


def _calculate_securitisation_non_ctp_net_jtds_from_arrays(
    batch: DrcPositionBatch,
    gross_jtd: FloatArray,
    scaled_jtd: FloatArray,
    *,
    context: DrcCalculationContext,
) -> tuple[NetJtd, ...]:
    offset_groups = _securitisation_non_ctp_offset_groups(batch, context=context)
    return _calculate_exact_group_net_jtds_from_arrays(
        batch,
        gross_jtd,
        scaled_jtd,
        offset_groups=offset_groups,
        risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
        seniority_layer="SECURITISATION_TRANCHE",
        net_prefix="sec-non-ctp",
        normal_reason=(
            "securitisation non-CTP netting used same-pool/same-tranche identity "
            "or explicit replication-group evidence"
        ),
        rejected_reason_code="SEC_NON_CTP_OFFSET_REQUIRES_SAME_POOL_TRANCHE_OR_REPLICATION",
        netting_citations=_sec_non_ctp_netting_citations(context.profile_id),
    )


def _calculate_ctp_net_jtds_from_arrays(
    batch: DrcPositionBatch,
    gross_jtd: FloatArray,
    scaled_jtd: FloatArray,
    *,
    context: DrcCalculationContext,
) -> tuple[NetJtd, ...]:
    offset_groups = _ctp_offset_groups(batch, context=context)
    return _calculate_exact_group_net_jtds_from_arrays(
        batch,
        gross_jtd,
        scaled_jtd,
        offset_groups=offset_groups,
        risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
        seniority_layer="CTP",
        net_prefix="ctp",
        normal_reason=(
            "CTP netting used exact exposure identity or explicit replication group evidence"
        ),
        rejected_reason_code="CTP_OFFSET_REQUIRES_EXACT_MATCH_OR_EXPLICIT_REPLICATION",
        netting_citations=_CTP_NETTING_CITATIONS,
    )


def _calculate_exact_group_net_jtds_from_arrays(
    batch: DrcPositionBatch,
    gross_jtd: FloatArray,
    scaled_jtd: FloatArray,
    *,
    offset_groups: ObjectArray,
    risk_class: DrcRiskClass,
    seniority_layer: str,
    net_prefix: str,
    normal_reason: str,
    rejected_reason_code: str,
    netting_citations: tuple[str, ...],
) -> tuple[NetJtd, ...]:
    grouped: dict[tuple[str, str], list[int]] = {}
    for index in _sorted_indices(batch):
        key = (cast(str, batch.bucket_keys[index]), cast(str, offset_groups[index]))
        grouped.setdefault(key, []).append(index)

    rejected_by_bucket = _rejected_exact_group_offsets(
        batch,
        offset_groups=offset_groups,
        net_prefix=net_prefix,
        rejected_reason_code=rejected_reason_code,
        netting_citations=netting_citations,
    )
    records: list[NetJtd] = []
    for key in sorted(grouped):
        bucket_key, group_key = key
        indices = grouped[key]
        long_indices = [
            index
            for index in indices
            if batch.default_directions[index] == DefaultDirection.LONG.value
        ]
        short_indices = [
            index
            for index in indices
            if batch.default_directions[index] == DefaultDirection.SHORT.value
        ]
        gross_long = math.fsum(float(gross_jtd[index]) for index in long_indices)
        gross_short = math.fsum(float(gross_jtd[index]) for index in short_indices)
        scaled_long = math.fsum(float(scaled_jtd[index]) for index in long_indices)
        scaled_short = math.fsum(float(scaled_jtd[index]) for index in short_indices)
        signed_net = scaled_long - scaled_short
        if signed_net == 0.0:
            continue
        direction = DefaultDirection.LONG if signed_net > 0.0 else DefaultDirection.SHORT
        records.append(
            NetJtd(
                net_jtd_id=(
                    f"net-{net_prefix}-{_slug(bucket_key)}-{_slug(group_key)}-"
                    f"{direction.value.lower()}"
                ),
                netting_group_id=f"ng-{net_prefix}-{_slug(bucket_key)}-{_slug(group_key)}",
                risk_class=risk_class,
                bucket_key=bucket_key,
                obligor_or_tranche_key=group_key,
                seniority_layer=seniority_layer,
                gross_long=gross_long,
                gross_short=gross_short,
                scaled_long=scaled_long,
                scaled_short=scaled_short,
                net_amount=abs(signed_net),
                net_direction=direction,
                position_ids=tuple(cast(str, batch.position_ids[index]) for index in indices),
                scaled_jtd_ids=tuple(f"scaled-{batch.position_ids[index]}" for index in indices),
                rejected_offsets=rejected_by_bucket.get(bucket_key, ()),
                branch_metadata=(
                    BranchMetadata(
                        branch_id=f"net-{net_prefix}-{_slug(bucket_key)}-{_slug(group_key)}",
                        branch_type=BranchType.NORMAL,
                        source_id=group_key,
                        selected=True,
                        reason=normal_reason,
                        citations=netting_citations,
                    ),
                ),
            )
        )
    return tuple(records)


def _rejected_exact_group_offsets(
    batch: DrcPositionBatch,
    *,
    offset_groups: ObjectArray,
    net_prefix: str,
    rejected_reason_code: str,
    netting_citations: tuple[str, ...],
) -> dict[str, tuple[RejectedOffset, ...]]:
    grouped: dict[str, list[int]] = {}
    for index in _sorted_indices(batch):
        grouped.setdefault(cast(str, batch.bucket_keys[index]), []).append(index)

    rejected_by_bucket: dict[str, tuple[RejectedOffset, ...]] = {}
    sequence = count(1)
    for bucket_key in sorted(grouped):
        indices = grouped[bucket_key]
        long_groups = _direction_groups(batch, indices, offset_groups, DefaultDirection.LONG)
        short_groups = _direction_groups(batch, indices, offset_groups, DefaultDirection.SHORT)
        rejected = _bounded_rejected_group_offsets(
            bucket_key=bucket_key,
            long_groups=long_groups,
            short_groups=short_groups,
            rejection_id_prefix=f"rej-{net_prefix}",
            sequence=sequence,
            representative=lambda item: _representative_scaled_id(batch, item),
            reason_code=rejected_reason_code,
            citations=netting_citations,
        )
        if rejected:
            rejected_by_bucket[bucket_key] = tuple(rejected)
    return rejected_by_bucket


def _direction_groups(
    batch: DrcPositionBatch,
    indices: Sequence[int],
    offset_groups: ObjectArray,
    direction: DefaultDirection,
) -> dict[str, list[int]]:
    grouped: dict[str, list[int]] = {}
    for index in indices:
        if batch.default_directions[index] == direction.value:
            grouped.setdefault(cast(str, offset_groups[index]), []).append(index)
    return grouped


def _representative_scaled_id(batch: DrcPositionBatch, indices: Sequence[int]) -> str:
    return sorted(f"scaled-{batch.position_ids[index]}" for index in indices)[0]


def _securitisation_non_ctp_offset_groups(
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
) -> ObjectArray:
    groups: list[str] = []
    for index in range(batch.row_count):
        position_id = cast(str, batch.position_ids[index])
        explicit = context.securitisation_non_ctp_offset_groups.get(position_id)
        if explicit is not None:
            groups.append(
                _required_text(
                    explicit,
                    f"securitisation_non_ctp_offset_groups[{position_id!r}]",
                )
            )
            continue
        pool_id = _optional_text(batch.issuer_ids[index])
        tranche_id = _optional_text(batch.tranche_ids[index])
        if pool_id is None:
            raise DrcInputError(
                "securitisation non-CTP offsetting requires issuer_id to carry the "
                f"underlying pool id for position {position_id}, unless an explicit "
                "securitisation_non_ctp_offset_group is supplied"
            )
        if tranche_id is None:
            raise DrcInputError(f"securitisation non-CTP position {position_id} has no tranche_id")
        groups.append(f"exact:pool:{pool_id}:tranche:{tranche_id}")
    return _batch_arrays.object_array(groups, copy=True)


def _ctp_offset_groups(
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
) -> ObjectArray:
    groups: list[str] = []
    for index in range(batch.row_count):
        position_id = cast(str, batch.position_ids[index])
        explicit = context.ctp_offset_groups.get(position_id)
        if explicit is not None:
            groups.append(_required_text(explicit, f"ctp_offset_groups[{position_id!r}]"))
            continue
        index_series_id = _optional_text(batch.index_series_ids[index])
        tranche_id = _optional_text(batch.tranche_ids[index])
        issuer_id = _optional_text(batch.issuer_ids[index])
        if index_series_id is not None and tranche_id is not None:
            groups.append(f"exact:index:{index_series_id}:tranche:{tranche_id}")
        elif index_series_id is not None:
            groups.append(f"exact:index:{index_series_id}:non-tranched")
        elif issuer_id is not None:
            groups.append(f"exact:single-name:{issuer_id}")
        elif tranche_id is not None:
            groups.append(f"exact:tranche:{tranche_id}")
        else:
            raise DrcInputError(f"CTP position {position_id} has no offset identity")
    return _batch_arrays.object_array(groups, copy=True)


def _net_group(
    batch: DrcPositionBatch,
    indices: list[int],
    gross_jtd: FloatArray,
    scaled_jtd: FloatArray,
    *,
    key: tuple[str, str],
) -> list[NetJtd]:
    bucket_key, issuer_key = key
    longs = _by_seniority(batch, indices, DefaultDirection.LONG)
    shorts = _by_seniority(batch, indices, DefaultDirection.SHORT)
    short_states = {
        seniority: [
            {
                "index": index,
                "remaining_gross": float(gross_jtd[index]),
                "remaining_scaled": float(scaled_jtd[index]),
            }
            for index in items
        ]
        for seniority, items in shorts.items()
    }
    rejected = _rejected_seniority_offsets(batch, bucket_key, issuer_key, longs, shorts)
    records: list[NetJtd] = []

    for seniority in sorted(longs, key=_seniority_rank):
        long_items = longs[seniority]
        scaled_long = float(sum(float(scaled_jtd[index]) for index in long_items))
        gross_long = float(sum(float(gross_jtd[index]) for index in long_items))
        used_short_scaled = 0.0
        used_short_gross = 0.0
        used_short_items: list[int] = []
        for short_seniority in sorted(shorts, key=_seniority_rank):
            if not _short_can_offset(long_seniority=seniority, short_seniority=short_seniority):
                continue
            remaining_long = scaled_long - used_short_scaled
            if remaining_long <= 0:
                break
            for short_state in short_states.get(short_seniority, ()):
                if remaining_long <= 0:
                    break
                consumed_scaled, consumed_gross = _consume_short_state(short_state, remaining_long)
                if consumed_scaled <= 0:
                    continue
                used_short_scaled += consumed_scaled
                used_short_gross += consumed_gross
                remaining_long -= consumed_scaled
                used_short_items.append(cast(int, short_state["index"]))

        net_amount = scaled_long - used_short_scaled
        if net_amount > 0:
            records.append(
                _net_record(
                    batch,
                    bucket_key=bucket_key,
                    issuer_key=issuer_key,
                    seniority=seniority,
                    direction=DefaultDirection.LONG,
                    gross_long=gross_long,
                    gross_short=used_short_gross,
                    scaled_long=scaled_long,
                    scaled_short=used_short_scaled,
                    net_amount=net_amount,
                    source_indices=(*long_items, *used_short_items),
                    rejected_offsets=rejected,
                )
            )

    for seniority in sorted(shorts, key=_seniority_rank):
        remaining_states = [
            short_state
            for short_state in short_states.get(seniority, ())
            if short_state["remaining_scaled"] > 0
        ]
        if not remaining_states:
            continue
        source_indices = tuple(cast(int, short_state["index"]) for short_state in remaining_states)
        remaining_gross = math.fsum(
            float(short_state["remaining_gross"]) for short_state in remaining_states
        )
        remaining_scaled = math.fsum(
            float(short_state["remaining_scaled"]) for short_state in remaining_states
        )
        records.append(
            _net_record(
                batch,
                bucket_key=bucket_key,
                issuer_key=issuer_key,
                seniority=seniority,
                direction=DefaultDirection.SHORT,
                gross_long=0.0,
                gross_short=remaining_gross,
                scaled_long=0.0,
                scaled_short=remaining_scaled,
                net_amount=remaining_scaled,
                source_indices=source_indices,
                rejected_offsets=rejected,
            )
        )

    return records


def _by_seniority(
    batch: DrcPositionBatch,
    indices: Sequence[int],
    direction: DefaultDirection,
) -> dict[DrcSeniority, list[int]]:
    grouped: dict[DrcSeniority, list[int]] = {}
    for index in indices:
        if DefaultDirection(cast(str, batch.default_directions[index])) == direction:
            grouped.setdefault(DrcSeniority(cast(str, batch.seniorities[index])), []).append(index)
    return grouped


def _consume_short_state(
    short_state: dict[str, float | int],
    requested_scaled: float,
) -> tuple[float, float]:
    remaining_scaled = cast(float, short_state["remaining_scaled"])
    if remaining_scaled <= 0:
        return 0.0, 0.0

    consumed_scaled = min(requested_scaled, remaining_scaled)
    if consumed_scaled <= 0:
        return 0.0, 0.0

    consumed_ratio = consumed_scaled / remaining_scaled
    consumed_gross = cast(float, short_state["remaining_gross"]) * consumed_ratio
    short_state["remaining_scaled"] = remaining_scaled - consumed_scaled
    short_state["remaining_gross"] = cast(float, short_state["remaining_gross"]) - consumed_gross
    return consumed_scaled, consumed_gross


def _net_record(
    batch: DrcPositionBatch,
    *,
    bucket_key: str,
    issuer_key: str,
    seniority: DrcSeniority,
    direction: DefaultDirection,
    gross_long: float,
    gross_short: float,
    scaled_long: float,
    scaled_short: float,
    net_amount: float,
    source_indices: tuple[int, ...],
    rejected_offsets: tuple[RejectedOffset, ...],
) -> NetJtd:
    seniority_label = seniority.value.lower()
    return NetJtd(
        net_jtd_id=f"net-{_slug(bucket_key)}-{_slug(issuer_key)}-{seniority_label}-{direction.value.lower()}",
        netting_group_id=f"ng-{_slug(bucket_key)}-{_slug(issuer_key)}-{seniority_label}",
        risk_class=DrcRiskClass.NON_SECURITISATION,
        bucket_key=bucket_key,
        obligor_or_tranche_key=issuer_key,
        seniority_layer=seniority.value,
        gross_long=gross_long,
        gross_short=gross_short,
        scaled_long=scaled_long,
        scaled_short=scaled_short,
        net_amount=net_amount,
        net_direction=direction,
        position_ids=tuple(cast(str, batch.position_ids[index]) for index in source_indices),
        scaled_jtd_ids=tuple(f"scaled-{batch.position_ids[index]}" for index in source_indices),
        rejected_offsets=rejected_offsets,
    )


def _rejected_seniority_offsets(
    batch: DrcPositionBatch,
    bucket_key: str,
    issuer_key: str,
    longs: dict[DrcSeniority, list[int]],
    shorts: dict[DrcSeniority, list[int]],
) -> tuple[RejectedOffset, ...]:
    rejected: list[RejectedOffset] = []
    sequence = count(1)
    for long_seniority, long_items in sorted(
        longs.items(), key=lambda item: _seniority_rank(item[0])
    ):
        for short_seniority, short_items in sorted(
            shorts.items(),
            key=lambda item: _seniority_rank(item[0]),
        ):
            if _short_can_offset(long_seniority=long_seniority, short_seniority=short_seniority):
                continue
            for long_index in long_items:
                for short_index in short_items:
                    rejected.append(
                        RejectedOffset(
                            rejection_id=(
                                f"rej-{_slug(bucket_key)}-{_slug(issuer_key)}-{next(sequence)}"
                            ),
                            long_source_id=f"scaled-{batch.position_ids[long_index]}",
                            short_source_id=f"scaled-{batch.position_ids[short_index]}",
                            reason_code="SHORT_HIGHER_SENIORITY_THAN_LONG",
                            citations=(_NETTING_CITATION,),
                        )
                    )
    return tuple(rejected)


def _capital_inputs(
    batch: DrcPositionBatch,
    net_jtds: tuple[NetJtd, ...],
) -> tuple[CapitalInput, ...]:
    credit_quality_by_position = {
        cast(str, batch.position_ids[index]): CreditQuality(
            cast(str, batch.credit_qualities[index])
        )
        for index in range(batch.row_count)
    }
    return tuple(
        CapitalInput(
            net_jtd=net_jtd,
            credit_quality=_credit_quality_for_net_jtd(net_jtd, credit_quality_by_position),
        )
        for net_jtd in net_jtds
    )


def _securitisation_non_ctp_capital_inputs_from_batch(
    net_jtds: tuple[NetJtd, ...],
    *,
    risk_weights: Mapping[str, float],
) -> tuple[SecuritisationNonCtpCapitalInput, ...]:
    inputs: list[SecuritisationNonCtpCapitalInput] = []
    for net_jtd in net_jtds:
        weights = tuple(
            sorted(
                _risk_weights_for_net_jtd(
                    net_jtd,
                    risk_weights=risk_weights,
                    field_name="context.securitisation_non_ctp_risk_weights",
                )
            )
        )
        if len(weights) != 1:
            raise DrcInputError(
                "securitisation non-CTP net JTD must map to exactly one risk weight: "
                f"{net_jtd.net_jtd_id}"
            )
        inputs.append(SecuritisationNonCtpCapitalInput(net_jtd=net_jtd, risk_weight=weights[0]))
    return tuple(inputs)


def _ctp_capital_inputs_from_batch(
    net_jtds: tuple[NetJtd, ...],
    *,
    risk_weights: Mapping[str, float],
) -> tuple[CtpCapitalInput, ...]:
    inputs: list[CtpCapitalInput] = []
    for net_jtd in net_jtds:
        weights = tuple(
            sorted(
                _risk_weights_for_net_jtd(
                    net_jtd,
                    risk_weights=risk_weights,
                    field_name="context.ctp_risk_weights",
                )
            )
        )
        if len(weights) != 1:
            raise DrcInputError(
                f"CTP net JTD must map to exactly one risk weight: {net_jtd.net_jtd_id}"
            )
        inputs.append(CtpCapitalInput(net_jtd=net_jtd, risk_weight=weights[0]))
    return tuple(inputs)


def _coerce_finite_non_negative_float(value: object, *, field_name: str) -> float:
    try:
        result = float(cast(Any, value))
    except (ValueError, TypeError) as exc:
        raise DrcInputError(f"{field_name} must be a valid finite number") from exc
    if not math.isfinite(result) or result < 0.0:
        raise DrcInputError(f"{field_name} must be finite and non-negative")
    return result


def _credit_quality_for_net_jtd(
    net_jtd: NetJtd,
    credit_quality_by_position: Mapping[str, CreditQuality],
) -> CreditQuality:
    credit_qualities = {
        credit_quality_by_position[position_id] for position_id in net_jtd.position_ids
    }
    if len(credit_qualities) != 1:
        raise DrcInputError(f"net JTD must map to exactly one credit quality: {net_jtd.net_jtd_id}")
    return next(iter(credit_qualities))


def _zero_nonsec_category() -> CategoryDrc:
    return CategoryDrc(
        category_id="category-drc-non-securitisation",
        risk_class=DrcRiskClass.NON_SECURITISATION,
        bucket_results=(),
        capital=0.0,
        branch_metadata=(
            BranchMetadata(
                branch_id="category-non-securitisation-zero",
                branch_type=BranchType.ZERO_DENOMINATOR,
                source_id=DrcRiskClass.NON_SECURITISATION.value,
                selected=True,
                reason="all supported net JTD records are zero",
                citations=(_ZERO_CATEGORY_CITATION,),
            ),
        ),
    )


def _collect_batch_citations(
    batch: DrcPositionBatch,
    *,
    category: CategoryDrc,
    net_jtds: tuple[NetJtd, ...],
    formula_citations: tuple[str, ...],
    profile_id: str,
    fx_citations: tuple[str, ...] = (),
) -> tuple[str, ...]:
    citation_ids = {*formula_citations, *fx_citations}
    if profile_id != BASEL_MAR22_PROFILE_ID:
        citation_ids.add("US_NPR_210_SCOPE")
    for group in batch.citation_ids:
        citation_ids.update(group)
    citation_ids.update(_branch_citations(category.branch_metadata))
    for bucket in category.bucket_results:
        citation_ids.update(bucket.citations)
        citation_ids.update(bucket.hbr.citations)
        citation_ids.update(_branch_citations(bucket.branch_metadata))
        citation_ids.update(_branch_citations(bucket.hbr.branch_metadata))
    for net_jtd in net_jtds:
        citation_ids.update(_branch_citations(net_jtd.branch_metadata))
        for rejected_offset in net_jtd.rejected_offsets:
            citation_ids.update(rejected_offset.citations)
    return tuple(sorted(citation_ids))


def _batch_api_citations(profile_id: str, risk_class: DrcRiskClass) -> tuple[str, ...]:
    if profile_id == BASEL_MAR22_PROFILE_ID and risk_class is DrcRiskClass.SECURITISATION_NON_CTP:
        return _BASEL_SEC_NON_CTP_BATCH_CITATIONS
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return ()
    return ("US_NPR_210_SCOPE",)


def _context_input_hash_for_batch(
    input_hash: str,
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
    risk_class: DrcRiskClass,
) -> str:
    if risk_class is DrcRiskClass.SECURITISATION_NON_CTP:
        return _hash_context_position_maps(
            input_hash,
            batch,
            risk_weights=effective_risk_weights(
                context,
                risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
            ),
            offset_groups=context.securitisation_non_ctp_offset_groups,
            risk_weight_key="securitisation_non_ctp_risk_weights",
            risk_weight_evidence_key="securitisation_non_ctp_risk_weight_evidence",
            fair_value_cap_evidence_key="securitisation_non_ctp_fair_value_cap_evidence",
            offset_group_key="securitisation_non_ctp_offset_groups",
            context=context,
            risk_class=risk_class,
        )
    if risk_class is DrcRiskClass.CORRELATION_TRADING_PORTFOLIO:
        return _hash_context_position_maps(
            input_hash,
            batch,
            risk_weights=effective_risk_weights(
                context,
                risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
            ),
            offset_groups=context.ctp_offset_groups,
            risk_weight_key="ctp_risk_weights",
            risk_weight_evidence_key="ctp_risk_weight_evidence",
            fair_value_cap_evidence_key="",
            offset_group_key="ctp_offset_groups",
            context=context,
            risk_class=risk_class,
        )
    return input_hash


def _batch_risk_weights_by_position(
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
    risk_class: DrcRiskClass,
) -> dict[str, float]:
    if risk_class == DrcRiskClass.NON_SECURITISATION:
        weights: dict[str, float] = {}
        for index in _sorted_indices(batch):
            position_id = cast(str, batch.position_ids[index])
            weights[position_id] = get_risk_weight_rule(
                cast(str, batch.bucket_keys[index]),
                CreditQuality(cast(str, batch.credit_qualities[index])),
                profile_id=context.profile_id,
            ).risk_weight
        return weights
    if risk_class == DrcRiskClass.SECURITISATION_NON_CTP:
        return dict(
            effective_risk_weights(
                context,
                risk_class=DrcRiskClass.SECURITISATION_NON_CTP,
            )
        )
    if risk_class == DrcRiskClass.CORRELATION_TRADING_PORTFOLIO:
        return dict(
            effective_risk_weights(
                context,
                risk_class=DrcRiskClass.CORRELATION_TRADING_PORTFOLIO,
            )
        )
    return {}


def _hash_context_position_maps(
    input_hash: str,
    batch: DrcPositionBatch,
    *,
    risk_weights: Mapping[str, float],
    offset_groups: Mapping[str, str],
    risk_weight_key: str,
    risk_weight_evidence_key: str,
    fair_value_cap_evidence_key: str,
    offset_group_key: str,
    context: DrcCalculationContext,
    risk_class: DrcRiskClass,
) -> str:
    position_ids = tuple(sorted(cast(str, position_id) for position_id in batch.position_ids))
    payload = {
        "input_hash": input_hash,
        risk_weight_key: {position_id: risk_weights[position_id] for position_id in position_ids},
        risk_weight_evidence_key: risk_weight_evidence_hash_payload(
            position_ids,
            context,
            risk_class=risk_class,
        ),
        offset_group_key: {
            position_id: offset_groups[position_id]
            for position_id in position_ids
            if position_id in offset_groups
        },
    }
    if fair_value_cap_evidence_key:
        payload[fair_value_cap_evidence_key] = fair_value_cap_hash_payload(
            position_ids,
            context,
        )
    return _hash_payload(payload)


def _batch_fair_value_cap_citations(
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
) -> tuple[str, ...]:
    citation_ids: set[str] = set()
    for position_id in batch.position_ids:
        evidence = context.securitisation_non_ctp_fair_value_cap_evidence.get(
            cast(str, position_id)
        )
        if evidence is not None:
            citation_ids.update(_sec_non_ctp_fair_value_cap_citations(context.profile_id))
            citation_ids.update(evidence.citation_ids)
    return tuple(sorted(citation_ids))


def _fair_value_cap_branch_metadata_for_batch(
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
    risk_class: DrcRiskClass,
) -> tuple[BranchMetadata, ...]:
    if risk_class is not DrcRiskClass.SECURITISATION_NON_CTP:
        return ()
    gross_jtd = _market_value_gross_jtd_array(batch)
    branches: list[BranchMetadata] = []
    evidence = context.securitisation_non_ctp_fair_value_cap_evidence
    if not evidence:
        return (
            BranchMetadata(
                branch_id="drc-securitisation-non-ctp-batch-no-fair-value-cap",
                branch_type=BranchType.NORMAL,
                source_id=context.profile_id,
                selected=True,
                reason=(
                    "batch securitisation non-CTP gross default exposure used market value; "
                    "no fair-value cap evidence was supplied"
                ),
                citations=_sec_non_ctp_gross_citations(context.profile_id),
            ),
        )
    for index in _sorted_indices(batch):
        position_id = cast(str, batch.position_ids[index])
        record = evidence.get(position_id)
        if record is None:
            branches.append(
                BranchMetadata(
                    branch_id=f"batch-sec-non-ctp-no-fair-value-cap-{_slug(position_id)}",
                    branch_type=BranchType.NORMAL,
                    source_id=position_id,
                    selected=True,
                    reason=(
                        "batch securitisation non-CTP position used market value; "
                        "no fair-value cap evidence was supplied"
                    ),
                    citations=_sec_non_ctp_gross_citations(context.profile_id),
                )
            )
            continue
        citations = tuple(
            sorted(
                {
                    *_sec_non_ctp_fair_value_cap_citations(context.profile_id),
                    *record.citation_ids,
                }
            )
        )
        if not record.eligible:
            branch_type = BranchType.NORMAL
            reason = (
                "batch fair-value cap evidence marked the position ineligible; "
                f"reason: {record.eligibility_reason}"
            )
        elif record.fair_value_cap_amount is not None and record.fair_value_cap_amount < float(
            gross_jtd[index]
        ):
            branch_type = BranchType.CAP
            reason = (
                "batch fair-value cap applied to securitisation non-CTP gross default "
                f"exposure: market_value={float(gross_jtd[index])}, "
                f"cap_amount={record.fair_value_cap_amount}"
            )
        else:
            branch_type = BranchType.NORMAL
            reason = (
                "batch fair-value cap evidence was eligible but not binding: "
                f"market_value={float(gross_jtd[index])}, "
                f"cap_amount={record.fair_value_cap_amount}"
            )
        branches.append(
            BranchMetadata(
                branch_id=f"batch-sec-non-ctp-fair-value-cap-{_slug(position_id)}",
                branch_type=branch_type,
                source_id=record.source_id,
                selected=True,
                reason=reason,
                citations=citations,
            )
        )
    return tuple(branches)


def _sec_non_ctp_gross_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_SEC_NON_CTP_GROSS_CITATIONS
    return _SEC_NON_CTP_GROSS_CITATIONS


def _sec_non_ctp_fair_value_cap_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_SEC_NON_CTP_FAIR_VALUE_CAP_CITATIONS
    return _SEC_NON_CTP_FAIR_VALUE_CAP_CITATIONS


def _sec_non_ctp_netting_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_SEC_NON_CTP_NETTING_CITATIONS
    return _SEC_NON_CTP_NETTING_CITATIONS


def _sec_non_ctp_batch_citations(profile_id: str) -> tuple[str, ...]:
    if profile_id == BASEL_MAR22_PROFILE_ID:
        return _BASEL_SEC_NON_CTP_BATCH_CITATIONS
    return _SEC_NON_CTP_BATCH_CITATIONS


def _branch_citations(branches: tuple[BranchMetadata, ...]) -> set[str]:
    citation_ids: set[str] = set()
    for branch in branches:
        citation_ids.update(branch.citations)
    return citation_ids


def _position_payload(batch: DrcPositionBatch, index: int) -> dict[str, object]:
    lineage = None
    if bool(batch.lineage_present[index]):
        lineage = {
            "source_system": batch.lineage_source_systems[index],
            "source_file": batch.lineage_source_files[index],
            "source_row_id": batch.source_row_ids[index],
            "source_column_map": dict(batch.source_column_maps[index]),
        }
    return {
        "position_id": batch.position_ids[index],
        "source_row_id": batch.source_row_ids[index],
        "desk_id": batch.desk_ids[index],
        "legal_entity": batch.legal_entities[index],
        "risk_class": batch.risk_classes[index],
        "instrument_type": batch.instrument_types[index],
        "default_direction": batch.default_directions[index],
        "issuer_id": batch.issuer_ids[index],
        "tranche_id": batch.tranche_ids[index],
        "index_series_id": batch.index_series_ids[index],
        "bucket_key": batch.bucket_keys[index],
        "seniority": batch.seniorities[index],
        "credit_quality": batch.credit_qualities[index],
        "notional": float(batch.notionals[index]),
        "market_value": _optional_float_payload(batch.market_values[index]),
        "cumulative_pnl": _optional_float_payload(batch.cumulative_pnls[index]),
        "maturity_years": float(batch.maturity_years[index]),
        "currency": batch.currencies[index],
        "lgd_override": _optional_float_payload(batch.lgd_overrides[index]),
        "is_defaulted": bool(batch.is_defaulted[index]),
        "is_gse": bool(batch.is_gse[index]),
        "is_pse": bool(batch.is_pse[index]),
        "is_covered_bond": bool(batch.is_covered_bond[index]),
        "lineage": lineage,
        "citation_ids": list(batch.citation_ids[index]),
    }


def _optional_float_payload(value: float) -> float | None:
    return None if math.isnan(float(value)) else float(value)


def _hash_payload(payload: object) -> str:
    encoded = bytes(json.dumps(jsonable(payload), sort_keys=True, separators=(",", ":")), "utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _raise_first_mismatch(
    values: ObjectArray,
    expected: str,
    *,
    mismatch_when_equal: bool = False,
    message: Callable[[int], str],
) -> None:
    mismatch = values == expected if mismatch_when_equal else values != expected
    if bool(np.any(mismatch)):
        index = int(np.nonzero(mismatch)[0][0])
        raise DrcInputError(message(index))


def _sorted_positions(positions: tuple[DrcPosition, ...]) -> tuple[DrcPosition, ...]:
    return tuple(
        sorted(positions, key=lambda position: (position.position_id, position.source_row_id))
    )


def _sorted_indices(batch: DrcPositionBatch) -> tuple[int, ...]:
    return tuple(
        sorted(
            range(batch.row_count),
            key=lambda index: (
                cast(str, batch.position_ids[index]),
                cast(str, batch.source_row_ids[index]),
            ),
        )
    )


def _short_can_offset(*, long_seniority: DrcSeniority, short_seniority: DrcSeniority) -> bool:
    return _seniority_rank(short_seniority) >= _seniority_rank(long_seniority)


def _seniority_rank(seniority: DrcSeniority) -> int:
    try:
        return _SENIORITY_RANK[seniority]
    except KeyError as exc:  # pragma: no cover - all enum values are mapped.
        raise DrcInputError(f"missing DRC seniority rank: {seniority.value}") from exc


__all__ = [
    "DrcBatchCapitalCalculation",
    "DrcPositionBatch",
    "build_drc_ctp_batch_from_columns",
    "build_drc_nonsec_batch_from_columns",
    "build_drc_nonsec_batch_from_positions",
    "build_drc_securitisation_non_ctp_batch_from_columns",
    "calculate_drc_capital_from_batch",
    "input_hash_for_drc_batch",
]
