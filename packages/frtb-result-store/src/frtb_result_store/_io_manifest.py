"""Manifest and compatibility helpers for result-store runs."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from frtb_common.hashing import stable_json_dumps

from frtb_result_store._version import __version__
from frtb_result_store.mart_schemas import MART_NAMES, MART_SCHEMAS, mart_schema_fingerprint
from frtb_result_store.model import ResultBundle, StorageBackend
from frtb_result_store.store_config import (
    RESULT_STORE_SCHEMA_VERSION,
    RUN_TABLE_NAMES,
    TABLE_NAMES,
    ResultStoreCompatibilityError,
    ResultStoreWriteError,
)
from frtb_result_store.store_schemas import (
    _TABLE_SCHEMAS,
    _table_schema_fingerprint,
)


class StoreManifestMixin:
    def _write_manifest(
        self: Any,
        bundle: ResultBundle,
        rows_by_table: Mapping[str, Sequence[Mapping[str, object]]],
        status_rows: Sequence[Mapping[str, object]],
        mart_rows_by_name: Mapping[str, Sequence[Mapping[str, object]]],
        staging_dir: Path,
    ) -> None:
        manifest_dir = self._manifest_path(bundle.run.run_id).parent
        manifest_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = self._manifest_path(bundle.run.run_id)
        staged_manifest_path = staging_dir / "manifest" / "run_manifest.json"
        staged_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest = {
            "schema_version": RESULT_STORE_SCHEMA_VERSION,
            "result_store_schema_version": RESULT_STORE_SCHEMA_VERSION,
            "writer_version": __version__,
            "backend": self.config.backend.value,
            "root_uri": self.root_uri,
            "paths": {
                "parquet": self._path_uri(self.parquet_root),
                "artifacts": self._path_uri(self.artifact_root),
                "manifests": self._path_uri(self.manifest_root),
            },
            "run_id": bundle.run.run_id,
            "run_group_id": bundle.run.run_group_id,
            "as_of_date": bundle.run.as_of_date.isoformat(),
            "regime_id": bundle.run.regime_id,
            "identity_payload": dict(bundle.run.identity_payload),
            "run_group_identity_payload": dict(bundle.run.run_group_identity_payload),
            "tables": {
                **{table_name: len(rows_by_table[table_name]) for table_name in RUN_TABLE_NAMES},
                "run_status_events": len(status_rows),
            },
            "marts": {mart_name: len(mart_rows_by_name[mart_name]) for mart_name in MART_NAMES},
            "base_table_schema_fingerprints": {
                table_name: _table_schema_fingerprint(table_name)
                for table_name in TABLE_NAMES
                if table_name in _TABLE_SCHEMAS
            },
            "artifact_schema_fingerprints": sorted(
                {
                    str(row["schema_fingerprint"])
                    for row in rows_by_table["artifact_refs"]
                    if row["schema_fingerprint"] is not None
                }
            ),
            "mart_schema_fingerprints": {
                mart_name: mart_schema_fingerprint(mart_name) for mart_name in MART_NAMES
            },
        }
        staged_manifest_path.write_text(
            stable_json_dumps(manifest) + "\n",
            encoding="utf-8",
        )
        if manifest_path.exists():
            raise ResultStoreWriteError(f"run already exists: {bundle.run.run_id}")
        if self.config.backend is StorageBackend.S3_PARQUET:
            self._publish_staged_file(staged_manifest_path, manifest_path)
        else:
            try:
                os.link(staged_manifest_path, manifest_path)
            except FileExistsError as exc:
                raise ResultStoreWriteError(f"run already exists: {bundle.run.run_id}") from exc
        staged_manifest_path.unlink(missing_ok=True)

    def _ensure_run_compatible(self: Any, run_id: str) -> None:
        errors = self._manifest_compatibility_errors(run_id)
        if errors:
            raise ResultStoreCompatibilityError(
                f"incompatible result-store run {run_id}: {'; '.join(errors)}",
                field="run_id",
            )

    def _is_run_compatible(self: Any, run_id: str) -> bool:
        try:
            return not self._manifest_compatibility_errors(run_id)
        except ResultStoreCompatibilityError:
            return False

    def _manifest_compatibility_errors(self: Any, run_id: str) -> tuple[str, ...]:
        manifest = self._read_manifest(run_id)
        version = manifest.get("result_store_schema_version", manifest.get("schema_version"))
        errors: list[str] = []
        if version != RESULT_STORE_SCHEMA_VERSION:
            errors.append(f"schema version {version!r} != {RESULT_STORE_SCHEMA_VERSION}")
        fingerprints = manifest.get("base_table_schema_fingerprints")
        if not isinstance(fingerprints, dict):
            errors.append("missing base table schema fingerprints")
            return tuple(errors)
        for table_name, fingerprint in fingerprints.items():
            if table_name in _TABLE_SCHEMAS and fingerprint != _table_schema_fingerprint(
                table_name
            ):
                errors.append(f"{table_name} schema fingerprint mismatch")
        mart_fingerprints = manifest.get("mart_schema_fingerprints")
        if not isinstance(mart_fingerprints, dict):
            errors.append("missing mart schema fingerprints")
            return tuple(errors)
        for mart_name, fingerprint in mart_fingerprints.items():
            if mart_name in MART_SCHEMAS and fingerprint != mart_schema_fingerprint(mart_name):
                errors.append(f"{mart_name} mart schema fingerprint mismatch")
        return tuple(errors)

    def _read_manifest(self: Any, run_id: str) -> Mapping[str, object]:
        try:
            manifest_text = self._manifest_path(run_id).read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ResultStoreCompatibilityError(
                f"run manifest not found: {run_id}",
                field="run_id",
            ) from exc
        try:
            loaded = json.loads(manifest_text)
        except json.JSONDecodeError as exc:
            raise ResultStoreCompatibilityError(
                f"malformed run manifest JSON: {exc}",
                field="run_id",
            ) from exc
        if not isinstance(loaded, dict):
            raise ResultStoreCompatibilityError("run manifest must be a JSON object")
        return cast(Mapping[str, object], loaded)
