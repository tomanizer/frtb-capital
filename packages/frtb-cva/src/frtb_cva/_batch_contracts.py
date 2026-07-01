"""CVA batch dataclasses and calculation result contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from frtb_common import CalculationScope

from frtb_cva._batch_columns import (
    BoolArray,
    FloatArray,
    ObjectArray,
)
from frtb_cva.data_models import (
    CvaCapitalResult,
)


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
    org_scopes: tuple[CalculationScope | None, ...] | None = None

    @property
    def row_count(self) -> int:
        """Return the number of counterparty rows in the batch.

        Returns
        -------
        int
            Length of the ``counterparty_ids`` column.
        """
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
    org_scopes: tuple[CalculationScope | None, ...] | None = None
    exposure_time_series_ids: ObjectArray | None = None

    @property
    def row_count(self) -> int:
        """Return the number of netting-set rows in the batch.

        Returns
        -------
        int
            Length of the ``netting_set_ids`` column.
        """
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
    sa_cva_hedge_purposes: ObjectArray
    sa_cva_hedge_instrument_types: ObjectArray
    whole_transaction_evidence_ids: ObjectArray
    market_risk_ima_eligibilities: ObjectArray
    market_risk_ima_exclusion_reasons: ObjectArray
    eligibility_evidence_ids: ObjectArray
    rejection_reasons: ObjectArray
    lineage_source_systems: ObjectArray
    lineage_source_files: ObjectArray
    lineage_source_row_ids: ObjectArray
    source_column_maps: tuple[tuple[tuple[str, str], ...], ...]
    source_hash: str | None = None
    handoff_hash: str | None = None
    diagnostics: tuple[Mapping[str, object], ...] = ()
    volatility_surface_ids: ObjectArray | None = None
    volatility_surface_point_ids: ObjectArray | None = None
    shock_ids: ObjectArray | None = None

    @property
    def row_count(self) -> int:
        """Return the number of hedge rows in the batch.

        Returns
        -------
        int
            Length of the ``hedge_ids`` column.
        """
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
        """Return the number of SA-CVA sensitivity rows in the batch.

        Returns
        -------
        int
            Length of the ``sensitivity_ids`` column.
        """
        return int(self.sensitivity_ids.shape[0])


@dataclass(frozen=True)
class CvaBatchCapitalCalculation:
    """CVA batch calculation plus materialization counters for audit."""

    result: CvaCapitalResult
    accepted_counterparty_dataclasses_materialized: int = 0
    accepted_netting_set_dataclasses_materialized: int = 0
    accepted_hedge_dataclasses_materialized: int = 0
    accepted_sensitivity_dataclasses_materialized: int = 0
