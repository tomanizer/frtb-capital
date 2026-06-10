"""CVA hedge Arrow column specifications for batch ingress."""

from __future__ import annotations

from frtb_common import ColumnSpec, NullPolicy, TabularLogicalType

CVA_HEDGE_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec("hedge_id", aliases=("hedgeId", "HedgeID"), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "source_row_id",
        aliases=("sourceRowId", "RowID"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "counterparty_id",
        aliases=("counterpartyId", "CounterpartyID"),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "hedge_type",
        aliases=("hedgeType",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec("notional", logical_type=TabularLogicalType.FLOAT),
    ColumnSpec(
        "remaining_maturity", aliases=("remainingMaturity",), logical_type=TabularLogicalType.FLOAT
    ),
    ColumnSpec(
        "discount_factor", aliases=("discountFactor",), logical_type=TabularLogicalType.FLOAT
    ),
    ColumnSpec(
        "reference_sector", aliases=("referenceSector",), logical_type=TabularLogicalType.STRING
    ),
    ColumnSpec(
        "reference_credit_quality",
        aliases=("referenceCreditQuality",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "reference_region", aliases=("referenceRegion",), logical_type=TabularLogicalType.STRING
    ),
    ColumnSpec(
        "reference_relation", aliases=("referenceRelation",), logical_type=TabularLogicalType.STRING
    ),
    ColumnSpec("eligibility", logical_type=TabularLogicalType.STRING),
    ColumnSpec("is_internal", aliases=("isInternal",), logical_type=TabularLogicalType.BOOLEAN),
    ColumnSpec(
        "discount_factor_explicit",
        aliases=("discountFactorExplicit",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "internal_desk_counterparty_id",
        aliases=("internalDeskCounterpartyId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "sa_cva_risk_class",
        aliases=("saCvaRiskClass",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "sa_cva_hedge_purpose",
        aliases=("saCvaHedgePurpose",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "sa_cva_hedge_instrument_type",
        aliases=("saCvaHedgeInstrumentType",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "whole_transaction_evidence_id",
        aliases=("wholeTransactionEvidenceId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "market_risk_ima_eligible",
        aliases=("marketRiskImaEligible",),
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "market_risk_ima_exclusion_reason",
        aliases=("marketRiskImaExclusionReason",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "eligibility_evidence_id",
        aliases=("eligibilityEvidenceId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "rejection_reason",
        aliases=("rejectionReason",),
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
