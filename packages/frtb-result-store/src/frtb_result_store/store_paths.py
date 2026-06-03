"""Path, SQL, and DuckDB naming utilities for the result store."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

from frtb_common.hashing import stable_json_hash

from frtb_result_store.artifacts import ArtifactWriteRequest
from frtb_result_store.mart_schemas import MART_SCHEMAS
from frtb_result_store.model import ArtifactType, ResultStoreContractError

_DUCKDB_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _normalize_s3_uri(root: Path | str) -> str:
    if not isinstance(root, str):
        raise ResultStoreContractError(
            "s3_parquet root must be an s3:// URI string",
            field="root",
        )
    parsed = urlparse(root)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ResultStoreContractError(
            "s3_parquet root must be an s3://bucket[/prefix] URI",
            field="root",
        )
    if unquote(parsed.netloc) in {".", ".."}:
        raise ResultStoreContractError(
            "s3_parquet root path must not contain relative components",
            field="root",
        )
    if parsed.query or parsed.fragment:
        raise ResultStoreContractError(
            "s3_parquet root must not include query or fragment",
            field="root",
        )
    raw_parts = [part for part in parsed.path.split("/") if part]
    decoded_parts = [unquote(part) for part in raw_parts]
    if any(part in {".", ".."} for part in decoded_parts):
        raise ResultStoreContractError(
            "s3_parquet root path must not contain relative components",
            field="root",
        )
    path = "/".join(raw_parts)
    return f"s3://{parsed.netloc}" + (f"/{path}" if path else "")


def _s3_mock_physical_root(root_uri: str, mock_root: Path) -> Path:
    parsed = urlparse(root_uri)
    path_parts = [unquote(part) for part in parsed.path.split("/") if part]
    return mock_root.resolve().joinpath(parsed.netloc, *path_parts)


def _validated_duckdb_name(value: str, field: str) -> str:
    if not isinstance(value, str) or not _DUCKDB_NAME_RE.fullmatch(value):
        raise ResultStoreContractError(
            f"{field} entries must be DuckDB setting or extension names",
            field=field,
        )
    return value


def _duckdb_literal(value: str | int | float | bool) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, str):
        return _sql_literal(value)
    raise ResultStoreContractError(
        "duckdb setting values must be string, number, or boolean",
        field="duckdb_settings",
    )


def _artifact_id_for_request(
    run_id: str,
    request: ArtifactWriteRequest,
    schema_fingerprint: str,
) -> str:
    artifact_type = ArtifactType(request.artifact_type)
    payload = {
        "run_id": run_id,
        "artifact_id_hint": request.artifact_id_hint,
        "artifact_type": artifact_type.value,
        "schema_fingerprint": schema_fingerprint,
        "partition_values": dict(request.partition_values),
    }
    return f"{artifact_type.value}:{stable_json_hash(payload)}"


def _safe_run_id(run_id: str) -> str:
    return quote(run_id, safe="")


def _artifact_safe_run_id(run_id: str) -> str:
    return _safe_run_id(run_id)


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _view_name(table_name: str) -> str:
    return f"frtb_result_store_{table_name}"


def _mart_view_name(mart_name: str) -> str:
    return f"frtb_result_store_mart_{mart_name}"


def _mart_columns(mart_name: str) -> tuple[str, ...]:
    if mart_name not in MART_SCHEMAS:
        raise ResultStoreContractError(f"unknown mart: {mart_name}", field="mart_name")
    return tuple(MART_SCHEMAS[mart_name].names)
