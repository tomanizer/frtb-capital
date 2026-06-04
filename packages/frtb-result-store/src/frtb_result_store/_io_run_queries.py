"""Run, hierarchy, status, event, and telemetry queries."""

from __future__ import annotations

from typing import Any

from frtb_result_store.model import (
    CalculationRun,
    HierarchyDefinition,
    HierarchyNode,
    InputSnapshotManifest,
    ResultEvent,
    ResultEventSeverity,
    RunStatus,
    RunStatusEvent,
    RunTelemetry,
)
from frtb_result_store.run_metadata_io import (
    input_manifest_from_row as _input_manifest_from_row,
)
from frtb_result_store.run_metadata_io import result_event_from_row as _result_event_from_row
from frtb_result_store.run_metadata_io import telemetry_from_row as _telemetry_from_row
from frtb_result_store.store_row_io import (
    _hierarchy_definition_from_row,
    _hierarchy_node_from_row,
    _run_from_row,
    _status_event_from_row,
)


class StoreRunQueryMixin:
    def run_exists(self: Any, run_id: str) -> bool:
        """Return whether a run has already been written."""

        return bool(self._manifest_path(run_id).exists())

    def list_runs(self: Any) -> tuple[CalculationRun, ...]:
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

    def get_run(self: Any, run_id: str) -> CalculationRun | None:
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

    def hierarchy_definition(self: Any, run_id: str) -> HierarchyDefinition | None:
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

    def hierarchy_nodes(self: Any, run_id: str) -> tuple[HierarchyNode, ...]:
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

    def input_snapshot_manifests(self: Any, run_id: str) -> tuple[InputSnapshotManifest, ...]:
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

    def result_events(self: Any, run_id: str) -> tuple[ResultEvent, ...]:
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

    def suggested_status(self: Any, run_id: str) -> RunStatus | None:
        """Return advisory status from result events without changing lifecycle."""

        if not self.run_exists(run_id):
            return None
        events = self.result_events(run_id)
        if any(event.severity is ResultEventSeverity.ERROR for event in events):
            return RunStatus.REJECTED
        return RunStatus.VALIDATED

    def run_telemetry(self: Any, run_id: str) -> tuple[RunTelemetry, ...]:
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

    def status_history(self: Any, run_id: str) -> tuple[RunStatusEvent, ...]:
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

    def latest_status_event(self: Any, run_id: str) -> RunStatusEvent | None:
        """Return the latest lifecycle event for a run, or ``None`` when absent."""

        history = self.status_history(run_id)
        return None if not history else history[-1]

    def latest_status(self: Any, run_id: str) -> RunStatus | None:
        """Return the latest lifecycle status for a run, or ``None`` when absent."""

        latest = self.latest_status_event(run_id)
        return None if latest is None else RunStatus(latest.to_status)
