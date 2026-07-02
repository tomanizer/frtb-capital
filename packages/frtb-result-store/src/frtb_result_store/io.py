"""DuckDB/Parquet result-store backend."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from frtb_result_store._io_catalog import StoreCatalogMixin
from frtb_result_store._io_desk_eligibility_queries import StoreDeskEligibilityQueryMixin
from frtb_result_store._io_manifest import StoreManifestMixin
from frtb_result_store._io_query import StoreQueryMixin
from frtb_result_store._io_rfet_nmrf_ses_queries import StoreRiskFactorEvidenceQueryMixin
from frtb_result_store._io_write import StoreWriteMixin
from frtb_result_store.model import ResultStoreContractError, StorageBackend
from frtb_result_store.store_config import (
    RUN_TABLE_NAMES,
    TABLE_NAMES,
    ResultStoreCompatibilityError,
    ResultStoreConfig,
    ResultStoreWriteError,
)
from frtb_result_store.store_paths import _s3_mock_physical_root

__all__ = [
    "RUN_TABLE_NAMES",
    "TABLE_NAMES",
    "DuckDbParquetResultStore",
    "ResultStoreCompatibilityError",
    "ResultStoreConfig",
    "ResultStoreWriteError",
]


class DuckDbParquetResultStore(
    StoreWriteMixin,
    StoreQueryMixin,
    StoreManifestMixin,
    StoreCatalogMixin,
    StoreRiskFactorEvidenceQueryMixin,
    StoreDeskEligibilityQueryMixin,
):
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
