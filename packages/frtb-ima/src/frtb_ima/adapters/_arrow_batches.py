"""Batch builders for normalized IMA Arrow handoff tables."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime

from frtb_common import NormalizedArrowTable, normalized_arrow_table_hash

from frtb_ima.adapters._arrow_columns import (
    _date_column,
    _ima_batch_column_kwargs,
    _read_ima_arrow_columns,
    _timestamp_column,
)
from frtb_ima.adapters._arrow_manifest import (
    _artifact_lineages_from_table,
    _manifest_as_of_date,
    _manifest_run_id,
)
from frtb_ima.adapters._arrow_specs import (
    _IMA_RFET_OBSERVATION_BATCH_COLUMN_ARGS,
    _IMA_RFET_OBSERVATION_DEFAULTS,
    _IMA_SCENARIO_METADATA_BATCH_COLUMN_ARGS,
    _IMA_SCENARIO_METADATA_DEFAULTS,
    IMA_INPUT_MANIFEST_ARROW_COLUMN_SPECS,
    IMA_RFET_OBSERVATION_ARROW_COLUMN_SPECS,
    IMA_SCENARIO_METADATA_ARROW_COLUMN_SPECS,
)
from frtb_ima.input_manifest import CapitalRunInputManifest
from frtb_ima.rfet_evidence import RFETObservationBatch
from frtb_ima.scenario import ScenarioMetadataBatch


def build_scenario_metadata_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> ScenarioMetadataBatch:
    """Build a columnar IMA scenario metadata batch from a normalized Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        Handoff.

    Returns
    -------
    ScenarioMetadataBatch
        Result of the operation.
    """

    if not isinstance(handoff, NormalizedArrowTable):
        raise ValueError("handoff must be NormalizedArrowTable")
    table = handoff.accepted
    columns = _read_ima_arrow_columns(table, IMA_SCENARIO_METADATA_ARROW_COLUMN_SPECS)
    return ScenarioMetadataBatch(
        scenario_dates=_date_column(table, "scenario_date"),
        **_ima_batch_column_kwargs(
            columns,
            _IMA_SCENARIO_METADATA_BATCH_COLUMN_ARGS,
            row_count=table.num_rows,
            defaults=_IMA_SCENARIO_METADATA_DEFAULTS,
        ),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_arrow_table_hash(handoff),
    )


def build_rfet_observation_batch_from_arrow(
    handoff: NormalizedArrowTable,
) -> RFETObservationBatch:
    """Build a columnar RFET observation batch from a normalized Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        Handoff.

    Returns
    -------
    RFETObservationBatch
        Result of the operation.
    """

    if not isinstance(handoff, NormalizedArrowTable):
        raise ValueError("handoff must be NormalizedArrowTable")
    table = handoff.accepted
    columns = _read_ima_arrow_columns(table, IMA_RFET_OBSERVATION_ARROW_COLUMN_SPECS)
    return RFETObservationBatch(
        observation_dates=_date_column(table, "observation_date"),
        observation_timestamps=_timestamp_column(table, "observation_timestamp"),
        **_ima_batch_column_kwargs(
            columns,
            _IMA_RFET_OBSERVATION_BATCH_COLUMN_ARGS,
            row_count=table.num_rows,
            defaults=_IMA_RFET_OBSERVATION_DEFAULTS,
        ),
        source_hash=handoff.source_hash,
        handoff_hash=normalized_arrow_table_hash(handoff),
    )


def build_capital_run_input_manifest_from_arrow(
    handoff: NormalizedArrowTable,
    *,
    run_id: str | None = None,
    as_of_date: date | datetime | str | None = None,
    schema_version: str | None = None,
    metadata: Mapping[str, str] | None = None,
) -> CapitalRunInputManifest:
    """Build an IMA capital-run input manifest from a normalized Arrow table.
    Parameters
    ----------
    handoff : NormalizedArrowTable
        Handoff.
    run_id : str | None, optional
        Run id.
    as_of_date : date | datetime | str | None, optional
        As of date.
    schema_version : str | None, optional
        Schema version.
    metadata : Mapping[str, str] | None, optional
        Metadata.

    Returns
    -------
    CapitalRunInputManifest
        Result of the operation.
    """

    if not isinstance(handoff, NormalizedArrowTable):
        raise ValueError("handoff must be NormalizedArrowTable")
    table = handoff.accepted
    columns = _read_ima_arrow_columns(table, IMA_INPUT_MANIFEST_ARROW_COLUMN_SPECS)

    artifacts = _artifact_lineages_from_table(table, columns)
    manifest_as_of = _manifest_as_of_date(
        as_of_date,
        metadata_value=handoff.metadata.get("as_of_date"),
        artifacts=artifacts,
    )
    manifest_metadata = {
        key: value
        for key, value in handoff.metadata.items()
        if key not in {"run_id", "as_of_date", "manifest_schema_version"}
    }
    if handoff.source_hash is not None:
        manifest_metadata["source_hash"] = handoff.source_hash
    if metadata is not None:
        manifest_metadata.update(metadata)

    manifest_schema_version = schema_version or handoff.metadata.get("manifest_schema_version")
    if manifest_schema_version is None:
        return CapitalRunInputManifest(
            run_id=_manifest_run_id(run_id, handoff.metadata.get("run_id")),
            as_of_date=manifest_as_of,
            artifacts=tuple(sorted(artifacts, key=lambda artifact: artifact.artifact_name)),
            metadata=manifest_metadata,
        )

    return CapitalRunInputManifest(
        run_id=_manifest_run_id(run_id, handoff.metadata.get("run_id")),
        as_of_date=manifest_as_of,
        artifacts=tuple(sorted(artifacts, key=lambda artifact: artifact.artifact_name)),
        metadata=manifest_metadata,
        schema_version=manifest_schema_version,
    )
