"""Complete append-only result bundle dataclass."""

from __future__ import annotations

from dataclasses import dataclass

from frtb_result_store._model_capital_records import (
    ArtifactRef,
    CapitalAttributionRecord,
    CapitalEdge,
    CapitalMeasure,
    CapitalNode,
    LineageRef,
    MovementResult,
)
from frtb_result_store._model_hierarchy import HierarchyDefinition, HierarchyNode
from frtb_result_store._model_risk_factor_metadata import (
    RiskFactorMetadataRecord,
    RiskFactorMetadataSnapshot,
    RiskFactorSourceMapping,
)
from frtb_result_store._model_run_records import (
    CalculationRun,
    InputSnapshotManifest,
    ResultEvent,
    RunTelemetry,
)
from frtb_result_store.model_enums import ResultStoreContractError
from frtb_result_store.model_validation import (
    _duplicate_values,
    _require_non_empty_tuple,
    _require_run_id,
    _tuple_bundle_sequences,
    _validate_bundle_attributions,
    _validate_bundle_edges,
    _validate_bundle_hierarchy,
    _validate_bundle_lineage,
    _validate_bundle_measures,
    _validate_bundle_movements,
    _validate_bundle_risk_factor_metadata,
)


@dataclass(frozen=True, slots=True)
class ResultBundle:
    """Complete append-only payload for one FRTB result-store run."""

    run: CalculationRun
    nodes: tuple[CapitalNode, ...]
    hierarchy_definition: HierarchyDefinition | None = None
    hierarchy_nodes: tuple[HierarchyNode, ...] = ()
    edges: tuple[CapitalEdge, ...] = ()
    measures: tuple[CapitalMeasure, ...] = ()
    artifacts: tuple[ArtifactRef, ...] = ()
    input_manifests: tuple[InputSnapshotManifest, ...] = ()
    lineage: tuple[LineageRef, ...] = ()
    attributions: tuple[CapitalAttributionRecord, ...] = ()
    movement_results: tuple[MovementResult, ...] = ()
    risk_factor_snapshots: tuple[RiskFactorMetadataSnapshot, ...] = ()
    risk_factor_metadata: tuple[RiskFactorMetadataRecord, ...] = ()
    risk_factor_source_mappings: tuple[RiskFactorSourceMapping, ...] = ()
    events: tuple[ResultEvent, ...] = ()
    telemetry: tuple[RunTelemetry, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.run, CalculationRun):
            raise ResultStoreContractError("run must be a CalculationRun", field="run")
        _require_non_empty_tuple(self.nodes, "nodes")
        _tuple_bundle_sequences(self)
        _validate_bundle_hierarchy(self)
        run_id = self.run.run_id
        node_ids = [node.node_id for node in self.nodes]
        duplicate_nodes = _duplicate_values(node_ids)
        if duplicate_nodes:
            raise ResultStoreContractError(
                f"duplicate node ids: {', '.join(duplicate_nodes)}",
                field="nodes",
            )
        hierarchy_node_ids = [node.hierarchy_node_id for node in self.hierarchy_nodes]
        duplicate_hierarchy_node_ids = _duplicate_values(hierarchy_node_ids)
        if duplicate_hierarchy_node_ids:
            raise ResultStoreContractError(
                f"duplicate hierarchy node ids: {', '.join(duplicate_hierarchy_node_ids)}",
                field="hierarchy_nodes",
            )
        known_nodes = set(node_ids) | set(hierarchy_node_ids)
        known_results = known_nodes | {artifact.artifact_id for artifact in self.artifacts}
        for node in self.nodes:
            _require_run_id(node.run_id, run_id, "nodes")
        _validate_bundle_edges(self.edges, run_id, known_nodes)
        _validate_bundle_measures(self.measures, run_id, known_nodes)
        for artifact in self.artifacts:
            _require_run_id(artifact.run_id, run_id, "artifacts")
        for manifest in self.input_manifests:
            _require_run_id(manifest.run_id, run_id, "input_manifests")
        _validate_bundle_lineage(self.lineage, run_id, known_results)
        _validate_bundle_attributions(self.attributions, run_id, known_nodes)
        _validate_bundle_movements(self.movement_results, run_id, known_nodes)
        _validate_bundle_risk_factor_metadata(self)
        for event in self.events:
            _require_run_id(event.run_id, run_id, "events")
        for telemetry in self.telemetry:
            _require_run_id(telemetry.run_id, run_id, "telemetry")
