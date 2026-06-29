"""Column mapping helpers and mapping-config export."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
from frtb_common import ColumnSpec, NormalizedArrowTable, normalized_arrow_table_hash, source_content_hash

from tools.onboarding_mapper.backend.catalog import TableCatalogEntry


def suggest_column_mapping(
    specs: Sequence[ColumnSpec],
    source_columns: Sequence[str],
) -> dict[str, str | None]:
    """Suggest canonical-to-source mappings using names and declared aliases."""

    exact_lookup = {name: name for name in source_columns}
    lower_lookup = {name.lower(): name for name in source_columns}
    used_sources: set[str] = set()
    mapping: dict[str, str | None] = {}

    for spec in specs:
        match: str | None = None
        for candidate in (spec.name, *spec.aliases):
            if candidate in exact_lookup and candidate not in used_sources:
                match = candidate
                break
            lowered = candidate.lower()
            if lowered in lower_lookup and lower_lookup[lowered] not in used_sources:
                match = lower_lookup[lowered]
                break
        if match is not None:
            used_sources.add(match)
        mapping[spec.name] = match
    return mapping


def apply_column_mapping(table: pa.Table, mapping: Mapping[str, str | None]) -> pa.Table:
    """Rename and project client columns into canonical column names."""

    columns: dict[str, pa.Array | pa.ChunkedArray] = {}
    for canonical_name, source_name in mapping.items():
        if not source_name:
            continue
        if source_name not in table.column_names:
            raise ValueError(f"Source column {source_name!r} is not present in the client table")
        columns[canonical_name] = table.column(source_name)
    if not columns:
        raise ValueError("At least one column mapping is required")
    return pa.table(columns)


def validate_mapped_table(
    entry: TableCatalogEntry,
    mapped_table: pa.Table,
    *,
    source_bytes: bytes | None = None,
) -> tuple[NormalizedArrowTable, bool, list[dict[str, object]]]:
    source_hash = source_content_hash(source_bytes) if source_bytes is not None else None
    diagnostics: list[dict[str, object]] = []
    batch_built = False

    try:
        normalized = entry.normalize(mapped_table, source_hash=source_hash)
    except TypeError:
        normalized = entry.normalize(mapped_table)
    except Exception as exc:
        diagnostics.append(
            {
                "code": "INPUT_TABLE_NORMALIZATION_ERROR",
                "message": str(exc),
                "severity": "error",
                "row_id": None,
                "column_name": None,
            }
        )
        from scripts.client_input_table_registry import empty_table_for_specs

        normalized = NormalizedArrowTable(
            accepted=empty_table_for_specs(entry.column_specs),
            column_specs=entry.column_specs,
            rejected=mapped_table,
            diagnostics=(),
            source_hash=source_hash,
        )
    else:
        diagnostics.extend(diagnostic.as_dict() for diagnostic in normalized.diagnostics)
        try:
            _build_batch_from_normalized(entry, normalized)
            batch_built = True
        except _BatchBuildSkipped:
            batch_built = False
        except Exception as exc:
            diagnostics.append(
                {
                    "code": "INPUT_TABLE_BATCH_BUILD_ERROR",
                    "message": str(exc),
                    "severity": "error",
                    "row_id": None,
                    "column_name": None,
                }
            )
    return normalized, batch_built, diagnostics


class _BatchBuildSkipped(Exception):
    """Raised when no batch builder is registered for a catalog entry."""


def _build_batch_from_normalized(entry: TableCatalogEntry, normalized: NormalizedArrowTable) -> None:
    from scripts.client_input_table_registry import resolve_input_table_entry

    try:
        registry_entry = resolve_input_table_entry(entry.package, entry.table_id)
    except KeyError:
        if entry.package == "frtb_sbm" and entry.sbm_risk_class and entry.sbm_risk_measure:
            import frtb_sbm

            frtb_sbm.build_sbm_batch_from_arrow(
                normalized,
                frtb_sbm.SbmRiskClass(entry.sbm_risk_class),
                frtb_sbm.SbmRiskMeasure(entry.sbm_risk_measure),
            )
            return
        if entry.package == "frtb_cva":
            import frtb_cva

            builders = {
                "counterparty": frtb_cva.build_cva_counterparty_batch_from_arrow,
                "netting_set": frtb_cva.build_cva_netting_set_batch_from_arrow,
                "hedge": frtb_cva.build_cva_hedge_batch_from_arrow,
                "sa_cva_sensitivity": frtb_cva.build_sa_cva_sensitivity_batch_from_arrow,
            }
            builder = builders.get(entry.table_id)
            if builder is None:
                raise _BatchBuildSkipped
            builder(normalized)
            return
        raise _BatchBuildSkipped

    if registry_entry.build_batch is None:
        raise _BatchBuildSkipped
    registry_entry.build_batch(normalized)


def build_mapping_document(
    *,
    entry: TableCatalogEntry,
    mapping: Mapping[str, str | None],
    source_connector: str,
    source_format: str | None,
    source_path: str | None,
    duckdb_database: str | None,
    duckdb_query: str | None,
    lineage_source_system: str,
    lineage_source_file: str | None,
) -> dict[str, Any]:
    target: dict[str, Any] = {
        "package": entry.package,
        "input_table": entry.table_id,
        "component": entry.component,
        "label": entry.label,
    }
    if entry.sbm_risk_class is not None:
        target["sbm_risk_class"] = entry.sbm_risk_class
    if entry.sbm_risk_measure is not None:
        target["sbm_risk_measure"] = entry.sbm_risk_measure

    source: dict[str, Any] = {"connector": source_connector}
    if source_connector == "duckdb":
        source["database"] = duckdb_database or ":memory:"
        source["query"] = duckdb_query or ""
    else:
        if source_format is not None:
            source["format"] = source_format
        if source_path is not None:
            source["path"] = source_path

    lineage_pairs = sorted(
        (source_name, canonical_name)
        for canonical_name, source_name in mapping.items()
        if source_name
    )

    return {
        "version": "1",
        "target": target,
        "source": source,
        "column_mapping": {
            canonical_name: source_name
            for canonical_name, source_name in sorted(mapping.items())
            if source_name
        },
        "lineage": {
            "source_system": lineage_source_system,
            "source_file": lineage_source_file,
            "source_column_map": [list(pair) for pair in lineage_pairs],
        },
    }


def serialize_mapping_document(document: Mapping[str, Any], fmt: str) -> str:
    if fmt == "json":
        return json.dumps(document, indent=2, sort_keys=True) + "\n"
    if fmt == "yaml":
        return _dump_yaml(document)
    if fmt == "toml":
        return _dump_toml(document)
    raise ValueError(f"Unsupported export format: {fmt}")


def mapping_filename(entry: TableCatalogEntry, fmt: str) -> str:
    extension = {"yaml": "yaml", "toml": "toml", "json": "json"}[fmt]
    return f"{entry.package}.{entry.table_id}.mapping.{extension}"


def _dump_yaml(value: Any, indent: int = 0) -> str:
    prefix = " " * indent
    if isinstance(value, dict):
        if not value:
            return "{}\n"
        lines: list[str] = []
        for key, item in value.items():
            rendered = _dump_yaml(item, indent + 2).rstrip("\n")
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.append(rendered)
            else:
                lines.append(f"{prefix}{key}: {rendered}")
        return "\n".join(lines) + "\n"
    if isinstance(value, list):
        if not value:
            return "[]\n"
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.append(_dump_yaml(item, indent + 2).rstrip("\n"))
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
        return "\n".join(lines) + "\n"
    return _yaml_scalar(value) + "\n"


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "" or any(character in text for character in ":#{}[]&*!|>'\"%@`"):
        return json.dumps(text)
    return text


def _dump_toml(value: Any, prefix: str = "") -> str:
    if not isinstance(value, dict):
        return f"{prefix} = {_toml_scalar(value)}\n"
    lines: list[str] = []
    inline: dict[str, Any] = {}
    tables: dict[str, dict[str, Any]] = {}
    for key, item in value.items():
        if isinstance(item, dict):
            tables[key] = item
        else:
            inline[key] = item
    for key, item in inline.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(item, list):
            lines.append(f"{full_key} = {_toml_list(item)}")
        else:
            lines.append(f"{full_key} = {_toml_scalar(item)}")
    for key, table in tables.items():
        header = f"{prefix}.{key}" if prefix else key
        lines.append(f"\n[{header}]")
        for sub_key, sub_value in table.items():
            if isinstance(sub_value, list):
                lines.append(f"{sub_key} = {_toml_list(sub_value)}")
            elif isinstance(sub_value, dict):
                raise ValueError("Nested TOML tables are not supported in this exporter")
            else:
                lines.append(f"{sub_key} = {_toml_scalar(sub_value)}")
    return "\n".join(line for line in lines if line).strip() + "\n"


def _toml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value))


def _toml_list(value: list[Any]) -> str:
    return "[" + ", ".join(_toml_scalar(item) for item in value) + "]"


def normalized_preview_hash(normalized: NormalizedArrowTable) -> str:
    return normalized_arrow_table_hash(normalized)
