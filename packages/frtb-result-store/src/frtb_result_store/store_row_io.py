"""Row serialization and deserialization for result-store tables."""

from __future__ import annotations

import time
from collections.abc import Sequence
from datetime import datetime
from typing import cast

import frtb_result_store.store_capital_rows as _store_capital_rows
import frtb_result_store.store_hierarchy_rows as _store_hierarchy_rows
from frtb_result_store._row_codecs import (
    optional_text as _optional_text,
)
from frtb_result_store.artifacts import RequiredArtifactExpectation
from frtb_result_store.model import (
    ArtifactRef,
    CalculationRun,
    ResultBundle,
    RunStatus,
    RunStatusEvent,
)
from frtb_result_store.run_metadata_io import (
    input_manifest_row as _input_manifest_row,
)
from frtb_result_store.run_metadata_io import (
    result_event_row as _result_event_row,
)
from frtb_result_store.run_metadata_io import (
    telemetry_row as _telemetry_row,
)

_run_row = _store_capital_rows._run_row
_node_row = _store_capital_rows._node_row
_edge_row = _store_capital_rows._edge_row
_measure_row = _store_capital_rows._measure_row
_artifact_row = _store_capital_rows._artifact_row
_artifact_expectation_row = _store_capital_rows._artifact_expectation_row
_lineage_row = _store_capital_rows._lineage_row
_attribution_row = _store_capital_rows._attribution_row
_movement_row = _store_capital_rows._movement_row
_run_from_row = _store_capital_rows._run_from_row
_node_from_row = _store_capital_rows._node_from_row
_edge_from_row = _store_capital_rows._edge_from_row
_measure_from_row = _store_capital_rows._measure_from_row
_artifact_from_row = _store_capital_rows._artifact_from_row
_lineage_from_row = _store_capital_rows._lineage_from_row
_attribution_from_row = _store_capital_rows._attribution_from_row
_movement_from_row = _store_capital_rows._movement_from_row
_hierarchy_definition_from_row = _store_hierarchy_rows._hierarchy_definition_from_row
_hierarchy_definition_row = _store_hierarchy_rows._hierarchy_definition_row
_hierarchy_level_from_mapping = _store_hierarchy_rows._hierarchy_level_from_mapping
_hierarchy_node_from_row = _store_hierarchy_rows._hierarchy_node_from_row
_hierarchy_node_row = _store_hierarchy_rows._hierarchy_node_row
_hierarchy_path_item_from_mapping = _store_hierarchy_rows._hierarchy_path_item_from_mapping
_json_object_list = _store_hierarchy_rows._json_object_list


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
