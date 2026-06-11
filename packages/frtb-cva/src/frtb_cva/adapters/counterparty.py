"""Counterparty column adapter for CVA batch contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from frtb_cva._batch_columns import (
    ColumnInput,
    _enum_array,
    _freeze_source_column_maps,
    _require_lengths,
    _require_optional_lengths,
    _require_unique,
    _required_text_array,
)
from frtb_cva._batch_contracts import CvaCounterpartyBatch
from frtb_cva.data_models import CreditQuality, CvaSector
from frtb_cva.validation import CvaInputError


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
    """Build a validated counterparty batch from aligned column inputs.

    Parameters
    ----------
    counterparty_ids, desk_ids, legal_entities, sectors, credit_qualities, regions,
    source_row_ids, lineage_source_systems, lineage_source_files : ColumnInput
        Required per-row columns with matching lengths.
    lineage_source_row_ids, source_column_maps, source_hash, handoff_hash, diagnostics,
    copy_arrays : optional
        Audit lineage and array materialisation controls.

    Returns
    -------
    CvaCounterpartyBatch
        Columnar batch with unique ``counterparty_id`` values.
    """
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
            credit_qualities, CreditQuality, "credit_quality", copy=copy_arrays
        ),
        regions=_required_text_array(regions, "region", copy=copy_arrays),
        source_row_ids=_required_text_array(source_row_ids, "source_row_id", copy=copy_arrays),
        lineage_source_systems=_required_text_array(
            lineage_source_systems, "lineage.source_system", copy=copy_arrays
        ),
        lineage_source_files=_required_text_array(
            lineage_source_files, "lineage.source_file", copy=copy_arrays
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
