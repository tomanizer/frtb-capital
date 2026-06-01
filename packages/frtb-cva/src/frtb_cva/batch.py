"""Package-owned CVA batches for high-volume BA-CVA and SA-CVA kernels."""

from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence, Sized
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Any, TypeVar, cast

import numpy as np
import numpy.typing as npt

from frtb_cva.aggregation import aggregate_weighted_sensitivities
from frtb_cva.audit import validate_cva_result_reconciliation
from frtb_cva.ba_cva import _unique_citations
from frtb_cva.data_models import (
    BaCvaCounterpartyCapital,
    BaCvaFullPortfolioResult,
    BaCvaHedgeRecognitionLine,
    BaCvaHedgeType,
    BaCvaReducedPortfolioResult,
    BaCvaStandAloneLine,
    CreditQuality,
    CvaCalculationContext,
    CvaCapitalResult,
    CvaCounterparty,
    CvaHedge,
    CvaMethod,
    CvaMethodComponentTotal,
    CvaNettingSet,
    CvaRegulatoryProfile,
    CvaRunControls,
    CvaSector,
    HedgeEligibility,
    HedgeReferenceRelation,
    SaCvaIndexTreatment,
    SaCvaRiskClass,
    SaCvaRiskClassCapital,
    SaCvaRiskFactorKey,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SaCvaWeightedSensitivity,
    SensitivityTag,
)
from frtb_cva.hedges import HedgeEligibilityDecision
from frtb_cva.reference_data import (
    ba_cva_alpha,
    ba_cva_beta,
    ba_cva_discount_scalar,
    ba_cva_hedge_counterparty_correlation,
    ba_cva_index_risk_weight_scalar,
    ba_cva_rho,
    ba_cva_risk_weight,
    compute_non_imm_discount_factor,
    resolve_netting_set_discount_factor,
)
from frtb_cva.regimes import get_cva_rule_profile
from frtb_cva.sa_cva import sa_cva_aggregation_config
from frtb_cva.sa_cva_reference_data import (
    CCS_QUALIFIED_INDEX_BUCKET,
    CCS_SINGLE_NAME_BUCKETS,
    EQUITY_QUALIFIED_INDEX_BUCKETS,
    RCS_DELTA_RISK_WEIGHTS,
    ccs_single_name_bucket_for_sector,
    parse_ccs_entity_key,
)
from frtb_cva.scope import ScopeResolution
from frtb_cva.validation import (
    VALID_AMOUNT_SIGN_CONVENTIONS,
    VALID_EAD_SIGN_CONVENTIONS,
    CvaInputError,
    normalise_ead_amount,
    normalise_sensitivity_amount,
    validate_calculation_context,
    validate_cva_counterparties,
    validate_cva_hedges,
    validate_cva_netting_sets,
    validate_m_cva_multiplier,
    validate_sa_cva_sensitivities,
)
from frtb_cva.weighted_sensitivity import (
    _weight_ccs_delta,
    _weight_commodity_delta,
    _weight_commodity_vega,
    _weight_equity_delta,
    _weight_equity_vega,
    _weight_fx_delta,
    _weight_fx_vega,
    _weight_girr_delta,
    _weight_girr_vega,
    _weight_rcs_delta,
    _weight_rcs_vega,
    sort_weighted_sensitivities,
)

ObjectArray = npt.NDArray[np.object_]
FloatArray = npt.NDArray[np.float64]
BoolArray = npt.NDArray[np.bool_]
ArrayInput = npt.NDArray[Any]
ColumnInput = Sequence[object] | ArrayInput
NullableColumnInput = Sequence[object | None] | ArrayInput
EnumT = TypeVar("EnumT", bound=StrEnum)
ArrayScalarT = TypeVar("ArrayScalarT", bound=np.generic)


@dataclass(frozen=True)
class CvaCounterpartyBatch:
    """Kernel-facing canonical counterparty batch."""

    counterparty_ids: ObjectArray
    desk_ids: ObjectArray
    legal_entities: ObjectArray
    sectors: ObjectArray
    credit_qualities: ObjectArray
    regions: ObjectArray
    source_row_ids: ObjectArray
    lineage_source_systems: ObjectArray
    lineage_source_files: ObjectArray
    lineage_source_row_ids: ObjectArray
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...]
    source_hash: str | None = None
    handoff_hash: str | None = None
    diagnostics: tuple[Mapping[str, object], ...] = ()

    @property
    def row_count(self) -> int:
        return int(self.counterparty_ids.shape[0])


@dataclass(frozen=True)
class CvaNettingSetBatch:
    """Kernel-facing canonical BA-CVA netting-set batch."""

    netting_set_ids: ObjectArray
    counterparty_ids: ObjectArray
    eads: FloatArray
    effective_maturities: FloatArray
    discount_factors: FloatArray
    currencies: ObjectArray
    sign_conventions: ObjectArray
    uses_imm_eads: BoolArray
    source_row_ids: ObjectArray
    carved_out_to_ba_cva: BoolArray
    discount_factor_explicit: BoolArray
    lineage_source_systems: ObjectArray
    lineage_source_files: ObjectArray
    lineage_source_row_ids: ObjectArray
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...]
    source_hash: str | None = None
    handoff_hash: str | None = None
    diagnostics: tuple[Mapping[str, object], ...] = ()

    @property
    def row_count(self) -> int:
        return int(self.netting_set_ids.shape[0])


@dataclass(frozen=True)
class CvaHedgeBatch:
    """Kernel-facing canonical CVA hedge batch."""

    hedge_ids: ObjectArray
    source_row_ids: ObjectArray
    counterparty_ids: ObjectArray
    hedge_types: ObjectArray
    notionals: FloatArray
    remaining_maturities: FloatArray
    discount_factors: FloatArray
    reference_sectors: ObjectArray
    reference_credit_qualities: ObjectArray
    reference_regions: ObjectArray
    reference_relations: ObjectArray
    eligibilities: ObjectArray
    is_internal: BoolArray
    discount_factor_explicit: BoolArray
    internal_desk_counterparty_ids: ObjectArray
    sa_cva_risk_classes: ObjectArray
    eligibility_evidence_ids: ObjectArray
    rejection_reasons: ObjectArray
    lineage_source_systems: ObjectArray
    lineage_source_files: ObjectArray
    lineage_source_row_ids: ObjectArray
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...]
    source_hash: str | None = None
    handoff_hash: str | None = None
    diagnostics: tuple[Mapping[str, object], ...] = ()

    @property
    def row_count(self) -> int:
        return int(self.hedge_ids.shape[0])


@dataclass(frozen=True)
class SaCvaSensitivityBatch:
    """Kernel-facing canonical SA-CVA sensitivity batch."""

    sensitivity_ids: ObjectArray
    risk_classes: ObjectArray
    risk_measures: ObjectArray
    sensitivity_tags: ObjectArray
    bucket_ids: ObjectArray
    risk_factor_keys: ObjectArray
    amounts: FloatArray
    amount_currencies: ObjectArray
    sign_conventions: ObjectArray
    source_row_ids: ObjectArray
    tenors: ObjectArray
    volatility_inputs: FloatArray
    hedge_ids: ObjectArray
    index_treatments: ObjectArray
    index_max_sector_weights: FloatArray
    index_homogeneous_sector_quality: BoolArray
    index_dominant_sectors: ObjectArray
    index_remap_bucket_ids: ObjectArray
    lineage_source_systems: ObjectArray
    lineage_source_files: ObjectArray
    lineage_source_row_ids: ObjectArray
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...]
    source_hash: str | None = None
    handoff_hash: str | None = None
    diagnostics: tuple[Mapping[str, object], ...] = ()

    @property
    def row_count(self) -> int:
        return int(self.sensitivity_ids.shape[0])


@dataclass(frozen=True)
class CvaBatchCapitalCalculation:
    """CVA batch calculation plus materialization counters for audit."""

    result: CvaCapitalResult
    accepted_counterparty_dataclasses_materialized: int = 0
    accepted_netting_set_dataclasses_materialized: int = 0
    accepted_hedge_dataclasses_materialized: int = 0
    accepted_sensitivity_dataclasses_materialized: int = 0


def build_cva_counterparty_batch_from_counterparties(
    counterparties: Iterable[CvaCounterparty],
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> CvaCounterpartyBatch:
    """Build a counterparty batch from existing canonical dataclasses."""

    validated = validate_cva_counterparties(counterparties)
    if not validated:
        raise CvaInputError("counterparty batch requires at least one row", field="counterparties")
    return build_cva_counterparty_batch_from_columns(
        counterparty_ids=[item.counterparty_id for item in validated],
        desk_ids=[item.desk_id for item in validated],
        legal_entities=[item.legal_entity for item in validated],
        sectors=[item.sector.value for item in validated],
        credit_qualities=[item.credit_quality.value for item in validated],
        regions=[item.region for item in validated],
        source_row_ids=[item.source_row_id for item in validated],
        lineage_source_systems=[
            "" if item.lineage is None else item.lineage.source_system for item in validated
        ],
        lineage_source_files=[
            "" if item.lineage is None else item.lineage.source_file for item in validated
        ],
        lineage_source_row_ids=[
            item.source_row_id if item.lineage is None else item.lineage.source_row_id
            for item in validated
        ],
        source_column_maps=[
            () if item.lineage is None else item.lineage.source_column_map for item in validated
        ],
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_cva_netting_set_batch_from_netting_sets(
    netting_sets: Iterable[CvaNettingSet],
    *,
    counterparties: Iterable[CvaCounterparty] | None = None,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> CvaNettingSetBatch:
    """Build a netting-set batch from existing canonical dataclasses."""

    validated_counterparties = (
        validate_cva_counterparties(counterparties) if counterparties is not None else None
    )
    validated = validate_cva_netting_sets(netting_sets, counterparties=validated_counterparties)
    if not validated:
        raise CvaInputError("netting-set batch requires at least one row", field="netting_sets")
    return build_cva_netting_set_batch_from_columns(
        netting_set_ids=[item.netting_set_id for item in validated],
        counterparty_ids=[item.counterparty_id for item in validated],
        eads=[item.ead for item in validated],
        effective_maturities=[item.effective_maturity for item in validated],
        discount_factors=[item.discount_factor for item in validated],
        currencies=[item.currency for item in validated],
        sign_conventions=[item.sign_convention for item in validated],
        uses_imm_eads=[item.uses_imm_ead for item in validated],
        source_row_ids=[item.source_row_id for item in validated],
        carved_out_to_ba_cva=[item.carved_out_to_ba_cva for item in validated],
        discount_factor_explicit=[item.discount_factor_explicit for item in validated],
        lineage_source_systems=[
            "" if item.lineage is None else item.lineage.source_system for item in validated
        ],
        lineage_source_files=[
            "" if item.lineage is None else item.lineage.source_file for item in validated
        ],
        lineage_source_row_ids=[
            item.source_row_id if item.lineage is None else item.lineage.source_row_id
            for item in validated
        ],
        source_column_maps=[
            () if item.lineage is None else item.lineage.source_column_map for item in validated
        ],
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_cva_hedge_batch_from_hedges(
    hedges: Iterable[CvaHedge],
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> CvaHedgeBatch:
    """Build a hedge batch from existing canonical dataclasses."""

    validated = validate_cva_hedges(hedges)
    return build_cva_hedge_batch_from_columns(
        hedge_ids=[item.hedge_id for item in validated],
        source_row_ids=[item.source_row_id for item in validated],
        counterparty_ids=[item.counterparty_id for item in validated],
        hedge_types=[item.hedge_type.value for item in validated],
        notionals=[item.notional for item in validated],
        remaining_maturities=[item.remaining_maturity for item in validated],
        discount_factors=[item.discount_factor for item in validated],
        reference_sectors=[item.reference_sector.value for item in validated],
        reference_credit_qualities=[item.reference_credit_quality.value for item in validated],
        reference_regions=[item.reference_region for item in validated],
        reference_relations=[item.reference_relation.value for item in validated],
        eligibilities=[item.eligibility.value for item in validated],
        is_internal=[item.is_internal for item in validated],
        discount_factor_explicit=[item.discount_factor_explicit for item in validated],
        internal_desk_counterparty_ids=[item.internal_desk_counterparty_id for item in validated],
        sa_cva_risk_classes=[
            None if item.sa_cva_risk_class is None else item.sa_cva_risk_class.value
            for item in validated
        ],
        eligibility_evidence_ids=[item.eligibility_evidence_id for item in validated],
        rejection_reasons=[item.rejection_reason for item in validated],
        lineage_source_systems=[
            "" if item.lineage is None else item.lineage.source_system for item in validated
        ],
        lineage_source_files=[
            "" if item.lineage is None else item.lineage.source_file for item in validated
        ],
        lineage_source_row_ids=[
            item.source_row_id if item.lineage is None else item.lineage.source_row_id
            for item in validated
        ],
        source_column_maps=[
            () if item.lineage is None else item.lineage.source_column_map for item in validated
        ],
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_sa_cva_sensitivity_batch_from_sensitivities(
    sensitivities: Iterable[SaCvaSensitivity],
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> SaCvaSensitivityBatch:
    """Build a sensitivity batch from existing canonical dataclasses."""

    validated = validate_sa_cva_sensitivities(sensitivities)
    if not validated:
        raise CvaInputError("sensitivity batch requires at least one row", field="sensitivities")
    return build_sa_cva_sensitivity_batch_from_columns(
        sensitivity_ids=[item.sensitivity_id for item in validated],
        risk_classes=[item.risk_class.value for item in validated],
        risk_measures=[item.risk_measure.value for item in validated],
        sensitivity_tags=[item.sensitivity_tag.value for item in validated],
        bucket_ids=[item.bucket_id for item in validated],
        risk_factor_keys=[item.risk_factor_key for item in validated],
        amounts=[item.amount for item in validated],
        amount_currencies=[item.amount_currency for item in validated],
        sign_conventions=[item.sign_convention for item in validated],
        source_row_ids=[item.source_row_id for item in validated],
        tenors=[item.tenor for item in validated],
        volatility_inputs=[item.volatility_input for item in validated],
        hedge_ids=[item.hedge_id for item in validated],
        index_treatments=[
            None if item.index_treatment is None else item.index_treatment.value
            for item in validated
        ],
        index_max_sector_weights=[item.index_max_sector_weight for item in validated],
        index_homogeneous_sector_quality=[
            item.index_homogeneous_sector_quality for item in validated
        ],
        index_dominant_sectors=[
            None if item.index_dominant_sector is None else item.index_dominant_sector.value
            for item in validated
        ],
        index_remap_bucket_ids=[item.index_remap_bucket_id for item in validated],
        lineage_source_systems=[
            "" if item.lineage is None else item.lineage.source_system for item in validated
        ],
        lineage_source_files=[
            "" if item.lineage is None else item.lineage.source_file for item in validated
        ],
        lineage_source_row_ids=[
            item.source_row_id if item.lineage is None else item.lineage.source_row_id
            for item in validated
        ],
        source_column_maps=[
            () if item.lineage is None else item.lineage.source_column_map for item in validated
        ],
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=diagnostics,
    )


def build_cva_counterparty_batch_from_columns(
    *,
    counterparty_ids: ColumnInput,
    desk_ids: ColumnInput,
    legal_entities: ColumnInput,
    sectors: ColumnInput,
    credit_qualities: ColumnInput,
    regions: ColumnInput,
    source_row_ids: ColumnInput,
    lineage_source_systems: ColumnInput,
    lineage_source_files: ColumnInput,
    lineage_source_row_ids: ColumnInput | None = None,
    source_column_maps: Sequence[Sequence[tuple[str, str]]] | None = None,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    copy_arrays: bool = True,
) -> CvaCounterpartyBatch:
    row_count = len(counterparty_ids)
    if row_count == 0:
        raise CvaInputError("counterparty batch requires at least one row", field="counterparties")
    _require_lengths(
        row_count,
        desk_ids=desk_ids,
        legal_entities=legal_entities,
        sectors=sectors,
        credit_qualities=credit_qualities,
        regions=regions,
        source_row_ids=source_row_ids,
        lineage_source_systems=lineage_source_systems,
        lineage_source_files=lineage_source_files,
    )
    _require_optional_lengths(
        row_count,
        lineage_source_row_ids=lineage_source_row_ids,
        source_column_maps=source_column_maps,
    )
    batch = CvaCounterpartyBatch(
        counterparty_ids=_required_text_array(
            counterparty_ids, "counterparty_id", copy=copy_arrays
        ),
        desk_ids=_required_text_array(desk_ids, "desk_id", copy=copy_arrays),
        legal_entities=_required_text_array(legal_entities, "legal_entity", copy=copy_arrays),
        sectors=_enum_array(sectors, CvaSector, "sector", copy=copy_arrays),
        credit_qualities=_enum_array(
            credit_qualities,
            CreditQuality,
            "credit_quality",
            copy=copy_arrays,
        ),
        regions=_required_text_array(regions, "region", copy=copy_arrays),
        source_row_ids=_required_text_array(source_row_ids, "source_row_id", copy=copy_arrays),
        lineage_source_systems=_required_text_array(
            lineage_source_systems,
            "lineage.source_system",
            copy=copy_arrays,
        ),
        lineage_source_files=_required_text_array(
            lineage_source_files,
            "lineage.source_file",
            copy=copy_arrays,
        ),
        lineage_source_row_ids=_required_text_array(
            source_row_ids if lineage_source_row_ids is None else lineage_source_row_ids,
            "lineage.source_row_id",
            copy=copy_arrays,
        ),
        source_column_maps=_freeze_source_column_maps(source_column_maps, row_count),
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=tuple(dict(item) for item in diagnostics),
    )
    _require_unique(batch.counterparty_ids, field="counterparty_id")
    return batch


def build_cva_netting_set_batch_from_columns(
    *,
    netting_set_ids: ColumnInput,
    counterparty_ids: ColumnInput,
    eads: ColumnInput,
    effective_maturities: ColumnInput,
    discount_factors: ColumnInput,
    currencies: ColumnInput,
    sign_conventions: ColumnInput,
    uses_imm_eads: ColumnInput,
    source_row_ids: ColumnInput,
    carved_out_to_ba_cva: ColumnInput | None = None,
    discount_factor_explicit: ColumnInput | None = None,
    lineage_source_systems: ColumnInput | None = None,
    lineage_source_files: ColumnInput | None = None,
    lineage_source_row_ids: ColumnInput | None = None,
    source_column_maps: Sequence[Sequence[tuple[str, str]]] | None = None,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    copy_arrays: bool = True,
) -> CvaNettingSetBatch:
    row_count = len(netting_set_ids)
    if row_count == 0:
        raise CvaInputError("netting-set batch requires at least one row", field="netting_sets")
    _require_lengths(
        row_count,
        counterparty_ids=counterparty_ids,
        eads=eads,
        effective_maturities=effective_maturities,
        discount_factors=discount_factors,
        currencies=currencies,
        sign_conventions=sign_conventions,
        uses_imm_eads=uses_imm_eads,
        source_row_ids=source_row_ids,
    )
    _require_optional_lengths(
        row_count,
        carved_out_to_ba_cva=carved_out_to_ba_cva,
        discount_factor_explicit=discount_factor_explicit,
        lineage_source_systems=lineage_source_systems,
        lineage_source_files=lineage_source_files,
        lineage_source_row_ids=lineage_source_row_ids,
        source_column_maps=source_column_maps,
    )
    netting_set_id_array = _required_text_array(netting_set_ids, "netting_set_id", copy=copy_arrays)
    sign_convention_array = _required_text_array(
        sign_conventions,
        "sign_convention",
        copy=copy_arrays,
    )
    ead_array = _normalised_ead_array(
        _float_array(eads, "ead", copy=copy_arrays),
        sign_convention_array,
        record_ids=netting_set_id_array,
    )
    batch = CvaNettingSetBatch(
        netting_set_ids=netting_set_id_array,
        counterparty_ids=_required_text_array(
            counterparty_ids, "counterparty_id", copy=copy_arrays
        ),
        eads=ead_array,
        effective_maturities=_float_array(
            effective_maturities,
            "effective_maturity",
            copy=copy_arrays,
        ),
        discount_factors=_float_array(discount_factors, "discount_factor", copy=copy_arrays),
        currencies=_required_text_array(currencies, "currency", copy=copy_arrays),
        sign_conventions=sign_convention_array,
        uses_imm_eads=_bool_array(uses_imm_eads, row_count, default=False, copy=copy_arrays),
        source_row_ids=_required_text_array(source_row_ids, "source_row_id", copy=copy_arrays),
        carved_out_to_ba_cva=_bool_array(
            carved_out_to_ba_cva,
            row_count,
            default=False,
            copy=copy_arrays,
        ),
        discount_factor_explicit=_bool_array(
            discount_factor_explicit,
            row_count,
            default=False,
            copy=copy_arrays,
        ),
        lineage_source_systems=_required_text_array(
            _default_text_sequence(lineage_source_systems, row_count, "cva-batch"),
            "lineage.source_system",
            copy=copy_arrays,
        ),
        lineage_source_files=_required_text_array(
            _default_text_sequence(lineage_source_files, row_count, "columns"),
            "lineage.source_file",
            copy=copy_arrays,
        ),
        lineage_source_row_ids=_required_text_array(
            source_row_ids if lineage_source_row_ids is None else lineage_source_row_ids,
            "lineage.source_row_id",
            copy=copy_arrays,
        ),
        source_column_maps=_freeze_source_column_maps(source_column_maps, row_count),
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=tuple(dict(item) for item in diagnostics),
    )
    _validate_netting_set_batch(batch)
    return batch


def build_cva_hedge_batch_from_columns(
    *,
    hedge_ids: ColumnInput,
    source_row_ids: ColumnInput,
    counterparty_ids: ColumnInput,
    hedge_types: ColumnInput,
    notionals: ColumnInput,
    remaining_maturities: ColumnInput,
    discount_factors: ColumnInput,
    reference_sectors: ColumnInput,
    reference_credit_qualities: ColumnInput,
    reference_regions: ColumnInput,
    reference_relations: ColumnInput,
    eligibilities: ColumnInput,
    is_internal: ColumnInput,
    discount_factor_explicit: ColumnInput | None = None,
    internal_desk_counterparty_ids: NullableColumnInput | None = None,
    sa_cva_risk_classes: NullableColumnInput | None = None,
    eligibility_evidence_ids: NullableColumnInput | None = None,
    rejection_reasons: NullableColumnInput | None = None,
    lineage_source_systems: ColumnInput | None = None,
    lineage_source_files: ColumnInput | None = None,
    lineage_source_row_ids: ColumnInput | None = None,
    source_column_maps: Sequence[Sequence[tuple[str, str]]] | None = None,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    copy_arrays: bool = True,
) -> CvaHedgeBatch:
    row_count = len(hedge_ids)
    _require_lengths(
        row_count,
        source_row_ids=source_row_ids,
        counterparty_ids=counterparty_ids,
        hedge_types=hedge_types,
        notionals=notionals,
        remaining_maturities=remaining_maturities,
        discount_factors=discount_factors,
        reference_sectors=reference_sectors,
        reference_credit_qualities=reference_credit_qualities,
        reference_regions=reference_regions,
        reference_relations=reference_relations,
        eligibilities=eligibilities,
        is_internal=is_internal,
    )
    _require_optional_lengths(
        row_count,
        discount_factor_explicit=discount_factor_explicit,
        internal_desk_counterparty_ids=internal_desk_counterparty_ids,
        sa_cva_risk_classes=sa_cva_risk_classes,
        eligibility_evidence_ids=eligibility_evidence_ids,
        rejection_reasons=rejection_reasons,
        lineage_source_systems=lineage_source_systems,
        lineage_source_files=lineage_source_files,
        lineage_source_row_ids=lineage_source_row_ids,
        source_column_maps=source_column_maps,
    )
    batch = CvaHedgeBatch(
        hedge_ids=_required_text_array(hedge_ids, "hedge_id", copy=copy_arrays),
        source_row_ids=_required_text_array(source_row_ids, "source_row_id", copy=copy_arrays),
        counterparty_ids=_required_text_array(
            counterparty_ids, "counterparty_id", copy=copy_arrays
        ),
        hedge_types=_enum_array(hedge_types, BaCvaHedgeType, "hedge_type", copy=copy_arrays),
        notionals=_float_array(notionals, "notional", copy=copy_arrays),
        remaining_maturities=_float_array(
            remaining_maturities,
            "remaining_maturity",
            copy=copy_arrays,
        ),
        discount_factors=_float_array(discount_factors, "discount_factor", copy=copy_arrays),
        reference_sectors=_enum_array(
            reference_sectors,
            CvaSector,
            "reference_sector",
            copy=copy_arrays,
        ),
        reference_credit_qualities=_enum_array(
            reference_credit_qualities,
            CreditQuality,
            "reference_credit_quality",
            copy=copy_arrays,
        ),
        reference_regions=_required_text_array(
            reference_regions, "reference_region", copy=copy_arrays
        ),
        reference_relations=_enum_array(
            reference_relations,
            HedgeReferenceRelation,
            "reference_relation",
            copy=copy_arrays,
        ),
        eligibilities=_enum_array(eligibilities, HedgeEligibility, "eligibility", copy=copy_arrays),
        is_internal=_bool_array(is_internal, row_count, default=False, copy=copy_arrays),
        discount_factor_explicit=_bool_array(
            discount_factor_explicit,
            row_count,
            default=False,
            copy=copy_arrays,
        ),
        internal_desk_counterparty_ids=_optional_text_array(
            internal_desk_counterparty_ids,
            row_count,
            copy=copy_arrays,
        ),
        sa_cva_risk_classes=_optional_enum_array(
            sa_cva_risk_classes,
            row_count,
            SaCvaRiskClass,
            "sa_cva_risk_class",
            copy=copy_arrays,
        ),
        eligibility_evidence_ids=_optional_text_array(
            eligibility_evidence_ids,
            row_count,
            copy=copy_arrays,
        ),
        rejection_reasons=_optional_text_array(rejection_reasons, row_count, copy=copy_arrays),
        lineage_source_systems=_required_text_array(
            _default_text_sequence(lineage_source_systems, row_count, "cva-batch"),
            "lineage.source_system",
            copy=copy_arrays,
        ),
        lineage_source_files=_required_text_array(
            _default_text_sequence(lineage_source_files, row_count, "columns"),
            "lineage.source_file",
            copy=copy_arrays,
        ),
        lineage_source_row_ids=_required_text_array(
            source_row_ids if lineage_source_row_ids is None else lineage_source_row_ids,
            "lineage.source_row_id",
            copy=copy_arrays,
        ),
        source_column_maps=_freeze_source_column_maps(source_column_maps, row_count),
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=tuple(dict(item) for item in diagnostics),
    )
    _validate_hedge_batch(batch)
    return batch


def build_sa_cva_sensitivity_batch_from_columns(
    *,
    sensitivity_ids: ColumnInput,
    risk_classes: ColumnInput,
    risk_measures: ColumnInput,
    sensitivity_tags: ColumnInput,
    bucket_ids: ColumnInput,
    risk_factor_keys: ColumnInput,
    amounts: ColumnInput,
    amount_currencies: ColumnInput,
    sign_conventions: ColumnInput,
    source_row_ids: ColumnInput,
    tenors: NullableColumnInput | None = None,
    volatility_inputs: NullableColumnInput | None = None,
    hedge_ids: NullableColumnInput | None = None,
    index_treatments: NullableColumnInput | None = None,
    index_max_sector_weights: NullableColumnInput | None = None,
    index_homogeneous_sector_quality: ColumnInput | None = None,
    index_dominant_sectors: NullableColumnInput | None = None,
    index_remap_bucket_ids: NullableColumnInput | None = None,
    lineage_source_systems: ColumnInput | None = None,
    lineage_source_files: ColumnInput | None = None,
    lineage_source_row_ids: ColumnInput | None = None,
    source_column_maps: Sequence[Sequence[tuple[str, str]]] | None = None,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
    copy_arrays: bool = True,
) -> SaCvaSensitivityBatch:
    row_count = len(sensitivity_ids)
    if row_count == 0:
        raise CvaInputError("sensitivity batch requires at least one row", field="sensitivities")
    _require_lengths(
        row_count,
        risk_classes=risk_classes,
        risk_measures=risk_measures,
        sensitivity_tags=sensitivity_tags,
        bucket_ids=bucket_ids,
        risk_factor_keys=risk_factor_keys,
        amounts=amounts,
        amount_currencies=amount_currencies,
        sign_conventions=sign_conventions,
        source_row_ids=source_row_ids,
    )
    _require_optional_lengths(
        row_count,
        tenors=tenors,
        volatility_inputs=volatility_inputs,
        hedge_ids=hedge_ids,
        index_treatments=index_treatments,
        index_max_sector_weights=index_max_sector_weights,
        index_homogeneous_sector_quality=index_homogeneous_sector_quality,
        index_dominant_sectors=index_dominant_sectors,
        index_remap_bucket_ids=index_remap_bucket_ids,
        lineage_source_systems=lineage_source_systems,
        lineage_source_files=lineage_source_files,
        lineage_source_row_ids=lineage_source_row_ids,
        source_column_maps=source_column_maps,
    )
    batch = SaCvaSensitivityBatch(
        sensitivity_ids=_required_text_array(sensitivity_ids, "sensitivity_id", copy=copy_arrays),
        risk_classes=_enum_array(risk_classes, SaCvaRiskClass, "risk_class", copy=copy_arrays),
        risk_measures=_enum_array(
            risk_measures,
            SaCvaRiskMeasure,
            "risk_measure",
            copy=copy_arrays,
        ),
        sensitivity_tags=_enum_array(
            sensitivity_tags,
            SensitivityTag,
            "sensitivity_tag",
            copy=copy_arrays,
        ),
        bucket_ids=_required_text_array(bucket_ids, "bucket_id", copy=copy_arrays),
        risk_factor_keys=_required_text_array(
            risk_factor_keys,
            "risk_factor_key",
            copy=copy_arrays,
        ),
        amounts=_float_array(amounts, "amount", copy=copy_arrays),
        amount_currencies=_required_text_array(
            amount_currencies,
            "amount_currency",
            copy=copy_arrays,
        ),
        sign_conventions=_required_text_array(
            sign_conventions,
            "sign_convention",
            copy=copy_arrays,
        ),
        source_row_ids=_required_text_array(source_row_ids, "source_row_id", copy=copy_arrays),
        tenors=_optional_text_array(tenors, row_count, copy=copy_arrays),
        volatility_inputs=_optional_float_array(volatility_inputs, row_count, copy=copy_arrays),
        hedge_ids=_optional_text_array(hedge_ids, row_count, copy=copy_arrays),
        index_treatments=_optional_enum_array(
            index_treatments,
            row_count,
            SaCvaIndexTreatment,
            "index_treatment",
            copy=copy_arrays,
        ),
        index_max_sector_weights=_optional_float_array(
            index_max_sector_weights,
            row_count,
            copy=copy_arrays,
        ),
        index_homogeneous_sector_quality=_bool_array(
            index_homogeneous_sector_quality,
            row_count,
            default=False,
            copy=copy_arrays,
        ),
        index_dominant_sectors=_optional_enum_array(
            index_dominant_sectors,
            row_count,
            CvaSector,
            "index_dominant_sector",
            copy=copy_arrays,
        ),
        index_remap_bucket_ids=_optional_text_array(
            index_remap_bucket_ids,
            row_count,
            copy=copy_arrays,
        ),
        lineage_source_systems=_required_text_array(
            _default_text_sequence(lineage_source_systems, row_count, "cva-batch"),
            "lineage.source_system",
            copy=copy_arrays,
        ),
        lineage_source_files=_required_text_array(
            _default_text_sequence(lineage_source_files, row_count, "columns"),
            "lineage.source_file",
            copy=copy_arrays,
        ),
        lineage_source_row_ids=_required_text_array(
            source_row_ids if lineage_source_row_ids is None else lineage_source_row_ids,
            "lineage.source_row_id",
            copy=copy_arrays,
        ),
        source_column_maps=_freeze_source_column_maps(source_column_maps, row_count),
        source_hash=source_hash,
        handoff_hash=handoff_hash,
        diagnostics=tuple(dict(item) for item in diagnostics),
    )
    _validate_sensitivity_batch(batch)
    return batch


def calculate_cva_capital_from_batches(
    context: CvaCalculationContext,
    counterparties: CvaCounterpartyBatch | None = None,
    netting_sets: CvaNettingSetBatch | None = None,
    *,
    hedges: CvaHedgeBatch | None = None,
    sensitivities: SaCvaSensitivityBatch | None = None,
) -> CvaBatchCapitalCalculation:
    """Calculate supported CVA capital from package-owned columnar batches."""

    validated_context = validate_calculation_context(context)
    counterparty_batch = counterparties or _empty_counterparty_batch()
    netting_set_batch = netting_sets or _empty_netting_set_batch()
    hedge_batch = hedges or _empty_hedge_batch()
    rule_profile = get_cva_rule_profile(validated_context.profile)
    scope = _resolve_scope_for_batches(validated_context, netting_set_batch)

    ba_cva_reduced: BaCvaReducedPortfolioResult | None = None
    ba_cva_full: BaCvaFullPortfolioResult | None = None
    ba_cva_counterparty_capitals: tuple[BaCvaCounterpartyCapital, ...] = ()
    ba_cva_netting_set_lines: tuple[BaCvaStandAloneLine, ...] = ()
    sa_cva_risk_class_capitals: tuple[SaCvaRiskClassCapital, ...] = ()
    method_components: list[CvaMethodComponentTotal] = []
    total_cva_capital = 0.0

    if scope.method is CvaMethod.MIXED_CARVE_OUT:
        if sensitivities is None:
            raise CvaInputError(
                "mixed carve-out requires SA-CVA sensitivities",
                field="sensitivities",
            )
        ba_counterparties, ba_netting_sets, sa_hedges = _partition_mixed_batches(
            counterparty_batch,
            netting_set_batch,
            hedge_batch,
            carve_out_netting_set_ids=scope.carve_out_netting_set_ids,
        )
        sa_cva_risk_class_capitals = calculate_sa_cva_capital_from_batch(
            sensitivities,
            hedges=sa_hedges,
            reporting_currency=validated_context.base_currency,
            profile=rule_profile.profile,
        )
        sa_total = sum(item.post_multiplier_capital for item in sa_cva_risk_class_capitals)
        method_components.append(
            CvaMethodComponentTotal(
                method=CvaMethod.SA_CVA,
                total_capital=sa_total,
                citations=tuple(
                    citation for item in sa_cva_risk_class_capitals for citation in item.citations
                ),
            )
        )
        ba_cva_reduced = calculate_reduced_portfolio_from_batches(
            ba_counterparties,
            ba_netting_sets,
            profile=rule_profile.profile,
        )
        method_components.append(
            CvaMethodComponentTotal(
                method=CvaMethod.BA_CVA_REDUCED,
                total_capital=ba_cva_reduced.k_reduced,
                citations=ba_cva_reduced.citations,
            )
        )
        ba_cva_counterparty_capitals = ba_cva_reduced.counterparty_capitals
        ba_cva_netting_set_lines = ba_cva_reduced.netting_set_lines
        total_cva_capital = sa_total + ba_cva_reduced.k_reduced
    elif scope.method is CvaMethod.BA_CVA_FULL:
        ba_cva_full = calculate_full_portfolio_from_batches(
            counterparty_batch,
            netting_set_batch,
            hedge_batch,
            profile=rule_profile.profile,
        )
        ba_cva_reduced = ba_cva_full.reduced
        ba_cva_counterparty_capitals = ba_cva_reduced.counterparty_capitals
        ba_cva_netting_set_lines = ba_cva_reduced.netting_set_lines
        total_cva_capital = ba_cva_full.k_full
    elif scope.method is CvaMethod.BA_CVA_REDUCED:
        ba_cva_reduced = calculate_reduced_portfolio_from_batches(
            counterparty_batch,
            netting_set_batch,
            profile=rule_profile.profile,
        )
        ba_cva_counterparty_capitals = ba_cva_reduced.counterparty_capitals
        ba_cva_netting_set_lines = ba_cva_reduced.netting_set_lines
        total_cva_capital = ba_cva_reduced.k_reduced
    elif scope.method is CvaMethod.SA_CVA:
        if counterparty_batch.row_count or netting_set_batch.row_count:
            raise CvaInputError(
                "SA-CVA does not accept counterparty or netting-set inputs; "
                "pass them only when method is BA_CVA_REDUCED or MIXED_CARVE_OUT",
                field="counterparties_or_netting_sets",
            )
        if sensitivities is None:
            raise CvaInputError("SA-CVA requires sensitivities", field="sensitivities")
        sa_cva_risk_class_capitals = calculate_sa_cva_capital_from_batch(
            sensitivities,
            hedges=hedge_batch,
            reporting_currency=validated_context.base_currency,
            profile=rule_profile.profile,
        )
        total_cva_capital = sum(item.post_multiplier_capital for item in sa_cva_risk_class_capitals)

    citations: tuple[str, ...] = ()
    if ba_cva_full is not None:
        citations = _merge_citations(citations, ba_cva_full.citations)
    if ba_cva_reduced is not None:
        citations = _collect_ba_citations(ba_cva_reduced.citations, ba_cva_netting_set_lines)
    if sa_cva_risk_class_capitals:
        citations = _merge_citations(
            citations,
            tuple(citation for item in sa_cva_risk_class_capitals for citation in item.citations),
        )

    result = CvaCapitalResult(
        run_id=validated_context.run_id,
        calculation_date=validated_context.calculation_date,
        base_currency=validated_context.base_currency,
        profile_id=rule_profile.profile.value,
        profile_hash=rule_profile.content_hash,
        input_hash=input_hash_for_cva_batches(
            validated_context,
            counterparty_batch,
            netting_set_batch,
            hedges=hedge_batch,
            sensitivities=sensitivities,
        ),
        method=scope.method,
        total_cva_capital=total_cva_capital,
        ba_cva_reduced=ba_cva_reduced,
        ba_cva_full=ba_cva_full,
        ba_cva_counterparty_capitals=ba_cva_counterparty_capitals,
        ba_cva_netting_set_lines=ba_cva_netting_set_lines,
        sa_cva_risk_class_capitals=sa_cva_risk_class_capitals,
        method_components=tuple(method_components),
        citations=citations,
        warnings=_profile_warnings(rule_profile.profile.value, scope.method),
        unsupported_flags=scope.unsupported_flags,
        audit_metadata=scope.audit_metadata,
    )
    validate_cva_result_reconciliation(result)
    return CvaBatchCapitalCalculation(result=result)


def calculate_reduced_portfolio_from_batches(
    counterparties: CvaCounterpartyBatch,
    netting_sets: CvaNettingSetBatch,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> BaCvaReducedPortfolioResult:
    """Calculate reduced BA-CVA from columnar counterparty/netting-set batches."""

    _validate_ba_relationships(counterparties, netting_sets)
    if counterparties.row_count == 0:
        raise CvaInputError("at least one counterparty is required", field="counterparties")

    netting_indices_by_counterparty = _netting_indices_by_counterparty(netting_sets)
    rho, rho_citation = ba_cva_rho(profile=profile)
    discount_scalar, discount_citation = ba_cva_discount_scalar(profile=profile)
    alpha, alpha_citation = ba_cva_alpha(profile=profile)

    capitals: list[BaCvaCounterpartyCapital] = []
    lines: list[BaCvaStandAloneLine] = []
    for counterparty_index in _sorted_indices(counterparties.counterparty_ids):
        counterparty_id = cast(str, counterparties.counterparty_ids[counterparty_index])
        netting_indices = netting_indices_by_counterparty.get(counterparty_id, ())
        if not netting_indices:
            raise CvaInputError(
                "counterparty has no netting sets",
                field="netting_sets",
                record_id=counterparty_id,
            )
        sector = CvaSector(cast(str, counterparties.sectors[counterparty_index]))
        credit_quality = CreditQuality(
            cast(str, counterparties.credit_qualities[counterparty_index])
        )
        risk_weight, rw_citation = ba_cva_risk_weight(
            sector,
            credit_quality,
            profile=profile,
        )
        counterparty_lines = tuple(
            _netting_set_line_from_batch(
                netting_sets,
                netting_index,
                counterparties,
                counterparty_index,
                profile=profile,
                risk_weight=risk_weight,
                risk_weight_citation=rw_citation,
                alpha=alpha,
                alpha_citation=alpha_citation,
                sector=sector,
                credit_quality=credit_quality,
            )
            for netting_index in netting_indices
        )
        lines.extend(counterparty_lines)
        standalone_total = sum(line.standalone_capital for line in counterparty_lines)
        capitals.append(
            BaCvaCounterpartyCapital(
                counterparty_id=counterparty_id,
                standalone_capital=standalone_total,
                netting_set_ids=tuple(line.netting_set_id for line in counterparty_lines),
                sector=sector,
                credit_quality=credit_quality,
                region=cast(str, counterparties.regions[counterparty_index]),
                citations=_unique_citations(rw_citation, "basel_mar50_15"),
            )
        )

    standalone_values = [capital.standalone_capital for capital in capitals]
    for counterparty_capital in capitals:
        if not math.isfinite(counterparty_capital.standalone_capital):
            raise CvaInputError(
                "standalone capital must be finite",
                field="standalone_capital",
                record_id=counterparty_capital.counterparty_id,
            )
    sum_scva = sum(standalone_values)
    sum_scva_squared = sum(value * value for value in standalone_values)
    k_portfolio = math.sqrt((rho * sum_scva) ** 2 + (1.0 - rho**2) * sum_scva_squared)
    return BaCvaReducedPortfolioResult(
        k_portfolio=k_portfolio,
        k_reduced=discount_scalar * k_portfolio,
        sum_scva=sum_scva,
        sum_scva_squared=sum_scva_squared,
        rho=rho,
        d_ba_cva=discount_scalar,
        alpha=alpha,
        counterparty_capitals=tuple(capitals),
        netting_set_lines=tuple(lines),
        citations=_unique_citations(
            rho_citation,
            discount_citation,
            alpha_citation,
            "basel_mar50_14",
        ),
    )


def calculate_full_portfolio_from_batches(
    counterparties: CvaCounterpartyBatch,
    netting_sets: CvaNettingSetBatch,
    hedges: CvaHedgeBatch | None = None,
    *,
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> BaCvaFullPortfolioResult:
    """Calculate full BA-CVA with hedge recognition from columnar batches."""

    hedge_batch = hedges or _empty_hedge_batch()
    reduced = calculate_reduced_portfolio_from_batches(
        counterparties, netting_sets, profile=profile
    )
    rho, rho_citation = ba_cva_rho(profile=profile)
    discount_scalar, discount_citation = ba_cva_discount_scalar(profile=profile)
    beta, beta_citation = ba_cva_beta(profile=profile)
    scva_by_counterparty = {
        item.counterparty_id: item.standalone_capital for item in reduced.counterparty_capitals
    }
    snh_by_counterparty: dict[str, float] = {
        counterparty_id: 0.0 for counterparty_id in scva_by_counterparty
    }
    hma_by_counterparty: dict[str, float] = {
        counterparty_id: 0.0 for counterparty_id in scva_by_counterparty
    }
    ih = 0.0
    hedge_lines: list[BaCvaHedgeRecognitionLine] = []

    for hedge_index in _sorted_indices(hedge_batch.hedge_ids):
        decision = _assess_ba_cva_hedge_eligibility(hedge_batch, hedge_index)
        counterparty_id = cast(str, hedge_batch.counterparty_ids[hedge_index])
        hedge_type = BaCvaHedgeType(cast(str, hedge_batch.hedge_types[hedge_index]))
        reference_relation = HedgeReferenceRelation(
            cast(str, hedge_batch.reference_relations[hedge_index])
        )
        if decision.eligibility is not HedgeEligibility.ELIGIBLE:
            hedge_lines.append(
                BaCvaHedgeRecognitionLine(
                    hedge_id=cast(str, hedge_batch.hedge_ids[hedge_index]),
                    counterparty_id=counterparty_id,
                    hedge_type=hedge_type,
                    eligibility=decision.eligibility,
                    reference_relation=reference_relation,
                    r_hc=0.0,
                    risk_weight=0.0,
                    snh_contribution=0.0,
                    hma_contribution=0.0,
                    index_contribution=0.0,
                    reason_code=decision.reason_code,
                    citations=decision.citations,
                )
            )
            continue
        if counterparty_id not in scva_by_counterparty:
            raise CvaInputError(
                "hedge counterparty is not in BA-CVA counterparty set",
                field="counterparty_id",
                record_id=counterparty_id,
            )
        r_hc, rhc_citation = ba_cva_hedge_counterparty_correlation(
            reference_relation,
            profile=profile,
        )
        risk_weight, rw_citation = _hedge_risk_weight(hedge_batch, hedge_index, profile=profile)
        discount_factor, df_citation, _ = _hedge_discount_factor(hedge_batch, hedge_index)
        weighted_notional = (
            risk_weight
            * float(hedge_batch.remaining_maturities[hedge_index])
            * float(hedge_batch.notionals[hedge_index])
            * discount_factor
        )
        if hedge_type is BaCvaHedgeType.INDEX_CDS:
            ih += weighted_notional
            hedge_lines.append(
                BaCvaHedgeRecognitionLine(
                    hedge_id=cast(str, hedge_batch.hedge_ids[hedge_index]),
                    counterparty_id=counterparty_id,
                    hedge_type=hedge_type,
                    eligibility=HedgeEligibility.ELIGIBLE,
                    reference_relation=reference_relation,
                    r_hc=r_hc,
                    risk_weight=risk_weight,
                    snh_contribution=0.0,
                    hma_contribution=0.0,
                    index_contribution=weighted_notional,
                    reason_code=decision.reason_code,
                    citations=_unique_citations(
                        rhc_citation,
                        rw_citation,
                        df_citation,
                        "basel_mar50_24",
                    ),
                )
            )
            continue
        snh_term = r_hc * weighted_notional
        snh_by_counterparty[counterparty_id] += snh_term
        hma_term = 0.0
        if reference_relation is not HedgeReferenceRelation.DIRECT:
            hma_term = (1.0 - r_hc**2) * (weighted_notional**2)
            hma_by_counterparty[counterparty_id] += hma_term
        hedge_lines.append(
            BaCvaHedgeRecognitionLine(
                hedge_id=cast(str, hedge_batch.hedge_ids[hedge_index]),
                counterparty_id=counterparty_id,
                hedge_type=hedge_type,
                eligibility=HedgeEligibility.ELIGIBLE,
                reference_relation=reference_relation,
                r_hc=r_hc,
                risk_weight=risk_weight,
                snh_contribution=snh_term,
                hma_contribution=hma_term,
                index_contribution=0.0,
                reason_code=decision.reason_code,
                citations=_unique_citations(
                    rhc_citation,
                    rw_citation,
                    df_citation,
                    "basel_mar50_23",
                ),
            )
        )

    adjusted = [
        scva_by_counterparty[counterparty_id] - snh_by_counterparty[counterparty_id]
        for counterparty_id in sorted(scva_by_counterparty)
    ]
    systematic = rho * sum(adjusted) - ih
    idiosyncratic = sum(value * value for value in adjusted)
    hma_total = sum(hma_by_counterparty.values())
    k_portfolio_hedged = math.sqrt(systematic**2 + (1.0 - rho**2) * idiosyncratic + hma_total)
    k_hedged = discount_scalar * k_portfolio_hedged
    k_full = beta * reduced.k_reduced + (1.0 - beta) * k_hedged
    beta_floor = beta * reduced.k_reduced
    beta_floor_binding = k_full + 1e-12 < beta_floor
    if beta_floor_binding:
        k_full = beta_floor

    return BaCvaFullPortfolioResult(
        k_full=k_full,
        k_hedged=k_hedged,
        k_reduced=reduced.k_reduced,
        k_portfolio_hedged=k_portfolio_hedged,
        ih=ih,
        beta=beta,
        beta_floor_binding=beta_floor_binding,
        rho=rho,
        d_ba_cva=discount_scalar,
        reduced=reduced,
        hedge_lines=tuple(hedge_lines),
        counterparty_adjusted_standalone=tuple(
            (
                counterparty_id,
                scva_by_counterparty[counterparty_id] - snh_by_counterparty[counterparty_id],
            )
            for counterparty_id in sorted(scva_by_counterparty)
        ),
        citations=_unique_citations(
            rho_citation,
            discount_citation,
            beta_citation,
            "basel_mar50_17",
            "basel_mar50_20",
            "basel_mar50_21",
        ),
    )


def calculate_sa_cva_capital_from_batch(
    sensitivities: SaCvaSensitivityBatch,
    *,
    hedges: CvaHedgeBatch | None = None,
    m_cva: float = 1.0,
    reporting_currency: str = "USD",
    profile: CvaRegulatoryProfile | str = CvaRegulatoryProfile.BASEL_MAR50_2020,
) -> tuple[SaCvaRiskClassCapital, ...]:
    """Calculate supported SA-CVA risk-class totals from a sensitivity batch."""

    validated_m_cva = validate_m_cva_multiplier(m_cva)
    if sensitivities.row_count == 0:
        raise CvaInputError("SA-CVA requires at least one sensitivity", field="sensitivities")
    grouped = _group_sa_cva_indices_by_path(sensitivities)
    hedge_batch = hedges or _empty_hedge_batch()
    eligible_hedges = _eligible_sa_cva_hedge_ids(hedge_batch)
    results: list[SaCvaRiskClassCapital] = []
    for risk_class, risk_measure in sorted(grouped, key=str):
        indices = grouped[(risk_class, risk_measure)]
        weighted = _compute_weighted_sensitivities_from_batch(
            sensitivities,
            indices,
            hedge_batch=hedge_batch,
            eligible_hedge_ids=eligible_hedges,
            reporting_currency=reporting_currency,
            profile=profile,
        )
        config = sa_cva_aggregation_config(risk_class, risk_measure, profile=profile)
        results.append(
            aggregate_weighted_sensitivities(
                sort_weighted_sensitivities(weighted),
                config=config,
                m_cva=validated_m_cva,
                profile=profile,
            )
        )
    return tuple(results)


def input_hash_for_cva_batches(
    context: CvaCalculationContext,
    counterparties: CvaCounterpartyBatch | None = None,
    netting_sets: CvaNettingSetBatch | None = None,
    *,
    hedges: CvaHedgeBatch | None = None,
    sensitivities: SaCvaSensitivityBatch | None = None,
) -> str:
    """Return the row-compatible deterministic input hash for CVA batches."""

    counterparty_payloads = (
        []
        if counterparties is None
        else [
            _counterparty_payload(counterparties, index)
            for index in range(counterparties.row_count)
        ]
    )
    netting_set_payloads = (
        []
        if netting_sets is None
        else [_netting_set_payload(netting_sets, index) for index in range(netting_sets.row_count)]
    )
    hedge_payloads = (
        []
        if hedges is None
        else [_hedge_payload(hedges, index) for index in range(hedges.row_count)]
    )
    sensitivity_payloads = (
        []
        if sensitivities is None
        else [
            _sensitivity_payload(sensitivities, index) for index in range(sensitivities.row_count)
        ]
    )
    return _hash_payload(
        {
            "context": _context_payload(context),
            "counterparties": counterparty_payloads,
            "netting_sets": netting_set_payloads,
            "hedges": hedge_payloads,
            "sensitivities": sensitivity_payloads,
        }
    )


_SUPPORTED_SA_CVA_PATHS: frozenset[tuple[SaCvaRiskClass, SaCvaRiskMeasure]] = frozenset(
    {
        (SaCvaRiskClass.GIRR, SaCvaRiskMeasure.DELTA),
        (SaCvaRiskClass.GIRR, SaCvaRiskMeasure.VEGA),
        (SaCvaRiskClass.FX, SaCvaRiskMeasure.DELTA),
        (SaCvaRiskClass.FX, SaCvaRiskMeasure.VEGA),
        (SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD, SaCvaRiskMeasure.DELTA),
        (SaCvaRiskClass.REFERENCE_CREDIT_SPREAD, SaCvaRiskMeasure.DELTA),
        (SaCvaRiskClass.REFERENCE_CREDIT_SPREAD, SaCvaRiskMeasure.VEGA),
        (SaCvaRiskClass.EQUITY, SaCvaRiskMeasure.DELTA),
        (SaCvaRiskClass.EQUITY, SaCvaRiskMeasure.VEGA),
        (SaCvaRiskClass.COMMODITY, SaCvaRiskMeasure.DELTA),
        (SaCvaRiskClass.COMMODITY, SaCvaRiskMeasure.VEGA),
    }
)


def _group_sa_cva_indices_by_path(
    sensitivities: SaCvaSensitivityBatch,
) -> dict[tuple[SaCvaRiskClass, SaCvaRiskMeasure], list[int]]:
    risk_classes = sensitivities.risk_classes
    risk_measures = sensitivities.risk_measures
    ccs_vega = (risk_classes == SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD.value) & (
        risk_measures == SaCvaRiskMeasure.VEGA.value
    )
    if bool(np.any(ccs_vega)):
        raise CvaInputError(
            "CCS vega capital is not permitted under MAR50.45 and MAR50.63",
            field="sensitivities",
        )

    supported_mask = np.zeros(sensitivities.row_count, dtype=np.bool_)
    grouped: dict[tuple[SaCvaRiskClass, SaCvaRiskMeasure], list[int]] = {}
    for risk_class, risk_measure in sorted(_SUPPORTED_SA_CVA_PATHS, key=str):
        path_mask = (risk_classes == risk_class.value) & (risk_measures == risk_measure.value)
        if not bool(np.any(path_mask)):
            continue
        grouped[(risk_class, risk_measure)] = [int(index) for index in np.nonzero(path_mask)[0]]
        supported_mask |= path_mask

    unsupported_mask = ~supported_mask
    if bool(np.any(unsupported_mask)):
        unsupported = {
            (
                SaCvaRiskClass(cast(str, risk_classes[index])),
                SaCvaRiskMeasure(cast(str, risk_measures[index])),
            )
            for index in np.nonzero(unsupported_mask)[0]
        }
        labels = ", ".join(
            f"{risk_class.value}/{risk_measure.value}"
            for risk_class, risk_measure in sorted(unsupported, key=str)
        )
        raise CvaInputError(
            f"unsupported SA-CVA risk classes: {labels}",
            field="sensitivities",
        )
    return grouped


def _validate_netting_set_batch(batch: CvaNettingSetBatch) -> None:
    _require_unique(batch.netting_set_ids, field="netting_set_id")
    for index in range(batch.row_count):
        record_id = cast(str, batch.netting_set_ids[index])
        sign_convention = cast(str, batch.sign_conventions[index])
        if sign_convention not in VALID_EAD_SIGN_CONVENTIONS:
            raise CvaInputError(
                f"sign_convention must be one of {sorted(VALID_EAD_SIGN_CONVENTIONS)}",
                field="sign_convention",
                record_id=record_id,
            )
        ead = float(batch.eads[index])
        normalised_ead = normalise_ead_amount(ead, source_sign_convention=sign_convention)  # type: ignore[arg-type]
        if normalised_ead != ead:
            raise CvaInputError(
                "EAD must be stored after sign-convention normalisation",
                field="ead",
                record_id=record_id,
            )
        if float(batch.effective_maturities[index]) < 0.0:
            raise CvaInputError(
                "effective maturity must be non-negative",
                field="effective_maturity",
                record_id=record_id,
            )
        if float(batch.discount_factors[index]) <= 0.0:
            raise CvaInputError(
                "discount factor must be positive",
                field="discount_factor",
                record_id=record_id,
            )


def _validate_hedge_batch(batch: CvaHedgeBatch) -> None:
    _require_unique(batch.hedge_ids, field="hedge_id")
    for index in range(batch.row_count):
        record_id = cast(str, batch.hedge_ids[index])
        if float(batch.notionals[index]) < 0.0:
            raise CvaInputError(
                "notional must be non-negative", field="notional", record_id=record_id
            )
        if HedgeEligibility(cast(str, batch.eligibilities[index])) is HedgeEligibility.ELIGIBLE:
            _required_text(
                batch.eligibility_evidence_ids[index], "eligibility_evidence_id", record_id
            )
        if HedgeEligibility(cast(str, batch.eligibilities[index])) is HedgeEligibility.INELIGIBLE:
            _required_text(batch.rejection_reasons[index], "rejection_reason", record_id)


def _validate_sensitivity_batch(batch: SaCvaSensitivityBatch) -> None:
    _require_unique(batch.sensitivity_ids, field="sensitivity_id")
    for index in range(batch.row_count):
        record_id = cast(str, batch.sensitivity_ids[index])
        sign_convention = cast(str, batch.sign_conventions[index])
        if sign_convention not in VALID_AMOUNT_SIGN_CONVENTIONS:
            raise CvaInputError(
                f"sign_convention must be one of {sorted(VALID_AMOUNT_SIGN_CONVENTIONS)}",
                field="sign_convention",
                record_id=record_id,
            )
        normalise_sensitivity_amount(float(batch.amounts[index]))
        risk_class = SaCvaRiskClass(cast(str, batch.risk_classes[index]))
        risk_measure = SaCvaRiskMeasure(cast(str, batch.risk_measures[index]))
        tenor = batch.tenors[index]
        if (
            risk_class is SaCvaRiskClass.GIRR
            and risk_measure is SaCvaRiskMeasure.DELTA
            and tenor is None
        ):
            raise CvaInputError(
                "GIRR delta sensitivities must specify tenor",
                field="tenor",
                record_id=record_id,
            )
        if risk_measure is SaCvaRiskMeasure.VEGA and math.isnan(
            float(batch.volatility_inputs[index])
        ):
            raise CvaInputError(
                "vega sensitivities must specify volatility_input",
                field="volatility_input",
                record_id=record_id,
            )
        if SensitivityTag(cast(str, batch.sensitivity_tags[index])) is SensitivityTag.HDG:
            _required_text(batch.hedge_ids[index], "hedge_id", record_id)
        max_sector_weight = float(batch.index_max_sector_weights[index])
        if not math.isnan(max_sector_weight) and not (0.0 <= max_sector_weight <= 1.0):
            raise CvaInputError(
                "index_max_sector_weight must be between 0.0 and 1.0",
                field="index_max_sector_weight",
                record_id=record_id,
            )


def _validate_ba_relationships(
    counterparties: CvaCounterpartyBatch,
    netting_sets: CvaNettingSetBatch,
) -> None:
    if netting_sets.row_count == 0:
        return
    missing_mask = ~np.isin(netting_sets.counterparty_ids, counterparties.counterparty_ids)
    if bool(np.any(missing_mask)):
        index = int(np.nonzero(missing_mask)[0][0])
        raise CvaInputError(
            "netting set references unknown counterparty",
            field="counterparty_id",
            record_id=cast(str, netting_sets.netting_set_ids[index]),
        )


def _netting_indices_by_counterparty(
    netting_sets: CvaNettingSetBatch,
) -> dict[str, tuple[int, ...]]:
    if netting_sets.row_count == 0:
        return {}
    counterparty_keys = np.asarray(netting_sets.counterparty_ids, dtype=str)
    netting_set_keys = np.asarray(netting_sets.netting_set_ids, dtype=str)
    order = np.lexsort((netting_set_keys, counterparty_keys))
    grouped: dict[str, tuple[int, ...]] = {}
    start = 0
    while start < order.shape[0]:
        counterparty_id = counterparty_keys[int(order[start])]
        end = start + 1
        while end < order.shape[0] and counterparty_keys[int(order[end])] == counterparty_id:
            end += 1
        grouped[counterparty_id] = tuple(int(index) for index in order[start:end])
        start = end
    return grouped


def _resolve_scope_for_batches(
    context: CvaCalculationContext,
    netting_sets: CvaNettingSetBatch,
) -> ScopeResolution:
    unsupported_flags: list[str] = []
    audit_metadata: list[tuple[str, str]] = [
        ("requested_method", context.method.value),
        ("sa_cva_approved", str(context.sa_cva_approved)),
    ]
    if context.method is CvaMethod.BA_CVA_FULL:
        audit_metadata.append(("resolved_method", CvaMethod.BA_CVA_FULL.value))
        return ScopeResolution(
            context.method,
            context.carve_out_netting_set_ids,
            tuple(audit_metadata),
            tuple(unsupported_flags),
        )
    if context.method is CvaMethod.SA_CVA:
        if not context.sa_cva_approved:
            raise CvaInputError(
                "SA-CVA requires sa_cva_approved=True in calculation context",
                field="sa_cva_approved",
            )
        audit_metadata.append(("resolved_method", CvaMethod.SA_CVA.value))
        return ScopeResolution(
            context.method,
            context.carve_out_netting_set_ids,
            tuple(audit_metadata),
            tuple(unsupported_flags),
        )
    if context.method is CvaMethod.MIXED_CARVE_OUT:
        if not context.sa_cva_approved:
            raise CvaInputError(
                "mixed carve-out requires sa_cva_approved=True in calculation context",
                field="sa_cva_approved",
            )
        if not context.carve_out_netting_set_ids:
            raise CvaInputError(
                "mixed carve-out requires carve_out_netting_set_ids",
                field="carve_out_netting_set_ids",
            )
        _validate_carve_out_batch_evidence(context.carve_out_netting_set_ids, netting_sets)
        audit_metadata.append(("resolved_method", CvaMethod.MIXED_CARVE_OUT.value))
        return ScopeResolution(
            context.method,
            context.carve_out_netting_set_ids,
            tuple(audit_metadata),
            tuple(unsupported_flags),
        )
    if context.carve_out_netting_set_ids:
        _validate_carve_out_batch_ids(context.carve_out_netting_set_ids, netting_sets)
    audit_metadata.append(("resolved_method", CvaMethod.BA_CVA_REDUCED.value))
    return ScopeResolution(
        CvaMethod.BA_CVA_REDUCED,
        context.carve_out_netting_set_ids,
        tuple(audit_metadata),
        tuple(unsupported_flags),
    )


def _validate_carve_out_batch_ids(
    carve_out_ids: tuple[str, ...],
    netting_sets: CvaNettingSetBatch,
) -> None:
    known_ids = {cast(str, value) for value in netting_sets.netting_set_ids.tolist()}
    for netting_set_id in carve_out_ids:
        if netting_set_id not in known_ids:
            raise CvaInputError(
                f"carve-out netting set {netting_set_id!r} is missing from inputs",
                field="carve_out_netting_set_ids",
                record_id=netting_set_id,
            )


def _validate_carve_out_batch_evidence(
    carve_out_ids: tuple[str, ...],
    netting_sets: CvaNettingSetBatch,
) -> None:
    _validate_carve_out_batch_ids(carve_out_ids, netting_sets)
    carve_out_set = set(carve_out_ids)
    for index in range(netting_sets.row_count):
        netting_set_id = cast(str, netting_sets.netting_set_ids[index])
        carved = bool(netting_sets.carved_out_to_ba_cva[index])
        if netting_set_id in carve_out_set and not carved:
            raise CvaInputError(
                "carved-out netting set must set carved_out_to_ba_cva=True",
                field="carved_out_to_ba_cva",
                record_id=netting_set_id,
            )
        if carved and netting_set_id not in carve_out_set:
            raise CvaInputError(
                "carved_out_to_ba_cva netting set must appear in carve_out_netting_set_ids",
                field="carve_out_netting_set_ids",
                record_id=netting_set_id,
            )


def _partition_mixed_batches(
    counterparties: CvaCounterpartyBatch,
    netting_sets: CvaNettingSetBatch,
    hedges: CvaHedgeBatch,
    *,
    carve_out_netting_set_ids: tuple[str, ...],
) -> tuple[CvaCounterpartyBatch, CvaNettingSetBatch, CvaHedgeBatch]:
    carve_out_set = set(carve_out_netting_set_ids)
    netting_indices = [
        index
        for index in range(netting_sets.row_count)
        if netting_sets.netting_set_ids[index] in carve_out_set
    ]
    ba_counterparty_ids = {
        cast(str, netting_sets.counterparty_ids[index]) for index in netting_indices
    }
    counterparty_indices = [
        index
        for index in range(counterparties.row_count)
        if counterparties.counterparty_ids[index] in ba_counterparty_ids
    ]
    hedge_indices = [
        index
        for index in range(hedges.row_count)
        if hedges.counterparty_ids[index] not in ba_counterparty_ids
    ]
    return (
        _subset_counterparties(counterparties, counterparty_indices),
        _subset_netting_sets(netting_sets, netting_indices),
        _subset_hedges(hedges, hedge_indices),
    )


def _netting_set_line_from_batch(
    netting_sets: CvaNettingSetBatch,
    netting_index: int,
    counterparties: CvaCounterpartyBatch,
    counterparty_index: int,
    *,
    profile: CvaRegulatoryProfile | str,
    risk_weight: float | None = None,
    risk_weight_citation: str | None = None,
    alpha: float | None = None,
    alpha_citation: str | None = None,
    sector: CvaSector | None = None,
    credit_quality: CreditQuality | None = None,
) -> BaCvaStandAloneLine:
    resolved_sector = sector or CvaSector(cast(str, counterparties.sectors[counterparty_index]))
    resolved_credit_quality = credit_quality or CreditQuality(
        cast(str, counterparties.credit_qualities[counterparty_index])
    )
    if risk_weight is None or risk_weight_citation is None:
        risk_weight, risk_weight_citation = ba_cva_risk_weight(
            resolved_sector,
            resolved_credit_quality,
            profile=profile,
        )
    if alpha is None or alpha_citation is None:
        alpha, alpha_citation = ba_cva_alpha(profile=profile)
    discount_factor, df_citation, discount_factor_supplied = resolve_netting_set_discount_factor(
        uses_imm_ead=bool(netting_sets.uses_imm_eads[netting_index]),
        effective_maturity=float(netting_sets.effective_maturities[netting_index]),
        supplied_discount_factor=float(netting_sets.discount_factors[netting_index]),
        discount_factor_explicit=bool(netting_sets.discount_factor_explicit[netting_index]),
        profile=profile,
    )
    standalone = (
        risk_weight
        * float(netting_sets.effective_maturities[netting_index])
        * float(netting_sets.eads[netting_index])
        * discount_factor
        / alpha
    )
    return BaCvaStandAloneLine(
        netting_set_id=cast(str, netting_sets.netting_set_ids[netting_index]),
        counterparty_id=cast(str, counterparties.counterparty_ids[counterparty_index]),
        sector=resolved_sector,
        credit_quality=resolved_credit_quality,
        ead=float(netting_sets.eads[netting_index]),
        effective_maturity=float(netting_sets.effective_maturities[netting_index]),
        discount_factor=discount_factor,
        alpha=alpha,
        risk_weight=risk_weight,
        standalone_capital=standalone,
        currency=cast(str, netting_sets.currencies[netting_index]),
        source_row_id=cast(str, netting_sets.source_row_ids[netting_index]),
        citations=_unique_citations(risk_weight_citation, alpha_citation, df_citation),
        uses_imm_ead=bool(netting_sets.uses_imm_eads[netting_index]),
        discount_factor_supplied=discount_factor_supplied,
    )


def _assess_sa_cva_hedge_eligibility(batch: CvaHedgeBatch, index: int) -> HedgeEligibilityDecision:
    hedge_id = cast(str, batch.hedge_ids[index])
    eligibility = HedgeEligibility(cast(str, batch.eligibilities[index]))
    sa_risk_class = (
        None
        if batch.sa_cva_risk_classes[index] is None
        else SaCvaRiskClass(cast(str, batch.sa_cva_risk_classes[index]))
    )
    if eligibility is HedgeEligibility.INELIGIBLE:
        return HedgeEligibilityDecision(
            hedge_id=hedge_id,
            eligibility=HedgeEligibility.INELIGIBLE,
            sa_cva_risk_class=sa_risk_class,
            reason_code=cast(str | None, batch.rejection_reasons[index])
            or "hedge_marked_ineligible",
            citations=("basel_mar50_37",),
        )
    if eligibility is HedgeEligibility.EXCLUDED:
        return HedgeEligibilityDecision(
            hedge_id=hedge_id,
            eligibility=HedgeEligibility.EXCLUDED,
            sa_cva_risk_class=sa_risk_class,
            reason_code="hedge_excluded_from_sa_cva",
            citations=("basel_mar50_39",),
        )
    if bool(batch.is_internal[index]) and not batch.eligibility_evidence_ids[index]:
        return HedgeEligibilityDecision(
            hedge_id=hedge_id,
            eligibility=HedgeEligibility.INELIGIBLE,
            sa_cva_risk_class=sa_risk_class,
            reason_code="internal_hedge_missing_back_to_back_evidence",
            citations=("basel_mar50_11", "basel_mar50_39"),
        )
    return HedgeEligibilityDecision(
        hedge_id=hedge_id,
        eligibility=HedgeEligibility.ELIGIBLE,
        sa_cva_risk_class=sa_risk_class,
        reason_code="eligible_whole_transaction_hedge",
        citations=("basel_mar50_37", "basel_mar50_38"),
    )


def _assess_ba_cva_hedge_eligibility(batch: CvaHedgeBatch, index: int) -> HedgeEligibilityDecision:
    hedge_type = BaCvaHedgeType(cast(str, batch.hedge_types[index]))
    hedge_id = cast(str, batch.hedge_ids[index])
    if hedge_type not in {
        BaCvaHedgeType.SINGLE_NAME_CDS,
        BaCvaHedgeType.SINGLE_NAME_CONTINGENT_CDS,
        BaCvaHedgeType.INDEX_CDS,
    }:
        return HedgeEligibilityDecision(
            hedge_id=hedge_id,
            eligibility=HedgeEligibility.INELIGIBLE,
            sa_cva_risk_class=None,
            reason_code="instrument_type_not_eligible_for_ba_cva",
            citations=("basel_mar50_18",),
        )
    sa_decision = _assess_sa_cva_hedge_eligibility(batch, index)
    if sa_decision.eligibility is not HedgeEligibility.ELIGIBLE:
        return replace(sa_decision, eligibility=HedgeEligibility.INELIGIBLE)
    return HedgeEligibilityDecision(
        hedge_id=hedge_id,
        eligibility=HedgeEligibility.ELIGIBLE,
        sa_cva_risk_class=sa_decision.sa_cva_risk_class,
        reason_code="eligible_ba_cva_credit_spread_hedge",
        citations=("basel_mar50_18", "basel_mar50_19", "basel_mar50_37"),
    )


def _eligible_sa_cva_hedge_ids(batch: CvaHedgeBatch) -> frozenset[str]:
    eligible: set[str] = set()
    for index in range(batch.row_count):
        if _assess_sa_cva_hedge_eligibility(batch, index).eligibility is HedgeEligibility.ELIGIBLE:
            eligible.add(cast(str, batch.hedge_ids[index]))
    return frozenset(eligible)


def _hedge_discount_factor(batch: CvaHedgeBatch, index: int) -> tuple[float, str, bool]:
    discount_factor = float(batch.discount_factors[index])
    if bool(batch.discount_factor_explicit[index]) or discount_factor != 1.0:
        return discount_factor, "basel_mar50_23", True
    calculated, citation = compute_non_imm_discount_factor(float(batch.remaining_maturities[index]))
    return calculated, citation, False


def _hedge_risk_weight(
    batch: CvaHedgeBatch,
    index: int,
    *,
    profile: CvaRegulatoryProfile | str,
) -> tuple[float, str]:
    risk_weight, citation = ba_cva_risk_weight(
        CvaSector(cast(str, batch.reference_sectors[index])),
        CreditQuality(cast(str, batch.reference_credit_qualities[index])),
        profile=profile,
    )
    if BaCvaHedgeType(cast(str, batch.hedge_types[index])) is BaCvaHedgeType.INDEX_CDS:
        scalar, scalar_citation = ba_cva_index_risk_weight_scalar(profile=profile)
        return risk_weight * scalar, scalar_citation
    return risk_weight, citation


def _compute_weighted_sensitivities_from_batch(
    batch: SaCvaSensitivityBatch,
    indices: list[int],
    *,
    hedge_batch: CvaHedgeBatch,
    eligible_hedge_ids: frozenset[str],
    reporting_currency: str,
    profile: CvaRegulatoryProfile | str,
) -> tuple[SaCvaWeightedSensitivity, ...]:
    grouped_cva: dict[SaCvaRiskFactorKey, float] = defaultdict(float)
    grouped_hedge: dict[SaCvaRiskFactorKey, float] = defaultdict(float)
    grouped_ids: dict[SaCvaRiskFactorKey, list[str]] = defaultdict(list)
    grouped_volatility: dict[SaCvaRiskFactorKey, float | None] = {}
    del hedge_batch

    for index in indices:
        key = _risk_factor_key_from_batch(batch, index, profile=profile)
        volatility = _optional_float_value(batch.volatility_inputs[index])
        if key in grouped_volatility and volatility != grouped_volatility[key]:
            raise CvaInputError(
                "conflicting volatility_input for the same risk factor key",
                field="volatility_input",
            )
        grouped_volatility.setdefault(key, volatility)
        tag = SensitivityTag(cast(str, batch.sensitivity_tags[index]))
        if tag is SensitivityTag.CVA:
            grouped_cva[key] += float(batch.amounts[index])
            grouped_ids[key].append(cast(str, batch.sensitivity_ids[index]))
        elif tag is SensitivityTag.HDG:
            hedge_id = cast(str | None, batch.hedge_ids[index])
            if hedge_id not in eligible_hedge_ids:
                continue
            grouped_hedge[key] += float(batch.amounts[index])
            grouped_ids[key].append(cast(str, batch.sensitivity_ids[index]))

    keys = sorted(
        set(grouped_cva) | set(grouped_hedge),
        key=lambda item: (item.bucket_id, item.risk_factor_key, item.tenor or ""),
    )
    if not keys:
        raise CvaInputError("SA-CVA path has no eligible sensitivities", field="sensitivities")
    risk_class = keys[0].risk_class
    risk_measure = keys[0].risk_measure
    if risk_class is SaCvaRiskClass.GIRR and risk_measure is SaCvaRiskMeasure.DELTA:
        return _weight_girr_delta(
            keys,
            grouped_cva,
            grouped_hedge,
            grouped_ids,
            reporting_currency=reporting_currency,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.GIRR and risk_measure is SaCvaRiskMeasure.VEGA:
        return _weight_girr_vega(
            keys, grouped_cva, grouped_hedge, grouped_ids, grouped_volatility, profile=profile
        )
    if risk_class is SaCvaRiskClass.FX and risk_measure is SaCvaRiskMeasure.DELTA:
        return _weight_fx_delta(
            keys,
            grouped_cva,
            grouped_hedge,
            grouped_ids,
            reporting_currency=reporting_currency,
            profile=profile,
        )
    if risk_class is SaCvaRiskClass.FX and risk_measure is SaCvaRiskMeasure.VEGA:
        return _weight_fx_vega(
            keys, grouped_cva, grouped_hedge, grouped_ids, grouped_volatility, profile=profile
        )
    if (
        risk_class is SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD
        and risk_measure is SaCvaRiskMeasure.DELTA
    ):
        return _weight_ccs_delta(keys, grouped_cva, grouped_hedge, grouped_ids, profile=profile)
    if (
        risk_class is SaCvaRiskClass.REFERENCE_CREDIT_SPREAD
        and risk_measure is SaCvaRiskMeasure.DELTA
    ):
        return _weight_rcs_delta(keys, grouped_cva, grouped_hedge, grouped_ids, profile=profile)
    if (
        risk_class is SaCvaRiskClass.REFERENCE_CREDIT_SPREAD
        and risk_measure is SaCvaRiskMeasure.VEGA
    ):
        return _weight_rcs_vega(
            keys, grouped_cva, grouped_hedge, grouped_ids, grouped_volatility, profile=profile
        )
    if risk_class is SaCvaRiskClass.EQUITY and risk_measure is SaCvaRiskMeasure.DELTA:
        return _weight_equity_delta(keys, grouped_cva, grouped_hedge, grouped_ids, profile=profile)
    if risk_class is SaCvaRiskClass.EQUITY and risk_measure is SaCvaRiskMeasure.VEGA:
        return _weight_equity_vega(
            keys, grouped_cva, grouped_hedge, grouped_ids, grouped_volatility, profile=profile
        )
    if risk_class is SaCvaRiskClass.COMMODITY and risk_measure is SaCvaRiskMeasure.DELTA:
        return _weight_commodity_delta(
            keys, grouped_cva, grouped_hedge, grouped_ids, profile=profile
        )
    if risk_class is SaCvaRiskClass.COMMODITY and risk_measure is SaCvaRiskMeasure.VEGA:
        return _weight_commodity_vega(
            keys, grouped_cva, grouped_hedge, grouped_ids, grouped_volatility, profile=profile
        )
    raise CvaInputError(
        f"unsupported SA-CVA risk class/measure: {risk_class.value}/{risk_measure.value}",
        field="risk_class",
    )


def _risk_factor_key_from_batch(
    batch: SaCvaSensitivityBatch,
    index: int,
    *,
    profile: CvaRegulatoryProfile | str,
) -> SaCvaRiskFactorKey:
    del profile
    risk_class = SaCvaRiskClass(cast(str, batch.risk_classes[index]))
    bucket_id = _resolve_sa_cva_bucket_from_batch(batch, index)
    return SaCvaRiskFactorKey(
        risk_class=risk_class,
        risk_measure=SaCvaRiskMeasure(cast(str, batch.risk_measures[index])),
        bucket_id=bucket_id,
        risk_factor_key=cast(str, batch.risk_factor_keys[index]),
        tenor=cast(str | None, batch.tenors[index]),
    )


def _resolve_sa_cva_bucket_from_batch(batch: SaCvaSensitivityBatch, index: int) -> str:
    risk_class = SaCvaRiskClass(cast(str, batch.risk_classes[index]))
    bucket = cast(str, batch.bucket_ids[index])
    treatment = (
        None
        if batch.index_treatments[index] is None
        else SaCvaIndexTreatment(cast(str, batch.index_treatments[index]))
    )
    record_id = cast(str, batch.sensitivity_ids[index])
    if treatment is SaCvaIndexTreatment.LOOK_THROUGH_REQUIRED:
        raise CvaInputError(
            "non-qualified index requires constituent look-through sensitivities",
            field="index_treatment",
            record_id=record_id,
        )
    if risk_class is SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD:
        return _resolve_ccs_bucket(batch, index, bucket, treatment)
    if risk_class is SaCvaRiskClass.REFERENCE_CREDIT_SPREAD:
        return _resolve_rcs_bucket(batch, index, bucket, treatment)
    if risk_class is SaCvaRiskClass.EQUITY:
        return _resolve_equity_bucket(batch, index, bucket, treatment)
    if treatment is not None:
        raise CvaInputError(
            "qualified-index routing is only supported for CCS, RCS, and equity",
            field="index_treatment",
            record_id=record_id,
        )
    return bucket


def _resolve_ccs_bucket(
    batch: SaCvaSensitivityBatch,
    index: int,
    bucket: str,
    treatment: SaCvaIndexTreatment | None,
) -> str:
    record_id = cast(str, batch.sensitivity_ids[index])
    ccs_index_buckets = frozenset({"1", "2", "3", "4", "5", "6", "7", CCS_QUALIFIED_INDEX_BUCKET})
    if bucket not in ccs_index_buckets and treatment is not None:
        raise CvaInputError(
            f"CCS bucket {bucket} does not support qualified-index treatment",
            field="bucket_id",
            record_id=record_id,
        )
    if bucket != CCS_QUALIFIED_INDEX_BUCKET:
        if treatment is SaCvaIndexTreatment.QUALIFIED_INDEX:
            raise CvaInputError(
                "qualified CCS index must use bucket 8",
                field="bucket_id",
                record_id=record_id,
            )
        return bucket
    if treatment is not SaCvaIndexTreatment.QUALIFIED_INDEX:
        raise CvaInputError(
            "CCS bucket 8 requires qualified-index treatment metadata",
            field="index_treatment",
            record_id=record_id,
        )
    return _sector_concentration_bucket(batch, index, default_bucket=bucket)


def _resolve_rcs_bucket(
    batch: SaCvaSensitivityBatch,
    index: int,
    bucket: str,
    treatment: SaCvaIndexTreatment | None,
) -> str:
    record_id = cast(str, batch.sensitivity_ids[index])
    if bucket == "8":
        if treatment is not SaCvaIndexTreatment.QUALIFIED_INDEX:
            raise CvaInputError(
                "RCS qualified index requires QUALIFIED_INDEX treatment",
                field="index_treatment",
                record_id=record_id,
            )
        return _sector_concentration_bucket(batch, index, default_bucket=bucket)
    if treatment is SaCvaIndexTreatment.QUALIFIED_INDEX:
        raise CvaInputError(
            "RCS qualified index must use bucket 8",
            field="bucket_id",
            record_id=record_id,
        )
    return bucket


def _resolve_equity_bucket(
    batch: SaCvaSensitivityBatch,
    index: int,
    bucket: str,
    treatment: SaCvaIndexTreatment | None,
) -> str:
    record_id = cast(str, batch.sensitivity_ids[index])
    if bucket in EQUITY_QUALIFIED_INDEX_BUCKETS:
        if treatment is not SaCvaIndexTreatment.QUALIFIED_INDEX:
            raise CvaInputError(
                "equity qualified-index buckets 12/13 require QUALIFIED_INDEX treatment",
                field="index_treatment",
                record_id=record_id,
            )
        return bucket
    if treatment is SaCvaIndexTreatment.QUALIFIED_INDEX:
        raise CvaInputError(
            "qualified equity index must use buckets 12 or 13",
            field="bucket_id",
            record_id=record_id,
        )
    return bucket


def _sector_concentration_bucket(
    batch: SaCvaSensitivityBatch,
    index: int,
    *,
    default_bucket: str,
) -> str:
    weight = float(batch.index_max_sector_weights[index])
    if math.isnan(weight):
        return default_bucket
    record_id = cast(str, batch.sensitivity_ids[index])
    if not math.isfinite(weight) or not (0.0 <= weight <= 1.0):
        raise CvaInputError(
            "index_max_sector_weight must be a finite probability between 0.0 and 1.0",
            field="index_max_sector_weight",
            record_id=record_id,
        )
    if weight <= 0.75:
        return default_bucket
    if not bool(batch.index_homogeneous_sector_quality[index]):
        raise CvaInputError(
            "index with >75% sector concentration must map to single-name bucket",
            field="index_max_sector_weight",
            record_id=record_id,
        )
    remap_bucket = batch.index_remap_bucket_ids[index]
    if remap_bucket is not None:
        bucket = cast(str, remap_bucket).strip()
        if not bucket:
            raise CvaInputError(
                "index_remap_bucket_id must be a non-empty bucket id",
                field="index_remap_bucket_id",
                record_id=record_id,
            )
        _validate_remap_bucket(
            SaCvaRiskClass(cast(str, batch.risk_classes[index])), bucket, record_id=record_id
        )
        return bucket
    risk_class = SaCvaRiskClass(cast(str, batch.risk_classes[index]))
    if risk_class is SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD:
        dominant_sector = batch.index_dominant_sectors[index]
        if dominant_sector is None:
            raise CvaInputError(
                "CCS index sector concentration requires index_dominant_sector "
                "or index_remap_bucket_id",
                field="index_dominant_sector",
                record_id=record_id,
            )
        _, credit_quality, _ = parse_ccs_entity_key(cast(str, batch.risk_factor_keys[index]))
        bucket, _ = ccs_single_name_bucket_for_sector(
            CvaSector(cast(str, dominant_sector)),
            credit_quality,
        )
        return bucket
    raise CvaInputError(
        "index with >75% sector concentration requires index_remap_bucket_id for this risk class",
        field="index_remap_bucket_id",
        record_id=record_id,
    )


def _validate_remap_bucket(
    risk_class: SaCvaRiskClass,
    bucket: str,
    *,
    record_id: str,
) -> None:
    if risk_class is SaCvaRiskClass.COUNTERPARTY_CREDIT_SPREAD:
        if bucket not in CCS_SINGLE_NAME_BUCKETS:
            raise CvaInputError(
                f"CCS index remap bucket {bucket} is not a single-name bucket",
                field="index_remap_bucket_id",
                record_id=record_id,
            )
    if risk_class is SaCvaRiskClass.REFERENCE_CREDIT_SPREAD:
        single_name_buckets = frozenset(RCS_DELTA_RISK_WEIGHTS) - {CCS_QUALIFIED_INDEX_BUCKET}
        if bucket not in single_name_buckets:
            raise CvaInputError(
                f"RCS index remap bucket {bucket} is not a single-name bucket",
                field="index_remap_bucket_id",
                record_id=record_id,
            )


def _collect_ba_citations(
    reduced_citations: tuple[str, ...],
    netting_set_lines: tuple[BaCvaStandAloneLine, ...],
) -> tuple[str, ...]:
    return _merge_citations(
        reduced_citations,
        tuple(citation for line in netting_set_lines for citation in line.citations),
    )


def _merge_citations(*groups: tuple[str, ...]) -> tuple[str, ...]:
    citation_ids: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for citation_id in group:
            if citation_id not in seen:
                citation_ids.append(citation_id)
                seen.add(citation_id)
    return tuple(citation_ids)


def _profile_warnings(profile_id: str, method: CvaMethod) -> tuple[str, ...]:
    if profile_id != "BASEL_MAR50_2020":
        return ()
    if method in {CvaMethod.SA_CVA, CvaMethod.MIXED_CARVE_OUT, CvaMethod.BA_CVA_FULL}:
        return ()
    return ()


def _context_payload(context: CvaCalculationContext) -> dict[str, object]:
    run_controls = context.run_controls or CvaRunControls()
    return {
        "run_id": context.run_id,
        "calculation_date": context.calculation_date.isoformat(),
        "base_currency": context.base_currency,
        "profile": context.profile.value,
        "method": context.method.value,
        "sa_cva_approved": context.sa_cva_approved,
        "materiality_threshold_elected": context.materiality_threshold_elected,
        "carve_out_netting_set_ids": list(context.carve_out_netting_set_ids),
        "desk_id": context.desk_id,
        "legal_entity": context.legal_entity,
        "citation_policy": context.citation_policy,
        "run_controls": {
            "audit_verbosity": run_controls.audit_verbosity,
            "retain_intermediate_details": run_controls.retain_intermediate_details,
            "unsupported_feature_behaviour": run_controls.unsupported_feature_behaviour,
        },
    }


def _counterparty_payload(batch: CvaCounterpartyBatch, index: int) -> dict[str, object]:
    return {
        "counterparty_id": batch.counterparty_ids[index],
        "desk_id": batch.desk_ids[index],
        "legal_entity": batch.legal_entities[index],
        "sector": batch.sectors[index],
        "credit_quality": batch.credit_qualities[index],
        "region": batch.regions[index],
        "source_row_id": batch.source_row_ids[index],
        "lineage": _lineage_payload(batch, index),
    }


def _netting_set_payload(batch: CvaNettingSetBatch, index: int) -> dict[str, object]:
    return {
        "netting_set_id": batch.netting_set_ids[index],
        "counterparty_id": batch.counterparty_ids[index],
        "ead": float(batch.eads[index]),
        "effective_maturity": float(batch.effective_maturities[index]),
        "discount_factor": float(batch.discount_factors[index]),
        "discount_factor_explicit": bool(batch.discount_factor_explicit[index]),
        "currency": batch.currencies[index],
        "sign_convention": batch.sign_conventions[index],
        "uses_imm_ead": bool(batch.uses_imm_eads[index]),
        "carved_out_to_ba_cva": bool(batch.carved_out_to_ba_cva[index]),
        "source_row_id": batch.source_row_ids[index],
        "lineage": _lineage_payload(batch, index),
    }


def _hedge_payload(batch: CvaHedgeBatch, index: int) -> dict[str, object]:
    return {
        "hedge_id": batch.hedge_ids[index],
        "source_row_id": batch.source_row_ids[index],
        "hedge_type": batch.hedge_types[index],
        "eligibility": batch.eligibilities[index],
        "counterparty_id": batch.counterparty_ids[index],
        "reference_sector": batch.reference_sectors[index],
        "reference_credit_quality": batch.reference_credit_qualities[index],
        "reference_region": batch.reference_regions[index],
        "reference_relation": batch.reference_relations[index],
        "notional": float(batch.notionals[index]),
        "remaining_maturity": float(batch.remaining_maturities[index]),
        "discount_factor": float(batch.discount_factors[index]),
        "discount_factor_explicit": bool(batch.discount_factor_explicit[index]),
        "is_internal": bool(batch.is_internal[index]),
        "internal_desk_counterparty_id": batch.internal_desk_counterparty_ids[index],
        "eligibility_evidence_id": batch.eligibility_evidence_ids[index],
        "rejection_reason": batch.rejection_reasons[index],
        "sa_cva_risk_class": batch.sa_cva_risk_classes[index],
        "lineage": _lineage_payload(batch, index),
    }


def _sensitivity_payload(batch: SaCvaSensitivityBatch, index: int) -> dict[str, object]:
    return {
        "sensitivity_id": batch.sensitivity_ids[index],
        "risk_class": batch.risk_classes[index],
        "risk_measure": batch.risk_measures[index],
        "sensitivity_tag": batch.sensitivity_tags[index],
        "bucket_id": batch.bucket_ids[index],
        "risk_factor_key": batch.risk_factor_keys[index],
        "tenor": batch.tenors[index],
        "amount": float(batch.amounts[index]),
        "amount_currency": batch.amount_currencies[index],
        "sign_convention": batch.sign_conventions[index],
        "volatility_input": _optional_float_value(batch.volatility_inputs[index]),
        "hedge_id": batch.hedge_ids[index],
        "index_treatment": batch.index_treatments[index],
        "index_max_sector_weight": _optional_float_value(batch.index_max_sector_weights[index]),
        "index_homogeneous_sector_quality": bool(batch.index_homogeneous_sector_quality[index]),
        "index_dominant_sector": batch.index_dominant_sectors[index],
        "index_remap_bucket_id": batch.index_remap_bucket_ids[index],
        "source_row_id": batch.source_row_ids[index],
        "lineage": _lineage_payload(batch, index),
    }


def _lineage_payload(
    batch: CvaCounterpartyBatch | CvaNettingSetBatch | CvaHedgeBatch | SaCvaSensitivityBatch,
    index: int,
) -> dict[str, object]:
    return {
        "source_system": batch.lineage_source_systems[index],
        "source_file": batch.lineage_source_files[index],
        "source_row_id": batch.lineage_source_row_ids[index],
        "source_column_map": [list(pair) for pair in batch.source_column_maps[index]],
    }


def _hash_payload(payload: dict[str, object]) -> str:
    encoded = bytes(json.dumps(payload, sort_keys=True, separators=(",", ":")), "utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_lengths(row_count: int, **columns: Sized) -> None:
    for name, values in columns.items():
        if len(values) != row_count:
            raise CvaInputError(f"{name} length does not match ids", field=name)


def _require_optional_lengths(row_count: int, **columns: Sized | None) -> None:
    for name, values in columns.items():
        if values is not None and len(values) != row_count:
            raise CvaInputError(f"{name} length does not match ids", field=name)


def _required_text_array(values: ColumnInput, field: str, *, copy: bool) -> ObjectArray:
    return _object_array([_required_text(value, field) for value in values], copy=copy)


def _optional_text_array(
    values: NullableColumnInput | None,
    row_count: int,
    *,
    copy: bool,
) -> ObjectArray:
    if values is None:
        return _object_array([None] * row_count, copy=copy)
    return _object_array([_optional_text(value) for value in values], copy=copy)


def _enum_array(
    values: ColumnInput,
    enum_type: type[EnumT],
    field: str,
    *,
    copy: bool,
) -> ObjectArray:
    return _object_array([_enum_value(value, enum_type, field) for value in values], copy=copy)


def _optional_enum_array(
    values: NullableColumnInput | None,
    row_count: int,
    enum_type: type[EnumT],
    field: str,
    *,
    copy: bool,
) -> ObjectArray:
    if values is None:
        return _object_array([None] * row_count, copy=copy)
    return _object_array(
        [_optional_enum_value(value, enum_type, field) for value in values], copy=copy
    )


def _float_array(values: ColumnInput, field: str, *, copy: bool) -> FloatArray:
    fast_array = _float_array_from_numpy(values, field=field, copy=copy, allow_nan=False)
    if fast_array is not None:
        return fast_array
    array = np.asarray([_finite_float(value, field) for value in values], dtype=np.float64)
    return _readonly_array(array, copy=copy)


def _normalised_ead_array(
    eads: FloatArray,
    sign_conventions: ObjectArray,
    *,
    record_ids: ObjectArray,
) -> FloatArray:
    normalised = np.empty_like(eads, dtype=np.float64)
    for index in range(eads.shape[0]):
        record_id = cast(str, record_ids[index])
        sign_convention = cast(str, sign_conventions[index])
        if sign_convention not in VALID_EAD_SIGN_CONVENTIONS:
            raise CvaInputError(
                f"sign_convention must be one of {sorted(VALID_EAD_SIGN_CONVENTIONS)}",
                field="sign_convention",
                record_id=record_id,
            )
        normalised[index] = normalise_ead_amount(
            float(eads[index]),
            source_sign_convention=sign_convention,  # type: ignore[arg-type]
        )
    normalised.setflags(write=False)
    return normalised


def _optional_float_array(
    values: NullableColumnInput | None,
    row_count: int,
    *,
    copy: bool,
) -> FloatArray:
    if values is None:
        array = np.full(row_count, np.nan, dtype=np.float64)
    elif (
        fast_array := _float_array_from_numpy(
            values,
            field="optional numeric field",
            copy=copy,
            allow_nan=True,
        )
    ) is not None:
        return fast_array
    else:
        array = np.asarray([_optional_float(value) for value in values], dtype=np.float64)
    return _readonly_array(array, copy=copy)


def _bool_array(
    values: ColumnInput | None,
    row_count: int,
    *,
    default: bool,
    copy: bool,
) -> BoolArray:
    if values is None:
        array = np.full(row_count, default, dtype=np.bool_)
    elif isinstance(values, np.ndarray) and values.dtype == np.bool_:
        array = np.asarray(values, dtype=np.bool_)
    else:
        array = np.asarray([_bool_value(value) for value in values], dtype=np.bool_)
    return _readonly_array(array, copy=copy)


def _float_array_from_numpy(
    values: ColumnInput | NullableColumnInput,
    *,
    field: str,
    copy: bool,
    allow_nan: bool,
) -> FloatArray | None:
    if not isinstance(values, np.ndarray) or values.dtype.kind not in {"f", "i", "u"}:
        return None
    array = np.asarray(values, dtype=np.float64)
    if allow_nan:
        invalid = ~np.isnan(array) & ~np.isfinite(array)
    else:
        invalid = ~np.isfinite(array)
    if bool(np.any(invalid)):
        raise CvaInputError("value must be finite", field=field)
    return _readonly_array(array, copy=copy)


def _object_array(values: NullableColumnInput, *, copy: bool) -> ObjectArray:
    array = np.asarray(values, dtype=object)
    return _readonly_array(array, copy=copy)


def _readonly_array(
    array: npt.NDArray[ArrayScalarT],
    *,
    copy: bool,
) -> npt.NDArray[ArrayScalarT]:
    frozen = array.copy() if copy else array.view()
    frozen.setflags(write=False)
    return frozen


def _required_text(value: object, field: str, record_id: str = "") -> str:
    if not isinstance(value, str) or not value.strip():
        raise CvaInputError("non-empty text is required", field=field, record_id=record_id)
    return value


def _optional_text(value: object | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return _required_text(value, "optional text field")


def _enum_value(value: object, enum_type: type[EnumT], field: str) -> str:
    text = _required_text(value, field)
    try:
        return enum_type(text).value
    except ValueError as exc:
        raise CvaInputError(f"invalid {field}", field=field) from exc


def _optional_enum_value(
    value: object | None,
    enum_type: type[EnumT],
    field: str,
) -> str | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return _enum_value(value, enum_type, field)


def _finite_float(value: object, field: str) -> float:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value,
        (int, float, np.integer, np.floating),
    ):
        raise CvaInputError("value must be numeric", field=field)
    number = float(value)
    if not math.isfinite(number):
        raise CvaInputError("value must be finite", field=field)
    return number


def _optional_float(value: object | None) -> float:
    if value is None:
        return math.nan
    if isinstance(value, (float, np.floating)) and math.isnan(float(value)):
        return math.nan
    if isinstance(value, str) and not value.strip():
        return math.nan
    return _finite_float(value, "optional numeric field")


def _optional_float_value(value: object) -> float | None:
    if isinstance(value, (int, float, np.integer, np.floating)):
        raw = float(value)
        if math.isnan(raw):
            return None
    number = _finite_float(value, "optional numeric field")
    if math.isnan(number):
        return None
    return number


def _bool_value(value: object) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n", ""}:
        return False
    raise CvaInputError(f"boolean field contains unsupported value: {value!r}")


def _require_unique(values: ObjectArray, *, field: str) -> None:
    seen: set[str] = set()
    for value in values:
        text = cast(str, value)
        if text in seen:
            raise CvaInputError(f"duplicate {field.replace('_', ' ')}", field=field, record_id=text)
        seen.add(text)


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


def _default_text_sequence(
    values: ColumnInput | None,
    row_count: int,
    default: str,
) -> ColumnInput:
    if values is not None:
        return values
    return [default] * row_count


def _sorted_indices(values: ObjectArray) -> list[int]:
    return sorted(range(values.shape[0]), key=lambda index: cast(str, values[index]))


def _empty_counterparty_batch() -> CvaCounterpartyBatch:
    return CvaCounterpartyBatch(
        counterparty_ids=_object_array([], copy=True),
        desk_ids=_object_array([], copy=True),
        legal_entities=_object_array([], copy=True),
        sectors=_object_array([], copy=True),
        credit_qualities=_object_array([], copy=True),
        regions=_object_array([], copy=True),
        source_row_ids=_object_array([], copy=True),
        lineage_source_systems=_object_array([], copy=True),
        lineage_source_files=_object_array([], copy=True),
        lineage_source_row_ids=_object_array([], copy=True),
        source_column_maps=(),
    )


def _empty_netting_set_batch() -> CvaNettingSetBatch:
    return CvaNettingSetBatch(
        netting_set_ids=_object_array([], copy=True),
        counterparty_ids=_object_array([], copy=True),
        eads=_empty_float_array(),
        effective_maturities=_empty_float_array(),
        discount_factors=_empty_float_array(),
        currencies=_object_array([], copy=True),
        sign_conventions=_object_array([], copy=True),
        uses_imm_eads=_empty_bool_array(),
        source_row_ids=_object_array([], copy=True),
        carved_out_to_ba_cva=_empty_bool_array(),
        discount_factor_explicit=_empty_bool_array(),
        lineage_source_systems=_object_array([], copy=True),
        lineage_source_files=_object_array([], copy=True),
        lineage_source_row_ids=_object_array([], copy=True),
        source_column_maps=(),
    )


def _empty_hedge_batch() -> CvaHedgeBatch:
    return CvaHedgeBatch(
        hedge_ids=_object_array([], copy=True),
        source_row_ids=_object_array([], copy=True),
        counterparty_ids=_object_array([], copy=True),
        hedge_types=_object_array([], copy=True),
        notionals=_empty_float_array(),
        remaining_maturities=_empty_float_array(),
        discount_factors=_empty_float_array(),
        reference_sectors=_object_array([], copy=True),
        reference_credit_qualities=_object_array([], copy=True),
        reference_regions=_object_array([], copy=True),
        reference_relations=_object_array([], copy=True),
        eligibilities=_object_array([], copy=True),
        is_internal=_empty_bool_array(),
        discount_factor_explicit=_empty_bool_array(),
        internal_desk_counterparty_ids=_object_array([], copy=True),
        sa_cva_risk_classes=_object_array([], copy=True),
        eligibility_evidence_ids=_object_array([], copy=True),
        rejection_reasons=_object_array([], copy=True),
        lineage_source_systems=_object_array([], copy=True),
        lineage_source_files=_object_array([], copy=True),
        lineage_source_row_ids=_object_array([], copy=True),
        source_column_maps=(),
    )


def _subset_counterparties(batch: CvaCounterpartyBatch, indices: list[int]) -> CvaCounterpartyBatch:
    return CvaCounterpartyBatch(
        counterparty_ids=_take_object(batch.counterparty_ids, indices),
        desk_ids=_take_object(batch.desk_ids, indices),
        legal_entities=_take_object(batch.legal_entities, indices),
        sectors=_take_object(batch.sectors, indices),
        credit_qualities=_take_object(batch.credit_qualities, indices),
        regions=_take_object(batch.regions, indices),
        source_row_ids=_take_object(batch.source_row_ids, indices),
        lineage_source_systems=_take_object(batch.lineage_source_systems, indices),
        lineage_source_files=_take_object(batch.lineage_source_files, indices),
        lineage_source_row_ids=_take_object(batch.lineage_source_row_ids, indices),
        source_column_maps=tuple(batch.source_column_maps[index] for index in indices),
        source_hash=batch.source_hash,
        handoff_hash=batch.handoff_hash,
        diagnostics=batch.diagnostics,
    )


def _subset_netting_sets(batch: CvaNettingSetBatch, indices: list[int]) -> CvaNettingSetBatch:
    return CvaNettingSetBatch(
        netting_set_ids=_take_object(batch.netting_set_ids, indices),
        counterparty_ids=_take_object(batch.counterparty_ids, indices),
        eads=_take_float(batch.eads, indices),
        effective_maturities=_take_float(batch.effective_maturities, indices),
        discount_factors=_take_float(batch.discount_factors, indices),
        currencies=_take_object(batch.currencies, indices),
        sign_conventions=_take_object(batch.sign_conventions, indices),
        uses_imm_eads=_take_bool(batch.uses_imm_eads, indices),
        source_row_ids=_take_object(batch.source_row_ids, indices),
        carved_out_to_ba_cva=_take_bool(batch.carved_out_to_ba_cva, indices),
        discount_factor_explicit=_take_bool(batch.discount_factor_explicit, indices),
        lineage_source_systems=_take_object(batch.lineage_source_systems, indices),
        lineage_source_files=_take_object(batch.lineage_source_files, indices),
        lineage_source_row_ids=_take_object(batch.lineage_source_row_ids, indices),
        source_column_maps=tuple(batch.source_column_maps[index] for index in indices),
        source_hash=batch.source_hash,
        handoff_hash=batch.handoff_hash,
        diagnostics=batch.diagnostics,
    )


def _subset_hedges(batch: CvaHedgeBatch, indices: list[int]) -> CvaHedgeBatch:
    return CvaHedgeBatch(
        hedge_ids=_take_object(batch.hedge_ids, indices),
        source_row_ids=_take_object(batch.source_row_ids, indices),
        counterparty_ids=_take_object(batch.counterparty_ids, indices),
        hedge_types=_take_object(batch.hedge_types, indices),
        notionals=_take_float(batch.notionals, indices),
        remaining_maturities=_take_float(batch.remaining_maturities, indices),
        discount_factors=_take_float(batch.discount_factors, indices),
        reference_sectors=_take_object(batch.reference_sectors, indices),
        reference_credit_qualities=_take_object(batch.reference_credit_qualities, indices),
        reference_regions=_take_object(batch.reference_regions, indices),
        reference_relations=_take_object(batch.reference_relations, indices),
        eligibilities=_take_object(batch.eligibilities, indices),
        is_internal=_take_bool(batch.is_internal, indices),
        discount_factor_explicit=_take_bool(batch.discount_factor_explicit, indices),
        internal_desk_counterparty_ids=_take_object(batch.internal_desk_counterparty_ids, indices),
        sa_cva_risk_classes=_take_object(batch.sa_cva_risk_classes, indices),
        eligibility_evidence_ids=_take_object(batch.eligibility_evidence_ids, indices),
        rejection_reasons=_take_object(batch.rejection_reasons, indices),
        lineage_source_systems=_take_object(batch.lineage_source_systems, indices),
        lineage_source_files=_take_object(batch.lineage_source_files, indices),
        lineage_source_row_ids=_take_object(batch.lineage_source_row_ids, indices),
        source_column_maps=tuple(batch.source_column_maps[index] for index in indices),
        source_hash=batch.source_hash,
        handoff_hash=batch.handoff_hash,
        diagnostics=batch.diagnostics,
    )


def _take_object(values: ObjectArray, indices: list[int]) -> ObjectArray:
    return _object_array([values[index] for index in indices], copy=True)


def _take_float(values: FloatArray, indices: list[int]) -> FloatArray:
    array = np.asarray([values[index] for index in indices], dtype=np.float64)
    array.setflags(write=False)
    return array


def _take_bool(values: BoolArray, indices: list[int]) -> BoolArray:
    array = np.asarray([values[index] for index in indices], dtype=np.bool_)
    array.setflags(write=False)
    return array


def _empty_float_array() -> FloatArray:
    array = np.asarray([], dtype=np.float64)
    array.setflags(write=False)
    return array


def _empty_bool_array() -> BoolArray:
    array = np.asarray([], dtype=np.bool_)
    array.setflags(write=False)
    return array


__all__ = [
    "CvaBatchCapitalCalculation",
    "CvaCounterpartyBatch",
    "CvaHedgeBatch",
    "CvaNettingSetBatch",
    "SaCvaSensitivityBatch",
    "build_cva_counterparty_batch_from_columns",
    "build_cva_counterparty_batch_from_counterparties",
    "build_cva_hedge_batch_from_columns",
    "build_cva_hedge_batch_from_hedges",
    "build_cva_netting_set_batch_from_columns",
    "build_cva_netting_set_batch_from_netting_sets",
    "build_sa_cva_sensitivity_batch_from_columns",
    "build_sa_cva_sensitivity_batch_from_sensitivities",
    "calculate_cva_capital_from_batches",
    "calculate_full_portfolio_from_batches",
    "calculate_reduced_portfolio_from_batches",
    "calculate_sa_cva_capital_from_batch",
    "input_hash_for_cva_batches",
]
