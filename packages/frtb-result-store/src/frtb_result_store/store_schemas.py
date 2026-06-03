"""Parquet table schemas and Arrow conversion helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pyarrow as pa  # type: ignore[import-untyped]
from frtb_common.hashing import stable_json_hash

def _dict_rows(
    columns: Sequence[str],
    rows: Sequence[Sequence[object]],
) -> tuple[dict[str, object], ...]:
    return tuple(dict(zip(columns, row, strict=True)) for row in rows)


def _arrow_table(rows: Sequence[Mapping[str, object]], schema: Any) -> Any:
    return pa.Table.from_pylist(list(rows), schema=schema)


def _table_schema_fingerprint(table_name: str) -> str:
    schema = _TABLE_SCHEMAS[table_name]
    return stable_json_hash(
        {
            "table_name": table_name,
            "fields": [
                {"name": field.name, "type": str(field.type), "nullable": field.nullable}
                for field in schema
            ],
        }
    )


_TABLE_SCHEMAS: dict[str, Any] = {
    "runs": pa.schema(
        [
            ("run_id", pa.string()),
            ("run_group_id", pa.string()),
            ("as_of_date", pa.string()),
            ("regime_id", pa.string()),
            ("base_currency", pa.string()),
            ("input_snapshot_id", pa.string()),
            ("calculation_scope", pa.string()),
            ("engine_version", pa.string()),
            ("code_version", pa.string()),
            ("calculation_policy_id", pa.string()),
            ("created_at", pa.string()),
            ("identity_payload_json", pa.string()),
            ("run_group_identity_payload_json", pa.string()),
            ("metadata_json", pa.string()),
        ]
    ),
    "hierarchy_definitions": pa.schema(
        [
            ("run_id", pa.string()),
            ("hierarchy_id", pa.string()),
            ("hierarchy_version", pa.string()),
            ("hierarchy_name", pa.string()),
            ("leaf_level", pa.string()),
            ("levels_json", pa.string()),
            ("created_at", pa.string()),
            ("metadata_json", pa.string()),
        ]
    ),
    "hierarchy_nodes": pa.schema(
        [
            ("run_id", pa.string()),
            ("hierarchy_id", pa.string()),
            ("hierarchy_version", pa.string()),
            ("hierarchy_node_id", pa.string()),
            ("parent_hierarchy_node_id", pa.string()),
            ("level_name", pa.string()),
            ("level_order", pa.int64()),
            ("business_key", pa.string()),
            ("label", pa.string()),
            ("path_json", pa.string()),
            ("metadata_json", pa.string()),
        ]
    ),
    "capital_nodes": pa.schema(
        [
            ("run_id", pa.string()),
            ("node_id", pa.string()),
            ("node_type", pa.string()),
            ("component", pa.string()),
            ("label", pa.string()),
            ("desk_id", pa.string()),
            ("portfolio_id", pa.string()),
            ("book_id", pa.string()),
            ("risk_class", pa.string()),
            ("bucket", pa.string()),
            ("issuer_id", pa.string()),
            ("counterparty_id", pa.string()),
            ("calculation_branch", pa.string()),
            ("regulatory_rule_id", pa.string()),
            ("sort_key", pa.int64()),
            ("metadata_json", pa.string()),
        ]
    ),
    "capital_edges": pa.schema(
        [
            ("run_id", pa.string()),
            ("parent_node_id", pa.string()),
            ("child_node_id", pa.string()),
            ("edge_type", pa.string()),
            ("aggregation_weight", pa.float64()),
            ("sort_key", pa.int64()),
        ]
    ),
    "capital_measures": pa.schema(
        [
            ("run_id", pa.string()),
            ("node_id", pa.string()),
            ("measure_name", pa.string()),
            ("amount", pa.float64()),
            ("currency", pa.string()),
            ("unit", pa.string()),
            ("scenario", pa.string()),
            ("methodology", pa.string()),
            ("regulatory_rule_id", pa.string()),
            ("citations_json", pa.string()),
            ("metadata_json", pa.string()),
        ]
    ),
    "artifact_refs": pa.schema(
        [
            ("run_id", pa.string()),
            ("artifact_id", pa.string()),
            ("component", pa.string()),
            ("artifact_type", pa.string()),
            ("uri", pa.string()),
            ("format", pa.string()),
            ("row_count", pa.int64()),
            ("schema_fingerprint", pa.string()),
            ("partition_keys_json", pa.string()),
            ("metadata_json", pa.string()),
        ]
    ),
    "artifact_expectations": pa.schema(
        [
            ("run_id", pa.string()),
            ("component", pa.string()),
            ("artifact_type", pa.string()),
            ("trigger_name", pa.string()),
            ("required", pa.bool_()),
            ("reason", pa.string()),
        ]
    ),
    "input_snapshot_manifests": pa.schema(
        [
            ("run_id", pa.string()),
            ("input_snapshot_id", pa.string()),
            ("input_snapshot_hash", pa.string()),
            ("as_of_date", pa.string()),
            ("source_system", pa.string()),
            ("handoff_key", pa.string()),
            ("row_count", pa.int64()),
            ("accepted_row_count", pa.int64()),
            ("rejected_row_count", pa.int64()),
            ("source_uri", pa.string()),
            ("source_hash", pa.string()),
            ("schema_fingerprint", pa.string()),
            ("metadata_json", pa.string()),
        ]
    ),
    "lineage_refs": pa.schema(
        [
            ("run_id", pa.string()),
            ("result_id", pa.string()),
            ("source_type", pa.string()),
            ("source_id", pa.string()),
            ("relationship", pa.string()),
            ("source_hash", pa.string()),
            ("metadata_json", pa.string()),
        ]
    ),
    "capital_attributions": pa.schema(
        [
            ("run_id", pa.string()),
            ("node_id", pa.string()),
            ("attribution_id", pa.string()),
            ("target_type", pa.string()),
            ("target_id", pa.string()),
            ("source_id", pa.string()),
            ("source_level", pa.string()),
            ("method", pa.string()),
            ("category", pa.string()),
            ("bucket_key", pa.string()),
            ("base_amount", pa.float64()),
            ("marginal_multiplier", pa.float64()),
            ("contribution", pa.float64()),
            ("residual", pa.float64()),
            ("unsupported_reason", pa.string()),
            ("artifact_id", pa.string()),
            ("metadata_json", pa.string()),
        ]
    ),
    "movement_results": pa.schema(
        [
            ("run_id", pa.string()),
            ("baseline_run_id", pa.string()),
            ("movement_id", pa.string()),
            ("node_id", pa.string()),
            ("movement_type", pa.string()),
            ("from_amount", pa.float64()),
            ("to_amount", pa.float64()),
            ("delta_amount", pa.float64()),
            ("base_currency", pa.string()),
            ("driver_type", pa.string()),
            ("driver_id", pa.string()),
            ("explanation", pa.string()),
            ("attribution_method", pa.string()),
            ("artifact_id", pa.string()),
            ("metadata_json", pa.string()),
        ]
    ),
    "result_events": pa.schema(
        [
            ("event_id", pa.string()),
            ("run_id", pa.string()),
            ("event_time", pa.string()),
            ("severity", pa.string()),
            ("event_type", pa.string()),
            ("message", pa.string()),
            ("component", pa.string()),
            ("suggested_status", pa.string()),
            ("metadata_json", pa.string()),
        ]
    ),
    "run_telemetry": pa.schema(
        [
            ("run_id", pa.string()),
            ("phase", pa.string()),
            ("duration_ms", pa.float64()),
            ("created_at", pa.string()),
            ("trace_id", pa.string()),
            ("span_id", pa.string()),
            ("row_count", pa.int64()),
            ("byte_count", pa.int64()),
            ("artifact_id", pa.string()),
            ("mart_name", pa.string()),
        ]
    ),
    "run_status_events": pa.schema(
        [
            ("event_id", pa.string()),
            ("run_id", pa.string()),
            ("from_status", pa.string()),
            ("to_status", pa.string()),
            ("event_time", pa.string()),
            ("actor", pa.string()),
            ("reason_code", pa.string()),
            ("reason_text", pa.string()),
            ("external_evidence_ref", pa.string()),
        ]
    ),
}
