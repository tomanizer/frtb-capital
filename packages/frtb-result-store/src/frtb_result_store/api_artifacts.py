"""Artifact drillthrough helpers for the read-only API."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote, urlparse

from frtb_result_store.io import DuckDbParquetResultStore
from frtb_result_store.model import ArtifactRef

Jsonable = Callable[[object], object]


def require_artifact_ref(
    store: DuckDbParquetResultStore,
    run_id: str,
    artifact_id: str,
    http_exception_type: type[Exception],
) -> ArtifactRef:
    for ref in store.artifact_refs(run_id):
        if ref.artifact_id == artifact_id:
            return ref
    raise http_exception_type(  # type: ignore[call-arg]
        status_code=404,
        detail=f"artifact not found: {artifact_id}",
    )


def artifact_download_path(
    store: DuckDbParquetResultStore,
    ref: ArtifactRef,
    http_exception_type: type[Exception],
) -> Path | None:
    path = _artifact_file_path(store, ref)
    if path is None:
        return None
    return _require_existing_parquet(path, ref, store, http_exception_type)


def artifact_page_payload(
    store: DuckDbParquetResultStore,
    ref: ArtifactRef,
    *,
    columns: Sequence[str] | None,
    filters: Sequence[str] | None,
    limit: int,
    offset: int,
    http_exception_type: type[Exception],
    to_jsonable: Jsonable,
) -> dict[str, object]:
    path = artifact_download_path(store, ref, http_exception_type)
    if path is None:
        return {
            "artifact": to_jsonable(ref),
            "mode": "s3_uri_handoff",
            "uri": ref.uri,
            "limit": limit,
            "offset": offset,
            "returned": 0,
            "filtered_row_count": None,
            "next_offset": None,
            "columns": [],
            "filters": {},
            "rows": [],
        }
    page = _read_parquet_page(
        path,
        columns=columns,
        filters=filters,
        limit=limit,
        offset=offset,
        http_exception_type=http_exception_type,
        to_jsonable=to_jsonable,
    )
    return {
        "artifact": to_jsonable(ref),
        "mode": "local_parquet",
        "limit": limit,
        "offset": offset,
        "returned": len(cast(list[dict[str, object]], page["rows"])),
        "row_count": ref.row_count,
        **page,
    }


def _artifact_file_path(store: DuckDbParquetResultStore, ref: ArtifactRef) -> Path | None:
    parsed = urlparse(ref.uri)
    if parsed.scheme == "file":
        return Path(unquote(parsed.path))
    if parsed.scheme == "":
        return Path(ref.uri)
    if parsed.scheme != "s3":
        return None
    root_uri = getattr(store, "root_uri", None)
    root = getattr(store, "root", None)
    if not isinstance(root_uri, str) or not isinstance(root, Path):
        return None
    prefix = f"{root_uri}/"
    return root / unquote(ref.uri.removeprefix(prefix)) if ref.uri.startswith(prefix) else None


def _require_existing_parquet(
    path: Path,
    ref: ArtifactRef,
    store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
) -> Path:
    resolved = path.resolve()
    if (
        resolved.suffix != ".parquet"
        or not resolved.is_file()
        or not resolved.is_relative_to(store.root.resolve())
    ):
        raise http_exception_type(  # type: ignore[call-arg]
            status_code=404,
            detail=f"artifact file not found: {ref.artifact_id}",
        )
    return resolved


def _read_parquet_page(
    path: Path,
    *,
    columns: Sequence[str] | None,
    filters: Sequence[str] | None,
    limit: int,
    offset: int,
    http_exception_type: type[Exception],
    to_jsonable: Jsonable,
) -> dict[str, object]:
    import duckdb

    relation = f"read_parquet({_sql_literal(str(path))})"
    try:
        with duckdb.connect(database=":memory:") as connection:
            available = _artifact_columns(connection, relation)
            selected = _selected_columns(columns, available, http_exception_type)
            where_sql, filter_values, filter_payload = _filter_clause(
                filters,
                available,
                http_exception_type,
            )
            order_by = ", ".join(_quote_identifier(column) for column in available)
            count_sql = f"SELECT count(*) FROM {relation}{where_sql}"
            count_row = connection.execute(count_sql, filter_values).fetchone()
            row_count = 0 if count_row is None else int(count_row[0])
            rows = connection.execute(
                (
                    f"SELECT {', '.join(_quote_identifier(column) for column in selected)} "
                    f"FROM {relation}{where_sql} ORDER BY {order_by} LIMIT ? OFFSET ?"
                ),
                (*filter_values, limit, offset),
            ).fetchall()
    except duckdb.Error as exc:
        raise http_exception_type(  # type: ignore[call-arg]
            status_code=422,
            detail="artifact page query failed",
        ) from exc
    next_offset = offset + len(rows)
    return {
        "columns": selected,
        "filters": filter_payload,
        "filtered_row_count": row_count,
        "next_offset": next_offset if next_offset < row_count else None,
        "rows": [
            {column: to_jsonable(value) for column, value in zip(selected, row)} for row in rows
        ],
    }


def _artifact_columns(connection: Any, relation: str) -> list[str]:
    rows = connection.execute(f"DESCRIBE SELECT * FROM {relation}").fetchall()
    return [str(row[0]) for row in rows]


def _selected_columns(
    columns: Sequence[str] | None,
    available: Sequence[str],
    http_exception_type: type[Exception],
) -> list[str]:
    requested = _flatten_query_values(columns)
    if not requested:
        return list(available)
    _validate_columns(requested, available, http_exception_type)
    return requested


def _filter_clause(
    filters: Sequence[str] | None,
    available: Sequence[str],
    http_exception_type: type[Exception],
) -> tuple[str, tuple[str, ...], dict[str, str]]:
    parsed = _parse_filters(filters, http_exception_type)
    if not parsed:
        return "", (), {}
    _validate_columns(tuple(parsed), available, http_exception_type)
    predicates = " AND ".join(f"{_quote_identifier(column)} = ?" for column in parsed)
    return f" WHERE {predicates}", tuple(parsed.values()), dict(parsed)


def _parse_filters(
    filters: Sequence[str] | None,
    http_exception_type: type[Exception],
) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in filters or ():
        column, separator, value = item.partition("=")
        if not column or not separator:
            raise http_exception_type(  # type: ignore[call-arg]
                status_code=422,
                detail="artifact filters must use column=value syntax",
            )
        parsed[column.strip()] = value.strip()
    return parsed


def _flatten_query_values(values: Sequence[str] | None) -> list[str]:
    flattened = [part.strip() for value in values or () for part in value.split(",")]
    return list(dict.fromkeys(part for part in flattened if part))


def _validate_columns(
    columns: Sequence[str],
    available: Sequence[str],
    http_exception_type: type[Exception],
) -> None:
    unknown = sorted(column for column in columns if column not in set(available))
    if unknown:
        raise http_exception_type(  # type: ignore[call-arg]
            status_code=422,
            detail=f"unknown artifact column(s): {', '.join(unknown)}",
        )


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
