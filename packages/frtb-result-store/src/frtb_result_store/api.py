"""Read-only FastAPI service for committed FRTB result-store runs."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.parse import unquote, urlparse

from frtb_common import jsonable

from frtb_result_store.io import DuckDbParquetResultStore, ResultStoreConfig
from frtb_result_store.model import (
    ArtifactRef,
    ArtifactType,
    CalculationRun,
    CapitalAttributionRecord,
    CapitalNode,
)

__all__ = ["create_result_store_app"]

_OPENAPI_TAGS = (
    "Runs",
    "Run Groups",
    "Capital Tree",
    "IMA",
    "SBM",
    "DRC",
    "RRAO",
    "CVA",
    "Movements",
    "Regime Comparison",
    "Artifacts",
    "Attribution",
    "Lineage",
    "Events",
)

_Endpoint = Callable[..., Any]


class _RouteRegistrar(Protocol):
    def get(
        self,
        path: str,
        *,
        tags: list[str] | None = None,
        summary: str | None = None,
        **kwargs: Any,
    ) -> Callable[[_Endpoint], _Endpoint]: ...


def create_result_store_app(
    store: DuckDbParquetResultStore | ResultStoreConfig | Path | str,
    *,
    title: str = "FRTB Result Store API",
) -> Any:
    """Return a read-only FastAPI app over committed result-store data."""

    try:
        from fastapi import FastAPI, HTTPException, Query
        from fastapi.responses import FileResponse
    except ModuleNotFoundError as exc:
        if exc.name == "fastapi":
            raise ModuleNotFoundError(
                "FastAPI service requires the optional 'api' extra; install "
                "frtb-result-store[api] to use create_result_store_app."
            ) from exc
        raise

    result_store = _coerce_store(store)
    app = FastAPI(
        title=title,
        summary="Read-only FRTB result-store service over committed run manifests.",
        version="1.0.0",
        openapi_tags=[{"name": tag} for tag in _OPENAPI_TAGS],
    )
    app.state.result_store = result_store

    routes = cast(_RouteRegistrar, app)
    _register_run_routes(routes, result_store, HTTPException)
    _register_capital_tree_routes(routes, result_store, HTTPException)
    _register_artifact_routes(routes, result_store, HTTPException, Query, FileResponse)
    _register_run_group_routes(routes, result_store, HTTPException)

    return app


def _register_run_routes(
    app: _RouteRegistrar,
    result_store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
) -> None:
    @app.get("/runs", tags=["Runs"], summary="List committed calculation runs")
    def list_runs() -> dict[str, object]:
        return {"runs": [_run_payload(result_store, run) for run in result_store.list_runs()]}

    @app.get("/run-groups", tags=["Run Groups"], summary="List committed run groups")
    def list_run_groups() -> dict[str, object]:
        return {"run_groups": _run_group_payloads(result_store.list_runs())}

    @app.get("/runs/{run_id}", tags=["Runs"], summary="Get one committed calculation run")
    def get_run(run_id: str) -> dict[str, object]:
        run = _require_run(result_store, run_id, http_exception_type)
        return _run_payload(result_store, run)

    @app.get("/runs/{run_id}/events", tags=["Events"], summary="Return result events for a run")
    def result_events(run_id: str) -> dict[str, object]:
        _require_run(result_store, run_id, http_exception_type)
        return {"events": _to_jsonable(result_store.result_events(run_id))}

    @app.get(
        "/runs/{run_id}/movements",
        tags=["Movements"],
        summary="Return movement explanation rows for a run",
    )
    def movement_results(run_id: str) -> dict[str, object]:
        _require_run(result_store, run_id, http_exception_type)
        return {
            "movements": _to_jsonable(result_store.movement_results(run_id)),
            "summary": _to_jsonable(result_store.movement_summary(run_id)),
        }


def _register_capital_tree_routes(
    app: _RouteRegistrar,
    result_store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
) -> None:
    @app.get(
        "/runs/{run_id}/capital-tree",
        tags=["Capital Tree"],
        summary="Return the flattened FRTB capital tree for a run",
    )
    def capital_tree(run_id: str) -> dict[str, object]:
        _require_run(result_store, run_id, http_exception_type)
        return {"nodes": _to_jsonable(result_store.capital_tree(run_id))}

    @app.get(
        "/runs/{run_id}/nodes/{node_id}",
        tags=["Capital Tree"],
        summary="Return one capital tree node",
    )
    def get_node(run_id: str, node_id: str) -> dict[str, object]:
        _require_run(result_store, run_id, http_exception_type)
        node = _find_node(result_store.capital_tree(run_id), node_id)
        if node is None:
            raise http_exception_type(  # type: ignore[call-arg]
                status_code=404,
                detail=f"capital node not found: {node_id}",
            )
        return cast(dict[str, object], _to_jsonable(node))

    @app.get(
        "/runs/{run_id}/nodes/{node_id}/children",
        tags=["Capital Tree"],
        summary="Return direct child capital nodes",
    )
    def child_nodes(run_id: str, node_id: str) -> dict[str, object]:
        _require_run(result_store, run_id, http_exception_type)
        return {"nodes": _to_jsonable(result_store.child_nodes(run_id, node_id))}

    @app.get(
        "/runs/{run_id}/nodes/{node_id}/measures",
        tags=["Capital Tree"],
        summary="Return scalar measures attached to one capital node",
    )
    def measures_for_node(run_id: str, node_id: str) -> dict[str, object]:
        _require_run(result_store, run_id, http_exception_type)
        return {"measures": _to_jsonable(result_store.measures_for_node(run_id, node_id))}

    @app.get(
        "/runs/{run_id}/nodes/{node_id}/attribution",
        tags=["Attribution"],
        summary="Return attribution rows attached to one capital node",
    )
    def attributions_for_node(run_id: str, node_id: str) -> dict[str, object]:
        _require_run(result_store, run_id, http_exception_type)
        return {
            "attributions": [
                _attribution_payload(attribution)
                for attribution in result_store.attributions_for_node(run_id, node_id)
            ]
        }

    @app.get(
        "/runs/{run_id}/nodes/{node_id}/lineage",
        tags=["Lineage"],
        summary="Return lineage rows for one stored result object",
    )
    def lineage_for_node(run_id: str, node_id: str) -> dict[str, object]:
        _require_run(result_store, run_id, http_exception_type)
        return {"lineage": _to_jsonable(result_store.lineage_for_result(run_id, node_id))}


def _register_artifact_routes(
    app: _RouteRegistrar,
    result_store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
    query: Any,
    file_response_type: type[Any],
) -> None:
    @app.get(
        "/runs/{run_id}/artifacts",
        tags=["Artifacts"],
        summary="Return artifact references for a run",
    )
    def artifact_refs(
        run_id: str,
        artifact_type: ArtifactType | None = query(
            default=None,
            description="Optional ArtifactType value",
        ),
    ) -> dict[str, object]:
        _require_run(result_store, run_id, http_exception_type)
        return {
            "artifacts": _to_jsonable(
                result_store.artifact_refs(run_id, artifact_type=artifact_type)
            )
        }

    @app.get(
        "/runs/{run_id}/artifacts/{artifact_id}/page",
        tags=["Artifacts"],
        summary="Return one deterministic page of artifact rows",
    )
    def artifact_page(
        run_id: str,
        artifact_id: str,
        columns: list[str] | None = query(
            default=None,
            description="Optional repeated or comma-separated column names",
        ),
        filters: list[str] | None = query(
            default=None,
            alias="filter",
            description="Optional repeated equality filters formatted as column=value",
        ),
        limit: int = query(default=100, ge=1, le=1000),
        offset: int = query(default=0, ge=0),
    ) -> dict[str, object]:
        _require_run(result_store, run_id, http_exception_type)
        ref = _require_artifact_ref(result_store, run_id, artifact_id, http_exception_type)
        return _artifact_page_payload(
            result_store,
            ref,
            columns=columns,
            filters=filters,
            limit=limit,
            offset=offset,
            http_exception_type=http_exception_type,
        )

    @app.get(
        "/runs/{run_id}/artifacts/{artifact_id}/download",
        tags=["Artifacts"],
        summary="Download a local Parquet artifact or return an object-store URI handoff",
    )
    def artifact_download(run_id: str, artifact_id: str) -> object:
        _require_run(result_store, run_id, http_exception_type)
        ref = _require_artifact_ref(result_store, run_id, artifact_id, http_exception_type)
        path = _artifact_file_path(result_store, ref)
        if path is None:
            return {
                "artifact": _to_jsonable(ref),
                "mode": "s3_uri_handoff",
                "uri": ref.uri,
            }
        _require_existing_parquet(path, ref, http_exception_type)
        return file_response_type(
            path,
            media_type="application/vnd.apache.parquet",
            filename=f"{ref.artifact_id}.parquet",
        )


def _register_run_group_routes(
    app: _RouteRegistrar,
    result_store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
) -> None:
    @app.get(
        "/run-groups/{run_group_id}/regime-comparison",
        tags=["Regime Comparison"],
        summary="Return per-run summary rows for one comparison group",
    )
    def regime_comparison(run_group_id: str) -> dict[str, object]:
        runs = tuple(run for run in result_store.list_runs() if _run_group_key(run) == run_group_id)
        if not runs:
            raise http_exception_type(  # type: ignore[call-arg]
                status_code=404,
                detail=f"run group not found: {run_group_id}",
            )
        return {
            "run_group_id": run_group_id,
            "runs": [_run_payload(result_store, run) for run in runs],
            "capital_summary": {
                run.run_id: _to_jsonable(result_store.capital_summary(run.run_id)) for run in runs
            },
            "component_breakdown": {
                run.run_id: _to_jsonable(result_store.component_breakdown(run.run_id))
                for run in runs
            },
        }


def _coerce_store(
    store: DuckDbParquetResultStore | ResultStoreConfig | Path | str,
) -> DuckDbParquetResultStore:
    if isinstance(store, DuckDbParquetResultStore):
        return store
    return DuckDbParquetResultStore(store)


def _require_run(
    store: DuckDbParquetResultStore,
    run_id: str,
    http_exception_type: type[Exception],
) -> CalculationRun:
    run = store.get_run(run_id)
    if run is None:
        raise http_exception_type(status_code=404, detail=f"run not found: {run_id}")  # type: ignore[call-arg]
    return run


def _find_node(nodes: Sequence[CapitalNode], node_id: str) -> CapitalNode | None:
    for node in nodes:
        if node.node_id == node_id:
            return node
    return None


def _require_artifact_ref(
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


def _artifact_page_payload(
    store: DuckDbParquetResultStore,
    ref: ArtifactRef,
    *,
    columns: Sequence[str] | None,
    filters: Sequence[str] | None,
    limit: int,
    offset: int,
    http_exception_type: type[Exception],
) -> dict[str, object]:
    path = _artifact_file_path(store, ref)
    if path is None:
        return {
            "artifact": _to_jsonable(ref),
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
    _require_existing_parquet(path, ref, http_exception_type)
    page = _read_parquet_page(
        path,
        columns=columns,
        filters=filters,
        limit=limit,
        offset=offset,
        http_exception_type=http_exception_type,
    )
    page_rows = cast(list[dict[str, object]], page["rows"])
    return {
        "artifact": _to_jsonable(ref),
        "mode": "local_parquet",
        "limit": limit,
        "offset": offset,
        "returned": len(page_rows),
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
    if not ref.uri.startswith(prefix):
        return None
    return root / unquote(ref.uri.removeprefix(prefix))


def _require_existing_parquet(
    path: Path,
    ref: ArtifactRef,
    http_exception_type: type[Exception],
) -> None:
    if path.suffix != ".parquet" or not path.is_file():
        raise http_exception_type(  # type: ignore[call-arg]
            status_code=404,
            detail=f"artifact file not found: {ref.artifact_id}",
        )


def _read_parquet_page(
    path: Path,
    *,
    columns: Sequence[str] | None,
    filters: Sequence[str] | None,
    limit: int,
    offset: int,
    http_exception_type: type[Exception],
) -> dict[str, object]:
    import duckdb

    relation = f"read_parquet({_sql_literal(str(path))})"
    with duckdb.connect(database=":memory:") as connection:
        available_columns = _artifact_columns(connection, relation)
        selected_columns = _selected_columns(columns, available_columns, http_exception_type)
        where_sql, filter_values, filter_payload = _filter_clause(
            filters,
            available_columns,
            http_exception_type,
        )
        order_by = ", ".join(_quote_identifier(column) for column in available_columns)
        count_sql = f"SELECT count(*) FROM {relation}{where_sql}"
        count_row = connection.execute(count_sql, filter_values).fetchone()
        filtered_row_count = 0 if count_row is None else int(count_row[0])
        select_sql = ", ".join(_quote_identifier(column) for column in selected_columns)
        rows = connection.execute(
            (
                f"SELECT {select_sql} FROM {relation}{where_sql} "
                f"ORDER BY {order_by} LIMIT ? OFFSET ?"
            ),
            (*filter_values, limit, offset),
        ).fetchall()
    next_offset = offset + len(rows)
    return {
        "columns": selected_columns,
        "filters": filter_payload,
        "filtered_row_count": filtered_row_count,
        "next_offset": next_offset if next_offset < filtered_row_count else None,
        "rows": [
            {column: _to_jsonable(value) for column, value in zip(selected_columns, row)}
            for row in rows
        ],
    }


def _artifact_columns(connection: Any, relation: str) -> list[str]:
    rows = connection.execute(f"DESCRIBE SELECT * FROM {relation}").fetchall()
    return [str(row[0]) for row in rows]


def _selected_columns(
    columns: Sequence[str] | None,
    available_columns: Sequence[str],
    http_exception_type: type[Exception],
) -> list[str]:
    requested = _flatten_query_values(columns)
    if not requested:
        return list(available_columns)
    _validate_columns(requested, available_columns, http_exception_type)
    return requested


def _filter_clause(
    filters: Sequence[str] | None,
    available_columns: Sequence[str],
    http_exception_type: type[Exception],
) -> tuple[str, tuple[str, ...], dict[str, str]]:
    parsed = _parse_filters(filters, http_exception_type)
    if not parsed:
        return "", (), {}
    _validate_columns(tuple(parsed), available_columns, http_exception_type)
    predicates = " AND ".join(f"{_quote_identifier(column)} = ?" for column in parsed)
    return f" WHERE {predicates}", tuple(parsed.values()), dict(parsed)


def _parse_filters(
    filters: Sequence[str] | None,
    http_exception_type: type[Exception],
) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in _flatten_query_values(filters):
        column, separator, value = item.partition("=")
        if not column or not separator:
            raise http_exception_type(  # type: ignore[call-arg]
                status_code=422,
                detail="artifact filters must use column=value syntax",
            )
        parsed[column.strip()] = value.strip()
    return parsed


def _flatten_query_values(values: Sequence[str] | None) -> list[str]:
    flattened: list[str] = []
    for value in values or ():
        flattened.extend(part.strip() for part in value.split(",") if part.strip())
    return list(dict.fromkeys(flattened))


def _validate_columns(
    columns: Sequence[str],
    available_columns: Sequence[str],
    http_exception_type: type[Exception],
) -> None:
    available = set(available_columns)
    unknown = sorted(column for column in columns if column not in available)
    if unknown:
        raise http_exception_type(  # type: ignore[call-arg]
            status_code=422,
            detail=f"unknown artifact column(s): {', '.join(unknown)}",
        )


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _run_payload(store: DuckDbParquetResultStore, run: CalculationRun) -> dict[str, object]:
    payload = cast(dict[str, object], _to_jsonable(run))
    payload["latest_status"] = _to_jsonable(store.latest_status(run.run_id))
    payload["suggested_status"] = _to_jsonable(store.suggested_status(run.run_id))
    return payload


def _run_group_payloads(runs: Sequence[CalculationRun]) -> list[dict[str, object]]:
    groups: dict[str, list[CalculationRun]] = {}
    for run in runs:
        groups.setdefault(_run_group_key(run), []).append(run)
    return [
        {
            "run_group_id": run_group_id,
            "run_count": len(group_runs),
            "run_ids": [run.run_id for run in group_runs],
            "regime_ids": sorted({run.regime_id for run in group_runs}),
            "as_of_dates": sorted({run.as_of_date.isoformat() for run in group_runs}),
        }
        for run_group_id, group_runs in sorted(groups.items())
    ]


def _run_group_key(run: CalculationRun) -> str:
    return run.run_group_id or f"run:{run.run_id}"


def _attribution_payload(attribution: CapitalAttributionRecord) -> dict[str, object]:
    payload = cast(dict[str, object], _to_jsonable(attribution))
    payload["attribution_id"] = attribution.attribution_id
    return payload


def _to_jsonable(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _to_jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_to_jsonable(item) for item in value]
    return jsonable(value)
