"""Normalization entrypoints for IMA Arrow handoff tables."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pyarrow as pa  # type: ignore[import-untyped]
from frtb_common import AdapterDiagnostic, NormalizedArrowTable, normalize_arrow_table

from frtb_ima.adapters._arrow_specs import (
    IMA_INPUT_MANIFEST_ARROW_COLUMN_SPECS,
    IMA_RFET_OBSERVATION_ARROW_COLUMN_SPECS,
    IMA_SCENARIO_METADATA_ARROW_COLUMN_SPECS,
)


def normalize_ima_input_manifest_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize an Arrow artifact-lineage table for IMA input manifest construction.
    Parameters
    ----------
    table : pa.Table
        Table.
    diagnostics : Sequence[AdapterDiagnostic], optional
        Diagnostics.
    metadata : Mapping[str, str] | None, optional
        Metadata.
    rejected : pa.Table | None, optional
        Rejected.
    source_hash : str | None, optional
        Source hash.

    Returns
    -------
    NormalizedArrowTable
        Result of the operation.
    """

    return normalize_arrow_table(
        table,
        column_specs=IMA_INPUT_MANIFEST_ARROW_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def normalize_ima_scenario_metadata_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize an Arrow scenario metadata table for IMA scenario-axis tables.
    Parameters
    ----------
    table : pa.Table
        Table.
    diagnostics : Sequence[AdapterDiagnostic], optional
        Diagnostics.
    metadata : Mapping[str, str] | None, optional
        Metadata.
    rejected : pa.Table | None, optional
        Rejected.
    source_hash : str | None, optional
        Source hash.

    Returns
    -------
    NormalizedArrowTable
        Result of the operation.
    """

    return normalize_arrow_table(
        table,
        column_specs=IMA_SCENARIO_METADATA_ARROW_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )


def normalize_ima_rfet_observation_arrow_table(
    table: pa.Table,
    *,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    rejected: pa.Table | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize an Arrow real-price observation table for RFET input tables.
    Parameters
    ----------
    table : pa.Table
        Table.
    diagnostics : Sequence[AdapterDiagnostic], optional
        Diagnostics.
    metadata : Mapping[str, str] | None, optional
        Metadata.
    rejected : pa.Table | None, optional
        Rejected.
    source_hash : str | None, optional
        Source hash.

    Returns
    -------
    NormalizedArrowTable
        Result of the operation.
    """

    return normalize_arrow_table(
        table,
        column_specs=IMA_RFET_OBSERVATION_ARROW_COLUMN_SPECS,
        rejected=rejected,
        diagnostics=diagnostics,
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=False,
    )
