"""IMA Arrow column specifications and adapter defaults."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from frtb_common import ColumnSpec, NullPolicy, TabularLogicalType

from frtb_ima.scenario import ScenarioSetType

IMA_INPUT_MANIFEST_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec("artifact_name", aliases=("artifactName",), logical_type=TabularLogicalType.STRING),
    ColumnSpec("artifact_type", aliases=("artifactType",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "schema_version",
        aliases=("schemaVersion",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec("source_system", aliases=("sourceSystem",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "source_version",
        aliases=("sourceVersion",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "extraction_timestamp",
        aliases=("extractionTimestamp",),
        logical_type=TabularLogicalType.TIMESTAMP,
    ),
    ColumnSpec("as_of_date", aliases=("asOfDate",), logical_type=TabularLogicalType.DATE),
    ColumnSpec("record_count", aliases=("recordCount",), logical_type=TabularLogicalType.INTEGER),
    ColumnSpec("vector_count", aliases=("vectorCount",), logical_type=TabularLogicalType.INTEGER),
    ColumnSpec("checksum", logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "sign_convention",
        aliases=("signConvention",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "validation_status",
        aliases=("validationStatus",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "validation_messages",
        aliases=("validationMessages",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "metadata_json",
        aliases=("metadataJson",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "source_row_id",
        aliases=("sourceRowId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)

IMA_SCENARIO_METADATA_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec("scenario_id", aliases=("scenarioId",), logical_type=TabularLogicalType.STRING),
    ColumnSpec(
        "scenario_date",
        aliases=("scenarioDate",),
        logical_type=TabularLogicalType.DATE,
    ),
    ColumnSpec(
        "scenario_set",
        aliases=("scenarioSet", "set_type", "setType"),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "calibration_window",
        aliases=("calibrationWindow",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "source",
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "provenance_json",
        aliases=("provenanceJson",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "source_row_id",
        aliases=("sourceRowId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)

IMA_RFET_OBSERVATION_ARROW_COLUMN_SPECS: tuple[ColumnSpec, ...] = (
    ColumnSpec(
        "risk_factor_name",
        aliases=("riskFactorName",),
        logical_type=TabularLogicalType.STRING,
    ),
    ColumnSpec(
        "observation_date",
        aliases=("observationDate",),
        logical_type=TabularLogicalType.DATE,
    ),
    ColumnSpec(
        "source",
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "vendor_id",
        aliases=("vendorId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "venue",
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "feed",
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "observation_timestamp",
        aliases=("observationTimestamp",),
        logical_type=TabularLogicalType.TIMESTAMP,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "date_normalization_evidence",
        aliases=("dateNormalizationEvidence",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "verifiable",
        logical_type=TabularLogicalType.BOOLEAN,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "verifiability_reason",
        aliases=("verifiabilityReason",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "data_pool_id",
        aliases=("dataPoolId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "vendor_audit_evidence_id",
        aliases=("vendorAuditEvidenceId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "source_row_id",
        aliases=("sourceRowId",),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
    ColumnSpec(
        "observation_time_series_id",
        aliases=("observationTimeSeriesId", "timeSeriesId"),
        logical_type=TabularLogicalType.STRING,
        required=False,
        null_policy=NullPolicy.ALLOW,
    ),
)
_IMA_SCENARIO_METADATA_BATCH_COLUMN_ARGS: Mapping[str, str] = {
    "scenario_id": "scenario_ids",
    "scenario_set": "scenario_sets",
    "calibration_window": "calibration_windows",
    "source": "sources",
    "provenance_json": "provenance_json",
    "source_row_id": "source_row_ids",
}

_IMA_RFET_OBSERVATION_BATCH_COLUMN_ARGS: Mapping[str, str] = {
    "risk_factor_name": "risk_factor_names",
    "source": "sources",
    "vendor_id": "vendor_ids",
    "venue": "venues",
    "feed": "feeds",
    "date_normalization_evidence": "date_normalization_evidence",
    "verifiable": "verifiable",
    "verifiability_reason": "verifiability_reasons",
    "data_pool_id": "data_pool_ids",
    "vendor_audit_evidence_id": "vendor_audit_evidence_ids",
    "source_row_id": "source_row_ids",
    "observation_time_series_id": "observation_time_series_ids",
}

_IMA_SCENARIO_METADATA_DEFAULTS: Mapping[str, object] = {
    "scenario_set": ScenarioSetType.CURRENT.value,
    "calibration_window": "",
    "source": "",
    "provenance_json": "",
    "source_row_id": "",
}

_IMA_RFET_OBSERVATION_DEFAULTS: Mapping[str, object] = {
    "source": "",
    "vendor_id": "",
    "venue": "",
    "feed": "",
    "date_normalization_evidence": "",
    "verifiable": True,
    "verifiability_reason": "",
    "data_pool_id": "",
    "vendor_audit_evidence_id": "",
    "source_row_id": "",
    "observation_time_series_id": "",
}

_IMA_LOCAL_LOGICAL_TYPES = frozenset(
    {
        TabularLogicalType.DATE,
        TabularLogicalType.TIMESTAMP,
    }
)


def _ensure_explicit_logical_types(*spec_groups: Sequence[ColumnSpec]) -> None:
    unknown = tuple(
        spec.name
        for spec_group in spec_groups
        for spec in spec_group
        if spec.logical_type is TabularLogicalType.UNKNOWN
    )
    if unknown:
        raise RuntimeError("IMA Arrow specs must declare logical_type: " + ", ".join(unknown))


_ensure_explicit_logical_types(
    IMA_INPUT_MANIFEST_ARROW_COLUMN_SPECS,
    IMA_SCENARIO_METADATA_ARROW_COLUMN_SPECS,
    IMA_RFET_OBSERVATION_ARROW_COLUMN_SPECS,
)
