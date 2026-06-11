"""Compatibility exports for result-store table row helpers."""

from __future__ import annotations

from collections.abc import Sequence

import frtb_result_store.store_capital_rows as _store_capital_rows
import frtb_result_store.store_hierarchy_rows as _store_hierarchy_rows
import frtb_result_store.store_status_rows as _store_status_rows
from frtb_result_store.artifacts import RequiredArtifactExpectation
from frtb_result_store.model import ArtifactRef, ResultBundle
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
_elapsed_ms = _store_status_rows._elapsed_ms
_initial_status_event = _store_status_rows._initial_status_event
_status_event_from_row = _store_status_rows._status_event_from_row
_status_event_row = _store_status_rows._status_event_row


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
