"""CRIF record and Arrow-table normalization orchestration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import pyarrow as pa  # type: ignore[import-untyped]

from frtb_common.arrow_table import NormalizedArrowTable, NormalizedTableError
from frtb_common.crif_columns_adapter import (
    _can_use_vectorized_static_mapping,
    _resolve_crif_columns,
    _risk_mapping_by_type,
    _validate_crif_column_specs,
    resolve_crif_column_name,
)
from frtb_common.crif_scalar_adapter import _normalize_crif_arrow_table_scalar_mapping
from frtb_common.crif_types import (
    CRIF_SOURCE_SYSTEM,
    DEFAULT_CRIF_COLUMN_SPECS,
    CrifColumnSpec,
    CrifRiskTypeMapper,
    CrifRiskTypeMapping,
    _stringify_record_value,
    _validate_non_empty,
)
from frtb_common.crif_vectorized_adapter import _normalize_crif_arrow_table_static_mapping


def crif_records_to_arrow_table(records: Sequence[Mapping[str, object]]) -> pa.Table:
    """Return an Arrow table from mapping rows using deterministic column order.

    Parameters
    ----------
    records : sequence of mapping
        CRIF-like rows with string field names and JSON-compatible values.

    Returns
    -------
    pyarrow.Table
        String-typed Arrow table with sorted union-of-keys column order.
    """

    rows = tuple(records)
    for index, record in enumerate(rows):
        if not isinstance(record, Mapping):
            raise NormalizedTableError(f"CRIF record at index {index} must be a mapping")
        for key in record:
            if not isinstance(key, str) or not key.strip():
                raise NormalizedTableError(
                    f"CRIF record at index {index} contains a non-string or blank field name"
                )

    column_names = sorted({key for record in rows for key in record})
    columns: dict[str, pa.Array] = {}
    for column_name in column_names:
        values = [_stringify_record_value(record.get(column_name)) for record in rows]
        columns[column_name] = pa.array(values, type=pa.string())
    return pa.table(columns)


def normalize_crif_records(
    records: Sequence[Mapping[str, object]],
    *,
    column_specs: Sequence[CrifColumnSpec] = DEFAULT_CRIF_COLUMN_SPECS,
    risk_type_mappings: Sequence[CrifRiskTypeMapping] = (),
    risk_type_mapper: CrifRiskTypeMapper | None = None,
    use_vectorized_static_mapping: bool = True,
    source_system: str = CRIF_SOURCE_SYSTEM,
    source_file: str = "crif.csv",
    metadata: Mapping[str, str] | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize CRIF-like mapping rows into an Arrow table.

    Parameters
    ----------
    records : sequence of mapping
        CRIF-like rows to materialise and normalise.
    column_specs : sequence of CrifColumnSpec, optional
        Target column contracts (default :data:`DEFAULT_CRIF_COLUMN_SPECS`).
    risk_type_mappings : sequence of CrifRiskTypeMapping, optional
        Static RiskType to output-column mappings.
    risk_type_mapper : callable, optional
        Callable mapper overriding static mappings when provided.
    use_vectorized_static_mapping : bool, optional
        Use the vectorised static mapping path when eligible (default ``True``).
    source_system : str, optional
        Adapter metadata source system label.
    source_file : str, optional
        Adapter metadata source file label.
    metadata : mapping, optional
        Additional adapter metadata merged into the envelope.
    source_hash : str, optional
        Precomputed source digest for the input rows.

    Returns
    -------
    NormalizedArrowTable
        Accepted/rejected CRIF normalisation envelope.
    """

    table = crif_records_to_arrow_table(records)
    return normalize_crif_arrow_table(
        table,
        column_specs=column_specs,
        risk_type_mappings=risk_type_mappings,
        risk_type_mapper=risk_type_mapper,
        use_vectorized_static_mapping=use_vectorized_static_mapping,
        source_system=source_system,
        source_file=source_file,
        metadata=metadata,
        source_hash=source_hash,
    )


def normalize_crif_arrow_table(
    table: pa.Table,
    *,
    column_specs: Sequence[CrifColumnSpec] = DEFAULT_CRIF_COLUMN_SPECS,
    risk_type_mappings: Sequence[CrifRiskTypeMapping] = (),
    risk_type_mapper: CrifRiskTypeMapper | None = None,
    use_vectorized_static_mapping: bool = True,
    source_system: str = CRIF_SOURCE_SYSTEM,
    source_file: str = "crif.csv",
    metadata: Mapping[str, str] | None = None,
    source_hash: str | None = None,
) -> NormalizedArrowTable:
    """Normalize a CRIF-like Arrow table with package-provided risk mappings.

    Parameters
    ----------
    table : pyarrow.Table
        CRIF-like Arrow table to normalise.
    column_specs : sequence of CrifColumnSpec, optional
        Target column contracts (default :data:`DEFAULT_CRIF_COLUMN_SPECS`).
    risk_type_mappings : sequence of CrifRiskTypeMapping, optional
        Static RiskType to output-column mappings.
    risk_type_mapper : callable, optional
        Callable mapper overriding static mappings when provided.
    use_vectorized_static_mapping : bool, optional
        Use the vectorised static mapping path when eligible (default ``True``).
    source_system : str, optional
        Adapter metadata source system label.
    source_file : str, optional
        Adapter metadata source file label.
    metadata : mapping, optional
        Additional adapter metadata merged into the envelope.
    source_hash : str, optional
        Precomputed source digest; otherwise derived from *table*.

    Returns
    -------
    NormalizedArrowTable
        Accepted/rejected CRIF normalisation envelope.
    """

    if not isinstance(table, pa.Table):
        raise TypeError("table must be a pyarrow.Table")
    _validate_non_empty(source_system, "source_system")
    _validate_non_empty(source_file, "source_file")
    specs = _validate_crif_column_specs(column_specs)
    risk_mapping_by_type = _risk_mapping_by_type(risk_type_mappings)
    resolved_columns = _resolve_crif_columns(table, specs)
    if (
        use_vectorized_static_mapping
        and risk_type_mapper is None
        and _can_use_vectorized_static_mapping(specs)
    ):
        return _normalize_crif_arrow_table_static_mapping(
            table,
            specs=specs,
            risk_type_mappings=tuple(risk_type_mappings),
            risk_mapping_by_type=risk_mapping_by_type,
            resolved_columns=resolved_columns,
            source_system=source_system,
            source_file=source_file,
            metadata=metadata,
            source_hash=source_hash,
        )
    return _normalize_crif_arrow_table_scalar_mapping(
        table,
        specs=specs,
        risk_mapping_by_type=risk_mapping_by_type,
        resolved_columns=resolved_columns,
        risk_type_mapper=risk_type_mapper,
        source_system=source_system,
        source_file=source_file,
        metadata=metadata,
        source_hash=source_hash,
    )


__all__ = [
    "crif_records_to_arrow_table",
    "normalize_crif_arrow_table",
    "normalize_crif_records",
    "resolve_crif_column_name",
]
