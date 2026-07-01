"""Bundle-level base table row assembly for result-store writes."""

from __future__ import annotations

from collections.abc import Sequence

import frtb_result_store.store_capital_rows as _store_capital_rows
import frtb_result_store.store_hierarchy_rows as _store_hierarchy_rows
from frtb_result_store.artifacts import RequiredArtifactExpectation
from frtb_result_store.model import ArtifactRef, ResultBundle
from frtb_result_store.risk_factor_metadata_rows import (
    _risk_factor_metadata_row,
    _risk_factor_snapshot_row,
    _risk_factor_source_mapping_row,
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


def _rows_for_bundle(
    bundle: ResultBundle,
    *,
    artifact_refs: Sequence[ArtifactRef] = (),
    artifact_expectations: Sequence[RequiredArtifactExpectation] = (),
) -> dict[str, list[dict[str, object]]]:
    artifacts = tuple(bundle.artifacts) + tuple(artifact_refs)
    return {
        "runs": [_store_capital_rows._run_row(bundle.run)],
        "hierarchy_definitions": (
            []
            if bundle.hierarchy_definition is None
            else [
                _store_hierarchy_rows._hierarchy_definition_row(
                    bundle.run.run_id,
                    bundle.hierarchy_definition,
                )
            ]
        ),
        "hierarchy_nodes": [
            _store_hierarchy_rows._hierarchy_node_row(bundle.run.run_id, node)
            for node in bundle.hierarchy_nodes
        ],
        "capital_nodes": [_store_capital_rows._node_row(node) for node in bundle.nodes],
        "capital_edges": [_store_capital_rows._edge_row(edge) for edge in bundle.edges],
        "capital_measures": [
            _store_capital_rows._measure_row(measure) for measure in bundle.measures
        ],
        "artifact_refs": [_store_capital_rows._artifact_row(artifact) for artifact in artifacts],
        "artifact_expectations": [
            _store_capital_rows._artifact_expectation_row(bundle.run.run_id, expectation)
            for expectation in artifact_expectations
        ],
        "input_snapshot_manifests": [
            _input_manifest_row(manifest) for manifest in bundle.input_manifests
        ],
        "lineage_refs": [_store_capital_rows._lineage_row(lineage) for lineage in bundle.lineage],
        "capital_attributions": [
            _store_capital_rows._attribution_row(attribution) for attribution in bundle.attributions
        ],
        "movement_results": [
            _store_capital_rows._movement_row(movement) for movement in bundle.movement_results
        ],
        "risk_factor_metadata_snapshots": [
            _risk_factor_snapshot_row(snapshot) for snapshot in bundle.risk_factor_snapshots
        ],
        "risk_factor_metadata": [
            _risk_factor_metadata_row(record) for record in bundle.risk_factor_metadata
        ],
        "risk_factor_source_mappings": [
            _risk_factor_source_mapping_row(mapping)
            for mapping in bundle.risk_factor_source_mappings
        ],
        "result_events": [_result_event_row(event) for event in bundle.events],
        "run_telemetry": [_telemetry_row(telemetry) for telemetry in bundle.telemetry],
    }


__all__ = ["_rows_for_bundle"]
