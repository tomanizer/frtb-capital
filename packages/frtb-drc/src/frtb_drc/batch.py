"""Package-owned DRC batches for high-volume non-securitisation kernels."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from itertools import count
from typing import Any, TypeVar, cast

import numpy as np
import numpy.typing as npt
from frtb_common import jsonable

from frtb_drc._version import __version__
from frtb_drc.capital import CapitalInput, calculate_category_drc
from frtb_drc.data_models import (
    BranchMetadata,
    BranchType,
    CategoryDrc,
    CreditQuality,
    DefaultDirection,
    DrcCalculationContext,
    DrcCapitalResult,
    DrcInstrumentType,
    DrcPosition,
    DrcRiskClass,
    DrcSeniority,
    NetJtd,
    RejectedOffset,
)
from frtb_drc.reference_data import get_lgd_rule, get_maturity_policy
from frtb_drc.regimes import DrcRuleProfile, ensure_risk_class_supported, get_rule_profile
from frtb_drc.validation import DrcInputError, validate_positions

ObjectArray = npt.NDArray[np.object_]
FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]
EnumT = TypeVar("EnumT", bound=StrEnum)

_FORMULA_CITATIONS = ("BASEL_MAR22_11", "BASEL_MAR22_13")
_NETTING_CITATION = "US_NPR_210_B_2"
_ZERO_CATEGORY_CITATION = "US_NPR_210_B_3_III"

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
) -> DrcPositionBatch:
    """
    Build a DRC batch from existing canonical position rows.

    This is a compatibility bridge for callers that already hold dataclasses.
    High-volume adapters should build from handoffs or columns.
    """

    validated = _sorted_positions(validate_positions(positions))
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
    )


def build_drc_nonsec_batch_from_columns(
    *,
    position_ids: Sequence[object],
    source_row_ids: Sequence[object],
    desk_ids: Sequence[object],
    legal_entities: Sequence[object],
    risk_classes: Sequence[object],
    instrument_types: Sequence[object],
    default_directions: Sequence[object],
    issuer_ids: Sequence[object | None],
    tranche_ids: Sequence[object | None] | None = None,
    index_series_ids: Sequence[object | None] | None = None,
    bucket_keys: Sequence[object | None],
    seniorities: Sequence[object | None],
    credit_qualities: Sequence[object | None],
    notionals: Sequence[object],
    market_values: Sequence[object | None] | None = None,
    cumulative_pnls: Sequence[object | None] | None = None,
    maturity_years: Sequence[object],
    currencies: Sequence[object],
    lgd_overrides: Sequence[object | None] | None = None,
    is_defaulted: Sequence[object] | None = None,
    is_gse: Sequence[object] | None = None,
    is_pse: Sequence[object] | None = None,
    is_covered_bond: Sequence[object] | None = None,
    lineage_source_systems: Sequence[object] | None = None,
    lineage_source_files: Sequence[object] | None = None,
    lineage_present: Sequence[object] | None = None,
    source_column_maps: Sequence[Sequence[tuple[str, str]]] | None = None,
    citation_ids: Sequence[Sequence[str]] | None = None,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    copy_arrays: bool = True,
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
        issuer_ids=issuer_ids,
        bucket_keys=bucket_keys,
        seniorities=seniorities,
        credit_qualities=credit_qualities,
        notionals=notionals,
        maturity_years=maturity_years,
        currencies=currencies,
    )
    optional_lengths = {
        "tranche_ids": tranche_ids,
        "index_series_ids": index_series_ids,
        "market_values": market_values,
        "cumulative_pnls": cumulative_pnls,
        "lgd_overrides": lgd_overrides,
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
        seniorities=_enum_array(seniorities, DrcSeniority, "seniority", copy=copy_arrays),
        credit_qualities=_enum_array(
            credit_qualities,
            CreditQuality,
            "credit_quality",
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
        lineage_present=_bool_array(lineage_present, row_count, default=True, copy=copy_arrays),
        source_column_maps=_freeze_source_column_maps(source_column_maps, row_count),
        citation_ids=_freeze_citation_ids(citation_ids, row_count),
        input_hash="",
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=tuple(dict(item) for item in diagnostics),
    )
    _validate_batch(batch)
    return replace(batch, input_hash=input_hash_for_drc_batch(batch))


def input_hash_for_drc_batch(batch: DrcPositionBatch) -> str:
    """Hash canonical DRC batch inputs in deterministic position-id order."""

    payload = [_position_payload(batch, index) for index in _sorted_indices(batch)]
    return _hash_payload(payload)


def calculate_drc_capital_from_batch(
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
) -> DrcBatchCapitalCalculation:
    """Calculate supported non-securitisation DRC capital from a columnar batch."""

    if not isinstance(batch, DrcPositionBatch):
        raise DrcInputError("batch must be DrcPositionBatch")
    _validate_context(context)
    profile = get_rule_profile(context.profile_id)
    _validate_supported_batch_run(batch, context=context, profile=profile)

    gross_jtd, lgd_citations = _gross_jtd_array(batch, profile_id=profile.profile_id)
    maturity_weights, scaled_jtd, maturity_citation = _scaled_jtd_array(
        batch,
        gross_jtd,
        profile_id=profile.profile_id,
    )
    net_jtds = _calculate_net_jtds_from_arrays(batch, gross_jtd, scaled_jtd)
    capital_inputs = _capital_inputs(batch, net_jtds)
    category = (
        calculate_category_drc(capital_inputs, profile_id=profile.profile_id)
        if capital_inputs
        else _zero_nonsec_category()
    )
    result = DrcCapitalResult(
        result_id=f"drc-{_slug(context.run_id)}-{batch.input_hash[:12]}",
        run_id=context.run_id,
        calculation_date=context.calculation_date,
        base_currency=context.base_currency,
        profile_id=profile.profile_id,
        profile_hash=profile.content_hash,
        input_hash=batch.input_hash,
        categories=(category,),
        total_drc=category.capital,
        citations=_collect_batch_citations(
            batch,
            category=category,
            net_jtds=net_jtds,
            lgd_citations=lgd_citations,
            maturity_citation=maturity_citation,
        ),
        warnings=(),
        branch_metadata=(
            BranchMetadata(
                branch_id="drc-non-securitisation-batch-api",
                branch_type=BranchType.NORMAL,
                source_id=profile.profile_id,
                selected=True,
                reason=(
                    "batch API executed supported non-securitisation path; "
                    "Euler attribution is not calculated"
                ),
                citations=("US_NPR_210_SCOPE",),
            ),
        ),
        package_name="frtb-drc",
        package_version=__version__,
        input_count=batch.row_count,
        rejected_input_count=len(batch.diagnostics),
        input_positions=(),
        gross_jtds=(),
        maturity_scaled_jtds=(),
        net_jtds=net_jtds,
    )
    return DrcBatchCapitalCalculation(
        result=result,
        gross_jtd=_immutable_float_array(gross_jtd),
        maturity_weights=_immutable_float_array(maturity_weights),
        scaled_jtd=_immutable_float_array(scaled_jtd),
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


def _validate_supported_batch_run(
    batch: DrcPositionBatch,
    *,
    context: DrcCalculationContext,
    profile: DrcRuleProfile,
) -> None:
    scoped_desk_id = context.desk_id.strip()
    scoped_legal_entity = context.legal_entity.strip()
    for index in range(batch.row_count):
        risk_class = DrcRiskClass(cast(str, batch.risk_classes[index]))
        ensure_risk_class_supported(profile, risk_class)
        if risk_class is not DrcRiskClass.NON_SECURITISATION:
            raise DrcInputError(f"DRC risk class is not implemented: {risk_class.value}")
        if cast(str, batch.currencies[index]) != context.base_currency:
            raise DrcInputError(
                f"position currency {batch.currencies[index]} does not match base currency "
                f"{context.base_currency}"
            )
        if scoped_desk_id and cast(str, batch.desk_ids[index]) != scoped_desk_id:
            raise DrcInputError(
                f"position {batch.position_ids[index]} desk_id {batch.desk_ids[index]} "
                f"does not match context desk_id {scoped_desk_id}"
            )
        if scoped_legal_entity and cast(str, batch.legal_entities[index]) != scoped_legal_entity:
            raise DrcInputError(
                f"position {batch.position_ids[index]} legal_entity "
                f"{batch.legal_entities[index]} does not match context legal_entity "
                f"{scoped_legal_entity}"
            )


def _validate_batch(batch: DrcPositionBatch) -> None:
    if not np.all(batch.risk_classes == DrcRiskClass.NON_SECURITISATION.value):
        raise DrcInputError("DRC batch only supports non-securitisation risk class")
    if np.any(batch.issuer_ids == None):  # noqa: E711
        raise DrcInputError("issuer_id is required for non-securitisation DRC batch")
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


def _gross_jtd_array(
    batch: DrcPositionBatch,
    *,
    profile_id: str,
) -> tuple[FloatArray, tuple[str, ...]]:
    if bool(np.any(~np.isnan(batch.lgd_overrides))):
        raise DrcInputError("explicit LGD overrides are not supported by the selected profile")

    lgd_rates = np.empty(batch.row_count, dtype=np.float64)
    citations: list[str] = []
    for index in range(batch.row_count):
        lgd_rule = get_lgd_rule(
            DrcSeniority(cast(str, batch.seniorities[index])),
            profile_id=profile_id,
            is_defaulted=bool(batch.is_defaulted[index]),
        )
        lgd_rates[index] = lgd_rule.lgd_rate
        citations.append(lgd_rule.citation_id)

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
    return gross.astype(np.float64), tuple(sorted(set(citations)))


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
    lgd_citations: tuple[str, ...],
    maturity_citation: str,
) -> tuple[str, ...]:
    citation_ids = {"US_NPR_210_SCOPE", *_FORMULA_CITATIONS, maturity_citation, *lgd_citations}
    if net_jtds:
        citation_ids.add(_NETTING_CITATION)
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
    encoded = json.dumps(jsonable(payload), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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


def _require_lengths(row_count: int, **columns: Sequence[object]) -> None:
    for name, values in columns.items():
        if len(values) != row_count:
            raise DrcInputError(f"{name} length does not match position_ids")


def _required_text_array(
    values: Sequence[object | None], field_name: str, *, copy: bool
) -> ObjectArray:
    array = _object_array([_required_text(value, field_name) for value in values], copy=copy)
    return array


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


def _required_float_array(values: Sequence[object], field_name: str, *, copy: bool) -> FloatArray:
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


def _bool_array(
    values: Sequence[object] | None,
    row_count: int,
    *,
    default: bool = False,
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


def _object_array(values: Sequence[object | None], *, copy: bool) -> ObjectArray:
    array = np.asarray(values, dtype=object)
    if copy:
        array = array.copy()
    array.setflags(write=False)
    return array


def _immutable_float_array(values: FloatArray) -> FloatArray:
    array = np.asarray(values, dtype=np.float64).copy()
    array.setflags(write=False)
    return array


def _required_text(value: object | None, field_name: str) -> str:
    text = _optional_text(value)
    if text is None:
        raise DrcInputError(f"{field_name} must be non-empty")
    return text


def _optional_text(value: object | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _required_float(value: object, field_name: str) -> float:
    if value is None:
        raise DrcInputError(f"{field_name} must be provided")
    try:
        number = float(cast(Any, value))
    except (TypeError, ValueError) as exc:
        raise DrcInputError(f"{field_name} must be numeric") from exc
    if not math.isfinite(number):
        raise DrcInputError(f"{field_name} must be finite")
    return number


def _optional_float(value: object | None) -> float:
    if value is None:
        return math.nan
    if isinstance(value, float) and math.isnan(value):
        return math.nan
    if isinstance(value, str) and not value.strip():
        return math.nan
    return _required_float(value, "optional numeric field")


def _bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n", ""}:
        return False
    raise DrcInputError(f"boolean field contains unsupported value: {value!r}")


def _coerce_enum_value(
    value: object | None,
    enum_type: type[EnumT],
    field_name: str,
) -> str:
    text = _required_text(value, field_name)
    try:
        return enum_type(text).value
    except ValueError as exc:
        raise DrcInputError(f"{field_name} contains unsupported value: {text}") from exc


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
            pairs.append((str(source), str(target)))
        frozen.append(tuple(sorted(pairs)))
    return tuple(frozen)


def _freeze_citation_ids(
    values: Sequence[Sequence[str]] | None,
    row_count: int,
) -> tuple[tuple[str, ...], ...]:
    if values is None:
        return tuple(("US_NPR_210_SCOPE",) for _ in range(row_count))
    return tuple(tuple(str(item) for item in row) for row in values)


def _short_can_offset(*, long_seniority: DrcSeniority, short_seniority: DrcSeniority) -> bool:
    return _seniority_rank(short_seniority) >= _seniority_rank(long_seniority)


def _seniority_rank(seniority: DrcSeniority) -> int:
    try:
        return _SENIORITY_RANK[seniority]
    except KeyError as exc:  # pragma: no cover - all enum values are mapped.
        raise DrcInputError(f"missing DRC seniority rank: {seniority.value}") from exc


def _slug(value: str) -> str:
    return value.lower().replace(" ", "-").replace("_", "-")


__all__ = [
    "DrcBatchCapitalCalculation",
    "DrcPositionBatch",
    "build_drc_nonsec_batch_from_columns",
    "build_drc_nonsec_batch_from_positions",
    "calculate_drc_capital_from_batch",
    "input_hash_for_drc_batch",
]
