"""FRTB result-store contracts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from frtb_common import CapitalComponentMetadata, ImplementationStatus, ValidationStatus

from frtb_result_store._version import __version__
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
    LineageRef,
    NodeType,
    ResultBundle,
    ResultStoreContractError,
    StorageBackend,
)

if TYPE_CHECKING:
    from frtb_result_store.io import (
        DuckDbParquetResultStore,
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
    "PACKAGE_METADATA",
    "ArtifactRef",
    "ArtifactType",
    "CalculationRun",
    "CapitalAttributionRecord",
    "CapitalEdge",
    "CapitalMeasure",
    "CapitalNode",
    "DuckDbParquetResultStore",
    "EdgeType",
    "FrtbComponent",
    "LineageRef",
    "NodeType",
    "ResultBundle",
    "ResultStoreConfig",
    "ResultStoreContractError",
    "ResultStoreWriteError",
    "StorageBackend",
    "__version__",
]

_BACKEND_EXPORTS = frozenset(
    {
        "DuckDbParquetResultStore",
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
        "ResultStoreConfig": ResultStoreConfig,
        "ResultStoreWriteError": ResultStoreWriteError,
    }
