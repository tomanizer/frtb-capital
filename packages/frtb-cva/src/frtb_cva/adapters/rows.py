"""Dataclass row adapters for CVA batch contracts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from frtb_cva._batch_contracts import (
    CvaCounterpartyBatch,
    CvaHedgeBatch,
    CvaNettingSetBatch,
    SaCvaSensitivityBatch,
)
from frtb_cva.adapters.columns import (
    build_cva_counterparty_batch_from_columns,
    build_cva_hedge_batch_from_columns,
    build_cva_netting_set_batch_from_columns,
)
from frtb_cva.adapters.sensitivity import build_sa_cva_sensitivity_batch_from_columns
from frtb_cva.data_models import (
    CvaCounterparty,
    CvaHedge,
    CvaNettingSet,
    CvaSourceLineage,
    SaCvaSensitivity,
)
from frtb_cva.validation import (
    CvaInputError,
    validate_cva_counterparties,
    validate_cva_hedges,
    validate_cva_netting_sets,
    validate_sa_cva_sensitivities,
)

_DEFAULT_ROW_SOURCE_SYSTEM = "canonical-dataclass"
_DEFAULT_ROW_SOURCE_FILE = "dataclass-input"


def _lineage_source_system(lineage: CvaSourceLineage | None) -> str:
    return _DEFAULT_ROW_SOURCE_SYSTEM if lineage is None else lineage.source_system


def _lineage_source_file(lineage: CvaSourceLineage | None) -> str:
    return _DEFAULT_ROW_SOURCE_FILE if lineage is None else lineage.source_file


def build_cva_counterparty_batch_from_counterparties(
    counterparties: Iterable[CvaCounterparty],
    *,
    source_hash: str | None = None,
    handoff_hash: str | None = None,
    diagnostics: Sequence[Mapping[str, object]] = (),
) -> CvaCounterpartyBatch:
    """Build a counterparty batch from existing canonical dataclasses.

    Parameters
    ----------
    counterparties : Iterable[CvaCounterparty]
        Validated counterparty dataclass rows.
    source_hash : str or None, optional
        Upstream content hash for audit lineage.
    handoff_hash : str or None, optional
        Normalized handoff hash when rows originate from Arrow adapters.
    diagnostics : Sequence[Mapping[str, object]], optional
        Adapter diagnostics stored on the batch container.

    Returns
    -------
    CvaCounterpartyBatch
        Columnar batch with frozen NumPy/object arrays.

    Raises
    ------
    CvaInputError
        If validation fails or the iterable is empty.
    """

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
        lineage_source_systems=[_lineage_source_system(item.lineage) for item in validated],
        lineage_source_files=[_lineage_source_file(item.lineage) for item in validated],
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
    """Build a netting-set batch from existing canonical dataclasses.

    Parameters
    ----------
    netting_sets : Iterable[CvaNettingSet]
        Validated netting-set dataclass rows.
    counterparties : Iterable[CvaCounterparty] or None, optional
        Counterparties used to validate netting-set counterparty references.
    source_hash : str or None, optional
        Upstream content hash for audit lineage.
    handoff_hash : str or None, optional
        Normalized handoff hash when rows originate from Arrow adapters.
    diagnostics : Sequence[Mapping[str, object]], optional
        Adapter diagnostics stored on the batch container.

    Returns
    -------
    CvaNettingSetBatch
        Columnar batch with EAD sign conventions already normalised on rows.

    Raises
    ------
    CvaInputError
        If validation fails or the iterable is empty.
    """

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
        lineage_source_systems=[_lineage_source_system(item.lineage) for item in validated],
        lineage_source_files=[_lineage_source_file(item.lineage) for item in validated],
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
    """Build a hedge batch from existing canonical dataclasses.

    Parameters
    ----------
    hedges : Iterable[CvaHedge]
        Hedge dataclass rows (may be empty).
    source_hash : str or None, optional
        Upstream content hash for audit lineage.
    handoff_hash : str or None, optional
        Normalized handoff hash when rows originate from Arrow adapters.
    diagnostics : Sequence[Mapping[str, object]], optional
        Adapter diagnostics stored on the batch container.

    Returns
    -------
    CvaHedgeBatch
        Columnar batch ready for BA-CVA full and SA-CVA hedge recognition paths.
    """

    validated = validate_cva_hedges(hedges)
    return build_cva_hedge_batch_from_columns(
        hedge_ids=[item.hedge_id for item in validated],
        source_row_ids=[item.source_row_id for item in validated],
        counterparty_ids=[item.counterparty_id for item in validated],
        hedge_types=[
            None if item.hedge_type is None else item.hedge_type.value for item in validated
        ],
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
        sa_cva_hedge_purposes=[
            None if item.sa_cva_hedge_purpose is None else item.sa_cva_hedge_purpose.value
            for item in validated
        ],
        sa_cva_hedge_instrument_types=[
            None
            if item.sa_cva_hedge_instrument_type is None
            else item.sa_cva_hedge_instrument_type.value
            for item in validated
        ],
        whole_transaction_evidence_ids=[item.whole_transaction_evidence_id for item in validated],
        market_risk_ima_eligibilities=[item.market_risk_ima_eligible for item in validated],
        market_risk_ima_exclusion_reasons=[
            item.market_risk_ima_exclusion_reason for item in validated
        ],
        eligibility_evidence_ids=[item.eligibility_evidence_id for item in validated],
        rejection_reasons=[item.rejection_reason for item in validated],
        lineage_source_systems=[_lineage_source_system(item.lineage) for item in validated],
        lineage_source_files=[_lineage_source_file(item.lineage) for item in validated],
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
    """Build a sensitivity batch from existing canonical dataclasses.

    Parameters
    ----------
    sensitivities : Iterable[SaCvaSensitivity]
        Validated SA-CVA sensitivity dataclass rows.
    source_hash : str or None, optional
        Upstream content hash for audit lineage.
    handoff_hash : str or None, optional
        Normalized handoff hash when rows originate from Arrow adapters.
    diagnostics : Sequence[Mapping[str, object]], optional
        Adapter diagnostics stored on the batch container.

    Returns
    -------
    SaCvaSensitivityBatch
        Columnar batch with index-treatment columns preserved for bucket routing.

    Raises
    ------
    CvaInputError
        If validation fails or the iterable is empty.
    """

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
        lineage_source_systems=[_lineage_source_system(item.lineage) for item in validated],
        lineage_source_files=[_lineage_source_file(item.lineage) for item in validated],
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
