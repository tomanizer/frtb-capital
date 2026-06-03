"""Stable schemas for persisted result-store reporting marts."""

from __future__ import annotations

import pyarrow as pa  # type: ignore[import-untyped]
from frtb_common.hashing import stable_json_hash

__all__ = ["MART_NAMES", "MART_SCHEMAS", "mart_schema_fingerprint"]

MART_SCHEMA_VERSION = 2
MART_NAMES = ("capital_summary", "capital_tree", "component_breakdown", "movement_summary")
MART_SCHEMAS: dict[str, pa.Schema] = {
    "capital_summary": pa.schema(
        [
            ("run_id", pa.string()),
            ("as_of_date", pa.string()),
            ("regime_id", pa.string()),
            ("base_currency", pa.string()),
            ("lifecycle_status", pa.string()),
            ("suggested_status", pa.string()),
            ("total_capital", pa.float64()),
            ("currency", pa.string()),
            ("node_count", pa.int64()),
            ("measure_count", pa.int64()),
            ("component_count", pa.int64()),
        ]
    ),
    "capital_tree": pa.schema(
        [
            ("run_id", pa.string()),
            ("node_id", pa.string()),
            ("parent_node_id", pa.string()),
            ("depth", pa.int64()),
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
    "component_breakdown": pa.schema(
        [
            ("run_id", pa.string()),
            ("component", pa.string()),
            ("amount", pa.float64()),
            ("currency", pa.string()),
            ("node_count", pa.int64()),
            ("measure_count", pa.int64()),
        ]
    ),
    "movement_summary": pa.schema(
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
            ("attribution_method", pa.string()),
            ("artifact_id", pa.string()),
        ]
    ),
}


def mart_schema_fingerprint(mart_name: str) -> str:
    schema = MART_SCHEMAS[mart_name]
    return stable_json_hash(
        {
            "mart_name": mart_name,
            "schema_version": MART_SCHEMA_VERSION,
            "fields": [
                {"name": field.name, "type": str(field.type), "nullable": field.nullable}
                for field in schema
            ],
        }
    )
