"""Schema export helpers for normalized Arrow ``ColumnSpec`` contracts."""

from __future__ import annotations

from collections.abc import Sequence

import pyarrow as pa  # type: ignore[import-untyped]

from frtb_common.arrow_table import (
    ColumnSpec,
    NormalizedTableError,
    NullPolicy,
    TabularLogicalType,
    validate_column_specs,
)


def column_spec_to_json_schema(spec: ColumnSpec) -> dict[str, object]:
    """Return a JSON Schema property for one Arrow column spec."""

    return {
        **_json_type_for_logical_type(spec.logical_type),
        "x-frtb-aliases": sorted(spec.aliases),
        "x-frtb-chunk-policy": spec.chunk_policy.value,
        "x-frtb-dictionary-policy": spec.dictionary_policy.value,
        "x-frtb-logical-type": spec.logical_type.value,
        "x-frtb-null-policy": spec.null_policy.value,
        "x-frtb-required": spec.required,
    }


def column_specs_to_json_schema(
    specs: Sequence[ColumnSpec],
    *,
    title: str,
    description: str | None = None,
) -> dict[str, object]:
    """Return a deterministic JSON Schema document for a column spec tuple."""

    validated = validate_column_specs(specs)
    schema: dict[str, object] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "additionalProperties": True,
        "properties": {spec.name: column_spec_to_json_schema(spec) for spec in validated},
        "required": [spec.name for spec in validated if spec.required],
        "title": title,
        "type": "object",
        "x-frtb-column-order": [spec.name for spec in validated],
    }
    if description is not None:
        schema["description"] = description
    return schema


def column_specs_to_arrow_schema(specs: Sequence[ColumnSpec]) -> pa.Schema:
    """Return a PyArrow schema matching the column specs."""

    validated = validate_column_specs(specs)
    return pa.schema(
        [
            pa.field(
                spec.name,
                _arrow_type_for_logical_type(spec.logical_type),
                nullable=spec.null_policy is not NullPolicy.FORBID,
                metadata={
                    b"frtb.aliases": bytes(",".join(sorted(spec.aliases)), "utf-8"),
                    b"frtb.chunk_policy": bytes(spec.chunk_policy.value, "utf-8"),
                    b"frtb.dictionary_policy": bytes(spec.dictionary_policy.value, "utf-8"),
                    b"frtb.logical_type": bytes(spec.logical_type.value, "utf-8"),
                    b"frtb.null_policy": bytes(spec.null_policy.value, "utf-8"),
                    b"frtb.required": bytes(str(spec.required).lower(), "utf-8"),
                },
            )
            for spec in validated
        ]
    )


def arrow_schema_to_dict(schema: pa.Schema) -> dict[str, object]:
    """Return a deterministic JSON-ready representation of a PyArrow schema."""

    fields: list[dict[str, object]] = []
    for field in schema:
        metadata = {
            key.decode(): value.decode() for key, value in sorted((field.metadata or {}).items())
        }
        fields.append(
            {
                "metadata": metadata,
                "name": field.name,
                "nullable": field.nullable,
                "type": str(field.type),
            }
        )
    return {"fields": fields}


def _json_type_for_logical_type(logical_type: TabularLogicalType) -> dict[str, object]:
    mapping: dict[TabularLogicalType, dict[str, object]] = {
        TabularLogicalType.BOOLEAN: {"type": "boolean"},
        TabularLogicalType.DATE: {"format": "date", "type": "string"},
        TabularLogicalType.DECIMAL: {"type": "number"},
        TabularLogicalType.DICTIONARY: {"type": "string"},
        TabularLogicalType.DICTIONARY_CODE: {"type": "integer"},
        TabularLogicalType.FLOAT: {"type": "number"},
        TabularLogicalType.INTEGER: {"type": "integer"},
        TabularLogicalType.STRING: {"type": "string"},
        TabularLogicalType.TIMESTAMP: {"format": "date-time", "type": "string"},
    }
    try:
        return dict(mapping[logical_type])
    except KeyError as exc:
        raise NormalizedTableError(
            f"Cannot export schema for unknown logical type {logical_type!r}"
        ) from exc


def _arrow_type_for_logical_type(logical_type: TabularLogicalType) -> pa.DataType:
    mapping: dict[TabularLogicalType, pa.DataType] = {
        TabularLogicalType.BOOLEAN: pa.bool_(),
        TabularLogicalType.DATE: pa.date32(),
        TabularLogicalType.DECIMAL: pa.decimal128(38, 12),
        TabularLogicalType.DICTIONARY: pa.dictionary(pa.int32(), pa.string()),
        TabularLogicalType.DICTIONARY_CODE: pa.int32(),
        TabularLogicalType.FLOAT: pa.float64(),
        TabularLogicalType.INTEGER: pa.int64(),
        TabularLogicalType.STRING: pa.string(),
        TabularLogicalType.TIMESTAMP: pa.timestamp("us", tz="UTC"),
    }
    try:
        return mapping[logical_type]
    except KeyError as exc:
        raise NormalizedTableError(
            f"Cannot export Arrow schema for unknown logical type {logical_type!r}"
        ) from exc


__all__ = [
    "arrow_schema_to_dict",
    "column_spec_to_json_schema",
    "column_specs_to_arrow_schema",
    "column_specs_to_json_schema",
]
