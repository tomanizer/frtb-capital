"""Package-neutral CRIF-to-Arrow normalization helpers.

This module owns shared CRIF mechanics only: source-column discovery, alias
normalization, primitive type coercion, accepted/rejected row partitioning,
diagnostics, and source metadata. Capital packages own risk-type mappings and
the regulatory meaning of accepted rows.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TypeAlias, cast

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.compute as pc  # type: ignore[import-untyped]

from frtb_common.arrow_table import (
    AdapterDiagnostic,
    ColumnSpec,
    DiagnosticSeverity,
    NormalizedArrowTable,
    NormalizedTableError,
    NullPolicy,
    TabularLogicalType,
    arrow_table_content_hash,
)

CRIF_SOURCE_SYSTEM = "crif"
CRIF_SOURCE_ROW_ID_COLUMN = "source_row_id"
CRIF_RISK_TYPE_COLUMN = "risk_type"
_FLOAT_TEXT_PATTERN = r"^[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eE][+-]?\d+)?$"
_INTEGER_TEXT_PATTERN = r"^[+-]?\d+$"
_NON_FINITE_TEXT_VALUES = frozenset(
    {
        "NAN",
        "+NAN",
        "-NAN",
        "INF",
        "+INF",
        "-INF",
        "INFINITY",
        "+INFINITY",
        "-INFINITY",
    }
)

CrifRiskTypeMapper: TypeAlias = Callable[
    [str, Mapping[str, object]],
    Mapping[str, object] | None,
]


@dataclass(frozen=True, slots=True)
class CrifColumnSpec:
    """Package-neutral CRIF source column extraction rule."""

    name: str
    aliases: tuple[str, ...] = ()
    logical_type: TabularLogicalType = TabularLogicalType.STRING
    required: bool = False
    default: object | None = None

    def __post_init__(self) -> None:
        _validate_non_empty(self.name, "CRIF column name")
        aliases = tuple(self.aliases)
        for alias in aliases:
            _validate_non_empty(alias, f"alias for {self.name!r}")
        if len(set(aliases)) != len(aliases):
            raise NormalizedTableError(f"CRIF column spec {self.name!r} repeats an alias")
        object.__setattr__(self, "aliases", aliases)

    def as_column_spec(self) -> ColumnSpec:
        """Return the generic handoff column declaration for this CRIF field."""

        return ColumnSpec(
            self.name,
            logical_type=self.logical_type,
            required=self.required,
            null_policy=NullPolicy.FORBID if self.required else NullPolicy.ALLOW,
        )


@dataclass(frozen=True, slots=True)
class CrifRiskTypeMapping:
    """Package-supplied mapping from CRIF RiskType values to output constants."""

    source_values: tuple[str, ...]
    output_values: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        values = tuple(_normalise_risk_type(value) for value in self.source_values)
        if not values:
            raise NormalizedTableError("CRIF risk-type mapping requires at least one value")
        if len(set(values)) != len(values):
            raise NormalizedTableError("CRIF risk-type mapping repeats a source value")
        frozen_outputs = MappingProxyType(dict(self.output_values))
        for key in frozen_outputs:
            _validate_non_empty(key, "CRIF risk-type output column")
        object.__setattr__(self, "source_values", values)
        object.__setattr__(self, "output_values", frozen_outputs)


@dataclass(frozen=True, slots=True)
class _VectorizedColumn:
    values: pa.Array
    errors: tuple[_VectorizedError, ...] = ()


@dataclass(frozen=True, slots=True)
class _VectorizedError:
    mask: pa.Array
    message: str


def _normalise_risk_type(value: object) -> str:
    return str(value).strip().upper()


def _column_key(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _stringify_record_value(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)


def _validate_non_empty(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise NormalizedTableError(f"{label} must be a non-empty string")


DEFAULT_CRIF_COLUMN_SPECS: tuple[CrifColumnSpec, ...] = (
    CrifColumnSpec(
        "sensitivity_id",
        aliases=("SensitivityId", "Sensitivity ID", "TradeId", "TradeID"),
    ),
    CrifColumnSpec(
        CRIF_SOURCE_ROW_ID_COLUMN,
        aliases=("RowId", "RowID", "sourceRowId", "source_row_id"),
    ),
    CrifColumnSpec(
        CRIF_RISK_TYPE_COLUMN,
        aliases=("RiskType", "risk_type", "RiskClass"),
        required=True,
    ),
    CrifColumnSpec("qualifier", aliases=("Qualifier",)),
    CrifColumnSpec("bucket", aliases=("Bucket",)),
    CrifColumnSpec("label1", aliases=("Label1", "Tenor", "tenor")),
    CrifColumnSpec("label2", aliases=("Label2", "OptionTenor", "option_tenor")),
    CrifColumnSpec(
        "amount",
        aliases=("Amount", "amount", "AmountUSD", "AmountUsd"),
        logical_type=TabularLogicalType.FLOAT,
    ),
    CrifColumnSpec(
        "amount_currency",
        aliases=("AmountCurrency", "amount_currency", "Currency", "currency"),
    ),
    CrifColumnSpec("desk_id", aliases=("DeskId", "DeskID", "desk_id", "Desk")),
    CrifColumnSpec(
        "legal_entity",
        aliases=("LegalEntity", "LegalEntityID", "legal_entity", "Entity"),
    ),
    CrifColumnSpec(
        "up_shock_amount",
        aliases=("CvrUp", "UpShock", "up_shock_amount"),
        logical_type=TabularLogicalType.FLOAT,
    ),
    CrifColumnSpec(
        "down_shock_amount",
        aliases=("CvrDown", "DownShock", "down_shock_amount"),
        logical_type=TabularLogicalType.FLOAT,
    ),
)


def crif_records_to_arrow_table(records: Sequence[Mapping[str, object]]) -> pa.Table:
    """Return an Arrow table from mapping rows using deterministic column order."""

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
    """Normalize CRIF-like mapping rows into an Arrow table."""

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
    """Normalize a CRIF-like Arrow table with package-provided risk mappings."""

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

    normalized_columns: dict[str, list[object | None]] = {}
    row_errors: list[list[AdapterDiagnostic]] = [[] for _ in range(table.num_rows)]
    for spec in specs:
        source_name = resolved_columns.get(spec.name)
        values = _source_values(table, source_name)
        normalized_columns[spec.name] = _coerce_column(
            values,
            spec,
            row_errors=row_errors,
        )

    source_row_ids = _source_row_ids(
        normalized_columns.get(CRIF_SOURCE_ROW_ID_COLUMN),
        table.num_rows,
    )
    normalized_columns[CRIF_SOURCE_ROW_ID_COLUMN] = list(source_row_ids)
    _attach_source_row_ids(row_errors, source_row_ids)

    mapping_outputs: dict[str, list[object | None]] = {}
    for row_index in range(table.num_rows):
        if row_errors[row_index]:
            continue
        risk_type = normalized_columns.get(CRIF_RISK_TYPE_COLUMN, [None] * table.num_rows)[
            row_index
        ]
        if not isinstance(risk_type, str) or not risk_type.strip():
            row_errors[row_index].append(
                _diagnostic(
                    code="crif.missing_risk_type",
                    message="CRIF RiskType is required",
                    row_id=source_row_ids[row_index],
                    column_name=CRIF_RISK_TYPE_COLUMN,
                )
            )
            continue
        output_values = _risk_mapping_output(
            risk_type,
            {name: values[row_index] for name, values in normalized_columns.items()},
            risk_mapping_by_type,
            risk_type_mapper,
        )
        if output_values is None:
            row_errors[row_index].append(
                _diagnostic(
                    code="crif.unsupported_risk_type",
                    message=f"unsupported CRIF RiskType {_normalise_risk_type(risk_type)!r}",
                    row_id=source_row_ids[row_index],
                    column_name=CRIF_RISK_TYPE_COLUMN,
                )
            )
            continue
        for column_name, value in output_values.items():
            mapping_outputs.setdefault(column_name, [None] * table.num_rows)[row_index] = value

    accepted_indices = tuple(index for index, errors in enumerate(row_errors) if not errors)
    rejected_indices = tuple(index for index, errors in enumerate(row_errors) if errors)
    accepted_table = _table_from_columns(
        {**normalized_columns, **mapping_outputs},
        accepted_indices,
        specs=specs,
        mapping_outputs=mapping_outputs,
    )
    diagnostics = tuple(errors[0] for errors in row_errors if errors)
    rejected_table = _rejected_table(
        table,
        source_row_ids=source_row_ids,
        row_errors=row_errors,
        rejected_indices=rejected_indices,
    )
    handoff_metadata = {
        "adapter": "crif",
        "source_file": source_file,
        "source_system": source_system,
    }
    if metadata is not None:
        handoff_metadata.update(metadata)

    return NormalizedArrowTable(
        accepted=accepted_table,
        column_specs=_handoff_column_specs(accepted_table, specs, mapping_outputs),
        row_id_column=CRIF_SOURCE_ROW_ID_COLUMN,
        rejected=rejected_table,
        diagnostics=diagnostics,
        metadata=handoff_metadata,
        source_hash=source_hash or arrow_table_content_hash(table),
        require_unique_row_ids=False,
    )


def resolve_crif_column_name(table: pa.Table, aliases: Sequence[str]) -> str | None:
    """Resolve a source column by CRIF aliases using case/spacing-insensitive matching."""

    if not isinstance(table, pa.Table):
        raise TypeError("table must be a pyarrow.Table")
    if not aliases:
        raise NormalizedTableError("at least one CRIF alias is required")
    by_key: dict[str, list[str]] = {}
    for column_name in table.column_names:
        by_key.setdefault(_column_key(column_name), []).append(column_name)
    matches: list[str] = []
    for alias in aliases:
        matches.extend(by_key.get(_column_key(alias), ()))
    unique_matches = tuple(dict.fromkeys(matches))
    if len(unique_matches) > 1:
        raise NormalizedTableError(
            f"CRIF aliases {tuple(aliases)!r} match multiple input columns: {unique_matches!r}"
        )
    return unique_matches[0] if unique_matches else None


def normalise_crif_risk_type(value: object) -> str:
    """Return the deterministic key used for CRIF RiskType mapping."""

    return _normalise_risk_type(value)


def _validate_crif_column_specs(
    column_specs: Sequence[CrifColumnSpec],
) -> tuple[CrifColumnSpec, ...]:
    specs = tuple(column_specs)
    seen_targets: set[str] = set()
    for spec in specs:
        if spec.name in seen_targets:
            raise NormalizedTableError(f"Duplicate CRIF target column {spec.name!r}")
        seen_targets.add(spec.name)
    return specs


def _risk_mapping_by_type(
    risk_type_mappings: Sequence[CrifRiskTypeMapping],
) -> Mapping[str, Mapping[str, object]]:
    by_type: dict[str, Mapping[str, object]] = {}
    for mapping in risk_type_mappings:
        for source_value in mapping.source_values:
            if source_value in by_type:
                raise NormalizedTableError(
                    f"CRIF RiskType {source_value!r} appears in multiple mappings"
                )
            by_type[source_value] = mapping.output_values
    return MappingProxyType(by_type)


def _resolve_crif_columns(
    table: pa.Table,
    specs: tuple[CrifColumnSpec, ...],
) -> Mapping[str, str]:
    return MappingProxyType(
        {
            spec.name: source_name
            for spec in specs
            if (source_name := resolve_crif_column_name(table, (spec.name, *spec.aliases)))
            is not None
        }
    )


def _can_use_vectorized_static_mapping(specs: tuple[CrifColumnSpec, ...]) -> bool:
    if not any(spec.name == CRIF_RISK_TYPE_COLUMN for spec in specs):
        return False
    supported_types = {
        TabularLogicalType.BOOLEAN,
        TabularLogicalType.FLOAT,
        TabularLogicalType.INTEGER,
        TabularLogicalType.STRING,
    }
    return all(spec.logical_type in supported_types for spec in specs)


def _normalize_crif_arrow_table_static_mapping(
    table: pa.Table,
    *,
    specs: tuple[CrifColumnSpec, ...],
    risk_type_mappings: tuple[CrifRiskTypeMapping, ...],
    risk_mapping_by_type: Mapping[str, Mapping[str, object]],
    resolved_columns: Mapping[str, str],
    source_system: str,
    source_file: str,
    metadata: Mapping[str, str] | None,
    source_hash: str | None,
) -> NormalizedArrowTable:
    row_count = table.num_rows
    normalized_columns: dict[str, pa.Array] = {}
    row_error_by_index: dict[int, AdapterDiagnostic] = {}
    valid_fields_mask = _bool_array(True, row_count)

    for spec in specs:
        source_name = resolved_columns.get(spec.name)
        vectorized = _coerce_column_arrow(table, source_name, spec)
        normalized_columns[spec.name] = vectorized.values
        for error in vectorized.errors:
            error_mask = _mask_and(valid_fields_mask, error.mask)
            _record_vectorized_errors(
                row_error_by_index,
                error_mask,
                code="crif.invalid_field",
                message=error.message,
                source_row_ids=None,
                column_name=spec.name,
            )
            valid_fields_mask = _mask_and(valid_fields_mask, _mask_not(error.mask))

    source_row_ids = _source_row_id_array(
        normalized_columns.get(CRIF_SOURCE_ROW_ID_COLUMN),
        row_count,
    )
    normalized_columns[CRIF_SOURCE_ROW_ID_COLUMN] = source_row_ids
    _attach_vectorized_source_row_ids(row_error_by_index, source_row_ids)

    risk_type_values = normalized_columns[CRIF_RISK_TYPE_COLUMN]
    risk_type_keys = _normalise_risk_type_array(risk_type_values)
    missing_risk_type_mask = _mask_and(valid_fields_mask, _empty_text_mask(risk_type_keys))
    _record_vectorized_errors(
        row_error_by_index,
        missing_risk_type_mask,
        code="crif.missing_risk_type",
        message="CRIF RiskType is required",
        source_row_ids=source_row_ids,
        column_name=CRIF_RISK_TYPE_COLUMN,
    )
    mapping_candidate_mask = _mask_and(valid_fields_mask, _mask_not(missing_risk_type_mask))
    supported_risk_type_mask = _supported_risk_type_mask(
        risk_type_keys,
        risk_mapping_by_type,
        row_count,
    )
    unsupported_mask = _mask_and(
        mapping_candidate_mask,
        _mask_not(supported_risk_type_mask),
    )
    _record_vectorized_errors(
        row_error_by_index,
        unsupported_mask,
        code="crif.unsupported_risk_type",
        message_by_index=_unsupported_risk_type_messages(risk_type_keys, unsupported_mask),
        source_row_ids=source_row_ids,
        column_name=CRIF_RISK_TYPE_COLUMN,
    )

    accepted_mask = _mask_and(mapping_candidate_mask, supported_risk_type_mask)
    mapping_outputs = _static_mapping_output_arrays(
        risk_type_keys,
        risk_type_mappings,
        row_count,
    )
    accepted_table = _table_from_arrow_columns(
        {**normalized_columns, **mapping_outputs},
        accepted_mask,
        specs=specs,
        mapping_outputs=mapping_outputs,
    )
    rejected_indices = tuple(sorted(row_error_by_index))
    diagnostics = tuple(row_error_by_index[index] for index in rejected_indices)
    rejected_table = _rejected_table_from_diagnostics(
        table,
        source_row_ids=source_row_ids,
        diagnostics_by_index=row_error_by_index,
        rejected_indices=rejected_indices,
    )
    handoff_metadata = {
        "adapter": "crif",
        "source_file": source_file,
        "source_system": source_system,
    }
    if metadata is not None:
        handoff_metadata.update(metadata)

    return NormalizedArrowTable(
        accepted=accepted_table,
        column_specs=_handoff_column_specs(accepted_table, specs, mapping_outputs),
        row_id_column=CRIF_SOURCE_ROW_ID_COLUMN,
        rejected=rejected_table,
        diagnostics=diagnostics,
        metadata=handoff_metadata,
        source_hash=source_hash or arrow_table_content_hash(table),
        require_unique_row_ids=False,
    )


def _coerce_column_arrow(
    table: pa.Table,
    source_name: str | None,
    spec: CrifColumnSpec,
) -> _VectorizedColumn:
    text = _source_text_array(table, source_name, spec)
    trimmed = pc.utf8_trim_whitespace(text)
    is_empty = _empty_text_mask(trimmed)
    missing_column = (
        (source_name is None or _source_column_is_all_null(table, source_name))
        and spec.required
        and spec.default is None
    )
    required_empty = is_empty if spec.required else _bool_array(False, table.num_rows)

    if spec.logical_type is TabularLogicalType.FLOAT:
        return _coerce_float_arrow(trimmed, is_empty, required_empty, spec, missing_column)
    if spec.logical_type is TabularLogicalType.INTEGER:
        return _coerce_integer_arrow(trimmed, is_empty, required_empty, spec, missing_column)
    if spec.logical_type is TabularLogicalType.BOOLEAN:
        return _coerce_boolean_arrow(trimmed, is_empty, required_empty, spec, missing_column)
    values = pc.if_else(is_empty, pa.scalar(None, type=pa.string()), trimmed)
    return _VectorizedColumn(
        cast(pa.Array, values),
        errors=_required_text_errors(required_empty, spec, missing_column),
    )


def _source_column_is_all_null(table: pa.Table, source_name: str | None) -> bool:
    if source_name is None or table.num_rows == 0:
        return source_name is None
    column = table.column(source_name)
    return bool(pc.all(pc.is_null(column)).as_py())


def _source_text_array(
    table: pa.Table,
    source_name: str | None,
    spec: CrifColumnSpec,
) -> pa.Array:
    if source_name is None:
        if spec.default is None:
            return pa.nulls(table.num_rows, type=pa.string())
        return pa.repeat(pa.scalar(str(spec.default), type=pa.string()), table.num_rows)
    column = table.column(source_name).combine_chunks()
    text = cast(pa.Array, pc.cast(column, pa.string()))
    if spec.default is None:
        return text
    return cast(
        pa.Array,
        pc.if_else(
            pc.is_null(text),
            pa.scalar(str(spec.default), type=pa.string()),
            text,
        ),
    )


def _coerce_float_arrow(
    trimmed: pa.Array,
    is_empty: pa.Array,
    required_empty: pa.Array,
    spec: CrifColumnSpec,
    missing_column: bool,
) -> _VectorizedColumn:
    filled = _filled_text(trimmed)
    numeric_text = cast(pa.Array, pc.match_substring_regex(filled, _FLOAT_TEXT_PATTERN))
    non_finite_text = cast(
        pa.Array,
        pc.is_in(pc.utf8_upper(filled), value_set=pa.array(sorted(_NON_FINITE_TEXT_VALUES))),
    )
    invalid_numeric = _mask_and(
        _mask_not(is_empty), _mask_not(_mask_or(numeric_text, non_finite_text))
    )
    invalid_finite = _mask_and(_mask_not(is_empty), non_finite_text)
    safe_text = pc.if_else(numeric_text, trimmed, pa.scalar(None, type=pa.string()))
    values = cast(pa.Array, pc.cast(safe_text, pa.float64()))
    finite_values = cast(pa.Array, pc.fill_null(pc.is_finite(values), True))
    invalid_finite = _mask_or(
        invalid_finite, _mask_and(_mask_not(is_empty), _mask_not(finite_values))
    )
    errors = (
        *_required_text_errors(required_empty, spec, missing_column),
        _VectorizedError(invalid_numeric, f"CRIF field {spec.name!r} must be numeric"),
        _VectorizedError(invalid_finite, f"CRIF field {spec.name!r} must be finite"),
    )
    return _VectorizedColumn(values, errors=errors)


def _coerce_integer_arrow(
    trimmed: pa.Array,
    is_empty: pa.Array,
    required_empty: pa.Array,
    spec: CrifColumnSpec,
    missing_column: bool,
) -> _VectorizedColumn:
    filled = _filled_text(trimmed)
    integer_text = cast(pa.Array, pc.match_substring_regex(filled, _INTEGER_TEXT_PATTERN))
    invalid_integer = _mask_and(_mask_not(is_empty), _mask_not(integer_text))
    safe_text = pc.if_else(integer_text, trimmed, pa.scalar(None, type=pa.string()))
    values = cast(pa.Array, pc.cast(safe_text, pa.int64()))
    errors = (
        *_required_text_errors(required_empty, spec, missing_column),
        _VectorizedError(invalid_integer, f"CRIF field {spec.name!r} must be an integer"),
    )
    return _VectorizedColumn(values, errors=errors)


def _coerce_boolean_arrow(
    trimmed: pa.Array,
    is_empty: pa.Array,
    required_empty: pa.Array,
    spec: CrifColumnSpec,
    missing_column: bool,
) -> _VectorizedColumn:
    lowered = pc.utf8_lower(_filled_text(trimmed))
    true_mask = cast(
        pa.Array,
        pc.is_in(lowered, value_set=pa.array(["1", "true", "yes", "y"])),
    )
    false_mask = cast(
        pa.Array,
        pc.is_in(lowered, value_set=pa.array(["0", "false", "no", "n"])),
    )
    valid_boolean = _mask_or(true_mask, false_mask)
    invalid_boolean = _mask_and(_mask_not(is_empty), _mask_not(valid_boolean))
    values = cast(
        pa.Array,
        pc.if_else(
            true_mask,
            pa.scalar(True, type=pa.bool_()),
            pc.if_else(false_mask, pa.scalar(False, type=pa.bool_()), pa.scalar(None, pa.bool_())),
        ),
    )
    errors = (
        *_required_text_errors(required_empty, spec, missing_column),
        _VectorizedError(invalid_boolean, f"CRIF field {spec.name!r} must be boolean"),
    )
    return _VectorizedColumn(values, errors=errors)


def _required_text_errors(
    required_empty: pa.Array,
    spec: CrifColumnSpec,
    missing_column: bool,
) -> tuple[_VectorizedError, ...]:
    if not spec.required:
        return ()
    message = (
        f"required CRIF column {spec.name!r} is missing"
        if missing_column
        else f"CRIF field {spec.name!r} is required"
    )
    return (_VectorizedError(required_empty, message),)


def _source_row_id_array(values: pa.Array | None, row_count: int) -> pa.Array:
    fallback = pc.cast(pa.array(range(row_count), type=pa.int64()), pa.string())
    if values is None:
        return cast(pa.Array, fallback)
    trimmed = pc.utf8_trim_whitespace(pc.cast(values, pa.string()))
    has_text = _mask_not(_empty_text_mask(cast(pa.Array, trimmed)))
    return cast(pa.Array, pc.if_else(has_text, trimmed, fallback))


def _normalise_risk_type_array(values: pa.Array) -> pa.Array:
    return cast(pa.Array, pc.utf8_upper(_filled_text(pc.utf8_trim_whitespace(values))))


def _supported_risk_type_mask(
    risk_type_keys: pa.Array,
    risk_mapping_by_type: Mapping[str, Mapping[str, object]],
    row_count: int,
) -> pa.Array:
    if not risk_mapping_by_type:
        return _mask_not(_empty_text_mask(risk_type_keys))
    return cast(
        pa.Array,
        pc.is_in(risk_type_keys, value_set=pa.array(sorted(risk_mapping_by_type))),
    )


def _unsupported_risk_type_messages(
    risk_type_keys: pa.Array,
    unsupported_mask: pa.Array,
) -> Mapping[int, str]:
    indices = _true_indices(unsupported_mask)
    if not indices:
        return {}
    values = risk_type_keys.take(pa.array(indices, type=pa.int64()))
    return {
        index: f"unsupported CRIF RiskType {cast(str, values[offset].as_py())!r}"
        for offset, index in enumerate(indices)
    }


def _static_mapping_output_arrays(
    risk_type_keys: pa.Array,
    risk_type_mappings: tuple[CrifRiskTypeMapping, ...],
    row_count: int,
) -> dict[str, pa.Array]:
    logical_types = _static_mapping_output_logical_types(risk_type_mappings)
    outputs = {
        column_name: _null_array(row_count, logical_type)
        for column_name, logical_type in logical_types.items()
    }
    for mapping in risk_type_mappings:
        mask = cast(
            pa.Array,
            pc.is_in(risk_type_keys, value_set=pa.array(mapping.source_values)),
        )
        for column_name, value in mapping.output_values.items():
            logical_type = logical_types[column_name]
            outputs[column_name] = cast(
                pa.Array,
                pc.if_else(
                    mask, _scalar_for_logical_type(value, logical_type), outputs[column_name]
                ),
            )
    return outputs


def _static_mapping_output_logical_types(
    risk_type_mappings: tuple[CrifRiskTypeMapping, ...],
) -> dict[str, TabularLogicalType]:
    values_by_column: dict[str, list[object]] = {}
    for mapping in risk_type_mappings:
        for column_name, value in mapping.output_values.items():
            values_by_column.setdefault(column_name, []).append(value)
    return {
        column_name: _mapping_output_logical_type(values, default=TabularLogicalType.STRING)
        for column_name, values in values_by_column.items()
    }


def _scalar_for_logical_type(value: object, logical_type: TabularLogicalType) -> pa.Scalar:
    if logical_type is TabularLogicalType.FLOAT:
        return pa.scalar(cast(float, value), type=pa.float64())
    return pa.scalar(None if value is None else str(value), type=pa.string())


def _null_array(row_count: int, logical_type: TabularLogicalType) -> pa.Array:
    if logical_type is TabularLogicalType.FLOAT:
        return pa.nulls(row_count, type=pa.float64())
    if logical_type is TabularLogicalType.INTEGER:
        return pa.nulls(row_count, type=pa.int64())
    if logical_type is TabularLogicalType.BOOLEAN:
        return pa.nulls(row_count, type=pa.bool_())
    return pa.nulls(row_count, type=pa.string())


def _table_from_arrow_columns(
    columns: Mapping[str, pa.Array],
    accepted_mask: pa.Array,
    *,
    specs: tuple[CrifColumnSpec, ...],
    mapping_outputs: Mapping[str, pa.Array],
) -> pa.Table:
    spec_by_name = {spec.name: spec for spec in specs}
    accepted_columns: dict[str, pa.Array] = {}
    for column_name in sorted(columns):
        values = cast(pa.Array, pc.filter(columns[column_name], accepted_mask))
        logical_type = spec_by_name.get(column_name, CrifColumnSpec(column_name)).logical_type
        if column_name in mapping_outputs:
            logical_type = _logical_type_for_arrow_array(values, default=logical_type)
        accepted_columns[column_name] = _cast_arrow_array(values, logical_type)
    return pa.table(accepted_columns)


def _logical_type_for_arrow_array(
    values: pa.Array,
    *,
    default: TabularLogicalType,
) -> TabularLogicalType:
    if pa.types.is_floating(values.type):
        return TabularLogicalType.FLOAT
    if pa.types.is_integer(values.type):
        return TabularLogicalType.INTEGER
    if pa.types.is_boolean(values.type):
        return TabularLogicalType.BOOLEAN
    return default


def _cast_arrow_array(values: pa.Array, logical_type: TabularLogicalType) -> pa.Array:
    if logical_type is TabularLogicalType.FLOAT:
        return cast(pa.Array, pc.cast(values, pa.float64()))
    if logical_type is TabularLogicalType.INTEGER:
        return cast(pa.Array, pc.cast(values, pa.int64()))
    if logical_type is TabularLogicalType.BOOLEAN:
        return cast(pa.Array, pc.cast(values, pa.bool_()))
    return cast(pa.Array, pc.cast(values, pa.string()))


def _record_vectorized_errors(
    row_error_by_index: dict[int, AdapterDiagnostic],
    mask: pa.Array,
    *,
    code: str,
    column_name: str,
    message: str | None = None,
    message_by_index: Mapping[int, str] | None = None,
    source_row_ids: pa.Array | None,
) -> None:
    for row_index in _true_indices(mask):
        if row_index in row_error_by_index:
            continue
        row_id = None
        if source_row_ids is not None:
            row_id = cast(str, source_row_ids[row_index].as_py())
        row_error_by_index[row_index] = _diagnostic(
            code=code,
            message=message_by_index.get(row_index, "")
            if message_by_index is not None
            else cast(str, message),
            row_id=row_id,
            column_name=column_name,
        )


def _attach_vectorized_source_row_ids(
    row_error_by_index: dict[int, AdapterDiagnostic],
    source_row_ids: pa.Array,
) -> None:
    for row_index, diagnostic in tuple(row_error_by_index.items()):
        if diagnostic.row_id is not None:
            continue
        row_error_by_index[row_index] = AdapterDiagnostic(
            code=diagnostic.code,
            message=diagnostic.message,
            severity=diagnostic.severity,
            row_id=cast(str, source_row_ids[row_index].as_py()),
            column_name=diagnostic.column_name,
        )


def _rejected_table_from_diagnostics(
    raw_table: pa.Table,
    *,
    source_row_ids: pa.Array,
    diagnostics_by_index: Mapping[int, AdapterDiagnostic],
    rejected_indices: Sequence[int],
) -> pa.Table | None:
    if not rejected_indices:
        return None
    columns: dict[str, list[str]] = {
        CRIF_SOURCE_ROW_ID_COLUMN: [],
        "rejection_code": [],
        "rejection_column": [],
        "rejection_reason": [],
        "source_row_json": [],
    }
    raw_columns = {
        column_name: raw_table.column(column_name) for column_name in raw_table.column_names
    }
    for row_index in rejected_indices:
        diagnostic = diagnostics_by_index[row_index]
        columns[CRIF_SOURCE_ROW_ID_COLUMN].append(cast(str, source_row_ids[row_index].as_py()))
        columns["rejection_code"].append(diagnostic.code)
        columns["rejection_column"].append(diagnostic.column_name or "")
        columns["rejection_reason"].append(diagnostic.message)
        source_row = {
            column_name: _stringify_record_value(values[row_index].as_py())
            for column_name, values in raw_columns.items()
        }
        columns["source_row_json"].append(
            json.dumps(source_row, sort_keys=True, separators=(",", ":"))
        )
    return pa.table(columns)


def _filled_text(values: pa.Array) -> pa.Array:
    return cast(pa.Array, pc.fill_null(values, ""))


def _empty_text_mask(values: pa.Array) -> pa.Array:
    filled = _filled_text(values)
    return _mask_or(pc.is_null(values), pc.equal(filled, ""))


def _bool_array(value: bool, row_count: int) -> pa.Array:
    return cast(pa.Array, pa.repeat(pa.scalar(value, type=pa.bool_()), row_count))


def _mask_and(left: pa.Array, right: pa.Array) -> pa.Array:
    return cast(pa.Array, pc.and_(pc.fill_null(left, False), pc.fill_null(right, False)))


def _mask_or(left: pa.Array, right: pa.Array) -> pa.Array:
    return cast(pa.Array, pc.or_(pc.fill_null(left, False), pc.fill_null(right, False)))


def _mask_not(mask: pa.Array) -> pa.Array:
    return cast(pa.Array, pc.invert(pc.fill_null(mask, False)))


def _true_indices(mask: pa.Array) -> tuple[int, ...]:
    indices = pc.indices_nonzero(pc.fill_null(mask, False)).to_numpy(zero_copy_only=False)
    return tuple(indices.tolist())


def _source_values(table: pa.Table, column_name: str | None) -> list[object | None]:
    if column_name is None:
        return [None] * table.num_rows
    return cast(list[object | None], table.column(column_name).combine_chunks().to_pylist())


def _coerce_column(
    values: Sequence[object | None],
    spec: CrifColumnSpec,
    *,
    row_errors: list[list[AdapterDiagnostic]],
) -> list[object | None]:
    coerced: list[object | None] = []
    missing_column = (
        all(value is None for value in values) and spec.required and spec.default is None
    )
    for row_index, value in enumerate(values):
        try:
            candidate = spec.default if value is None and spec.default is not None else value
            coerced.append(_coerce_value(candidate, spec))
        except NormalizedTableError as exc:
            coerced.append(None)
            row_errors[row_index].append(
                _diagnostic(
                    code="crif.invalid_field",
                    message=(
                        f"required CRIF column {spec.name!r} is missing"
                        if missing_column
                        else str(exc)
                    ),
                    row_id=None,
                    column_name=spec.name,
                )
            )
    return coerced


def _coerce_value(value: object | None, spec: CrifColumnSpec) -> object | None:
    if value is None:
        if spec.required:
            raise NormalizedTableError(f"CRIF field {spec.name!r} is required")
        return None
    if spec.logical_type is TabularLogicalType.FLOAT:
        return _coerce_float(value, spec)
    if spec.logical_type is TabularLogicalType.INTEGER:
        return _coerce_integer(value, spec)
    if spec.logical_type is TabularLogicalType.BOOLEAN:
        return _coerce_boolean(value, spec)
    text = str(value).strip()
    if not text:
        if spec.required:
            raise NormalizedTableError(f"CRIF field {spec.name!r} is required")
        return None
    return text


def _coerce_float(value: object, spec: CrifColumnSpec) -> float | None:
    text = str(value).strip()
    if not text:
        if spec.required:
            raise NormalizedTableError(f"CRIF field {spec.name!r} is required")
        return None
    try:
        float_value = float(text)
    except (TypeError, ValueError) as exc:
        raise NormalizedTableError(f"CRIF field {spec.name!r} must be numeric") from exc
    if not math.isfinite(float_value):
        raise NormalizedTableError(f"CRIF field {spec.name!r} must be finite")
    return float_value


def _coerce_integer(value: object, spec: CrifColumnSpec) -> int | None:
    text = str(value).strip()
    if not text:
        if spec.required:
            raise NormalizedTableError(f"CRIF field {spec.name!r} is required")
        return None
    try:
        return int(text)
    except (TypeError, ValueError) as exc:
        raise NormalizedTableError(f"CRIF field {spec.name!r} must be an integer") from exc


def _coerce_boolean(value: object, spec: CrifColumnSpec) -> bool | None:
    text = str(value).strip().lower()
    if not text:
        if spec.required:
            raise NormalizedTableError(f"CRIF field {spec.name!r} is required")
        return None
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    raise NormalizedTableError(f"CRIF field {spec.name!r} must be boolean")


def _source_row_ids(values: Sequence[object | None] | None, row_count: int) -> list[str]:
    if values is None:
        return [str(index) for index in range(row_count)]
    row_ids: list[str] = []
    for index, value in enumerate(values):
        text = "" if value is None else str(value).strip()
        row_ids.append(text or str(index))
    return row_ids


def _attach_source_row_ids(
    row_errors: Sequence[list[AdapterDiagnostic]],
    source_row_ids: Sequence[str],
) -> None:
    for row_index, errors in enumerate(row_errors):
        for error_index, diagnostic in enumerate(errors):
            if diagnostic.row_id is not None:
                continue
            errors[error_index] = AdapterDiagnostic(
                code=diagnostic.code,
                message=diagnostic.message,
                severity=diagnostic.severity,
                row_id=source_row_ids[row_index],
                column_name=diagnostic.column_name,
            )


def _risk_mapping_output(
    risk_type: str,
    row: Mapping[str, object],
    risk_mapping_by_type: Mapping[str, Mapping[str, object]],
    risk_type_mapper: CrifRiskTypeMapper | None,
) -> Mapping[str, object] | None:
    if risk_type_mapper is not None:
        return risk_type_mapper(risk_type, row)
    if not risk_mapping_by_type:
        return {}
    return risk_mapping_by_type.get(_normalise_risk_type(risk_type))


def _table_from_columns(
    columns: Mapping[str, Sequence[object | None]],
    indices: Sequence[int],
    *,
    specs: tuple[CrifColumnSpec, ...],
    mapping_outputs: Mapping[str, Sequence[object | None]],
) -> pa.Table:
    spec_by_name = {spec.name: spec for spec in specs}
    accepted_columns: dict[str, pa.Array] = {}
    for column_name in sorted(columns):
        values = [columns[column_name][index] for index in indices]
        logical_type = spec_by_name.get(column_name, CrifColumnSpec(column_name)).logical_type
        if column_name in mapping_outputs:
            logical_type = _mapping_output_logical_type(values, default=logical_type)
        accepted_columns[column_name] = _arrow_array(values, logical_type)
    return pa.table(accepted_columns)


def _mapping_output_logical_type(
    values: Sequence[object | None],
    *,
    default: TabularLogicalType,
) -> TabularLogicalType:
    non_null_values = [value for value in values if value is not None]
    if not non_null_values:
        return default
    if all(isinstance(value, float) for value in non_null_values):
        for value in non_null_values:
            if not math.isfinite(cast(float, value)):
                raise NormalizedTableError("CRIF mapping output float values must be finite")
        return TabularLogicalType.FLOAT
    return default


def _arrow_array(values: Sequence[object | None], logical_type: TabularLogicalType) -> pa.Array:
    if logical_type is TabularLogicalType.FLOAT:
        return pa.array(values, type=pa.float64())
    if logical_type is TabularLogicalType.INTEGER:
        return pa.array(values, type=pa.int64())
    if logical_type is TabularLogicalType.BOOLEAN:
        return pa.array(values, type=pa.bool_())
    return pa.array([None if value is None else str(value) for value in values], type=pa.string())


def _rejected_table(
    raw_table: pa.Table,
    *,
    source_row_ids: Sequence[str],
    row_errors: Sequence[Sequence[AdapterDiagnostic]],
    rejected_indices: Sequence[int],
) -> pa.Table | None:
    if not rejected_indices:
        return None
    columns: dict[str, list[str]] = {
        CRIF_SOURCE_ROW_ID_COLUMN: [],
        "rejection_code": [],
        "rejection_column": [],
        "rejection_reason": [],
        "source_row_json": [],
    }
    raw_columns = {
        column_name: raw_table.column(column_name).combine_chunks()
        for column_name in raw_table.column_names
    }
    for row_index in rejected_indices:
        diagnostic = row_errors[row_index][0]
        columns[CRIF_SOURCE_ROW_ID_COLUMN].append(source_row_ids[row_index])
        columns["rejection_code"].append(diagnostic.code)
        columns["rejection_column"].append(diagnostic.column_name or "")
        columns["rejection_reason"].append(diagnostic.message)
        source_row = {
            column_name: _stringify_record_value(values[row_index].as_py())
            for column_name, values in raw_columns.items()
        }
        columns["source_row_json"].append(
            json.dumps(source_row, sort_keys=True, separators=(",", ":"))
        )
    return pa.table(columns)


def _handoff_column_specs(
    table: pa.Table,
    specs: tuple[CrifColumnSpec, ...],
    mapping_outputs: Mapping[str, Sequence[object | None]],
) -> tuple[ColumnSpec, ...]:
    spec_by_name = {spec.name: spec for spec in specs}
    handoff_specs: list[ColumnSpec] = []
    for column_name in table.column_names:
        if column_name in spec_by_name:
            handoff_specs.append(spec_by_name[column_name].as_column_spec())
            continue
        null_policy = NullPolicy.FORBID
        if column_name in mapping_outputs and table[column_name].null_count:
            null_policy = NullPolicy.ALLOW
        handoff_specs.append(ColumnSpec(column_name, null_policy=null_policy))
    return tuple(handoff_specs)


def _diagnostic(
    *,
    code: str,
    message: str,
    row_id: str | None,
    column_name: str,
) -> AdapterDiagnostic:
    return AdapterDiagnostic(
        code=code,
        message=message,
        severity=DiagnosticSeverity.ERROR,
        row_id=row_id,
        column_name=column_name,
    )


__all__ = [
    "CRIF_RISK_TYPE_COLUMN",
    "CRIF_SOURCE_ROW_ID_COLUMN",
    "CRIF_SOURCE_SYSTEM",
    "DEFAULT_CRIF_COLUMN_SPECS",
    "CrifColumnSpec",
    "CrifRiskTypeMapper",
    "CrifRiskTypeMapping",
    "crif_records_to_arrow_table",
    "normalise_crif_risk_type",
    "normalize_crif_arrow_table",
    "normalize_crif_records",
    "resolve_crif_column_name",
]
