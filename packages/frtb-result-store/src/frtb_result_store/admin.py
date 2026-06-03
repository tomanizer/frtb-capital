"""Administrative helpers for disposable catalogs and one-way exports."""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import duckdb
from frtb_common.hashing import stable_json_dumps

from frtb_result_store.io import (
    RUN_TABLE_NAMES,
    TABLE_NAMES,
    DuckDbParquetResultStore,
)
from frtb_result_store.mart_schemas import MART_NAMES
from frtb_result_store.model import (
    ArtifactRef,
    ArtifactType,
    ResultStoreContractError,
    StorageBackend,
)
from frtb_result_store.observability import result_store_span

__all__ = [
    "RunExportResult",
    "StoreInspection",
    "StoreValidationResult",
]


@dataclass(frozen=True, slots=True)
class StoreInspection:
    """Small operator-facing summary for a result-store root."""

    root: str
    backend: str
    catalog_path: str
    catalog_exists: bool
    run_count: int
    run_ids: tuple[str, ...]
    table_file_counts: Mapping[str, int]
    mart_file_counts: Mapping[str, int]

    def to_dict(self) -> dict[str, object]:
        return {
            "root": self.root,
            "backend": self.backend,
            "catalog_path": self.catalog_path,
            "catalog_exists": self.catalog_exists,
            "run_count": self.run_count,
            "run_ids": list(self.run_ids),
            "table_file_counts": dict(self.table_file_counts),
            "mart_file_counts": dict(self.mart_file_counts),
        }


@dataclass(frozen=True, slots=True)
class StoreValidationResult:
    """Validation outcome for manifest-gated result-store files."""

    ok: bool
    errors: tuple[str, ...]
    warning_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "errors": list(self.errors),
            "warning_count": self.warning_count,
        }


@dataclass(frozen=True, slots=True)
class RunExportResult:
    """Result metadata for a single-run one-way export."""

    run_id: str
    output_path: Path
    checksums: Mapping[str, str]

    def to_dict(self) -> dict[str, object]:
        return {
            "run_id": self.run_id,
            "output_path": str(self.output_path),
            "file_count": len(self.checksums),
            "checksums": dict(self.checksums),
        }


def inspect_store(store: DuckDbParquetResultStore) -> StoreInspection:
    """Return an operator summary without relying on the DuckDB catalog."""

    run_ids = _run_ids(store)
    return StoreInspection(
        root=str(store.root),
        backend=store.config.backend.value,
        catalog_path=str(store.catalog_path),
        catalog_exists=store.catalog_path.exists(),
        run_count=len(run_ids),
        run_ids=run_ids,
        table_file_counts={name: len(store._table_files(name)) for name in TABLE_NAMES},
        mart_file_counts={name: len(store._mart_files(name)) for name in MART_NAMES},
    )


def validate_store(store: DuckDbParquetResultStore) -> StoreValidationResult:
    """Validate committed manifests and their required Parquet evidence."""

    errors: list[str] = []
    for run_id in _run_ids(store):
        try:
            store._ensure_run_compatible(run_id)
        except ResultStoreContractError as exc:
            errors.append(str(exc))
            continue
        for table_name in RUN_TABLE_NAMES:
            path = store._run_table_path(table_name, run_id)
            if not path.exists():
                errors.append(f"missing base parquet for {run_id}: {table_name}")
        status_dir = store.parquet_root / "run_status_events" / _safe_run_id(run_id)
        if not tuple(status_dir.glob("*.parquet")):
            errors.append(f"missing lifecycle event parquet for {run_id}")
        for mart_name in MART_NAMES:
            path = store._mart_path(mart_name, run_id)
            if not path.exists():
                errors.append(f"missing mart parquet for {run_id}: {mart_name}")
        for artifact in store.artifact_refs(run_id):
            artifact_path = _artifact_physical_path(store, artifact)
            if artifact_path is not None and not artifact_path.exists():
                errors.append(f"missing artifact parquet for {run_id}: {artifact.artifact_id}")
    return StoreValidationResult(ok=not errors, errors=tuple(errors))


def read_only_connection(store: DuckDbParquetResultStore) -> Any:
    """Open a best-effort read-only DuckDB catalog connection.

    The catalog is derived convenience state. If it is absent, this helper
    refreshes it first, then opens the database with DuckDB's read-only mode so
    writes fail on platforms where DuckDB enforces that flag.
    """

    if not store.catalog_path.exists():
        store.refresh_catalog()
    connection = duckdb.connect(str(store.catalog_path), read_only=True)
    store._configure_duckdb(connection)
    return connection


def export_run(
    store: DuckDbParquetResultStore,
    run_id: str,
    output_path: Path | str,
    *,
    overwrite: bool = False,
) -> RunExportResult:
    """Write one manifest-gated run export with SHA-256 checksums."""

    if not store.run_exists(run_id):
        raise ResultStoreContractError(f"run does not exist: {run_id}", field="run_id")
    store._ensure_run_compatible(run_id)
    output = Path(output_path)
    if output.exists():
        if not overwrite:
            raise ResultStoreContractError(
                f"export output already exists: {output}",
                field="output_path",
            )
        shutil.rmtree(output)
    output.mkdir(parents=True)

    copied: list[Path] = []
    span_attributes = {"frtb.run_id": run_id}
    with result_store_span("frtb_result_store.export_run", span_attributes):
        _copy_file(store._manifest_path(run_id), output / "run_manifest.json", copied)
        for table_name in RUN_TABLE_NAMES:
            _copy_file(
                store._run_table_path(table_name, run_id),
                output / "parquet" / "base" / table_name / f"{_safe_run_id(run_id)}.parquet",
                copied,
            )
        for event in store.status_history(run_id):
            _copy_file(
                store._status_event_path(run_id, event.event_id),
                output
                / "parquet"
                / "base"
                / "run_status_events"
                / _safe_run_id(run_id)
                / f"{_safe_run_id(event.event_id)}.parquet",
                copied,
            )
        for mart_name in MART_NAMES:
            _copy_file(
                store._mart_path(mart_name, run_id),
                output / "parquet" / "marts" / mart_name / f"{_safe_run_id(run_id)}.parquet",
                copied,
            )
        for artifact in store.artifact_refs(run_id):
            path = _artifact_physical_path(store, artifact)
            if path is None:
                raise ResultStoreContractError(
                    f"artifact parquet is not exportable: {artifact.artifact_id}",
                    field="artifact_id",
                )
            if not path.exists():
                raise ResultStoreContractError(
                    f"missing artifact parquet: {artifact.artifact_id}",
                    field="artifact_id",
                )
            _copy_file(
                path, output / "parquet" / "artifacts" / _artifact_export_name(artifact), copied
            )

    checksums = _checksums(output, copied)
    checksum_path = output / "checksums.json"
    checksum_path.write_text(
        stable_json_dumps({"algorithm": "sha256", "files": dict(checksums)}) + "\n",
        encoding="utf-8",
    )
    return RunExportResult(run_id=run_id, output_path=output, checksums=checksums)


def _run_ids(store: DuckDbParquetResultStore) -> tuple[str, ...]:
    return tuple(run.run_id for run in store.list_runs())


def _copy_file(source: Path, destination: Path, copied: list[Path]) -> None:
    if not source.exists():
        raise ResultStoreContractError(f"export source file missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    copied.append(destination)


def _checksums(root: Path, paths: Sequence[Path]) -> Mapping[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256(path)
        for path in sorted(paths, key=lambda item: item.relative_to(root).as_posix())
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_physical_path(store: DuckDbParquetResultStore, artifact: ArtifactRef) -> Path | None:
    if artifact.uri is None:
        return _artifact_path_from_id(store, artifact)
    parsed = urlparse(artifact.uri)
    if parsed.scheme == "file":
        return Path(unquote(parsed.path))
    if parsed.scheme == "s3":
        if store.config.backend is not StorageBackend.S3_PARQUET:
            return None
        root_uri = store.root_uri
        if not artifact.uri.startswith(f"{root_uri}/"):
            return None
        relative = artifact.uri[len(root_uri) + 1 :]
        return store.root / relative
    return None


def _artifact_path_from_id(store: DuckDbParquetResultStore, artifact: ArtifactRef) -> Path:
    return (
        store.artifact_root
        / f"artifact_type={ArtifactType(artifact.artifact_type).value}"
        / f"run_id={_safe_run_id(artifact.run_id)}"
        / f"artifact_id={_safe_run_id(artifact.artifact_id)}"
        / "data.parquet"
    )


def _artifact_export_name(artifact: ArtifactRef) -> str:
    return (
        f"artifact_type={ArtifactType(artifact.artifact_type).value}/"
        f"run_id={_safe_run_id(artifact.run_id)}/"
        f"artifact_id={_safe_run_id(artifact.artifact_id)}/data.parquet"
    )


def _safe_run_id(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")
