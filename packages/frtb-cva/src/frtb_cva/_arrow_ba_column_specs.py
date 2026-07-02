"""BA-CVA Arrow column specifications for CVA batch ingress."""

from __future__ import annotations

from frtb_common import ColumnSpec, NullPolicy, TabularLogicalType

CVA_COUNTERPARTY_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec(
        "counterparty_id",
        aliases=("counterpartyId", "CounterpartyID"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("desk_id", aliases=("deskId", "DeskID"), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "legal_entity",
        aliases=("legalEntity", "LegalEntity"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("sector", logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "credit_quality", aliases=("creditQuality",), logical_type=TabularLogicalType.STRING
    ),
    ColumnSpec("region", logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "source_row_id",
        aliases=("sourceRowId", "RowID"),
        logical_type=TabularLogicalType.STRING,
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

CVA_NETTING_SET_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec(
        "netting_set_id",
        aliases=("nettingSetId", "NettingSetID"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "counterparty_id",
        aliases=("counterpartyId", "CounterpartyID"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("ead", aliases=("EAD", "exposure"), logical_type=TabularLogicalType.FLOAT),
    ColumnSpec(
        "effective_maturity",
        aliases=("effectiveMaturity", "maturity"),
        logical_type=TabularLogicalType.FLOAT,
    ),
    ColumnSpec(
        "discount_factor", aliases=("discountFactor",), logical_type=TabularLogicalType.FLOAT
    ),
    ColumnSpec("currency", logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "sign_convention", aliases=("signConvention",), logical_type=TabularLogicalType.STRING
    ),
    ColumnSpec("uses_imm_ead", aliases=("usesImmEad",), logical_type=TabularLogicalType.BOOLEAN),
    ColumnSpec(
        "source_row_id",
        aliases=("sourceRowId", "RowID"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "carved_out_to_ba_cva",
        aliases=("carvedOutToBaCva",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "discount_factor_explicit",
        aliases=("discountFactorExplicit",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "exposure_time_series_id",
        aliases=("exposureTimeSeriesId", "exposure_time_series", "exposureScenarioRef"),
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
