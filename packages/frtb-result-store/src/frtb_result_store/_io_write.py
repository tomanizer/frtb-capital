"""Write-path helpers for the DuckDB/Parquet result store."""

from __future__ import annotations

import logging
import shutil
import time
from collections.abc import Mapping, Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any, cast

import pyarrow.parquet as pq  # type: ignore[import-untyped]

from frtb_result_store.artifacts import (
    ArtifactWriteRequest,
    StagedArtifact,
    artifact_expectations_for_requests,
    artifact_schema_for,
    stage_artifact_write,
    validate_artifact_ref_targets,
    validate_required_artifacts,
)
from frtb_result_store.mart_schemas import MART_NAMES, MART_SCHEMAS
from frtb_result_store.marts import mart_rows_for_bundle
from frtb_result_store.model import (
    ArtifactRef,
    ArtifactType,
    ResultBundle,
    RunStatus,
    RunStatusEvent,
    StorageBackend,
)
from frtb_result_store.observability import current_trace_ids, result_store_span
from frtb_result_store.run_metadata_io import (
    artifact_byte_count as _artifact_byte_count,
)
from frtb_result_store.run_metadata_io import (
    generated_telemetry_rows as _generated_telemetry_rows,
)
from frtb_result_store.store_config import RUN_TABLE_NAMES, ResultStoreWriteError
from frtb_result_store.store_paths import _artifact_id_for_request, _safe_run_id
from frtb_result_store.store_row_io import _rows_for_bundle
from frtb_result_store.store_schemas import _TABLE_SCHEMAS, _arrow_table
from frtb_result_store.store_status_rows import (
    _elapsed_ms,
    _initial_status_event,
    _status_event_row,
)

_LOGGER = logging.getLogger(__name__)


class StoreWriteMixin:
    def write_bundle(
        self: Any,
        bundle: ResultBundle,
        *,
        artifact_requests: Sequence[ArtifactWriteRequest] = (),
    ) -> None:
        """Persist one validated run bundle.

        The operation is append-only by ``run_id``. Rewriting the same run is a
        hard error; corrections must be represented by a new calculation run.
        Parameters
        ----------
        bundle : ResultBundle
            Bundle.
        artifact_requests : Sequence[ArtifactWriteRequest], optional
            Artifact requests.
        """

        run_id = bundle.run.run_id
        if self.run_exists(run_id):
            raise ResultStoreWriteError(f"run already exists: {bundle.run.run_id}")

        initial_status_event = _initial_status_event(bundle.run)
        status_rows = [_status_event_row(initial_status_event)]
        safe_run_id = _safe_run_id(run_id)
        staging_dir = self.root / "_staging" / safe_run_id
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        self._remove_orphaned_run_files(run_id)
        staging_dir.mkdir(parents=True)

        moved_paths: list[Path] = []
        staged_artifacts: tuple[StagedArtifact, ...] = ()
        span_attributes = {
            "frtb.run_id": run_id,
            "frtb.regime_id": bundle.run.regime_id,
            "frtb.as_of_date": bundle.run.as_of_date.isoformat(),
        }
        try:
            with result_store_span("frtb_result_store.write_bundle", span_attributes):
                rows_by_table, staged_artifacts, committed_artifacts = self._write_staged_tables(
                    bundle,
                    artifact_requests,
                    staging_dir,
                )
            pq.write_table(
                _arrow_table(status_rows, _TABLE_SCHEMAS["run_status_events"]),
                staging_dir / "run_status_events.parquet",
            )
            mart_rows_by_name = self._write_staged_marts(
                bundle,
                lifecycle_status=RunStatus(initial_status_event.to_status),
                staging_dir=staging_dir,
            )

            moved_paths.extend(
                self._move_staged_run_tables(run_id, initial_status_event.event_id, staging_dir)
            )
            moved_paths.extend(self._move_staged_marts(run_id, staging_dir))
            moved_paths.extend(self._move_staged_artifacts(staged_artifacts))
            validate_artifact_ref_targets(committed_artifacts)

            self._write_manifest(
                bundle,
                rows_by_table,
                status_rows,
                mart_rows_by_name,
                staging_dir,
            )
        except Exception:
            for path in moved_paths:
                path.unlink(missing_ok=True)
            shutil.rmtree(
                self.parquet_root / "run_status_events" / safe_run_id,
                ignore_errors=True,
            )
            self._remove_orphaned_artifacts(run_id)
            self._remove_orphaned_marts(run_id)
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)

        # The catalog is derived convenience state. A refresh failure must not
        # turn a fully manifested run into a failed append.
        self._refresh_catalog_after_commit(span_attributes)

    def _write_staged_tables(
        self: Any,
        bundle: ResultBundle,
        artifact_requests: Sequence[ArtifactWriteRequest],
        staging_dir: Path,
    ) -> tuple[
        dict[str, list[dict[str, object]]],
        tuple[StagedArtifact, ...],
        tuple[ArtifactRef, ...],
    ]:
        artifact_started = time.perf_counter()
        staged_artifacts = self._stage_artifact_requests(
            bundle,
            artifact_requests,
            staging_dir,
        )
        artifact_duration_ms = _elapsed_ms(artifact_started)
        artifact_expectations = artifact_expectations_for_requests(artifact_requests)
        generated_artifacts = tuple(artifact.ref for artifact in staged_artifacts)
        committed_artifacts = tuple(bundle.artifacts) + generated_artifacts
        validate_required_artifacts(bundle.nodes, committed_artifacts, artifact_expectations)
        rows_by_table = _rows_for_bundle(
            bundle,
            artifact_refs=generated_artifacts,
            artifact_expectations=artifact_expectations,
        )
        base_started = time.perf_counter()
        for table_name in RUN_TABLE_NAMES:
            if table_name == "run_telemetry":
                continue
            table = _arrow_table(rows_by_table[table_name], _TABLE_SCHEMAS[table_name])
            pq.write_table(table, staging_dir / f"{table_name}.parquet")
        rows_by_table["run_telemetry"].extend(
            _generated_telemetry_rows(
                bundle=bundle,
                artifact_duration_ms=artifact_duration_ms,
                artifact_count=len(staged_artifacts),
                artifact_byte_count=_artifact_byte_count(staged_artifacts),
                base_duration_ms=_elapsed_ms(base_started),
                base_row_count=sum(
                    len(rows)
                    for table_name, rows in rows_by_table.items()
                    if table_name != "run_telemetry"
                ),
            )
        )
        pq.write_table(
            _arrow_table(rows_by_table["run_telemetry"], _TABLE_SCHEMAS["run_telemetry"]),
            staging_dir / "run_telemetry.parquet",
        )
        return rows_by_table, staged_artifacts, committed_artifacts

    def _write_staged_marts(
        self: Any,
        bundle: ResultBundle,
        *,
        lifecycle_status: RunStatus,
        staging_dir: Path,
    ) -> dict[str, list[dict[str, object]]]:
        mart_rows_by_name = mart_rows_for_bundle(bundle, lifecycle_status=lifecycle_status)
        mart_staging_dir = staging_dir / "marts"
        mart_staging_dir.mkdir(parents=True, exist_ok=True)
        for mart_name in MART_NAMES:
            pq.write_table(
                _arrow_table(mart_rows_by_name[mart_name], MART_SCHEMAS[mart_name]),
                mart_staging_dir / f"{mart_name}.parquet",
            )
        return mart_rows_by_name

    def _move_staged_run_tables(
        self: Any,
        run_id: str,
        status_event_id: str,
        staging_dir: Path,
    ) -> tuple[Path, ...]:
        moved_paths: list[Path] = []
        for table_name in RUN_TABLE_NAMES:
            final_path = self._run_table_path(table_name, run_id)
            if final_path.exists():
                raise ResultStoreWriteError(f"run table already exists: {table_name}/{run_id}")
            self._publish_staged_file(staging_dir / f"{table_name}.parquet", final_path)
            moved_paths.append(final_path)
        status_path = self._status_event_path(run_id, status_event_id)
        if status_path.exists():
            raise ResultStoreWriteError(f"status event already exists: {status_event_id}")
        self._publish_staged_file(staging_dir / "run_status_events.parquet", status_path)
        moved_paths.append(status_path)
        return tuple(moved_paths)

    def _move_staged_marts(self: Any, run_id: str, staging_dir: Path) -> tuple[Path, ...]:
        moved_paths: list[Path] = []
        for mart_name in MART_NAMES:
            final_path = self._mart_path(mart_name, run_id)
            if final_path.exists():
                raise ResultStoreWriteError(f"mart already exists: {mart_name}/{run_id}")
            self._publish_staged_file(staging_dir / "marts" / f"{mart_name}.parquet", final_path)
            moved_paths.append(final_path)
        return tuple(moved_paths)

    def _refresh_catalog_after_commit(self: Any, span_attributes: Mapping[str, object]) -> None:
        with result_store_span("frtb_result_store.refresh_catalog", span_attributes):
            try:
                self.refresh_catalog()
            except Exception:
                trace_id, span_id = current_trace_ids()
                _LOGGER.warning(
                    "result-store catalog refresh failed after committed run",
                    extra={"trace_id": trace_id, "span_id": span_id},
                    exc_info=True,
                )

    def _stage_artifact_requests(
        self: Any,
        bundle: ResultBundle,
        artifact_requests: Sequence[ArtifactWriteRequest],
        staging_dir: Path,
    ) -> tuple[StagedArtifact, ...]:
        return tuple(
            stage_artifact_write(
                run=bundle.run,
                request=request,
                staging_dir=staging_dir,
                final_root=self.artifact_root,
                final_uri=self._artifact_uri(bundle.run.run_id, request),
            )
            for request in artifact_requests
        )

    def _move_staged_artifacts(
        self: Any,
        staged_artifacts: Sequence[StagedArtifact],
    ) -> tuple[Path, ...]:
        moved_paths: list[Path] = []
        for artifact in staged_artifacts:
            if artifact.final_path.exists():
                raise ResultStoreWriteError(f"artifact already exists: {artifact.ref.artifact_id}")
            self._publish_staged_file(artifact.staged_path, artifact.final_path)
            moved_paths.append(artifact.final_path)
        return tuple(moved_paths)

    def _publish_staged_file(self: Any, staged_path: Path, final_path: Path) -> None:
        final_path.parent.mkdir(parents=True, exist_ok=True)
        if self.config.backend is StorageBackend.S3_PARQUET:
            try:
                shutil.copy2(staged_path, final_path)
                staged_path.unlink()
            except Exception:
                final_path.unlink(missing_ok=True)
                raise
            return
        staged_path.rename(final_path)

    def _artifact_uri(self: Any, run_id: str, request: ArtifactWriteRequest) -> str | None:
        if self.config.backend is not StorageBackend.S3_PARQUET:
            return None
        entry = artifact_schema_for(request.schema_id)
        artifact_id = _artifact_id_for_request(run_id, request, entry.schema_fingerprint)
        final_path = (
            self.artifact_root
            / f"artifact_type={ArtifactType(request.artifact_type).value}"
            / f"run_id={_safe_run_id(run_id)}"
            / f"artifact_id={_safe_run_id(artifact_id)}"
            / "data.parquet"
        )
        return cast(str | None, self._path_uri(final_path))

    def append_status_event(self: Any, event: RunStatusEvent) -> None:
        """Append a lifecycle status event for an existing committed run.
        Parameters
        ----------
        event : RunStatusEvent
            Event.
        """

        if not self.run_exists(event.run_id):
            raise ResultStoreWriteError(f"run does not exist: {event.run_id}")
        event_path = self._status_event_path(event.run_id, event.event_id)
        if event_path.exists():
            raise ResultStoreWriteError(f"status event already exists: {event.event_id}")
        latest_status = self.latest_status(event.run_id)
        if event.from_status != latest_status:
            raise ResultStoreWriteError(
                f"status transition expected from {latest_status}, got {event.from_status}"
            )
        event_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = event_path.with_suffix(".parquet.tmp")
        pq.write_table(
            _arrow_table([_status_event_row(event)], _TABLE_SCHEMAS["run_status_events"]),
            temp_path,
        )
        temp_path.replace(event_path)

        with suppress(Exception):
            self.refresh_catalog()
