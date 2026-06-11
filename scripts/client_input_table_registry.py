"""Registry of public client input table contracts for validation-only tooling."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

import pyarrow as pa  # type: ignore[import-untyped]
from frtb_common import ColumnSpec, NormalizedArrowTable

NormalizeCallable = Callable[..., NormalizedArrowTable]
BuildBatchCallable = Callable[[NormalizedArrowTable], object]


@dataclass(frozen=True)
class InputTableEntry:
    package: str
    input_table_id: str
    column_specs: tuple[ColumnSpec, ...]
    normalize: NormalizeCallable
    build_batch: BuildBatchCallable | None = None


def input_table_registry() -> Mapping[tuple[str, str], InputTableEntry]:
    """Return the public input table registry used by validation scripts."""

    import frtb_cva
    import frtb_drc
    import frtb_ima
    import frtb_rrao
    import frtb_sbm

    entries = (
        InputTableEntry(
            package="frtb_drc",
            input_table_id="nonsec",
            column_specs=frtb_drc.DRC_NONSEC_ARROW_COLUMN_SPECS,
            normalize=frtb_drc.normalize_drc_nonsec_arrow_table,
            build_batch=frtb_drc.build_drc_nonsec_batch_from_arrow,
        ),
        InputTableEntry(
            package="frtb_drc",
            input_table_id="securitisation_non_ctp",
            column_specs=frtb_drc.DRC_SECURITISATION_NON_CTP_ARROW_COLUMN_SPECS,
            normalize=frtb_drc.normalize_drc_securitisation_non_ctp_arrow_table,
            build_batch=frtb_drc.build_drc_securitisation_non_ctp_batch_from_arrow,
        ),
        InputTableEntry(
            package="frtb_drc",
            input_table_id="ctp",
            column_specs=frtb_drc.DRC_CTP_ARROW_COLUMN_SPECS,
            normalize=frtb_drc.normalize_drc_ctp_arrow_table,
            build_batch=frtb_drc.build_drc_ctp_batch_from_arrow,
        ),
        InputTableEntry(
            package="frtb_rrao",
            input_table_id="positions",
            column_specs=frtb_rrao.RRAO_ARROW_COLUMN_SPECS,
            normalize=frtb_rrao.normalize_rrao_arrow_table,
            build_batch=frtb_rrao.build_rrao_batch_from_arrow,
        ),
        InputTableEntry(
            package="frtb_cva",
            input_table_id="counterparty",
            column_specs=frtb_cva.CVA_COUNTERPARTY_ARROW_COLUMN_SPECS,
            normalize=frtb_cva.normalize_cva_counterparty_arrow_table,
            build_batch=frtb_cva.build_cva_counterparty_batch_from_arrow,
        ),
        InputTableEntry(
            package="frtb_cva",
            input_table_id="netting_set",
            column_specs=frtb_cva.CVA_NETTING_SET_ARROW_COLUMN_SPECS,
            normalize=frtb_cva.normalize_cva_netting_set_arrow_table,
            build_batch=frtb_cva.build_cva_netting_set_batch_from_arrow,
        ),
        InputTableEntry(
            package="frtb_sbm",
            input_table_id="girr_delta",
            column_specs=frtb_sbm.GIRR_DELTA_ARROW_COLUMN_SPECS,
            normalize=_normalize_sbm_girr_delta_arrow_table,
            build_batch=_build_sbm_girr_delta_batch_from_arrow,
        ),
        InputTableEntry(
            package="frtb_ima",
            input_table_id="scenario_metadata",
            column_specs=frtb_ima.IMA_SCENARIO_METADATA_ARROW_COLUMN_SPECS,
            normalize=frtb_ima.normalize_ima_scenario_metadata_arrow_table,
            build_batch=frtb_ima.build_scenario_metadata_batch_from_arrow,
        ),
        InputTableEntry(
            package="frtb_ima",
            input_table_id="rfet_observation",
            column_specs=frtb_ima.IMA_RFET_OBSERVATION_ARROW_COLUMN_SPECS,
            normalize=frtb_ima.normalize_ima_rfet_observation_arrow_table,
            build_batch=frtb_ima.build_rfet_observation_batch_from_arrow,
        ),
    )
    return {(entry.package, entry.input_table_id): entry for entry in entries}


def _normalize_sbm_girr_delta_arrow_table(table: pa.Table) -> NormalizedArrowTable:
    import frtb_sbm

    return frtb_sbm.normalize_sbm_arrow_table(
        table,
        frtb_sbm.SbmRiskClass.GIRR,
        frtb_sbm.SbmRiskMeasure.DELTA,
    )


def _build_sbm_girr_delta_batch_from_arrow(handoff: NormalizedArrowTable) -> object:
    import frtb_sbm

    return frtb_sbm.build_sbm_batch_from_arrow(
        handoff,
        frtb_sbm.SbmRiskClass.GIRR,
        frtb_sbm.SbmRiskMeasure.DELTA,
    )


def resolve_input_table_entry(package: str, input_table_id: str) -> InputTableEntry:
    registry = input_table_registry()
    key = (package, input_table_id)
    try:
        return registry[key]
    except KeyError as exc:
        available = ", ".join(f"{pkg}:{input_table}" for pkg, input_table in sorted(registry))
        raise KeyError(
            f"Unknown input table {package}:{input_table_id}. Available: {available}"
        ) from exc


def empty_table_for_specs(specs: tuple[ColumnSpec, ...]) -> pa.Table:
    return pa.table({spec.name: [] for spec in specs})


__all__ = [
    "InputTableEntry",
    "empty_table_for_specs",
    "input_table_registry",
    "resolve_input_table_entry",
]
