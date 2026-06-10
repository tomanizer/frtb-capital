"""SA-CVA sensitivity Arrow column specifications for batch ingress."""

from __future__ import annotations

from frtb_common import ColumnSpec, NullPolicy, TabularLogicalType

SA_CVA_SENSITIVITY_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec(
        "sensitivity_id",
        aliases=("sensitivityId", "SensitivityID", "RiskFactorID"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("risk_class", aliases=("riskClass",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("risk_measure", aliases=("riskMeasure",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "sensitivity_tag", aliases=("sensitivityTag", "tag"), logical_type=TabularLogicalType.STRING
    ),
    ColumnSpec("bucket_id", aliases=("bucketId", "bucket"), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "risk_factor_key",
        aliases=("riskFactorKey", "qualifier"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("amount", aliases=("Amount",), logical_type=TabularLogicalType.FLOAT),
    ColumnSpec(
        "amount_currency",
        aliases=("amountCurrency", "currency"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "sign_convention", aliases=("signConvention",), logical_type=TabularLogicalType.STRING
    ),
    ColumnSpec(
        "source_row_id",
        aliases=("sourceRowId", "RowID"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "tenor",
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "volatility_input",
        aliases=("volatilityInput",),
        logical_type=TabularLogicalType.FLOAT,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "hedge_id",
        aliases=("hedgeId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "index_treatment",
        aliases=("indexTreatment",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "index_max_sector_weight",
        aliases=("indexMaxSectorWeight",),
        logical_type=TabularLogicalType.FLOAT,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "index_homogeneous_sector_quality",
        aliases=("indexHomogeneousSectorQuality",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "index_dominant_sector",
        aliases=("indexDominantSector",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "index_remap_bucket_id",
        aliases=("indexRemapBucketId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
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
        aliases=("lineageSourceRowId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)
