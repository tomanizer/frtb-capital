"""Result-store configuration constants and settings."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from frtb_result_store.model import ResultStoreContractError, StorageBackend
from frtb_result_store.store_paths import _normalize_s3_uri, _validated_duckdb_name

RESULT_STORE_SCHEMA_VERSION = 3
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
    "risk_factor_metadata_snapshots",
    "risk_factor_metadata",
    "risk_factor_source_mappings",
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
