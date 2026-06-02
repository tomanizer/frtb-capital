"""Arrow-backed normalized tabular handoff primitives.

This module owns package-neutral ingestion mechanics only. Capital packages own
their regulatory meanings, package-specific batches, and NumPy kernel inputs.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Literal, cast

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]
import pyarrow.ipc as pa_ipc  # type: ignore[import-untyped]

from frtb_common.hashing import stable_json_hash

DEFAULT_ROW_ID_COLUMN = "row_id"
SortDirection = Literal["ascending", "descending"]


class TabularHandoffError(ValueError):
    """Raised when a normalized tabular handoff violates shared invariants."""


class DiagnosticSeverity(StrEnum):
    """Adapter diagnostic severity."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class TabularLogicalType(StrEnum):
    """Package-neutral logical column classes for adapter contracts."""

    BOOLEAN = "boolean"
    DATE = "date"
    DECIMAL = "decimal"
    DICTIONARY = "dictionary"
    DICTIONARY_CODE = "dictionary_code"
    FLOAT = "float"
    INTEGER = "integer"
    STRING = "string"
    TIMESTAMP = "timestamp"
    UNKNOWN = "unknown"


class NullPolicy(StrEnum):
    """Column null handling policy."""

    ALLOW = "allow"
    FORBID = "forbid"


class ChunkPolicy(StrEnum):
    """Column chunking policy."""

    ALLOW = "allow"
    FORBID = "forbid"


class DictionaryPolicy(StrEnum):
    """Dictionary encoding policy for Arrow columns."""

    ALLOW = "allow"
    FORBID = "forbid"
    REQUIRE = "require"


@dataclass(frozen=True, slots=True)
class ColumnSpec:
    """Package-neutral column declaration for a normalized Arrow handoff."""

    name: str
    aliases: tuple[str, ...] = ()
    logical_type: TabularLogicalType = TabularLogicalType.UNKNOWN
    required: bool = True
    null_policy: NullPolicy = NullPolicy.FORBID
    chunk_policy: ChunkPolicy = ChunkPolicy.ALLOW
    dictionary_policy: DictionaryPolicy = DictionaryPolicy.ALLOW

    def __post_init__(self) -> None:
        aliases = tuple(self.aliases)
        _validate_non_empty_name(self.name, "column name")
        for alias in aliases:
            _validate_non_empty_name(alias, f"alias for {self.name!r}")
        if len(set(aliases)) != len(aliases):
            raise TabularHandoffError(f"Column spec {self.name!r} repeats an alias")
        if self.name in aliases:
            raise TabularHandoffError(f"Column spec {self.name!r} aliases itself")
        object.__setattr__(self, "aliases", aliases)

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic, JSON-serialisable representation."""

        return {
            "aliases": list(self.aliases),
            "chunk_policy": self.chunk_policy.value,
            "dictionary_policy": self.dictionary_policy.value,
            "logical_type": self.logical_type.value,
            "name": self.name,
            "null_policy": self.null_policy.value,
            "required": self.required,
        }


@dataclass(frozen=True, slots=True)
class AdapterDiagnostic:
    """Package-neutral adapter diagnostic tied to a row id and/or column."""

    code: str
    message: str
    severity: DiagnosticSeverity = DiagnosticSeverity.ERROR
    row_id: str | None = None
    column_name: str | None = None

    def __post_init__(self) -> None:
        _validate_non_empty_name(self.code, "diagnostic code")
        _validate_non_empty_name(self.message, "diagnostic message")
        if self.column_name is not None:
            _validate_non_empty_name(self.column_name, "diagnostic column name")
        if self.row_id is not None:
            _validate_non_empty_name(self.row_id, "diagnostic row id")

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic, JSON-serialisable representation."""

        return {
            "code": self.code,
            "column_name": self.column_name,
            "message": self.message,
            "row_id": self.row_id,
            "severity": self.severity.value,
        }


@dataclass(frozen=True, slots=True)
class NormalizedTabularHandoff:
    """Accepted/rejected Arrow tables and diagnostics after adapter normalization."""

    accepted: pa.Table
    column_specs: tuple[ColumnSpec, ...] = ()
    row_id_column: str | None = None
    rejected: pa.Table | None = None
    diagnostics: tuple[AdapterDiagnostic, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)
    source_hash: str | None = None
    require_unique_row_ids: bool = False

    def __post_init__(self) -> None:
        _require_table(self.accepted, "accepted")
        if self.rejected is not None:
            _require_table(self.rejected, "rejected")
        if self.row_id_column is not None:
            _validate_non_empty_name(self.row_id_column, "row id column")

        column_specs = validate_column_specs(self.column_specs)
        diagnostics = tuple(self.diagnostics)
        metadata = _freeze_metadata(self.metadata)
        object.__setattr__(self, "column_specs", column_specs)
        object.__setattr__(self, "diagnostics", diagnostics)
        object.__setattr__(self, "metadata", metadata)

        _validate_arrow_table(
            self.accepted,
            column_specs=column_specs,
            row_id_column=self.row_id_column,
            require_unique_row_ids=self.require_unique_row_ids,
        )


def normalize_arrow_table(
    table: pa.Table,
    *,
    column_specs: Sequence[ColumnSpec] = (),
    row_id_column: str | None = None,
    rejected: pa.Table | None = None,
    diagnostics: Sequence[AdapterDiagnostic] = (),
    metadata: Mapping[str, str] | None = None,
    source_hash: str | None = None,
    require_unique_row_ids: bool = False,
) -> NormalizedTabularHandoff:
    """Normalize aliases to canonical names and validate a handoff table."""

    _require_table(table, "table")
    specs = validate_column_specs(column_specs)
    accepted = _rename_alias_columns(table, specs)
    return NormalizedTabularHandoff(
        accepted=accepted,
        column_specs=specs,
        row_id_column=row_id_column,
        rejected=rejected,
        diagnostics=tuple(diagnostics),
        metadata={} if metadata is None else metadata,
        source_hash=source_hash,
        require_unique_row_ids=require_unique_row_ids,
    )


def validate_arrow_table(
    table: pa.Table,
    *,
    column_specs: Sequence[ColumnSpec] = (),
    row_id_column: str | None = None,
    require_unique_row_ids: bool = False,
) -> None:
    """Validate an already-normalized Arrow table against shared handoff rules."""

    _require_table(table, "table")
    specs = validate_column_specs(column_specs)
    _validate_arrow_table(
        table,
        column_specs=specs,
        row_id_column=row_id_column,
        require_unique_row_ids=require_unique_row_ids,
    )


def validate_column_specs(column_specs: Sequence[ColumnSpec]) -> tuple[ColumnSpec, ...]:
    """Validate that canonical names and aliases are globally unambiguous."""

    specs = tuple(column_specs)
    seen: dict[str, str] = {}
    for spec in specs:
        for candidate in (spec.name, *spec.aliases):
            previous = seen.get(candidate)
            if previous is not None:
                raise TabularHandoffError(
                    f"Column identifier {candidate!r} is used by both {previous!r} "
                    f"and {spec.name!r}"
                )
            seen[candidate] = spec.name
    return specs


def resolve_column_name(table: pa.Table, spec: ColumnSpec) -> str | None:
    """Resolve a canonical column name or alias in an Arrow table."""

    _require_table(table, "table")
    matches = _matching_column_names(table, spec)
    if len(matches) > 1:
        raise TabularHandoffError(
            f"Column spec {spec.name!r} matches multiple input columns: {matches!r}"
        )
    if not matches:
        return None
    return matches[0]


def dictionary_code_chunks(column: pa.ChunkedArray) -> tuple[pa.Array, ...]:
    """Return dictionary index arrays for a dictionary-encoded Arrow column."""

    if not _is_dictionary_column(column):
        raise TabularHandoffError("Column is not dictionary encoded")
    code_chunks: list[pa.Array] = []
    for chunk in column.chunks:
        dictionary_chunk = cast(pa.DictionaryArray, chunk)
        code_chunks.append(dictionary_chunk.indices)
    return tuple(code_chunks)


def dictionary_code_column(table: pa.Table, column_name: str) -> pa.ChunkedArray:
    """Return the dictionary index column for a table column."""

    _require_table(table, "table")
    _require_existing_column(table, column_name)
    return pa.chunked_array(dictionary_code_chunks(table.column(column_name)))


def sort_table_by_columns(
    table: pa.Table,
    column_names: Sequence[str],
    *,
    direction: SortDirection = "ascending",
) -> pa.Table:
    """Return a table sorted by named columns with deterministic direction."""

    _require_table(table, "table")
    for column_name in column_names:
        _require_existing_column(table, column_name)
    if direction not in {"ascending", "descending"}:
        raise TabularHandoffError(f"Unsupported sort direction: {direction!r}")
    if not column_names:
        return table
    sort_keys = [(column_name, direction) for column_name in column_names]
    return table.sort_by(sort_keys)


def source_content_hash(source: bytes | str) -> str:
    """Return a stable SHA-256 hash for source bytes or text."""

    source_bytes = bytes(source, "utf-8") if isinstance(source, str) else source
    return hashlib.sha256(source_bytes).hexdigest()


def arrow_table_content_hash(table: pa.Table) -> str:
    """Return a stable SHA-256 hash for Arrow table schema and contents."""

    _require_table(table, "table")
    canonical = table.combine_chunks()
    sink = pa.BufferOutputStream()
    with pa_ipc.new_stream(sink, canonical.schema) as writer:
        writer.write_table(canonical)
    return hashlib.sha256(sink.getvalue().to_pybytes()).hexdigest()


def normalized_handoff_hash(handoff: NormalizedTabularHandoff) -> str:
    """Return a deterministic hash for a normalized handoff envelope."""

    rejected_hash = None
    if handoff.rejected is not None:
        rejected_hash = arrow_table_content_hash(handoff.rejected)

    payload: dict[str, object] = {
        "accepted_hash": arrow_table_content_hash(handoff.accepted),
        "column_specs": [spec.as_dict() for spec in handoff.column_specs],
        "diagnostics": [diagnostic.as_dict() for diagnostic in handoff.diagnostics],
        "metadata": dict(sorted(handoff.metadata.items())),
        "rejected_hash": rejected_hash,
        "require_unique_row_ids": handoff.require_unique_row_ids,
        "row_id_column": handoff.row_id_column,
        "source_hash": handoff.source_hash,
    }
    return stable_json_hash(payload)


def _validate_arrow_table(
    table: pa.Table,
    *,
    column_specs: tuple[ColumnSpec, ...],
    row_id_column: str | None,
    require_unique_row_ids: bool,
) -> None:
    _validate_unique_column_names(table)
    for spec in column_specs:
        column = _column_for_canonical_spec(table, spec)
        if column is None:
            if spec.required:
                raise TabularHandoffError(f"Required column {spec.name!r} is missing")
            continue
        _validate_column_policy(spec, column)

    if row_id_column is not None:
        _require_existing_column(table, row_id_column)
        if require_unique_row_ids:
            _validate_unique_row_ids(table, row_id_column)


def _validate_column_policy(spec: ColumnSpec, column: pa.ChunkedArray) -> None:
    if spec.null_policy is NullPolicy.FORBID and column.null_count:
        raise TabularHandoffError(f"Column {spec.name!r} contains nulls")
    if spec.chunk_policy is ChunkPolicy.FORBID and column.num_chunks > 1:
        raise TabularHandoffError(f"Column {spec.name!r} contains multiple chunks")

    is_dictionary = _is_dictionary_column(column)
    if spec.dictionary_policy is DictionaryPolicy.FORBID and is_dictionary:
        raise TabularHandoffError(f"Column {spec.name!r} is dictionary encoded")
    if spec.dictionary_policy is DictionaryPolicy.REQUIRE and not is_dictionary:
        raise TabularHandoffError(f"Column {spec.name!r} is not dictionary encoded")


def _rename_alias_columns(table: pa.Table, column_specs: tuple[ColumnSpec, ...]) -> pa.Table:
    rename_by_source: dict[str, str] = {}
    for spec in column_specs:
        source_name = resolve_column_name(table, spec)
        if source_name is None or source_name == spec.name:
            continue
        rename_by_source[source_name] = spec.name

    if not rename_by_source:
        return table

    normalized_names = [
        rename_by_source.get(column_name, column_name) for column_name in table.column_names
    ]
    if len(set(normalized_names)) != len(normalized_names):
        raise TabularHandoffError("Alias normalization would produce duplicate column names")
    return table.rename_columns(normalized_names)


def _matching_column_names(table: pa.Table, spec: ColumnSpec) -> tuple[str, ...]:
    names = set(table.column_names)
    return tuple(candidate for candidate in (spec.name, *spec.aliases) if candidate in names)


def _column_for_canonical_spec(table: pa.Table, spec: ColumnSpec) -> pa.ChunkedArray | None:
    if spec.name not in table.column_names:
        return None
    return table.column(spec.name)


def _validate_unique_column_names(table: pa.Table) -> None:
    if len(set(table.column_names)) != len(table.column_names):
        raise TabularHandoffError("Arrow table contains duplicate column names")


def _validate_unique_row_ids(table: pa.Table, row_id_column: str) -> None:
    column = table.column(row_id_column)
    if column.null_count:
        raise TabularHandoffError(f"Row id column {row_id_column!r} contains nulls")
    distinct = pc.count_distinct(column, mode="only_valid").as_py()
    if cast(int, distinct) != table.num_rows:
        raise TabularHandoffError(f"Row id column {row_id_column!r} contains duplicates")


def _is_dictionary_column(column: pa.ChunkedArray) -> bool:
    return bool(pa.types.is_dictionary(column.type))


def _require_existing_column(table: pa.Table, column_name: str) -> None:
    _validate_non_empty_name(column_name, "column name")
    if column_name not in table.column_names:
        raise TabularHandoffError(f"Column {column_name!r} is missing")


def _require_table(value: object, name: str) -> None:
    if not isinstance(value, pa.Table):
        raise TypeError(f"{name} must be a pyarrow.Table")


def _freeze_metadata(metadata: Mapping[str, str]) -> Mapping[str, str]:
    frozen = dict(metadata)
    for key, value in frozen.items():
        if not isinstance(key, str) or not key:
            raise TabularHandoffError("Metadata keys must be non-empty strings")
        if not isinstance(value, str):
            raise TabularHandoffError(f"Metadata value for {key!r} must be a string")
    return MappingProxyType(frozen)


def _validate_non_empty_name(value: str, label: str) -> None:
    if not isinstance(value, str) or not value:
        raise TabularHandoffError(f"{label} must be a non-empty string")
