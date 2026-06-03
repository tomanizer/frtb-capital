"""DuckDB/Parquet result-store backend."""

from __future__ import annotations

import json
import shutil
from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, cast
from urllib.parse import quote, unquote

import duckdb
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from frtb_common import AttributionMethod
from frtb_common.hashing import stable_json_dumps

from frtb_result_store.artifacts import (
    ArtifactWriteRequest,
    StagedArtifact,
    stage_artifact_write,
)
from frtb_result_store.model import (
    ArtifactRef,
    ArtifactType,
    CalculationRun,
    CapitalAttributionRecord,
    CapitalEdge,
    CapitalMeasure,
    CapitalNode,
    EdgeType,
    FrtbComponent,
    HierarchyDefinition,
    HierarchyLevel,
    HierarchyNode,
    LineageRef,
    NodeType,
    ResultBundle,
    ResultStoreContractError,
    RunStatus,
    RunStatusEvent,
    StorageBackend,
)

__all__ = [
    "DuckDbParquetResultStore",
    "ResultStoreConfig",
    "ResultStoreWriteError",
]


RESULT_STORE_SCHEMA_VERSION = 1
RUN_TABLE_NAMES = (
    "runs",
    "hierarchy_definitions",
    "hierarchy_nodes",
    "capital_nodes",
    "capital_edges",
    "capital_measures",
    "artifact_refs",
    "lineage_refs",
    "capital_attributions",
)
EVENT_TABLE_NAMES = ("run_status_events",)
TABLE_NAMES = RUN_TABLE_NAMES + EVENT_TABLE_NAMES


class ResultStoreWriteError(RuntimeError):
    """Raised when a result bundle cannot be written append-only."""


@dataclass(frozen=True, slots=True)
class ResultStoreConfig:
    """Concrete storage settings for the first result-store backend."""

    root: Path
    backend: StorageBackend = StorageBackend.LOCAL_PARQUET
    catalog_filename: str = "catalog.duckdb"

    def __post_init__(self) -> None:
        object.__setattr__(self, "backend", StorageBackend(self.backend))
        if not isinstance(self.root, Path):
            object.__setattr__(self, "root", Path(self.root))
        if not self.catalog_filename:
            raise ResultStoreContractError(
                "catalog_filename must be non-empty text",
                field="catalog_filename",
            )


class DuckDbParquetResultStore:
    """Append-only local Parquet store queried through DuckDB.

    The executable first slice writes one Parquet file per run per table under
    ``root/parquet``. A run is visible only after its manifest has been written.
    The DuckDB catalog is derived and rebuildable; query methods use independent
    in-memory DuckDB connections over committed Parquet files.
    """

    def __init__(self, config: ResultStoreConfig | Path) -> None:
        if isinstance(config, Path):
            config = ResultStoreConfig(root=config)
        self.config = config
        if self.config.backend is not StorageBackend.LOCAL_PARQUET:
            raise ResultStoreContractError(
                f"{self.config.backend.value} backend is reserved for a later implementation",
                field="backend",
            )
        self.root = self.config.root.resolve()
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
        try:
            staged_artifacts = self._stage_artifact_requests(
                bundle,
                artifact_requests,
                staging_dir,
            )
            rows_by_table = _rows_for_bundle(
                bundle,
                artifact_refs=tuple(artifact.ref for artifact in staged_artifacts),
            )
            for table_name in RUN_TABLE_NAMES:
                table = _arrow_table(rows_by_table[table_name], _TABLE_SCHEMAS[table_name])
                pq.write_table(table, staging_dir / f"{table_name}.parquet")
            pq.write_table(
                _arrow_table(status_rows, _TABLE_SCHEMAS["run_status_events"]),
                staging_dir / "run_status_events.parquet",
            )

            for table_name in RUN_TABLE_NAMES:
                final_path = self._run_table_path(table_name, run_id)
                if final_path.exists():
                    raise ResultStoreWriteError(f"run table already exists: {table_name}/{run_id}")
                final_path.parent.mkdir(parents=True, exist_ok=True)
                (staging_dir / f"{table_name}.parquet").rename(final_path)
                moved_paths.append(final_path)
            status_path = self._status_event_path(run_id, initial_status_event.event_id)
            if status_path.exists():
                raise ResultStoreWriteError(
                    f"status event already exists: {initial_status_event.event_id}"
                )
            status_path.parent.mkdir(parents=True, exist_ok=True)
            (staging_dir / "run_status_events.parquet").rename(status_path)
            moved_paths.append(status_path)
            moved_paths.extend(self._move_staged_artifacts(staged_artifacts))

            self._write_manifest(bundle, rows_by_table, status_rows)
        except Exception:
            for path in moved_paths:
                path.unlink(missing_ok=True)
            shutil.rmtree(
                self.parquet_root / "run_status_events" / safe_run_id,
                ignore_errors=True,
            )
            self._remove_orphaned_artifacts(run_id)
            shutil.rmtree(staging_dir, ignore_errors=True)
            raise
        finally:
            shutil.rmtree(staging_dir, ignore_errors=True)

        # The catalog is derived convenience state. A refresh failure must not
        # turn a fully manifested run into a failed append.
        with suppress(Exception):
            self.refresh_catalog()

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
            artifact.final_path.parent.mkdir(parents=True, exist_ok=True)
            artifact.staged_path.rename(artifact.final_path)
            moved_paths.append(artifact.final_path)
        return tuple(moved_paths)

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
        return tuple(_run_from_row(row) for row in rows)

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
        """Return all capital graph nodes for one run."""

        if not self.run_exists(run_id):
            return ()
        rows = self._fetchall(
            "capital_nodes",
            """
            SELECT run_id, node_id, node_type, component, label, desk_id, portfolio_id,
                   book_id, risk_class, bucket, issuer_id, counterparty_id,
                   calculation_branch, regulatory_rule_id, sort_key, metadata_json
            FROM {table}
            WHERE run_id = ?
            ORDER BY sort_key, node_id
            """,
            (run_id,),
        )
        return tuple(_node_from_row(row) for row in rows)

    def child_nodes(self, run_id: str, parent_node_id: str) -> tuple[CapitalNode, ...]:
        """Return direct child nodes in graph order."""

        if not self.run_exists(run_id):
            return ()
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
            SELECT run_id, node_id, contribution_id, source_id, source_level, category,
                   base_amount, method, bucket_key, marginal_multiplier, contribution,
                   residual, reason, metadata_json
            FROM {table}
            WHERE run_id = ? AND node_id = ?
            ORDER BY contribution_id
            """,
            (run_id, node_id),
        )
        return tuple(_attribution_from_row(row) for row in rows)

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
        finally:
            con.close()

    def _write_manifest(
        self,
        bundle: ResultBundle,
        rows_by_table: Mapping[str, Sequence[Mapping[str, object]]],
        status_rows: Sequence[Mapping[str, object]],
    ) -> None:
        manifest_dir = self._manifest_path(bundle.run.run_id).parent
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = self._manifest_path(bundle.run.run_id)
        temp_manifest_path = manifest_path.with_suffix(".json.tmp")
        manifest = {
            "schema_version": RESULT_STORE_SCHEMA_VERSION,
            "backend": self.config.backend.value,
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
        }
        temp_manifest_path.write_text(
            stable_json_dumps(manifest) + "\n",
            encoding="utf-8",
        )
        temp_manifest_path.replace(manifest_path)

    def _fetchall(
        self,
        table_name: str,
        sql_template: str,
        parameters: Sequence[object] = (),
    ) -> tuple[tuple[object, ...], ...]:
        if not self._has_table_files(table_name):
            return ()
        sql = sql_template.format(table=self._parquet_relation(table_name))
        return self._fetch_custom(sql, parameters)

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
        return duckdb.connect(str(self.catalog_path))

    def _connect_query(self) -> Any:
        return duckdb.connect()

    def _run_table_path(self, table_name: str, run_id: str) -> Path:
        if table_name not in RUN_TABLE_NAMES:
            raise ResultStoreContractError(f"unknown table: {table_name}", field="table_name")
        return self.parquet_root / table_name / f"{_safe_run_id(run_id)}.parquet"

    def _status_event_path(self, run_id: str, event_id: str) -> Path:
        return (
            self.parquet_root
            / "run_status_events"
            / _safe_run_id(run_id)
            / f"{_safe_run_id(event_id)}.parquet"
        )

    def _has_table_files(self, table_name: str) -> bool:
        return bool(self._table_files(table_name))

    def _parquet_relation(self, table_name: str) -> str:
        file_paths = ", ".join(_sql_literal(str(path)) for path in self._table_files(table_name))
        return f"read_parquet([{file_paths}], union_by_name = true)"

    def _manifest_path(self, run_id: str) -> Path:
        return self.manifest_root / _safe_run_id(run_id) / "run_manifest.json"

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

    def _remove_orphaned_run_files(self, run_id: str) -> None:
        for table_name in RUN_TABLE_NAMES:
            self._run_table_path(table_name, run_id).unlink(missing_ok=True)
        shutil.rmtree(
            self.parquet_root / "run_status_events" / _safe_run_id(run_id),
            ignore_errors=True,
        )
        self._remove_orphaned_artifacts(run_id)

    def _remove_orphaned_artifacts(self, run_id: str) -> None:
        safe_run_id = _artifact_safe_run_id(run_id)
        for path in self.artifact_root.glob(f"artifact_type=*/run_id={safe_run_id}"):
            shutil.rmtree(path, ignore_errors=True)


def _rows_for_bundle(
    bundle: ResultBundle,
    *,
    artifact_refs: Sequence[ArtifactRef] = (),
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
        "lineage_refs": [_lineage_row(lineage) for lineage in bundle.lineage],
        "capital_attributions": [
            _attribution_row(attribution) for attribution in bundle.attributions
        ],
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
        "contribution_id": attribution.contribution_id,
        "source_id": attribution.source_id,
        "source_level": attribution.source_level,
        "category": attribution.category,
        "base_amount": attribution.base_amount,
        "method": _stored_value(attribution.method),
        "bucket_key": attribution.bucket_key,
        "marginal_multiplier": attribution.marginal_multiplier,
        "contribution": attribution.contribution,
        "residual": attribution.residual,
        "reason": attribution.reason,
        "metadata_json": _metadata_json(attribution.metadata),
    }


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
        source_id=str(row[3]),
        source_level=str(row[4]),
        category=str(row[5]),
        base_amount=_float_value(row[6]),
        method=AttributionMethod(str(row[7])),
        bucket_key=_optional_text(row[8]),
        marginal_multiplier=_optional_float(row[9]),
        contribution=_optional_float(row[10]),
        residual=_float_value(row[11]),
        reason=str(row[12]),
        metadata=_json_mapping(row[13]),
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


def _metadata_json(metadata: Mapping[str, object]) -> str:
    return str(stable_json_dumps(dict(metadata)))


def _json_mapping(value: object) -> Mapping[str, object]:
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ResultStoreContractError(f"malformed JSON object: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ResultStoreContractError("JSON field must decode to an object")
    return parsed


def _json_text_tuple(value: object) -> tuple[str, ...]:
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ResultStoreContractError(f"malformed JSON text list: {exc}") from exc
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ResultStoreContractError("JSON field must decode to a list of strings")
    return tuple(parsed)


def _json_object_list(value: object) -> tuple[Mapping[str, object], ...]:
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ResultStoreContractError(f"malformed JSON object list: {exc}") from exc
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        raise ResultStoreContractError("JSON field must decode to a list of objects")
    return tuple(parsed)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return _float_value(value)


def _float_value(value: object) -> float:
    if isinstance(value, bool):
        raise ResultStoreContractError("numeric field must not be boolean")
    if isinstance(value, int | float | str):
        try:
            return float(value)
        except ValueError as exc:
            raise ResultStoreContractError(f"invalid numeric value: {value}") from exc
    raise ResultStoreContractError("numeric field must be int, float, or numeric text")


def _int_value(value: object) -> int:
    if isinstance(value, bool):
        raise ResultStoreContractError("integer field must not be boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise ResultStoreContractError(f"invalid integer value: {value}") from exc
    raise ResultStoreContractError("integer field must be int or integer text")


def _stored_value(value: StrEnum | str) -> str:
    if isinstance(value, StrEnum):
        return value.value
    return value


def _safe_run_id(run_id: str) -> str:
    return quote(run_id, safe="")


def _artifact_safe_run_id(run_id: str) -> str:
    return _safe_run_id(run_id)


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _view_name(table_name: str) -> str:
    return f"frtb_result_store_{table_name}"


def _arrow_table(rows: Sequence[Mapping[str, object]], schema: Any) -> Any:
    return pa.Table.from_pylist(list(rows), schema=schema)


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
            ("contribution_id", pa.string()),
            ("source_id", pa.string()),
            ("source_level", pa.string()),
            ("category", pa.string()),
            ("base_amount", pa.float64()),
            ("method", pa.string()),
            ("bucket_key", pa.string()),
            ("marginal_multiplier", pa.float64()),
            ("contribution", pa.float64()),
            ("residual", pa.float64()),
            ("reason", pa.string()),
            ("metadata_json", pa.string()),
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
