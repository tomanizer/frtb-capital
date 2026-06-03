"""FRTB result-store contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from frtb_common import CapitalComponentMetadata, ImplementationStatus, ValidationStatus

from frtb_result_store._version import __version__
from frtb_result_store.artifacts import (
    ARTIFACT_SCHEMA_REGISTRY,
    ArtifactSchemaEntry,
    ArtifactWriteRequest,
    RequiredArtifactExpectation,
    artifact_schema_fingerprint,
    artifact_schema_for,
)
from frtb_result_store.capital_graph import (
    build_standard_capital_edges,
    build_standard_capital_graph,
    capital_node_from_spec,
    capital_node_identity_payload,
    generate_capital_node_id,
)
from frtb_result_store.hierarchy import (
    build_hierarchy_nodes,
    default_hierarchy_definition,
    generate_hierarchy_node_id,
)
from frtb_result_store.model import (
    ArtifactRef,
    ArtifactType,
    CalculationRun,
    CapitalAttributionRecord,
    CapitalEdge,
    CapitalMeasure,
    CapitalNode,
    CapitalNodeFamily,
    CapitalNodeSpec,
    EdgeType,
    FrtbComponent,
    HierarchyDefinition,
    HierarchyLevel,
    HierarchyNode,
    InputSnapshotManifest,
    LineageRef,
    NodeType,
    ResultBundle,
    ResultEvent,
    ResultEventSeverity,
    ResultEventType,
    ResultStoreContractError,
    RunStatus,
    RunStatusEvent,
    RunTelemetry,
    StorageBackend,
    TelemetryPhase,
    canonical_run_group_identity_payload,
    canonical_run_identity_payload,
    generate_run_group_id,
    generate_run_id,
)

if TYPE_CHECKING:
    from frtb_result_store.io import (
        DuckDbParquetResultStore,
        ResultStoreCompatibilityError,
        ResultStoreConfig,
        ResultStoreWriteError,
    )

PACKAGE_METADATA = CapitalComponentMetadata(
    package_name="frtb-result-store",
    import_name="frtb_result_store",
    component_name="FRTB result store",
    implementation_status=ImplementationStatus.PARTIAL,
    validation_status=ValidationStatus.PENDING,
)

__all__ = [
    "ARTIFACT_SCHEMA_REGISTRY",
    "PACKAGE_METADATA",
    "ArtifactRef",
    "ArtifactSchemaEntry",
    "ArtifactType",
    "ArtifactWriteRequest",
    "CalculationRun",
    "CapitalAttributionRecord",
    "CapitalEdge",
    "CapitalMeasure",
    "CapitalNode",
    "CapitalNodeFamily",
    "CapitalNodeSpec",
    "DuckDbParquetResultStore",
    "EdgeType",
    "FrtbComponent",
    "HierarchyDefinition",
    "HierarchyLevel",
    "HierarchyNode",
    "InputSnapshotManifest",
    "LineageRef",
    "NodeType",
    "RequiredArtifactExpectation",
    "ResultBundle",
    "ResultEvent",
    "ResultEventSeverity",
    "ResultEventType",
    "ResultStoreCompatibilityError",
    "ResultStoreConfig",
    "ResultStoreContractError",
    "ResultStoreWriteError",
    "RunStatus",
    "RunStatusEvent",
    "RunTelemetry",
    "StorageBackend",
    "TelemetryPhase",
    "__version__",
    "artifact_schema_fingerprint",
    "artifact_schema_for",
    "build_hierarchy_nodes",
    "build_standard_capital_edges",
    "build_standard_capital_graph",
    "canonical_run_group_identity_payload",
    "canonical_run_identity_payload",
    "capital_node_from_spec",
    "capital_node_identity_payload",
    "default_hierarchy_definition",
    "generate_capital_node_id",
    "generate_hierarchy_node_id",
    "generate_run_group_id",
    "generate_run_id",
]

_BACKEND_EXPORTS = frozenset(
    {
        "DuckDbParquetResultStore",
        "ResultStoreCompatibilityError",
        "ResultStoreConfig",
        "ResultStoreWriteError",
    }
)


def __getattr__(name: str) -> object:
    """Lazily expose backend classes without making core import require DuckDB."""

    if name not in _BACKEND_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    exports = _load_backend_exports()
    globals().update(exports)
    return exports[name]


def _load_backend_exports() -> dict[str, object]:
    try:
        from frtb_result_store.io import (
            DuckDbParquetResultStore,
            ResultStoreCompatibilityError,
            ResultStoreConfig,
            ResultStoreWriteError,
        )
    except ModuleNotFoundError as exc:
        if exc.name == "duckdb":
            raise ModuleNotFoundError(
                "DuckDB backend requires the optional 'duckdb' extra; install "
                "frtb-result-store[duckdb] to use DuckDbParquetResultStore."
            ) from exc
        raise
    return {
        "DuckDbParquetResultStore": DuckDbParquetResultStore,
        "ResultStoreCompatibilityError": ResultStoreCompatibilityError,
        "ResultStoreConfig": ResultStoreConfig,
        "ResultStoreWriteError": ResultStoreWriteError,
    }
