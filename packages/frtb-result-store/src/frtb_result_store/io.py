"""DuckDB/Parquet result-store backend."""

from __future__ import annotations

import json
import logging
import os
import shutil
import time
from collections.abc import Mapping, Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote

import duckdb
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from frtb_common.hashing import stable_json_dumps

from frtb_result_store._version import __version__
from frtb_result_store.artifacts import (
    ArtifactWriteRequest,
    StagedArtifact,
    artifact_expectations_for_requests,
    artifact_schema_for,
    stage_artifact_write,
    validate_artifact_ref_targets,
    validate_required_artifacts,
)
from frtb_result_store.mart_schemas import MART_NAMES, MART_SCHEMAS, mart_schema_fingerprint
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
    HierarchyDefinition,
    HierarchyNode,
    InputSnapshotManifest,
    LineageRef,
    MovementResult,
    MovementSummaryRow,
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
    result_event_from_row as _result_event_from_row,
)
from frtb_result_store.run_metadata_io import (
    telemetry_from_row as _telemetry_from_row,
)
from frtb_result_store.store_config import (
    RESULT_STORE_SCHEMA_VERSION,
    RUN_TABLE_NAMES,
    TABLE_NAMES,
    ResultStoreCompatibilityError,
    ResultStoreConfig,
    ResultStoreWriteError,
)
from frtb_result_store.store_paths import (
    _artifact_id_for_request,
    _artifact_safe_run_id,
    _duckdb_literal,
    _mart_columns,
    _mart_view_name,
    _s3_mock_physical_root,
    _safe_run_id,
    _sql_literal,
    _view_name,
)
from frtb_result_store.store_row_io import (
    _artifact_from_row,
    _attribution_from_row,
    _edge_from_row,
    _elapsed_ms,
    _hierarchy_definition_from_row,
    _hierarchy_node_from_row,
    _initial_status_event,
    _lineage_from_row,
    _measure_from_row,
    _movement_from_row,
    _node_from_row,
    _rows_for_bundle,
    _run_from_row,
    _status_event_from_row,
    _status_event_row,
)
from frtb_result_store.store_schemas import (
    _TABLE_SCHEMAS,
    _arrow_table,
    _dict_rows,
    _table_schema_fingerprint,
)

__all__ = [
    "RUN_TABLE_NAMES",
    "TABLE_NAMES",
    "DuckDbParquetResultStore",
    "ResultStoreCompatibilityError",
    "ResultStoreConfig",
    "ResultStoreWriteError",
]

_LOGGER = logging.getLogger(__name__)


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
            LIMIT ?
            """,
            (run_id, limit),
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
