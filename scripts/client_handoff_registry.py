"""Registry of public client handoff contracts for validation-only tooling."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

import pyarrow as pa  # type: ignore[import-untyped]
from frtb_common import ColumnSpec, NormalizedArrowTable

NormalizeCallable = Callable[..., NormalizedArrowTable]
BuildBatchCallable = Callable[[NormalizedArrowTable], object]


@dataclass(frozen=True)
class HandoffEntry:
    package: str
    handoff_id: str
    column_specs: tuple[ColumnSpec, ...]
    normalize: NormalizeCallable
    build_batch: BuildBatchCallable | None = None


def handoff_registry() -> Mapping[tuple[str, str], HandoffEntry]:
    """Return the public handoff registry used by validation scripts."""

    import frtb_cva
    import frtb_drc
    import frtb_ima
    import frtb_rrao
    import frtb_sbm

    entries = (
        HandoffEntry(
            package="frtb_drc",
            handoff_id="nonsec",
            column_specs=frtb_drc.DRC_NONSEC_ARROW_COLUMN_SPECS,
            normalize=frtb_drc.normalize_drc_nonsec_arrow_table,
            build_batch=frtb_drc.build_drc_nonsec_batch_from_arrow,
        ),
        HandoffEntry(
            package="frtb_drc",
            handoff_id="securitisation_non_ctp",
            column_specs=frtb_drc.DRC_SECURITISATION_NON_CTP_ARROW_COLUMN_SPECS,
            normalize=frtb_drc.normalize_drc_securitisation_non_ctp_arrow_table,
            build_batch=frtb_drc.build_drc_securitisation_non_ctp_batch_from_arrow,
        ),
        HandoffEntry(
            package="frtb_drc",
            handoff_id="ctp",
            column_specs=frtb_drc.DRC_CTP_ARROW_COLUMN_SPECS,
            normalize=frtb_drc.normalize_drc_ctp_arrow_table,
            build_batch=frtb_drc.build_drc_ctp_batch_from_arrow,
        ),
        HandoffEntry(
            package="frtb_rrao",
            handoff_id="positions",
            column_specs=frtb_rrao.RRAO_ARROW_COLUMN_SPECS,
            normalize=frtb_rrao.normalize_rrao_arrow_table,
            build_batch=frtb_rrao.build_rrao_batch_from_arrow,
        ),
        HandoffEntry(
            package="frtb_cva",
            handoff_id="counterparty",
            column_specs=frtb_cva.CVA_COUNTERPARTY_ARROW_COLUMN_SPECS,
            normalize=frtb_cva.normalize_cva_counterparty_arrow_table,
            build_batch=frtb_cva.build_cva_counterparty_batch_from_arrow,
        ),
        HandoffEntry(
            package="frtb_cva",
            handoff_id="netting_set",
            column_specs=frtb_cva.CVA_NETTING_SET_ARROW_COLUMN_SPECS,
            normalize=frtb_cva.normalize_cva_netting_set_arrow_table,
            build_batch=frtb_cva.build_cva_netting_set_batch_from_arrow,
        ),
        HandoffEntry(
            package="frtb_sbm",
            handoff_id="girr_delta",
            column_specs=frtb_sbm.GIRR_DELTA_ARROW_COLUMN_SPECS,
            normalize=frtb_sbm.normalize_girr_delta_arrow_table,
            build_batch=frtb_sbm.build_girr_delta_batch_from_arrow,
        ),
        HandoffEntry(
            package="frtb_ima",
            handoff_id="scenario_metadata",
            column_specs=frtb_ima.IMA_SCENARIO_METADATA_ARROW_COLUMN_SPECS,
            normalize=frtb_ima.normalize_ima_scenario_metadata_arrow_table,
            build_batch=frtb_ima.build_scenario_metadata_batch_from_arrow,
        ),
        HandoffEntry(
            package="frtb_ima",
            handoff_id="rfet_observation",
            column_specs=frtb_ima.IMA_RFET_OBSERVATION_ARROW_COLUMN_SPECS,
            normalize=frtb_ima.normalize_ima_rfet_observation_arrow_table,
            build_batch=frtb_ima.build_rfet_observation_batch_from_arrow,
        ),
    )
    return {(entry.package, entry.handoff_id): entry for entry in entries}


def resolve_handoff_entry(package: str, handoff_id: str) -> HandoffEntry:
    registry = handoff_registry()
    key = (package, handoff_id)
    try:
        return registry[key]
    except KeyError as exc:
        available = ", ".join(f"{pkg}:{handoff}" for pkg, handoff in sorted(registry))
        raise KeyError(f"Unknown handoff {package}:{handoff_id}. Available: {available}") from exc


def empty_table_for_specs(specs: tuple[ColumnSpec, ...]) -> pa.Table:
    return pa.table({spec.name: [] for spec in specs})


__all__ = ["HandoffEntry", "empty_table_for_specs", "handoff_registry", "resolve_handoff_entry"]
