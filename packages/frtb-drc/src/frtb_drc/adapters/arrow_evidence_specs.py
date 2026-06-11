"""Arrow column specs for DRC evidence handoffs."""

from __future__ import annotations

from frtb_common import ColumnSpec, NullPolicy, TabularLogicalType

DRC_RISK_WEIGHT_EVIDENCE_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec("position_id", aliases=("positionId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("risk_class", aliases=("riskClass",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "source_profile_id",
        aliases=("sourceProfileId",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("source_table", aliases=("sourceTable",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("source_method", aliases=("sourceMethod",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "effective_risk_weight",
        aliases=("effectiveRiskWeight", "risk_weight", "riskWeight"),
        logical_type=TabularLogicalType.FLOAT,
    ),
    ColumnSpec("as_of_date", aliases=("asOfDate",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("source_id", aliases=("sourceId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "lineage_source_system",
        aliases=("source_system", "sourceSystem"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "lineage_source_file",
        aliases=("source_file", "sourceFile"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "lineage_source_row_id",
        aliases=("source_row_id", "sourceRowId"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("citation_ids", aliases=("citationIds",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "is_stale",
        aliases=("isStale",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "validation_flags",
        aliases=("validationFlags",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)

DRC_FAIR_VALUE_CAP_EVIDENCE_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec("position_id", aliases=("positionId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "source_profile_id",
        aliases=("sourceProfileId",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("eligible", logical_type=TabularLogicalType.BOOLEAN),
    ColumnSpec(
        "fair_value_cap_amount",
        aliases=("fairValueCapAmount",),
        logical_type=TabularLogicalType.FLOAT,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "eligibility_reason",
        aliases=("eligibilityReason",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("as_of_date", aliases=("asOfDate",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("source_id", aliases=("sourceId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "lineage_source_system",
        aliases=("source_system", "sourceSystem"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "lineage_source_file",
        aliases=("source_file", "sourceFile"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "lineage_source_row_id",
        aliases=("source_row_id", "sourceRowId"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("citation_ids", aliases=("citationIds",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "is_stale",
        aliases=("isStale",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "validation_flags",
        aliases=("validationFlags",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)

__all__ = [
    "DRC_FAIR_VALUE_CAP_EVIDENCE_ARROW_COLUMN_SPECS",
    "DRC_RISK_WEIGHT_EVIDENCE_ARROW_COLUMN_SPECS",
]
