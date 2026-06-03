"""DuckDB/Parquet result-store backend."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import time
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast
from urllib.parse import quote, unquote, urlparse

import duckdb
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from frtb_common import AttributionMethod
from frtb_common.hashing import stable_json_dumps, stable_json_hash

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
    json_text_tuple as _json_text_tuple,
)
from frtb_result_store._row_codecs import (
    metadata_json as _metadata_json,
)
from frtb_result_store._row_codecs import (
    optional_float as _optional_float,
)
from frtb_result_store._row_codecs import (
    optional_text as _optional_text,
)
from frtb_result_store._row_codecs import (
    stored_value as _stored_value,
)
from frtb_result_store._version import __version__
from frtb_result_store.artifacts import (
    ArtifactWriteRequest,
    RequiredArtifactExpectation,
    StagedArtifact,
    artifact_expectations_for_requests,
    artifact_schema_for,
    stage_artifact_write,
    validate_artifact_ref_targets,
    validate_required_artifacts,
)
from frtb_result_store.mart_schemas import (
    MART_NAMES,
    MART_SCHEMAS,
    mart_schema_fingerprint,
)
from frtb_result_store.marts import (
    capital_summary_from_row,
    capital_tree_mart_from_row,
    component_breakdown_from_row,
    mart_rows_for_bundle,
    movement_summary_from_row,
)
from frtb_result_store.model import (
    ArtifactRef,
    ArtifactType,
    CalculationRun,
    CapitalAttributionRecord,
    CapitalEdge,
    CapitalMeasure,
    CapitalNode,
    CapitalSummaryRow,
    CapitalTreeMartRow,
    ComponentBreakdownRow,
    EdgeType,
    FrtbComponent,
    HierarchyDefinition,
    HierarchyLevel,
    HierarchyNode,
    InputSnapshotManifest,
    LineageRef,
    MovementResult,
    MovementSummaryRow,
    NodeType,
    ResultBundle,
    ResultEvent,
    ResultEventSeverity,
    ResultStoreContractError,
    RunStatus,
    RunStatusEvent,
    RunTelemetry,
    StorageBackend,
)
from frtb_result_store.observability import current_trace_ids, result_store_span
from frtb_result_store.run_metadata_io import (
    artifact_byte_count as _artifact_byte_count,
)
from frtb_result_store.run_metadata_io import (
    generated_telemetry_rows as _generated_telemetry_rows,
)
from frtb_result_store.run_metadata_io import (
    input_manifest_from_row as _input_manifest_from_row,
)
from frtb_result_store.run_metadata_io import (
    input_manifest_row as _input_manifest_row,
)
from frtb_result_store.run_metadata_io import (
    result_event_from_row as _result_event_from_row,
)
from frtb_result_store.run_metadata_io import (
    result_event_row as _result_event_row,
)
from frtb_result_store.run_metadata_io import (
    telemetry_from_row as _telemetry_from_row,
)
from frtb_result_store.run_metadata_io import (
    telemetry_row as _telemetry_row,
)

__all__ = [
    "DuckDbParquetResultStore",
    "ResultStoreCompatibilityError",
    "ResultStoreConfig",
    "ResultStoreWriteError",
]


RESULT_STORE_SCHEMA_VERSION = 2
_LOGGER = logging.getLogger(__name__)
RUN_TABLE_NAMES = (
    "runs",
    "hierarchy_definitions",
    "hierarchy_nodes",
    "capital_nodes",
    "capital_edges",
    "capital_measures",
    "artifact_refs",
    "artifact_expectations",
    "input_snapshot_manifests",
    "lineage_refs",
    "capital_attributions",
    "movement_results",
    "result_events",
    "run_telemetry",
)
EVENT_TABLE_NAMES = ("run_status_events",)
TABLE_NAMES = RUN_TABLE_NAMES + EVENT_TABLE_NAMES


class ResultStoreWriteError(RuntimeError):
    """Raised when a result bundle cannot be written append-only."""


class ResultStoreCompatibilityError(ResultStoreContractError):
    """Raised when one committed run is incompatible with this reader."""


@dataclass(frozen=True, slots=True)
class ResultStoreConfig:
    """Concrete storage settings for the first result-store backend."""

    root: Path | str
    backend: StorageBackend = StorageBackend.LOCAL_PARQUET
    catalog_filename: str = "catalog.duckdb"
    s3_mock_root: Path | str | None = None
    duckdb_extensions: tuple[str, ...] = ()
    duckdb_install_extensions: bool = False
    duckdb_settings: Mapping[str, str | int | float | bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "backend", StorageBackend(self.backend))
        if not self.catalog_filename:
            raise ResultStoreContractError(
                "catalog_filename must be non-empty text",
                field="catalog_filename",
            )
        if not isinstance(self.duckdb_install_extensions, bool):
            raise ResultStoreContractError(
                "duckdb_install_extensions must be boolean",
                field="duckdb_install_extensions",
            )
        object.__setattr__(
            self,
            "duckdb_extensions",
            tuple(
                _validated_duckdb_name(extension, "duckdb_extensions")
                for extension in self.duckdb_extensions
            ),
        )
        object.__setattr__(
            self,
            "duckdb_settings",
            MappingProxyType(
                {
                    _validated_duckdb_name(name, "duckdb_settings"): value
                    for name, value in self.duckdb_settings.items()
                }
            ),
        )
        if self.backend is StorageBackend.S3_PARQUET:
            object.__setattr__(self, "root", _normalize_s3_uri(self.root))
            if self.s3_mock_root is None:
                raise ResultStoreContractError(
                    "s3_parquet backend requires s3_mock_root for local mock read/write",
                    field="s3_mock_root",
                )
            object.__setattr__(self, "s3_mock_root", Path(self.s3_mock_root))
            return
        if isinstance(self.root, str) and self.root.startswith("s3://"):
            raise ResultStoreContractError(
                "s3:// roots require the s3_parquet backend",
                field="root",
            )
        if not isinstance(self.root, Path):
            object.__setattr__(self, "root", Path(self.root))
        if self.s3_mock_root is not None:
            raise ResultStoreContractError(
                "s3_mock_root is only valid for s3_parquet backend",
                field="s3_mock_root",
            )


class DuckDbParquetResultStore:
    """Append-only Parquet store queried through DuckDB.

    Local mode writes one Parquet file per run per table under ``root/parquet``.
    S3 mode keeps the same logical layout under an ``s3://`` root and uses an
    explicit local mock root for deterministic integration tests. A run is
    visible only after its manifest has been written.
    """

    def __init__(self, config: ResultStoreConfig | Path | str) -> None:
        if isinstance(config, Path):
            config = ResultStoreConfig(root=config)
        elif isinstance(config, str):
            config = ResultStoreConfig(root=config)
        self.config = config
        if self.config.backend is StorageBackend.DUCKLAKE:
            raise ResultStoreContractError(
                f"{self.config.backend.value} backend is reserved for a later implementation",
                field="backend",
            )
        if self.config.backend is StorageBackend.S3_PARQUET:
            root_uri = cast(str, self.config.root)
            self.root_uri = root_uri
            self.root = _s3_mock_physical_root(
                root_uri,
                cast(Path, self.config.s3_mock_root),
            )
        else:
            self.root = cast(Path, self.config.root).resolve()
            self.root_uri = self.root.as_uri()
        self.parquet_root = self.root / "parquet"
        self.artifact_root = self.root / "artifacts"
        self.manifest_root = self.root / "manifests"
        self.catalog_path = self.root / self.config.catalog_filename
        self.root.mkdir(parents=True, exist_ok=True)

    def write_bundle(
        self,
        bundle: ResultBundle,
        *,
        artifact_requests: Sequence[ArtifactWriteRequest] = (),
    ) -> None:
        """Persist one validated run bundle.

        The operation is append-only by ``run_id``. Rewriting the same run is a
        hard error; corrections must be represented by a new calculation run.
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
        self,
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
        self,
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
        self,
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

    def _move_staged_marts(self, run_id: str, staging_dir: Path) -> tuple[Path, ...]:
        moved_paths: list[Path] = []
        for mart_name in MART_NAMES:
            final_path = self._mart_path(mart_name, run_id)
            if final_path.exists():
                raise ResultStoreWriteError(f"mart already exists: {mart_name}/{run_id}")
            self._publish_staged_file(staging_dir / "marts" / f"{mart_name}.parquet", final_path)
            moved_paths.append(final_path)
        return tuple(moved_paths)

    def _refresh_catalog_after_commit(self, span_attributes: Mapping[str, object]) -> None:
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
        self,
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
        self,
        staged_artifacts: Sequence[StagedArtifact],
    ) -> tuple[Path, ...]:
        moved_paths: list[Path] = []
        for artifact in staged_artifacts:
            if artifact.final_path.exists():
                raise ResultStoreWriteError(f"artifact already exists: {artifact.ref.artifact_id}")
            self._publish_staged_file(artifact.staged_path, artifact.final_path)
            moved_paths.append(artifact.final_path)
        return tuple(moved_paths)

    def _publish_staged_file(self, staged_path: Path, final_path: Path) -> None:
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

    def _artifact_uri(self, run_id: str, request: ArtifactWriteRequest) -> str | None:
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
        return self._path_uri(final_path)

    def run_exists(self, run_id: str) -> bool:
        """Return whether a run has already been written."""

        return self._manifest_path(run_id).exists()

    def list_runs(self) -> tuple[CalculationRun, ...]:
        """Return stored calculation runs ordered by business date and run id."""

        rows = self._fetchall(
            "runs",
            """
            SELECT run_id, run_group_id, as_of_date, regime_id, base_currency, input_snapshot_id,
                   calculation_scope, engine_version, code_version,
                   calculation_policy_id, created_at, identity_payload_json,
                   run_group_identity_payload_json, metadata_json
            FROM {table}
            ORDER BY as_of_date, run_id
            """,
        )
        return tuple(_run_from_row(row) for row in rows if self._is_run_compatible(str(row[0])))

    def get_run(self, run_id: str) -> CalculationRun | None:
        """Return a stored run by id, or ``None`` when absent."""

        if not self.run_exists(run_id):
            return None
        rows = self._fetchall(
            "runs",
            """
            SELECT run_id, run_group_id, as_of_date, regime_id, base_currency, input_snapshot_id,
                   calculation_scope, engine_version, code_version,
                   calculation_policy_id, created_at, identity_payload_json,
                   run_group_identity_payload_json, metadata_json
            FROM {table}
            WHERE run_id = ?
            """,
            (run_id,),
        )
        return None if not rows else _run_from_row(rows[0])

    def hierarchy_definition(self, run_id: str) -> HierarchyDefinition | None:
        """Return the hierarchy definition stored with a run, when present."""

        if not self.run_exists(run_id):
            return None
        rows = self._fetchall(
            "hierarchy_definitions",
            """
            SELECT run_id, hierarchy_id, hierarchy_version, hierarchy_name, leaf_level,
                   levels_json, created_at, metadata_json
            FROM {table}
            WHERE run_id = ?
            ORDER BY hierarchy_id, hierarchy_version
            """,
            (run_id,),
        )
        return None if not rows else _hierarchy_definition_from_row(rows[0])

    def hierarchy_nodes(self, run_id: str) -> tuple[HierarchyNode, ...]:
        """Return generated hierarchy nodes stored with a run."""

        if not self.run_exists(run_id):
            return ()
        rows = self._fetchall(
            "hierarchy_nodes",
            """
            SELECT run_id, hierarchy_id, hierarchy_version, hierarchy_node_id,
                   parent_hierarchy_node_id, level_name, level_order, business_key,
                   label, path_json, metadata_json
            FROM {table}
            WHERE run_id = ?
            ORDER BY level_order, hierarchy_node_id
            """,
            (run_id,),
        )
        return tuple(_hierarchy_node_from_row(row) for row in rows)

    def capital_tree(self, run_id: str) -> tuple[CapitalNode, ...]:
        """Return all capital graph nodes for one run from the persisted mart."""

        return tuple(row.to_node() for row in self.capital_tree_mart(run_id))

    def capital_summary(self, run_id: str) -> tuple[CapitalSummaryRow, ...]:
        """Return persisted dashboard summary rows for one run."""

        if not self.run_exists(run_id):
            return ()
        rows = self._fetch_mart(
            "capital_summary",
            """
            SELECT run_id, as_of_date, regime_id, base_currency, lifecycle_status,
                   suggested_status, total_capital, currency, node_count, measure_count,
                   component_count
            FROM {mart}
            WHERE run_id = ?
            ORDER BY run_id
            """,
            (run_id,),
        )
        return tuple(capital_summary_from_row(row) for row in rows)

    def capital_tree_mart(self, run_id: str) -> tuple[CapitalTreeMartRow, ...]:
        """Return persisted flattened capital tree rows for one run."""

        if not self.run_exists(run_id):
            return ()
        rows = self._fetch_mart(
            "capital_tree",
            """
            SELECT run_id, node_id, parent_node_id, depth, node_type, component, label,
                   desk_id, portfolio_id, book_id, risk_class, bucket, issuer_id,
                   counterparty_id, calculation_branch, regulatory_rule_id, sort_key,
                   metadata_json
            FROM {mart}
            WHERE run_id = ?
            ORDER BY depth, sort_key, node_id
            """,
            (run_id,),
        )
        return tuple(capital_tree_mart_from_row(row) for row in rows)

    def component_breakdown(self, run_id: str) -> tuple[ComponentBreakdownRow, ...]:
        """Return persisted component-level dashboard totals for one run."""

        if not self.run_exists(run_id):
            return ()
        rows = self._fetch_mart(
            "component_breakdown",
            """
            SELECT run_id, component, amount, currency, node_count, measure_count
            FROM {mart}
            WHERE run_id = ?
            ORDER BY component
            """,
            (run_id,),
        )
        return tuple(component_breakdown_from_row(row) for row in rows)

    def movement_summary(
        self,
        run_id: str,
        *,
        node_id: str | None = None,
    ) -> tuple[MovementSummaryRow, ...]:
        """Return persisted movement summary rows for one run, optionally by node."""

        if not self.run_exists(run_id):
            return ()
        where_clause = "WHERE run_id = ?"
        parameters: tuple[object, ...] = (run_id,)
        if node_id is not None:
            where_clause += " AND node_id = ?"
            parameters = (run_id, node_id)
        rows = self._fetch_mart(
            "movement_summary",
            f"""
            SELECT run_id, baseline_run_id, movement_id, node_id, movement_type,
                   from_amount, to_amount, delta_amount, base_currency, driver_type,
                   driver_id, attribution_method, artifact_id
            FROM {{mart}}
            {where_clause}
            ORDER BY node_id, movement_type, driver_type, driver_id, movement_id
            """,
            parameters,
        )
        return tuple(movement_summary_from_row(row) for row in rows)

    def top_contributors(self, run_id: str, *, limit: int = 10) -> tuple[dict[str, object], ...]:
        """Return top attribution contributors from the persisted mart."""

        if not self.run_exists(run_id):
            return ()
        limit = max(1, limit)
        columns = _mart_columns("top_contributors")
        rows = self._fetch_mart(
            "top_contributors",
            f"""
            SELECT {", ".join(columns)}
            FROM {{mart}}
            WHERE run_id = ?
            ORDER BY rank
            LIMIT {limit}
            """,
            (run_id,),
        )
        return _dict_rows(columns, rows)

    def mart_rows(self, run_id: str, mart_name: str) -> tuple[dict[str, object], ...]:
        """Return rows from one persisted mart for a committed run."""

        if not self.run_exists(run_id):
            return ()
        columns = _mart_columns(mart_name)
        rows = self._fetch_mart(
            mart_name,
            f"""
            SELECT {", ".join(columns)}
            FROM {{mart}}
            WHERE run_id = ?
            ORDER BY {", ".join(columns[: min(3, len(columns))])}
            """,
            (run_id,),
        )
        return _dict_rows(columns, rows)

    def regime_comparison(self, run_group_id: str) -> tuple[dict[str, object], ...]:
        """Return persisted comparison rows for one run group."""

        columns = _mart_columns("regime_comparison")
        if not self._has_mart_files("regime_comparison"):
            return ()
        rows = self._fetch_custom(
            f"""
            SELECT {", ".join(columns)}
            FROM {self._mart_relation("regime_comparison")}
            WHERE run_group_id = ?
            ORDER BY as_of_date, regime_id, run_id
            """,
            (run_group_id,),
        )
        return _dict_rows(columns, rows)

    def child_nodes(self, run_id: str, parent_node_id: str) -> tuple[CapitalNode, ...]:
        """Return direct child nodes in graph order."""

        if not self.run_exists(run_id):
            return ()
        self._ensure_run_compatible(run_id)
        if not self._has_table_files("capital_nodes") or not self._has_table_files("capital_edges"):
            return ()
        rows = self._fetch_custom(
            """
            SELECT n.run_id, n.node_id, n.node_type, n.component, n.label, n.desk_id,
                   n.portfolio_id, n.book_id, n.risk_class, n.bucket, n.issuer_id,
                   n.counterparty_id, n.calculation_branch, n.regulatory_rule_id,
                   n.sort_key, n.metadata_json
            FROM {nodes} n
            JOIN {edges} e
              ON e.run_id = n.run_id
             AND e.child_node_id = n.node_id
            WHERE e.run_id = ? AND e.parent_node_id = ?
            ORDER BY e.sort_key, n.sort_key, n.node_id
            """.format(
                nodes=self._parquet_relation("capital_nodes"),
                edges=self._parquet_relation("capital_edges"),
            ),
            (run_id, parent_node_id),
        )
        return tuple(_node_from_row(row) for row in rows)

    def edges(self, run_id: str) -> tuple[CapitalEdge, ...]:
        """Return graph edges for one run."""

        if not self.run_exists(run_id):
            return ()
        rows = self._fetchall(
            "capital_edges",
            """
            SELECT run_id, parent_node_id, child_node_id, edge_type,
                   aggregation_weight, sort_key
            FROM {table}
            WHERE run_id = ?
            ORDER BY sort_key, parent_node_id, child_node_id
            """,
            (run_id,),
        )
        return tuple(_edge_from_row(row) for row in rows)

    def measures_for_node(self, run_id: str, node_id: str) -> tuple[CapitalMeasure, ...]:
        """Return scalar measures attached to one node."""

        if not self.run_exists(run_id):
            return ()
        rows = self._fetchall(
            "capital_measures",
            """
            SELECT run_id, node_id, measure_name, amount, currency, unit, scenario,
                   methodology, regulatory_rule_id, citations_json, metadata_json
            FROM {table}
            WHERE run_id = ? AND node_id = ?
            ORDER BY measure_name, scenario NULLS FIRST
            """,
            (run_id, node_id),
        )
        return tuple(_measure_from_row(row) for row in rows)

    def artifact_refs(
        self,
        run_id: str,
        *,
        artifact_type: ArtifactType | str | None = None,
    ) -> tuple[ArtifactRef, ...]:
        """Return large-artifact references for a run."""

        if not self.run_exists(run_id):
            return ()
        if artifact_type is None:
            rows = self._fetchall(
                "artifact_refs",
                """
                SELECT run_id, artifact_id, component, artifact_type, uri, format,
                       row_count, schema_fingerprint, partition_keys_json, metadata_json
                FROM {table}
                WHERE run_id = ?
                ORDER BY artifact_type, artifact_id
                """,
                (run_id,),
            )
        else:
            coerced = ArtifactType(artifact_type).value
            rows = self._fetchall(
                "artifact_refs",
                """
                SELECT run_id, artifact_id, component, artifact_type, uri, format,
                       row_count, schema_fingerprint, partition_keys_json, metadata_json
                FROM {table}
                WHERE run_id = ? AND artifact_type = ?
                ORDER BY artifact_id
                """,
                (run_id, coerced),
            )
        return tuple(_artifact_from_row(row) for row in rows)

    def attributions_for_node(
        self,
        run_id: str,
        node_id: str,
    ) -> tuple[CapitalAttributionRecord, ...]:
        """Return attribution rows attached to one capital node."""

        if not self.run_exists(run_id):
            return ()
        rows = self._fetchall(
            "capital_attributions",
            """
            SELECT run_id, node_id, attribution_id, target_type, target_id, source_id,
                   source_level, method, category, bucket_key, base_amount,
                   marginal_multiplier, contribution, residual, unsupported_reason,
                   artifact_id, metadata_json
            FROM {table}
            WHERE run_id = ? AND node_id = ?
            ORDER BY attribution_id
            """,
            (run_id, node_id),
        )
        return tuple(_attribution_from_row(row) for row in rows)

    def movement_results(
        self,
        run_id: str,
        *,
        baseline_run_id: str | None = None,
        node_id: str | None = None,
    ) -> tuple[MovementResult, ...]:
        """Return official movement result rows attached to one current run."""

        if not self.run_exists(run_id):
            return ()
        filters = ["run_id = ?"]
        parameters: list[object] = [run_id]
        if baseline_run_id is not None:
            filters.append("baseline_run_id = ?")
            parameters.append(baseline_run_id)
        if node_id is not None:
            filters.append("node_id = ?")
            parameters.append(node_id)
        rows = self._fetchall(
            "movement_results",
            f"""
            SELECT run_id, baseline_run_id, movement_id, node_id, movement_type,
                   from_amount, to_amount, delta_amount, base_currency, driver_type,
                   driver_id, explanation, attribution_method, artifact_id, metadata_json
            FROM {{table}}
            WHERE {" AND ".join(filters)}
            ORDER BY node_id, movement_type, driver_type, driver_id, movement_id
            """,
            tuple(parameters),
        )
        return tuple(_movement_from_row(row) for row in rows)

    def lineage_for_result(self, run_id: str, result_id: str) -> tuple[LineageRef, ...]:
        """Return lineage references for a stored result object."""

        if not self.run_exists(run_id):
            return ()
        rows = self._fetchall(
            "lineage_refs",
            """
            SELECT run_id, result_id, source_type, source_id, relationship, source_hash,
                   metadata_json
            FROM {table}
            WHERE run_id = ? AND result_id = ?
            ORDER BY source_type, source_id, relationship
            """,
            (run_id, result_id),
        )
        return tuple(_lineage_from_row(row) for row in rows)

    def input_snapshot_manifests(self, run_id: str) -> tuple[InputSnapshotManifest, ...]:
        """Return compact input snapshot evidence rows for a run."""

        if not self.run_exists(run_id):
            return ()
        rows = self._fetchall(
            "input_snapshot_manifests",
            """
            SELECT run_id, input_snapshot_id, input_snapshot_hash, as_of_date, source_system,
                   handoff_key, row_count, accepted_row_count, rejected_row_count, source_uri,
                   source_hash, schema_fingerprint, metadata_json
            FROM {table}
            WHERE run_id = ?
            ORDER BY input_snapshot_id, handoff_key
            """,
            (run_id,),
        )
        return tuple(_input_manifest_from_row(row) for row in rows)

    def result_events(self, run_id: str) -> tuple[ResultEvent, ...]:
        """Return non-lifecycle result events for one committed run."""

        if not self.run_exists(run_id):
            return ()
        rows = self._fetchall(
            "result_events",
            """
            SELECT event_id, run_id, event_time, severity, event_type, message,
                   component, suggested_status, metadata_json
            FROM {table}
            WHERE run_id = ?
            ORDER BY event_time, event_id
            """,
            (run_id,),
        )
        return tuple(_result_event_from_row(row) for row in rows)

    def suggested_status(self, run_id: str) -> RunStatus | None:
        """Return advisory status from result events without changing lifecycle."""

        if not self.run_exists(run_id):
            return None
        events = self.result_events(run_id)
        if any(event.severity is ResultEventSeverity.ERROR for event in events):
            return RunStatus.REJECTED
        return RunStatus.VALIDATED

    def run_telemetry(self, run_id: str) -> tuple[RunTelemetry, ...]:
        """Return compact persisted telemetry rows for a run."""

        if not self.run_exists(run_id):
            return ()
        rows = self._fetchall(
            "run_telemetry",
            """
            SELECT run_id, phase, duration_ms, created_at, trace_id, span_id,
                   row_count, byte_count, artifact_id, mart_name
            FROM {table}
            WHERE run_id = ?
            ORDER BY created_at, phase, artifact_id NULLS FIRST, mart_name NULLS FIRST
            """,
            (run_id,),
        )
        return tuple(_telemetry_from_row(row) for row in rows)

    def status_history(self, run_id: str) -> tuple[RunStatusEvent, ...]:
        """Return append-only lifecycle events for one committed run."""

        if not self.run_exists(run_id):
            return ()
        rows = self._fetchall(
            "run_status_events",
            """
            SELECT event_id, run_id, from_status, to_status, event_time, actor,
                   reason_code, reason_text, external_evidence_ref
            FROM {table}
            WHERE run_id = ?
            ORDER BY event_time, event_id
            """,
            (run_id,),
        )
        return tuple(_status_event_from_row(row) for row in rows)

    def latest_status_event(self, run_id: str) -> RunStatusEvent | None:
        """Return the latest lifecycle event for a run, or ``None`` when absent."""

        history = self.status_history(run_id)
        return None if not history else history[-1]

    def latest_status(self, run_id: str) -> RunStatus | None:
        """Return the latest lifecycle status for a run, or ``None`` when absent."""

        latest = self.latest_status_event(run_id)
        return None if latest is None else RunStatus(latest.to_status)

    def append_status_event(self, event: RunStatusEvent) -> None:
        """Append a lifecycle status event for an existing committed run."""

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

    def cleanup_orphaned_staging(self, *, run_id: str | None = None) -> tuple[str, ...]:
        """Remove abandoned staging directories that are not committed manifests."""

        staging_root = self.root / "_staging"
        if not staging_root.exists():
            return ()
        if run_id is not None:
            path = staging_root / _safe_run_id(run_id)
            if not path.exists():
                return ()
            shutil.rmtree(path)
            return (run_id,)
        removed: list[str] = []
        for path in sorted(staging_root.iterdir()):
            if not path.is_dir():
                continue
            shutil.rmtree(path)
            if not path.exists():
                removed.append(unquote(path.name))
        return tuple(removed)

    def resolve_run_id_prefix(self, prefix: str) -> str | None:
        """Resolve a unique full run id from a display prefix.

        Ambiguous prefixes fail closed instead of returning an arbitrary run.
        """

        if not prefix:
            raise ResultStoreContractError("run_id prefix must be non-empty", field="prefix")
        matches = tuple(run_id for run_id in self._committed_run_ids() if run_id.startswith(prefix))
        if len(matches) > 1:
            raise ResultStoreContractError(
                f"ambiguous run_id prefix: {prefix}",
                field="prefix",
            )
        return None if not matches else matches[0]

    def refresh_catalog(self) -> None:
        """Create or replace DuckDB views over the Parquet result tables."""

        con = self._connect_catalog()
        try:
            for table_name in TABLE_NAMES:
                if self._has_table_files(table_name):
                    con.execute(
                        f"CREATE OR REPLACE VIEW {_view_name(table_name)} AS "
                        f"SELECT * FROM {self._parquet_relation(table_name)}"
                    )
            for mart_name in MART_NAMES:
                if self._has_mart_files(mart_name):
                    con.execute(
                        f"CREATE OR REPLACE VIEW {_mart_view_name(mart_name)} AS "
                        f"SELECT * FROM {self._mart_relation(mart_name)}"
                    )
        finally:
            con.close()

    def read_only_connection(self) -> Any:
        from frtb_result_store.admin import read_only_connection

        return read_only_connection(self)

    def inspect(self) -> object:
        from frtb_result_store.admin import inspect_store

        return inspect_store(self)

    def validate_store(self) -> object:
        from frtb_result_store.admin import validate_store

        return validate_store(self)

    def export_run(self, run_id: str, output_path: Path | str, *, overwrite: bool = False) -> Any:
        from frtb_result_store.admin import export_run

        return export_run(self, run_id, output_path, overwrite=overwrite)

    def _write_manifest(
        self,
        bundle: ResultBundle,
        rows_by_table: Mapping[str, Sequence[Mapping[str, object]]],
        status_rows: Sequence[Mapping[str, object]],
        mart_rows_by_name: Mapping[str, Sequence[Mapping[str, object]]],
        staging_dir: Path,
    ) -> None:
        manifest_dir = self._manifest_path(bundle.run.run_id).parent
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = self._manifest_path(bundle.run.run_id)
        staged_manifest_path = staging_dir / "manifest" / "run_manifest.json"
        staged_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema_version": RESULT_STORE_SCHEMA_VERSION,
            "result_store_schema_version": RESULT_STORE_SCHEMA_VERSION,
            "writer_version": __version__,
            "backend": self.config.backend.value,
            "root_uri": self.root_uri,
            "paths": {
                "parquet": self._path_uri(self.parquet_root),
                "artifacts": self._path_uri(self.artifact_root),
                "manifests": self._path_uri(self.manifest_root),
            },
            "run_id": bundle.run.run_id,
            "run_group_id": bundle.run.run_group_id,
            "as_of_date": bundle.run.as_of_date.isoformat(),
            "regime_id": bundle.run.regime_id,
            "identity_payload": dict(bundle.run.identity_payload),
            "run_group_identity_payload": dict(bundle.run.run_group_identity_payload),
            "tables": {
                **{table_name: len(rows_by_table[table_name]) for table_name in RUN_TABLE_NAMES},
                "run_status_events": len(status_rows),
            },
            "marts": {mart_name: len(mart_rows_by_name[mart_name]) for mart_name in MART_NAMES},
            "base_table_schema_fingerprints": {
                table_name: _table_schema_fingerprint(table_name)
                for table_name in TABLE_NAMES
                if table_name in _TABLE_SCHEMAS
            },
            "artifact_schema_fingerprints": sorted(
                {
                    str(row["schema_fingerprint"])
                    for row in rows_by_table["artifact_refs"]
                    if row["schema_fingerprint"] is not None
                }
            ),
            "mart_schema_fingerprints": {
                mart_name: mart_schema_fingerprint(mart_name) for mart_name in MART_NAMES
            },
        }
        staged_manifest_path.write_text(
            stable_json_dumps(manifest) + "\n",
            encoding="utf-8",
        )
        if manifest_path.exists():
            raise ResultStoreWriteError(f"run already exists: {bundle.run.run_id}")
        if self.config.backend is StorageBackend.S3_PARQUET:
            self._publish_staged_file(staged_manifest_path, manifest_path)
        else:
            try:
                os.link(staged_manifest_path, manifest_path)
            except FileExistsError as exc:
                raise ResultStoreWriteError(f"run already exists: {bundle.run.run_id}") from exc
        staged_manifest_path.unlink(missing_ok=True)

    def _fetchall(
        self,
        table_name: str,
        sql_template: str,
        parameters: Sequence[object] = (),
    ) -> tuple[tuple[object, ...], ...]:
        if not self._has_table_files(table_name):
            return ()
        if parameters and isinstance(parameters[0], str) and self.run_exists(parameters[0]):
            self._ensure_run_compatible(parameters[0])
        sql = sql_template.format(table=self._parquet_relation(table_name))
        return self._fetch_custom(sql, parameters)

    def _fetch_mart(
        self,
        mart_name: str,
        sql_template: str,
        parameters: Sequence[object] = (),
    ) -> tuple[tuple[object, ...], ...]:
        if not self._has_mart_files(mart_name):
            return ()
        relation = self._mart_relation(mart_name)
        if parameters and isinstance(parameters[0], str):
            run_id = parameters[0]
            if self.run_exists(run_id):
                self._ensure_run_compatible(run_id)
                mart_path = self._mart_path(mart_name, run_id)
                if not mart_path.exists():
                    return ()
                relation = f"read_parquet({_sql_literal(str(mart_path))})"
        sql = sql_template.format(mart=relation)
        return self._fetch_custom(sql, parameters)

    def _ensure_run_compatible(self, run_id: str) -> None:
        errors = self._manifest_compatibility_errors(run_id)
        if errors:
            raise ResultStoreCompatibilityError(
                f"incompatible result-store run {run_id}: {'; '.join(errors)}",
                field="run_id",
            )

    def _is_run_compatible(self, run_id: str) -> bool:
        try:
            return not self._manifest_compatibility_errors(run_id)
        except ResultStoreCompatibilityError:
            return False

    def _manifest_compatibility_errors(self, run_id: str) -> tuple[str, ...]:
        manifest = self._read_manifest(run_id)
        version = manifest.get("result_store_schema_version", manifest.get("schema_version"))
        errors: list[str] = []
        if version != RESULT_STORE_SCHEMA_VERSION:
            errors.append(f"schema version {version!r} != {RESULT_STORE_SCHEMA_VERSION}")
        fingerprints = manifest.get("base_table_schema_fingerprints")
        if not isinstance(fingerprints, dict):
            errors.append("missing base table schema fingerprints")
            return tuple(errors)
        for table_name, fingerprint in fingerprints.items():
            if table_name in _TABLE_SCHEMAS and fingerprint != _table_schema_fingerprint(
                table_name
            ):
                errors.append(f"{table_name} schema fingerprint mismatch")
        mart_fingerprints = manifest.get("mart_schema_fingerprints")
        if not isinstance(mart_fingerprints, dict):
            errors.append("missing mart schema fingerprints")
            return tuple(errors)
        for mart_name, fingerprint in mart_fingerprints.items():
            if mart_name in MART_SCHEMAS and fingerprint != mart_schema_fingerprint(mart_name):
                errors.append(f"{mart_name} mart schema fingerprint mismatch")
        return tuple(errors)

    def _read_manifest(self, run_id: str) -> Mapping[str, object]:
        try:
            manifest_text = self._manifest_path(run_id).read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ResultStoreCompatibilityError(
                f"run manifest not found: {run_id}",
                field="run_id",
            ) from exc
        try:
            loaded = json.loads(manifest_text)
        except json.JSONDecodeError as exc:
            raise ResultStoreCompatibilityError(
                f"malformed run manifest JSON: {exc}",
                field="run_id",
            ) from exc
        if not isinstance(loaded, dict):
            raise ResultStoreCompatibilityError("run manifest must be a JSON object")
        return cast(Mapping[str, object], loaded)

    def _fetch_custom(
        self,
        sql: str,
        parameters: Sequence[object] = (),
    ) -> tuple[tuple[object, ...], ...]:
        con = self._connect_query()
        try:
            raw_rows = con.execute(sql, parameters).fetchall()
            return tuple(tuple(row) for row in raw_rows)
        finally:
            con.close()

    def _connect_catalog(self) -> Any:
        con = duckdb.connect(str(self.catalog_path))
        self._configure_duckdb(con)
        return con

    def _connect_query(self) -> Any:
        con = duckdb.connect()
        self._configure_duckdb(con)
        return con

    def _configure_duckdb(self, con: Any) -> None:
        for extension in self.config.duckdb_extensions:
            if self.config.duckdb_install_extensions:
                con.execute(f"INSTALL {extension}")
            con.execute(f"LOAD {extension}")
        for name, value in self.config.duckdb_settings.items():
            con.execute(f"SET {name} = {_duckdb_literal(value)}")

    def _run_table_path(self, table_name: str, run_id: str) -> Path:
        if table_name not in RUN_TABLE_NAMES:
            raise ResultStoreContractError(f"unknown table: {table_name}", field="table_name")
        return self.parquet_root / table_name / f"{_safe_run_id(run_id)}.parquet"

    def _mart_path(self, mart_name: str, run_id: str) -> Path:
        if mart_name not in MART_NAMES:
            raise ResultStoreContractError(f"unknown mart: {mart_name}", field="mart_name")
        return self.parquet_root / "marts" / mart_name / f"{_safe_run_id(run_id)}.parquet"

    def _status_event_path(self, run_id: str, event_id: str) -> Path:
        return (
            self.parquet_root
            / "run_status_events"
            / _safe_run_id(run_id)
            / f"{_safe_run_id(event_id)}.parquet"
        )

    def _has_table_files(self, table_name: str) -> bool:
        return bool(self._table_files(table_name))

    def _has_mart_files(self, mart_name: str) -> bool:
        return bool(self._mart_files(mart_name))

    def _parquet_relation(self, table_name: str) -> str:
        file_paths = ", ".join(_sql_literal(str(path)) for path in self._table_files(table_name))
        return f"read_parquet([{file_paths}], union_by_name = true)"

    def _mart_relation(self, mart_name: str) -> str:
        file_paths = ", ".join(_sql_literal(str(path)) for path in self._mart_files(mart_name))
        return f"read_parquet([{file_paths}], union_by_name = true)"

    def _manifest_path(self, run_id: str) -> Path:
        return self.manifest_root / _safe_run_id(run_id) / "run_manifest.json"

    def _path_uri(self, path: Path) -> str:
        if self.config.backend is not StorageBackend.S3_PARQUET:
            return path.resolve().as_uri()
        relative = path.relative_to(self.root).as_posix()
        return f"{self.root_uri}/{relative}"

    def _committed_run_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                unquote(path.parent.name) for path in self.manifest_root.glob("*/run_manifest.json")
            )
        )

    def _table_files(self, table_name: str) -> tuple[Path, ...]:
        if table_name not in TABLE_NAMES:
            raise ResultStoreContractError(f"unknown table: {table_name}", field="table_name")
        if table_name == "run_status_events":
            return tuple(
                sorted(
                    path
                    for run_id in self._committed_run_ids()
                    for path in (self.parquet_root / table_name / _safe_run_id(run_id)).glob(
                        "*.parquet"
                    )
                )
            )
        return tuple(
            path
            for run_id in self._committed_run_ids()
            if (path := self._run_table_path(table_name, run_id)).exists()
        )

    def _mart_files(self, mart_name: str) -> tuple[Path, ...]:
        if mart_name not in MART_NAMES:
            raise ResultStoreContractError(f"unknown mart: {mart_name}", field="mart_name")
        return tuple(
            path
            for run_id in self._committed_run_ids()
            if (path := self._mart_path(mart_name, run_id)).exists()
        )

    def _remove_orphaned_run_files(self, run_id: str) -> None:
        for table_name in RUN_TABLE_NAMES:
            self._run_table_path(table_name, run_id).unlink(missing_ok=True)
        shutil.rmtree(
            self.parquet_root / "run_status_events" / _safe_run_id(run_id),
            ignore_errors=True,
        )
        self._remove_orphaned_artifacts(run_id)
        self._remove_orphaned_marts(run_id)

    def _remove_orphaned_artifacts(self, run_id: str) -> None:
        safe_run_id = _artifact_safe_run_id(run_id)
        for path in self.artifact_root.glob(f"artifact_type=*/run_id={safe_run_id}"):
            shutil.rmtree(path, ignore_errors=True)

    def _remove_orphaned_marts(self, run_id: str) -> None:
        for mart_name in MART_NAMES:
            self._mart_path(mart_name, run_id).unlink(missing_ok=True)


def _rows_for_bundle(
    bundle: ResultBundle,
    *,
    artifact_refs: Sequence[ArtifactRef] = (),
    artifact_expectations: Sequence[RequiredArtifactExpectation] = (),
) -> dict[str, list[dict[str, object]]]:
    artifacts = tuple(bundle.artifacts) + tuple(artifact_refs)
    return {
        "runs": [_run_row(bundle.run)],
        "hierarchy_definitions": (
            []
            if bundle.hierarchy_definition is None
            else [_hierarchy_definition_row(bundle.run.run_id, bundle.hierarchy_definition)]
        ),
        "hierarchy_nodes": [
            _hierarchy_node_row(bundle.run.run_id, node) for node in bundle.hierarchy_nodes
        ],
        "capital_nodes": [_node_row(node) for node in bundle.nodes],
        "capital_edges": [_edge_row(edge) for edge in bundle.edges],
        "capital_measures": [_measure_row(measure) for measure in bundle.measures],
        "artifact_refs": [_artifact_row(artifact) for artifact in artifacts],
        "artifact_expectations": [
            _artifact_expectation_row(bundle.run.run_id, expectation)
            for expectation in artifact_expectations
        ],
        "input_snapshot_manifests": [
            _input_manifest_row(manifest) for manifest in bundle.input_manifests
        ],
        "lineage_refs": [_lineage_row(lineage) for lineage in bundle.lineage],
        "capital_attributions": [
            _attribution_row(attribution) for attribution in bundle.attributions
        ],
        "movement_results": [_movement_row(movement) for movement in bundle.movement_results],
        "result_events": [_result_event_row(event) for event in bundle.events],
        "run_telemetry": [_telemetry_row(telemetry) for telemetry in bundle.telemetry],
    }


def _hierarchy_definition_row(
    run_id: str,
    definition: HierarchyDefinition,
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "hierarchy_id": definition.hierarchy_id,
        "hierarchy_version": definition.hierarchy_version,
        "hierarchy_name": definition.hierarchy_name,
        "leaf_level": definition.leaf_level,
        "levels_json": stable_json_dumps(
            [
                {
                    "level_name": level.level_name,
                    "dimension": level.dimension,
                    "level_order": level.level_order,
                }
                for level in definition.levels
            ]
        ),
        "created_at": definition.created_at.isoformat(),
        "metadata_json": _metadata_json(definition.metadata),
    }


def _hierarchy_node_row(run_id: str, node: HierarchyNode) -> dict[str, object]:
    return {
        "run_id": run_id,
        "hierarchy_id": node.hierarchy_id,
        "hierarchy_version": node.hierarchy_version,
        "hierarchy_node_id": node.hierarchy_node_id,
        "parent_hierarchy_node_id": node.parent_hierarchy_node_id,
        "level_name": node.level_name,
        "level_order": node.level_order,
        "business_key": node.business_key,
        "label": node.label,
        "path_json": stable_json_dumps(
            [
                {"level_name": level_name, "business_key": business_key}
                for level_name, business_key in node.path
            ]
        ),
        "metadata_json": _metadata_json(node.metadata),
    }


def _run_row(run: CalculationRun) -> dict[str, object]:
    return {
        "run_id": run.run_id,
        "run_group_id": run.run_group_id,
        "as_of_date": run.as_of_date.isoformat(),
        "regime_id": run.regime_id,
        "base_currency": run.base_currency,
        "input_snapshot_id": run.input_snapshot_id,
        "calculation_scope": run.calculation_scope,
        "engine_version": run.engine_version,
        "code_version": run.code_version,
        "calculation_policy_id": run.calculation_policy_id,
        "created_at": run.created_at.isoformat(),
        "identity_payload_json": _metadata_json(run.identity_payload),
        "run_group_identity_payload_json": _metadata_json(run.run_group_identity_payload),
        "metadata_json": _metadata_json(run.metadata),
    }


def _node_row(node: CapitalNode) -> dict[str, object]:
    return {
        "run_id": node.run_id,
        "node_id": node.node_id,
        "node_type": _stored_value(node.node_type),
        "component": _stored_value(node.component),
        "label": node.label,
        "desk_id": node.desk_id,
        "portfolio_id": node.portfolio_id,
        "book_id": node.book_id,
        "risk_class": node.risk_class,
        "bucket": node.bucket,
        "issuer_id": node.issuer_id,
        "counterparty_id": node.counterparty_id,
        "calculation_branch": node.calculation_branch,
        "regulatory_rule_id": node.regulatory_rule_id,
        "sort_key": node.sort_key,
        "metadata_json": _metadata_json(node.metadata),
    }


def _edge_row(edge: CapitalEdge) -> dict[str, object]:
    return {
        "run_id": edge.run_id,
        "parent_node_id": edge.parent_node_id,
        "child_node_id": edge.child_node_id,
        "edge_type": _stored_value(edge.edge_type),
        "aggregation_weight": edge.aggregation_weight,
        "sort_key": edge.sort_key,
    }


def _measure_row(measure: CapitalMeasure) -> dict[str, object]:
    return {
        "run_id": measure.run_id,
        "node_id": measure.node_id,
        "measure_name": measure.measure_name,
        "amount": measure.amount,
        "currency": measure.currency,
        "unit": measure.unit,
        "scenario": measure.scenario,
        "methodology": measure.methodology,
        "regulatory_rule_id": measure.regulatory_rule_id,
        "citations_json": stable_json_dumps(measure.citations),
        "metadata_json": _metadata_json(measure.metadata),
    }


def _artifact_row(artifact: ArtifactRef) -> dict[str, object]:
    return {
        "run_id": artifact.run_id,
        "artifact_id": artifact.artifact_id,
        "component": _stored_value(artifact.component),
        "artifact_type": _stored_value(artifact.artifact_type),
        "uri": artifact.uri,
        "format": artifact.format,
        "row_count": artifact.row_count,
        "schema_fingerprint": artifact.schema_fingerprint,
        "partition_keys_json": stable_json_dumps(artifact.partition_keys),
        "metadata_json": _metadata_json(artifact.metadata),
    }


def _artifact_expectation_row(
    run_id: str,
    expectation: RequiredArtifactExpectation,
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "component": _stored_value(expectation.component),
        "artifact_type": _stored_value(expectation.artifact_type),
        "trigger_name": expectation.trigger_name,
        "required": expectation.required,
        "reason": expectation.reason,
    }


def _lineage_row(lineage: LineageRef) -> dict[str, object]:
    return {
        "run_id": lineage.run_id,
        "result_id": lineage.result_id,
        "source_type": lineage.source_type,
        "source_id": lineage.source_id,
        "relationship": lineage.relationship,
        "source_hash": lineage.source_hash,
        "metadata_json": _metadata_json(lineage.metadata),
    }


def _attribution_row(attribution: CapitalAttributionRecord) -> dict[str, object]:
    return {
        "run_id": attribution.run_id,
        "node_id": attribution.node_id,
        "attribution_id": attribution.attribution_id,
        "target_type": attribution.target_type,
        "target_id": attribution.target_id,
        "source_id": attribution.source_id,
        "source_level": attribution.source_level,
        "method": _stored_value(attribution.method),
        "category": attribution.category,
        "bucket_key": attribution.bucket_key,
        "base_amount": attribution.base_amount,
        "marginal_multiplier": attribution.marginal_multiplier,
        "contribution": attribution.contribution,
        "residual": attribution.residual,
        "unsupported_reason": attribution.unsupported_reason,
        "artifact_id": attribution.artifact_id,
        "metadata_json": _metadata_json(attribution.metadata),
    }


def _movement_row(movement: MovementResult) -> dict[str, object]:
    return {
        "run_id": movement.run_id,
        "baseline_run_id": movement.baseline_run_id,
        "movement_id": movement.movement_id,
        "node_id": movement.node_id,
        "movement_type": movement.movement_type,
        "from_amount": movement.from_amount,
        "to_amount": movement.to_amount,
        "delta_amount": movement.delta_amount,
        "base_currency": movement.base_currency,
        "driver_type": movement.driver_type,
        "driver_id": movement.driver_id,
        "explanation": movement.explanation,
        "attribution_method": None
        if movement.attribution_method is None
        else _stored_value(movement.attribution_method),
        "artifact_id": movement.artifact_id,
        "metadata_json": _metadata_json(movement.metadata),
    }


def _elapsed_ms(started_at: float) -> float:
    return (time.perf_counter() - started_at) * 1000.0


def _initial_status_event(run: CalculationRun) -> RunStatusEvent:
    return RunStatusEvent.transition(
        run_id=run.run_id,
        from_status=None,
        to_status=RunStatus.CANDIDATE,
        event_time=run.created_at,
        actor="result-store",
        reason_code="RUN_COMMITTED",
        reason_text="Run committed to result store",
    )


def _status_event_row(event: RunStatusEvent) -> dict[str, object]:
    from_status = None if event.from_status is None else cast(RunStatus, event.from_status)
    to_status = cast(RunStatus, event.to_status)
    return {
        "event_id": event.event_id,
        "run_id": event.run_id,
        "from_status": None if from_status is None else from_status.value,
        "to_status": to_status.value,
        "event_time": event.event_time.isoformat(),
        "actor": event.actor,
        "reason_code": event.reason_code,
        "reason_text": event.reason_text,
        "external_evidence_ref": event.external_evidence_ref,
    }


def _run_from_row(row: Sequence[object]) -> CalculationRun:
    return CalculationRun(
        run_id=str(row[0]),
        run_group_id=_optional_text(row[1]),
        as_of_date=date.fromisoformat(str(row[2])),
        regime_id=str(row[3]),
        base_currency=str(row[4]),
        input_snapshot_id=str(row[5]),
        calculation_scope=str(row[6]),
        engine_version=str(row[7]),
        code_version=str(row[8]),
        calculation_policy_id=str(row[9]),
        created_at=datetime.fromisoformat(str(row[10])),
        identity_payload=_json_mapping(row[11]),
        run_group_identity_payload=_json_mapping(row[12]),
        metadata=_json_mapping(row[13]),
    )


def _hierarchy_definition_from_row(row: Sequence[object]) -> HierarchyDefinition:
    return HierarchyDefinition(
        hierarchy_id=str(row[1]),
        hierarchy_version=str(row[2]),
        hierarchy_name=str(row[3]),
        leaf_level=str(row[4]),
        levels=tuple(_hierarchy_level_from_mapping(item) for item in _json_object_list(row[5])),
        created_at=datetime.fromisoformat(str(row[6])),
        metadata=_json_mapping(row[7]),
    )


def _hierarchy_node_from_row(row: Sequence[object]) -> HierarchyNode:
    path = tuple(_hierarchy_path_item_from_mapping(item) for item in _json_object_list(row[9]))
    return HierarchyNode(
        hierarchy_id=str(row[1]),
        hierarchy_version=str(row[2]),
        hierarchy_node_id=str(row[3]),
        parent_hierarchy_node_id=_optional_text(row[4]),
        level_name=str(row[5]),
        level_order=_int_value(row[6]),
        business_key=str(row[7]),
        label=str(row[8]),
        path=path,
        metadata=_json_mapping(row[10]),
    )


def _hierarchy_level_from_mapping(value: Mapping[str, object]) -> HierarchyLevel:
    level_name = _required_mapping_value(value, "level_name", "hierarchy level")
    dimension = _required_mapping_value(value, "dimension", "hierarchy level")
    level_order = _required_mapping_value(value, "level_order", "hierarchy level")
    return HierarchyLevel(
        level_name=str(level_name),
        dimension=str(dimension),
        level_order=_int_value(level_order),
    )


def _hierarchy_path_item_from_mapping(value: Mapping[str, object]) -> tuple[str, str]:
    level_name = _required_mapping_value(value, "level_name", "hierarchy node path")
    business_key = _required_mapping_value(value, "business_key", "hierarchy node path")
    return str(level_name), str(business_key)


def _required_mapping_value(
    value: Mapping[str, object],
    key: str,
    context: str,
) -> object:
    if key not in value:
        raise ResultStoreContractError(f"missing key in {context}: {key}")
    return value[key]


def _node_from_row(row: Sequence[object]) -> CapitalNode:
    return CapitalNode(
        run_id=str(row[0]),
        node_id=str(row[1]),
        node_type=NodeType(str(row[2])),
        component=FrtbComponent(str(row[3])),
        label=str(row[4]),
        desk_id=_optional_text(row[5]),
        portfolio_id=_optional_text(row[6]),
        book_id=_optional_text(row[7]),
        risk_class=_optional_text(row[8]),
        bucket=_optional_text(row[9]),
        issuer_id=_optional_text(row[10]),
        counterparty_id=_optional_text(row[11]),
        calculation_branch=_optional_text(row[12]),
        regulatory_rule_id=_optional_text(row[13]),
        sort_key=_int_value(row[14]),
        metadata=_json_mapping(row[15]),
    )


def _edge_from_row(row: Sequence[object]) -> CapitalEdge:
    return CapitalEdge(
        run_id=str(row[0]),
        parent_node_id=str(row[1]),
        child_node_id=str(row[2]),
        edge_type=EdgeType(str(row[3])),
        aggregation_weight=_float_value(row[4]),
        sort_key=_int_value(row[5]),
    )


def _measure_from_row(row: Sequence[object]) -> CapitalMeasure:
    return CapitalMeasure(
        run_id=str(row[0]),
        node_id=str(row[1]),
        measure_name=str(row[2]),
        amount=_float_value(row[3]),
        currency=str(row[4]),
        unit=str(row[5]),
        scenario=_optional_text(row[6]),
        methodology=_optional_text(row[7]),
        regulatory_rule_id=_optional_text(row[8]),
        citations=_json_text_tuple(row[9]),
        metadata=_json_mapping(row[10]),
    )


def _artifact_from_row(row: Sequence[object]) -> ArtifactRef:
    return ArtifactRef(
        run_id=str(row[0]),
        artifact_id=str(row[1]),
        component=FrtbComponent(str(row[2])),
        artifact_type=ArtifactType(str(row[3])),
        uri=str(row[4]),
        format=str(row[5]),
        row_count=_int_value(row[6]),
        schema_fingerprint=_optional_text(row[7]),
        partition_keys=_json_text_tuple(row[8]),
        metadata=_json_mapping(row[9]),
    )


def _lineage_from_row(row: Sequence[object]) -> LineageRef:
    return LineageRef(
        run_id=str(row[0]),
        result_id=str(row[1]),
        source_type=str(row[2]),
        source_id=str(row[3]),
        relationship=str(row[4]),
        source_hash=_optional_text(row[5]),
        metadata=_json_mapping(row[6]),
    )


def _attribution_from_row(row: Sequence[object]) -> CapitalAttributionRecord:
    return CapitalAttributionRecord(
        run_id=str(row[0]),
        node_id=str(row[1]),
        contribution_id=str(row[2]),
        source_id=str(row[5]),
        source_level=str(row[6]),
        method=AttributionMethod(str(row[7])),
        category=str(row[8]),
        bucket_key=_optional_text(row[9]),
        base_amount=_float_value(row[10]),
        marginal_multiplier=_optional_float(row[11]),
        contribution=_optional_float(row[12]),
        residual=_float_value(row[13]),
        reason=str(row[14]),
        target_type=str(row[3]),
        target_id=str(row[4]),
        unsupported_reason=str(row[14]),
        artifact_id=_optional_text(row[15]),
        metadata=_json_mapping(row[16]),
    )


def _movement_from_row(row: Sequence[object]) -> MovementResult:
    return MovementResult(
        run_id=str(row[0]),
        baseline_run_id=str(row[1]),
        movement_id=str(row[2]),
        node_id=str(row[3]),
        movement_type=str(row[4]),
        from_amount=_float_value(row[5]),
        to_amount=_float_value(row[6]),
        delta_amount=_float_value(row[7]),
        base_currency=str(row[8]),
        driver_type=str(row[9]),
        driver_id=str(row[10]),
        explanation=str(row[11]),
        attribution_method=_optional_text(row[12]),
        artifact_id=_optional_text(row[13]),
        metadata=_json_mapping(row[14]),
    )


def _status_event_from_row(row: Sequence[object]) -> RunStatusEvent:
    from_status_text = _optional_text(row[2])
    return RunStatusEvent(
        event_id=str(row[0]),
        run_id=str(row[1]),
        from_status=None if not from_status_text else RunStatus(from_status_text),
        to_status=RunStatus(str(row[3])),
        event_time=datetime.fromisoformat(str(row[4])),
        actor=str(row[5]),
        reason_code=str(row[6]),
        reason_text=str(row[7]),
        external_evidence_ref=_optional_text(row[8]),
    )


def _json_object_list(value: object) -> tuple[Mapping[str, object], ...]:
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ResultStoreContractError(f"malformed JSON object list: {exc}") from exc
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        raise ResultStoreContractError("JSON field must decode to a list of objects")
    return tuple(parsed)


_DUCKDB_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _normalize_s3_uri(root: Path | str) -> str:
    if not isinstance(root, str):
        raise ResultStoreContractError(
            "s3_parquet root must be an s3:// URI string",
            field="root",
        )
    parsed = urlparse(root)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ResultStoreContractError(
            "s3_parquet root must be an s3://bucket[/prefix] URI",
            field="root",
        )
    if unquote(parsed.netloc) in {".", ".."}:
        raise ResultStoreContractError(
            "s3_parquet root path must not contain relative components",
            field="root",
        )
    if parsed.query or parsed.fragment:
        raise ResultStoreContractError(
            "s3_parquet root must not include query or fragment",
            field="root",
        )
    raw_parts = [part for part in parsed.path.split("/") if part]
    decoded_parts = [unquote(part) for part in raw_parts]
    if any(part in {".", ".."} for part in decoded_parts):
        raise ResultStoreContractError(
            "s3_parquet root path must not contain relative components",
            field="root",
        )
    path = "/".join(raw_parts)
    return f"s3://{parsed.netloc}" + (f"/{path}" if path else "")


def _s3_mock_physical_root(root_uri: str, mock_root: Path) -> Path:
    parsed = urlparse(root_uri)
    path_parts = [unquote(part) for part in parsed.path.split("/") if part]
    return mock_root.resolve().joinpath(parsed.netloc, *path_parts)


def _validated_duckdb_name(value: str, field: str) -> str:
    if not isinstance(value, str) or not _DUCKDB_NAME_RE.fullmatch(value):
        raise ResultStoreContractError(
            f"{field} entries must be DuckDB setting or extension names",
            field=field,
        )
    return value


def _duckdb_literal(value: str | int | float | bool) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, str):
        return _sql_literal(value)
    raise ResultStoreContractError(
        "duckdb setting values must be string, number, or boolean",
        field="duckdb_settings",
    )


def _artifact_id_for_request(
    run_id: str,
    request: ArtifactWriteRequest,
    schema_fingerprint: str,
) -> str:
    artifact_type = ArtifactType(request.artifact_type)
    payload = {
        "run_id": run_id,
        "artifact_id_hint": request.artifact_id_hint,
        "artifact_type": artifact_type.value,
        "schema_fingerprint": schema_fingerprint,
        "partition_values": dict(request.partition_values),
    }
    return f"{artifact_type.value}:{stable_json_hash(payload)}"


def _safe_run_id(run_id: str) -> str:
    return quote(run_id, safe="")


def _artifact_safe_run_id(run_id: str) -> str:
    return _safe_run_id(run_id)


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _view_name(table_name: str) -> str:
    return f"frtb_result_store_{table_name}"


def _mart_view_name(mart_name: str) -> str:
    return f"frtb_result_store_mart_{mart_name}"


def _mart_columns(mart_name: str) -> tuple[str, ...]:
    if mart_name not in MART_SCHEMAS:
        raise ResultStoreContractError(f"unknown mart: {mart_name}", field="mart_name")
    return tuple(MART_SCHEMAS[mart_name].names)


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
