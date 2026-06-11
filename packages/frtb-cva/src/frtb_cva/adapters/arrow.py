"""Arrow handoff adapters for CVA counterparty, netting-set, hedge, and sensitivity batches.

This module normalises vendor Arrow inputs through
:func:`frtb_common.normalize_arrow_table` and materialises
:mod:`frtb_cva.batch` columnar batches through package-owned entity specs.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, TypeVar

import pyarrow as pa  # type: ignore[import-untyped]
from frtb_common import (
    AdapterDiagnostic,
    NormalizedArrowTable,
    normalize_arrow_table,
    normalized_arrow_table_hash,
    read_arrow_columns,
)

from frtb_cva.batch import (
    CvaCounterpartyBatch,
    CvaHedgeBatch,
    CvaNettingSetBatch,
    SaCvaSensitivityBatch,
)
from frtb_cva.registry import (
    CVA_COUNTERPARTY_ARROW_COLUMN_SPECS,
    CVA_COUNTERPARTY_ENTITY_SPEC,
    CVA_ENTITY_BATCH_SPECS,
    CVA_HEDGE_ARROW_COLUMN_SPECS,
    CVA_HEDGE_ENTITY_SPEC,
    CVA_NETTING_SET_ARROW_COLUMN_SPECS,
    CVA_NETTING_SET_ENTITY_SPEC,
    SA_CVA_SENSITIVITY_ARROW_COLUMN_SPECS,
    SA_CVA_SENSITIVITY_ENTITY_SPEC,
    EntityBatchSpec,
)
from frtb_cva.validation import CvaInputError

T = TypeVar("T")


def normalize_cva_counterparty_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalise a counterparty Arrow table to the CVA column contract.

    Parameters
    ----------
    table : pyarrow.Table
        Raw vendor counterparty table.
    diagnostics : Sequence[AdapterDiagnostic], optional
        Adapter diagnostics to attach to the handoff.
    metadata : Mapping[str, str] or None, optional
        Handoff metadata stored on the normalized table.
    rejected : pyarrow.Table or None, optional
        Pre-rejected rows to merge into the handoff partition.
    source_hash : str or None, optional
        Upstream content hash for audit lineage.

    Returns
    -------
    NormalizedArrowTable
        Accepted/rejected partition with CVA counterparty column specs applied.
    """
    return normalize_cva_arrow_table(
        table,
        CVA_COUNTERPARTY_ENTITY_SPEC,
        diagnostics=diagnostics,
        metadata=metadata,
        rejected=rejected,
        source_hash=source_hash,
    )


def normalize_cva_netting_set_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalise a netting-set Arrow table to the CVA column contract.

    Parameters
    ----------
    table : pyarrow.Table
        Raw vendor netting-set table.
    diagnostics : Sequence[AdapterDiagnostic], optional
        Adapter diagnostics to attach to the handoff.
    metadata : Mapping[str, str] or None, optional
        Handoff metadata stored on the normalized table.
    rejected : pyarrow.Table or None, optional
        Pre-rejected rows to merge into the handoff partition.
    source_hash : str or None, optional
        Upstream content hash for audit lineage.

    Returns
    -------
    NormalizedArrowTable
        Accepted/rejected partition with CVA netting-set column specs applied.
    """
    return normalize_cva_arrow_table(
        table,
        CVA_NETTING_SET_ENTITY_SPEC,
        diagnostics=diagnostics,
        metadata=metadata,
        rejected=rejected,
        source_hash=source_hash,
    )


def normalize_cva_hedge_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalise a hedge Arrow table to the CVA column contract.

    Parameters
    ----------
    table : pyarrow.Table
        Raw vendor hedge table.
    diagnostics : Sequence[AdapterDiagnostic], optional
        Adapter diagnostics to attach to the handoff.
    metadata : Mapping[str, str] or None, optional
        Handoff metadata stored on the normalized table.
    rejected : pyarrow.Table or None, optional
        Pre-rejected rows to merge into the handoff partition.
    source_hash : str or None, optional
        Upstream content hash for audit lineage.

    Returns
    -------
    NormalizedArrowTable
        Accepted/rejected partition with CVA hedge column specs applied.
    """
    return normalize_cva_arrow_table(
        table,
        CVA_HEDGE_ENTITY_SPEC,
        diagnostics=diagnostics,
        metadata=metadata,
        rejected=rejected,
        source_hash=source_hash,
    )


def normalize_sa_cva_sensitivity_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalise an SA-CVA sensitivity Arrow table to the CVA column contract.

    Parameters
    ----------
    table : pyarrow.Table
        Raw vendor sensitivity table.
    diagnostics : Sequence[AdapterDiagnostic], optional
        Adapter diagnostics to attach to the handoff.
    metadata : Mapping[str, str] or None, optional
        Handoff metadata stored on the normalized table.
    rejected : pyarrow.Table or None, optional
        Pre-rejected rows to merge into the handoff partition.
    source_hash : str or None, optional
        Upstream content hash for audit lineage.

    Returns
    -------
    NormalizedArrowTable
        Accepted/rejected partition with SA-CVA sensitivity column specs applied.
    """
    return normalize_cva_arrow_table(
        table,
        SA_CVA_SENSITIVITY_ENTITY_SPEC,
        diagnostics=diagnostics,
        metadata=metadata,
        rejected=rejected,
        source_hash=source_hash,
    )


def build_cva_counterparty_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> CvaCounterpartyBatch:
    """Materialise a counterparty batch from a normalized Arrow handoff.

    Parameters
    ----------
    handoff : NormalizedArrowTable
        Accepted counterparty rows produced by :func:`normalize_cva_counterparty_arrow_table`.

    Returns
    -------
    CvaCounterpartyBatch
        Validated columnar batch with handoff and source hashes attached.

    Raises
    ------
    CvaInputError
        If ``handoff`` is not a :class:`~frtb_common.arrow_table.NormalizedArrowTable`.
    """
    return build_cva_batch_from_arrow(handoff, CVA_COUNTERPARTY_ENTITY_SPEC)


def build_cva_netting_set_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> CvaNettingSetBatch:
    """Materialise a netting-set batch from a normalized Arrow handoff.

    Parameters
    ----------
    handoff : NormalizedArrowTable
        Accepted netting-set rows from :func:`normalize_cva_netting_set_arrow_table`.

    Returns
    -------
    CvaNettingSetBatch
        Validated columnar batch with EAD sign conventions enforced.

    Raises
    ------
    CvaInputError
        If ``handoff`` is not a :class:`~frtb_common.arrow_table.NormalizedArrowTable`.
    """
    return build_cva_batch_from_arrow(handoff, CVA_NETTING_SET_ENTITY_SPEC)


def build_cva_hedge_batch_from_arrow(handoff: NormalizedArrowTable) -> CvaHedgeBatch:
    """Materialise a hedge batch from a normalized Arrow handoff.

    Parameters
    ----------
    handoff : NormalizedArrowTable
        Accepted hedge rows from :func:`normalize_cva_hedge_arrow_table`.

    Returns
    -------
    CvaHedgeBatch
        Validated columnar batch with eligibility columns preserved.

    Raises
    ------
    CvaInputError
        If ``handoff`` is not a :class:`~frtb_common.arrow_table.NormalizedArrowTable`.
    """
    return build_cva_batch_from_arrow(handoff, CVA_HEDGE_ENTITY_SPEC)


def build_sa_cva_sensitivity_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> SaCvaSensitivityBatch:
    """Materialise an SA-CVA sensitivity batch from a normalized Arrow handoff.

    Parameters
    ----------
    handoff : NormalizedArrowTable
        Accepted sensitivity rows from :func:`normalize_sa_cva_sensitivity_arrow_table`.

    Returns
    -------
    SaCvaSensitivityBatch
        Validated columnar batch ready for SA-CVA kernel weighting.

    Raises
    ------
    CvaInputError
        If ``handoff`` is not a :class:`~frtb_common.arrow_table.NormalizedArrowTable`.
    """
    return build_cva_batch_from_arrow(handoff, SA_CVA_SENSITIVITY_ENTITY_SPEC)


def normalize_cva_arrow_table(
    table: pa.Table,
    spec: EntityBatchSpec[Any],
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalise a CVA Arrow table using an entity batch spec.

    Parameters
    ----------
    table : pyarrow.Table
        Raw vendor table for the entity.
    spec : EntityBatchSpec
        CVA entity column contract and builder dispatch metadata.
    diagnostics, metadata, rejected, source_hash : optional
        Handoff diagnostics, audit metadata, rejected partition, and source hash.

    Returns
    -------
    NormalizedArrowTable
        Accepted/rejected partition with the entity column specs applied.
    """
    return normalize_arrow_table(
        table,
        column_specs=spec.column_specs,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def build_cva_batch_from_arrow(handoff: NormalizedArrowTable, spec: EntityBatchSpec[T]) -> T:
    """Materialise a CVA batch from a normalized Arrow handoff and entity spec.

    Parameters
    ----------
    handoff : NormalizedArrowTable
        Accepted entity rows produced by :func:`normalize_cva_arrow_table`.
    spec : EntityBatchSpec
        CVA entity column contract and column-builder dispatch metadata.

    Returns
    -------
    T
        Validated package-local batch produced by ``spec.build_from_columns``.

    Raises
    ------
    CvaInputError
        If ``handoff`` is not a :class:`~frtb_common.arrow_table.NormalizedArrowTable`.
    """
    if not isinstance(handoff, NormalizedArrowTable):
        raise CvaInputError("handoff must be NormalizedArrowTable", field="handoff")
    columns = read_arrow_columns(handoff.accepted, spec.column_specs, error=_cva_error)
    batch = spec.build_from_columns(
        **_cva_batch_column_kwargs(columns, spec.column_to_argument),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_arrow_table_hash(handoff),
        diagnostics=_diagnostics(handoff),
        copy_arrays=False,
    )
    if spec.validate_batch is not None:
        spec.validate_batch(batch)
    return batch


def _cva_batch_column_kwargs(
    columns: Mapping[str, object],
    column_args: Mapping[str, str],
) -> dict[str, Any]:
    return {
        argument_name: columns[column_name]
        for column_name, argument_name in column_args.items()
        if column_name in columns
    }


def _cva_error(message: str, field: str | None) -> CvaInputError:
    return CvaInputError(message, field="" if field is None else field)


def _diagnostics(handoff: NormalizedArrowTable) -> tuple[Mapping[str, object], ...]:
    return tuple(diagnostic.as_dict() for diagnostic in handoff.diagnostics)


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
    "build_cva_batch_from_arrow",
    "build_cva_counterparty_batch_from_arrow",
    "build_cva_hedge_batch_from_arrow",
    "build_cva_netting_set_batch_from_arrow",
    "build_sa_cva_sensitivity_batch_from_arrow",
    "normalize_cva_arrow_table",
    "normalize_cva_counterparty_arrow_table",
    "normalize_cva_hedge_arrow_table",
    "normalize_cva_netting_set_arrow_table",
    "normalize_sa_cva_sensitivity_arrow_table",
]
