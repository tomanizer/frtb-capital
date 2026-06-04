"""Catalog, connection, path, and cleanup helpers for result-store IO."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote

import duckdb

from frtb_result_store.mart_schemas import MART_NAMES
from frtb_result_store.model import ResultStoreContractError, StorageBackend
from frtb_result_store.store_config import RUN_TABLE_NAMES, TABLE_NAMES
from frtb_result_store.store_paths import (
    _artifact_safe_run_id,
    _duckdb_literal,
    _mart_view_name,
    _safe_run_id,
    _sql_literal,
    _view_name,
)


class StoreCatalogMixin:
    def cleanup_orphaned_staging(self: Any, *, run_id: str | None = None) -> tuple[str, ...]:
        """Remove abandoned staging directories that are not committed manifests."""

        staging_root = self.root / "_staging"
        if not staging_root.exists():
            return ()
        if run_id is not None:
            path = staging_root / _safe_run_id(run_id)
            if not path.exists():
                return ()
            shutil.rmtree(path)
            return (run_id,)
        removed: list[str] = []
        for path in sorted(staging_root.iterdir()):
            if not path.is_dir():
                continue
            shutil.rmtree(path)
            if not path.exists():
                removed.append(unquote(path.name))
        return tuple(removed)

    def resolve_run_id_prefix(self: Any, prefix: str) -> str | None:
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

    def refresh_catalog(self: Any) -> None:
        """Create or replace DuckDB views over the Parquet result tables."""

        con = self._connect_catalog()
        try:
            for table_name in TABLE_NAMES:
                if self._has_table_files(table_name):
                    con.execute(
                        f"CREATE OR REPLACE VIEW {_view_name(table_name)} AS "
                        f"SELECT * FROM {self._parquet_relation(table_name)}"
                    )
            for mart_name in MART_NAMES:
                if self._has_mart_files(mart_name):
                    con.execute(
                        f"CREATE OR REPLACE VIEW {_mart_view_name(mart_name)} AS "
                        f"SELECT * FROM {self._mart_relation(mart_name)}"
                    )
        finally:
            con.close()

    def read_only_connection(self: Any) -> Any:
        from frtb_result_store.admin import read_only_connection

        return read_only_connection(self)

    def inspect(self: Any) -> object:
        from frtb_result_store.admin import inspect_store

        return inspect_store(self)

    def validate_store(self: Any) -> object:
        from frtb_result_store.admin import validate_store

        return validate_store(self)

    def export_run(
        self: Any, run_id: str, output_path: Path | str, *, overwrite: bool = False
    ) -> Any:
        from frtb_result_store.admin import export_run

        return export_run(self, run_id, output_path, overwrite=overwrite)

    def _connect_catalog(self: Any) -> Any:
        con = duckdb.connect(str(self.catalog_path))
        self._configure_duckdb(con)
        return con

    def _connect_query(self: Any) -> Any:
        con = duckdb.connect()
        self._configure_duckdb(con)
        return con

    def _configure_duckdb(self: Any, con: Any) -> None:
        for extension in self.config.duckdb_extensions:
            if self.config.duckdb_install_extensions:
                con.execute(f"INSTALL {extension}")
            con.execute(f"LOAD {extension}")
        for name, value in self.config.duckdb_settings.items():
            con.execute(f"SET {name} = {_duckdb_literal(value)}")

    def _run_table_path(self: Any, table_name: str, run_id: str) -> Path:
        if table_name not in RUN_TABLE_NAMES:
            raise ResultStoreContractError(f"unknown table: {table_name}", field="table_name")
        return cast(Path, self.parquet_root / table_name / f"{_safe_run_id(run_id)}.parquet")

    def _mart_path(self: Any, mart_name: str, run_id: str) -> Path:
        if mart_name not in MART_NAMES:
            raise ResultStoreContractError(f"unknown mart: {mart_name}", field="mart_name")
        return cast(
            Path,
            self.parquet_root / "marts" / mart_name / f"{_safe_run_id(run_id)}.parquet",
        )

    def _status_event_path(self: Any, run_id: str, event_id: str) -> Path:
        return cast(
            Path,
            self.parquet_root
            / "run_status_events"
            / _safe_run_id(run_id)
            / f"{_safe_run_id(event_id)}.parquet",
        )

    def _has_table_files(self: Any, table_name: str) -> bool:
        return bool(self._table_files(table_name))

    def _has_mart_files(self: Any, mart_name: str) -> bool:
        return bool(self._mart_files(mart_name))

    def _parquet_relation(self: Any, table_name: str) -> str:
        file_paths = ", ".join(_sql_literal(str(path)) for path in self._table_files(table_name))
        return f"read_parquet([{file_paths}], union_by_name = true)"

    def _mart_relation(self: Any, mart_name: str) -> str:
        file_paths = ", ".join(_sql_literal(str(path)) for path in self._mart_files(mart_name))
        return f"read_parquet([{file_paths}], union_by_name = true)"

    def _manifest_path(self: Any, run_id: str) -> Path:
        return cast(Path, self.manifest_root / _safe_run_id(run_id) / "run_manifest.json")

    def _path_uri(self: Any, path: Path) -> str:
        if self.config.backend is not StorageBackend.S3_PARQUET:
            return path.resolve().as_uri()
        relative = path.relative_to(self.root).as_posix()
        return f"{self.root_uri}/{relative}"

    def _committed_run_ids(self: Any) -> tuple[str, ...]:
        manifest_root = cast(Path, self.manifest_root)
        return tuple(
            sorted(unquote(path.parent.name) for path in manifest_root.glob("*/run_manifest.json"))
        )

    def _table_files(self: Any, table_name: str) -> tuple[Path, ...]:
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

    def _mart_files(self: Any, mart_name: str) -> tuple[Path, ...]:
        if mart_name not in MART_NAMES:
            raise ResultStoreContractError(f"unknown mart: {mart_name}", field="mart_name")
        return tuple(
            path
            for run_id in self._committed_run_ids()
            if (path := self._mart_path(mart_name, run_id)).exists()
        )

    def _remove_orphaned_run_files(self: Any, run_id: str) -> None:
        for table_name in RUN_TABLE_NAMES:
            self._run_table_path(table_name, run_id).unlink(missing_ok=True)
        shutil.rmtree(
            self.parquet_root / "run_status_events" / _safe_run_id(run_id),
            ignore_errors=True,
        )
        self._remove_orphaned_artifacts(run_id)
        self._remove_orphaned_marts(run_id)

    def _remove_orphaned_artifacts(self: Any, run_id: str) -> None:
        safe_run_id = _artifact_safe_run_id(run_id)
        for path in self.artifact_root.glob(f"artifact_type=*/run_id={safe_run_id}"):
            shutil.rmtree(path, ignore_errors=True)

    def _remove_orphaned_marts(self: Any, run_id: str) -> None:
        for mart_name in MART_NAMES:
            self._mart_path(mart_name, run_id).unlink(missing_ok=True)
