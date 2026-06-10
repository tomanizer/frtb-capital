"""CVA Arrow entity specifications for normalized batch ingress."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from frtb_common import ColumnSpec, TabularLogicalType

from frtb_cva._arrow_ba_column_specs import (
    CVA_COUNTERPARTY_ARROW_COLUMN_SPECS,
    CVA_NETTING_SET_ARROW_COLUMN_SPECS,
)
from frtb_cva._arrow_hedge_column_specs import CVA_HEDGE_ARROW_COLUMN_SPECS
from frtb_cva._arrow_sa_column_specs import SA_CVA_SENSITIVITY_ARROW_COLUMN_SPECS
from frtb_cva.batch import (
    build_cva_counterparty_batch_from_columns,
    build_cva_hedge_batch_from_columns,
    build_cva_netting_set_batch_from_columns,
    build_sa_cva_sensitivity_batch_from_columns,
)


@dataclass(frozen=True)
class EntityBatchSpec:
    """CVA Arrow ingress contract for one batch entity.

    Parameters
    ----------
    entity : str
        Stable package-local entity key used by wrappers and diagnostics.
    column_specs : tuple[ColumnSpec, ...]
        Normalized Arrow column contract for the entity.
    column_to_argument : Mapping[str, str]
        Mapping from normalized Arrow column names to the column-builder keyword names.
    build_from_columns : Callable[..., object]
        Package-local column builder that materialises and validates the batch contract.
    validate_batch : Callable[[object], None] or None, optional
        Optional post-build validator for future entity-specific checks.
    """

    entity: str
    column_specs: tuple[ColumnSpec, ...]
    column_to_argument: Mapping[str, str]
    build_from_columns: Callable[..., object]
    validate_batch: Callable[[object], None] | None = None

    @property
    def required_columns(self) -> tuple[str, ...]:
        """Normalized column names required by this entity."""
        return tuple(spec.name for spec in self.column_specs if spec.required)

    @property
    def optional_columns(self) -> tuple[str, ...]:
        """Normalized column names accepted as optional by this entity."""
        return tuple(spec.name for spec in self.column_specs if not spec.required)


_CVA_COUNTERPARTY_BATCH_COLUMN_ARGS: Mapping[str, str] = {
    "counterparty_id": "counterparty_ids",
    "desk_id": "desk_ids",
    "legal_entity": "legal_entities",
    "sector": "sectors",
    "credit_quality": "credit_qualities",
    "region": "regions",
    "source_row_id": "source_row_ids",
    "lineage_source_system": "lineage_source_systems",
    "lineage_source_file": "lineage_source_files",
    "lineage_source_row_id": "lineage_source_row_ids",
}

_CVA_NETTING_SET_BATCH_COLUMN_ARGS: Mapping[str, str] = {
    "netting_set_id": "netting_set_ids",
    "counterparty_id": "counterparty_ids",
    "ead": "eads",
    "effective_maturity": "effective_maturities",
    "discount_factor": "discount_factors",
    "currency": "currencies",
    "sign_convention": "sign_conventions",
    "uses_imm_ead": "uses_imm_eads",
    "source_row_id": "source_row_ids",
    "carved_out_to_ba_cva": "carved_out_to_ba_cva",
    "discount_factor_explicit": "discount_factor_explicit",
    "lineage_source_system": "lineage_source_systems",
    "lineage_source_file": "lineage_source_files",
    "lineage_source_row_id": "lineage_source_row_ids",
}

_CVA_HEDGE_BATCH_COLUMN_ARGS: Mapping[str, str] = {
    "hedge_id": "hedge_ids",
    "source_row_id": "source_row_ids",
    "counterparty_id": "counterparty_ids",
    "hedge_type": "hedge_types",
    "notional": "notionals",
    "remaining_maturity": "remaining_maturities",
    "discount_factor": "discount_factors",
    "reference_sector": "reference_sectors",
    "reference_credit_quality": "reference_credit_qualities",
    "reference_region": "reference_regions",
    "reference_relation": "reference_relations",
    "eligibility": "eligibilities",
    "is_internal": "is_internal",
    "discount_factor_explicit": "discount_factor_explicit",
    "internal_desk_counterparty_id": "internal_desk_counterparty_ids",
    "sa_cva_risk_class": "sa_cva_risk_classes",
    "sa_cva_hedge_purpose": "sa_cva_hedge_purposes",
    "sa_cva_hedge_instrument_type": "sa_cva_hedge_instrument_types",
    "whole_transaction_evidence_id": "whole_transaction_evidence_ids",
    "market_risk_ima_eligible": "market_risk_ima_eligibilities",
    "market_risk_ima_exclusion_reason": "market_risk_ima_exclusion_reasons",
    "eligibility_evidence_id": "eligibility_evidence_ids",
    "rejection_reason": "rejection_reasons",
    "lineage_source_system": "lineage_source_systems",
    "lineage_source_file": "lineage_source_files",
    "lineage_source_row_id": "lineage_source_row_ids",
}

_SA_CVA_SENSITIVITY_BATCH_COLUMN_ARGS: Mapping[str, str] = {
    "sensitivity_id": "sensitivity_ids",
    "risk_class": "risk_classes",
    "risk_measure": "risk_measures",
    "sensitivity_tag": "sensitivity_tags",
    "bucket_id": "bucket_ids",
    "risk_factor_key": "risk_factor_keys",
    "amount": "amounts",
    "amount_currency": "amount_currencies",
    "sign_convention": "sign_conventions",
    "source_row_id": "source_row_ids",
    "tenor": "tenors",
    "volatility_input": "volatility_inputs",
    "hedge_id": "hedge_ids",
    "index_treatment": "index_treatments",
    "index_max_sector_weight": "index_max_sector_weights",
    "index_homogeneous_sector_quality": "index_homogeneous_sector_quality",
    "index_dominant_sector": "index_dominant_sectors",
    "index_remap_bucket_id": "index_remap_bucket_ids",
    "lineage_source_system": "lineage_source_systems",
    "lineage_source_file": "lineage_source_files",
    "lineage_source_row_id": "lineage_source_row_ids",
}


def _ensure_explicit_logical_types(*spec_groups: Sequence[ColumnSpec]) -> None:
    unknown = tuple(
        spec.name
        for spec_group in spec_groups
        for spec in spec_group
        if spec.logical_type is TabularLogicalType.UNKNOWN
    )
    if unknown:
        raise RuntimeError("CVA Arrow specs must declare logical_type: " + ", ".join(unknown))


_ensure_explicit_logical_types(
    CVA_COUNTERPARTY_ARROW_COLUMN_SPECS,
    CVA_NETTING_SET_ARROW_COLUMN_SPECS,
    CVA_HEDGE_ARROW_COLUMN_SPECS,
    SA_CVA_SENSITIVITY_ARROW_COLUMN_SPECS,
)

CVA_COUNTERPARTY_ENTITY_SPEC = EntityBatchSpec(
    entity="counterparty",
    column_specs=CVA_COUNTERPARTY_ARROW_COLUMN_SPECS,
    column_to_argument=_CVA_COUNTERPARTY_BATCH_COLUMN_ARGS,
    build_from_columns=build_cva_counterparty_batch_from_columns,
)
CVA_NETTING_SET_ENTITY_SPEC = EntityBatchSpec(
    entity="netting_set",
    column_specs=CVA_NETTING_SET_ARROW_COLUMN_SPECS,
    column_to_argument=_CVA_NETTING_SET_BATCH_COLUMN_ARGS,
    build_from_columns=build_cva_netting_set_batch_from_columns,
)
CVA_HEDGE_ENTITY_SPEC = EntityBatchSpec(
    entity="hedge",
    column_specs=CVA_HEDGE_ARROW_COLUMN_SPECS,
    column_to_argument=_CVA_HEDGE_BATCH_COLUMN_ARGS,
    build_from_columns=build_cva_hedge_batch_from_columns,
)
SA_CVA_SENSITIVITY_ENTITY_SPEC = EntityBatchSpec(
    entity="sa_cva_sensitivity",
    column_specs=SA_CVA_SENSITIVITY_ARROW_COLUMN_SPECS,
    column_to_argument=_SA_CVA_SENSITIVITY_BATCH_COLUMN_ARGS,
    build_from_columns=build_sa_cva_sensitivity_batch_from_columns,
)

CVA_ENTITY_BATCH_SPECS: Mapping[str, EntityBatchSpec] = {
    spec.entity: spec
    for spec in (
        CVA_COUNTERPARTY_ENTITY_SPEC,
        CVA_NETTING_SET_ENTITY_SPEC,
        CVA_HEDGE_ENTITY_SPEC,
        SA_CVA_SENSITIVITY_ENTITY_SPEC,
    )
}

__all__ = [
    "CVA_COUNTERPARTY_ARROW_COLUMN_SPECS",
    "CVA_COUNTERPARTY_ENTITY_SPEC",
    "CVA_ENTITY_BATCH_SPECS",
    "CVA_HEDGE_ARROW_COLUMN_SPECS",
    "CVA_HEDGE_ENTITY_SPEC",
    "CVA_NETTING_SET_ARROW_COLUMN_SPECS",
    "CVA_NETTING_SET_ENTITY_SPEC",
    "SA_CVA_SENSITIVITY_ARROW_COLUMN_SPECS",
    "SA_CVA_SENSITIVITY_ENTITY_SPEC",
    "EntityBatchSpec",
]
