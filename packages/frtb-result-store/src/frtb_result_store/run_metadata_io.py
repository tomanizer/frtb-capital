"""Row codecs for run-scoped input, event, and telemetry metadata."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

from frtb_result_store._row_codecs import (
    float_value as _float_value,
)
from frtb_result_store._row_codecs import (
    int_value as _int_value,
)
from frtb_result_store._row_codecs import (
    json_mapping as _json_mapping,
)
from frtb_result_store._row_codecs import (
    metadata_json as _metadata_json,
)
from frtb_result_store._row_codecs import (
    optional_text as _optional_text,
)
from frtb_result_store._row_codecs import (
    stored_value as _stored_value,
)
from frtb_result_store.artifacts import StagedArtifact
from frtb_result_store.model import (
    InputSnapshotManifest,
    ResultBundle,
    ResultEvent,
    ResultEventSeverity,
    RunTelemetry,
    TelemetryPhase,
)
from frtb_result_store.observability import current_trace_ids

__all__ = [
    "artifact_byte_count",
    "generated_telemetry_rows",
    "input_manifest_from_row",
    "input_manifest_row",
    "result_event_from_row",
    "result_event_row",
    "telemetry_from_row",
    "telemetry_row",
]


def input_manifest_row(manifest: InputSnapshotManifest) -> dict[str, object]:
    return {
        "run_id": manifest.run_id,
        "input_snapshot_id": manifest.input_snapshot_id,
        "input_snapshot_hash": manifest.input_snapshot_hash,
        "as_of_date": manifest.as_of_date.isoformat(),
        "source_system": manifest.source_system,
        "handoff_key": manifest.handoff_key,
        "row_count": manifest.row_count,
        "accepted_row_count": manifest.accepted_row_count,
        "rejected_row_count": manifest.rejected_row_count,
        "source_uri": manifest.source_uri,
        "source_hash": manifest.source_hash,
        "schema_fingerprint": manifest.schema_fingerprint,
        "metadata_json": _metadata_json(manifest.metadata),
    }


def result_event_row(event: ResultEvent) -> dict[str, object]:
    return {
        "event_id": event.event_id,
        "run_id": event.run_id,
        "event_time": event.event_time.isoformat(),
        "severity": _stored_value(event.severity),
        "event_type": _stored_value(event.event_type),
        "message": event.message,
        "component": None if event.component is None else _stored_value(event.component),
        "suggested_status": (
            None if event.suggested_status is None else _stored_value(event.suggested_status)
        ),
        "metadata_json": _metadata_json(event.metadata),
    }


def telemetry_row(telemetry: RunTelemetry) -> dict[str, object]:
    return {
        "run_id": telemetry.run_id,
        "phase": _stored_value(telemetry.phase),
        "duration_ms": telemetry.duration_ms,
        "created_at": telemetry.created_at.isoformat(),
        "trace_id": telemetry.trace_id,
        "span_id": telemetry.span_id,
        "row_count": telemetry.row_count,
        "byte_count": telemetry.byte_count,
        "artifact_id": telemetry.artifact_id,
        "mart_name": telemetry.mart_name,
    }


def generated_telemetry_rows(
    *,
    bundle: ResultBundle,
    artifact_duration_ms: float,
    artifact_count: int,
    artifact_byte_count: int,
    base_duration_ms: float,
    base_row_count: int,
) -> list[dict[str, object]]:
    trace_id, span_id = current_trace_ids()
    created_at = bundle.run.created_at
    rows = [
        RunTelemetry(
            run_id=bundle.run.run_id,
            phase=TelemetryPhase.ARTIFACT_WRITE,
            duration_ms=artifact_duration_ms,
            created_at=created_at,
            trace_id=trace_id,
            span_id=span_id,
            row_count=artifact_count,
            byte_count=artifact_byte_count,
        ),
        RunTelemetry(
            run_id=bundle.run.run_id,
            phase=TelemetryPhase.BASE_TABLE_WRITE,
            duration_ms=base_duration_ms,
            created_at=created_at,
            trace_id=trace_id,
            span_id=span_id,
            row_count=base_row_count,
        ),
        RunTelemetry(
            run_id=bundle.run.run_id,
            phase=TelemetryPhase.MART_GENERATION,
            duration_ms=0.0,
            created_at=created_at,
            trace_id=trace_id,
            span_id=span_id,
            row_count=0,
        ),
        RunTelemetry(
            run_id=bundle.run.run_id,
            phase=TelemetryPhase.CATALOG_REFRESH,
            duration_ms=0.0,
            created_at=created_at,
            trace_id=trace_id,
            span_id=span_id,
        ),
    ]
    return [telemetry_row(row) for row in rows]


def artifact_byte_count(staged_artifacts: Sequence[StagedArtifact]) -> int:
    return sum(
        _metadata_int(artifact.ref.metadata.get("byte_count", 0)) for artifact in staged_artifacts
    )


def input_manifest_from_row(row: Sequence[object]) -> InputSnapshotManifest:
    return InputSnapshotManifest(
        run_id=str(row[0]),
        input_snapshot_id=str(row[1]),
        input_snapshot_hash=str(row[2]),
        as_of_date=date.fromisoformat(str(row[3])),
        source_system=str(row[4]),
        handoff_key=str(row[5]),
        row_count=_int_value(row[6]),
        accepted_row_count=_int_value(row[7]),
        rejected_row_count=_int_value(row[8]),
        source_uri=_optional_text(row[9]),
        source_hash=_optional_text(row[10]),
        schema_fingerprint=_optional_text(row[11]),
        metadata=_json_mapping(row[12]),
    )


def result_event_from_row(row: Sequence[object]) -> ResultEvent:
    return ResultEvent(
        event_id=str(row[0]),
        run_id=str(row[1]),
        event_time=datetime.fromisoformat(str(row[2])),
        severity=ResultEventSeverity(str(row[3])),
        event_type=str(row[4]),
        message=str(row[5]),
        component=_optional_text(row[6]),
        suggested_status=_optional_text(row[7]),
        metadata=_json_mapping(row[8]),
    )


def telemetry_from_row(row: Sequence[object]) -> RunTelemetry:
    return RunTelemetry(
        run_id=str(row[0]),
        phase=TelemetryPhase(str(row[1])),
        duration_ms=_float_value(row[2]),
        created_at=datetime.fromisoformat(str(row[3])),
        trace_id=_optional_text(row[4]),
        span_id=_optional_text(row[5]),
        row_count=None if row[6] is None else _int_value(row[6]),
        byte_count=None if row[7] is None else _int_value(row[7]),
        artifact_id=_optional_text(row[8]),
        mart_name=_optional_text(row[9]),
    )


def _metadata_int(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        return int(value)
    return 0
