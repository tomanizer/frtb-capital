"""Read-only FastAPI service for committed FRTB result-store runs."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Protocol, cast

from frtb_common import jsonable

from frtb_result_store.api_artifacts import (
    artifact_download_path,
    artifact_page_payload,
    require_artifact_ref,
)
from frtb_result_store.io import DuckDbParquetResultStore, ResultStoreConfig
from frtb_result_store.model import (
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
        "/runs/{run_id}/top-contributors",
        tags=["Attribution"],
        summary="Return top persisted attribution contributors",
    )
    def top_contributors(run_id: str, limit: int = 10) -> dict[str, object]:
        if limit < 1 or limit > 1000:
            raise http_exception_type(  # type: ignore[call-arg]
                status_code=422,
                detail="limit must be between 1 and 1000",
            )
        _require_run(result_store, run_id, http_exception_type)
        return {"contributors": _to_jsonable(result_store.top_contributors(run_id, limit=limit))}

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
        ref = require_artifact_ref(result_store, run_id, artifact_id, http_exception_type)
        return artifact_page_payload(
            result_store,
            ref,
            columns=columns,
            filters=filters,
            limit=limit,
            offset=offset,
            http_exception_type=http_exception_type,
            to_jsonable=_to_jsonable,
        )

    @app.get(
        "/runs/{run_id}/artifacts/{artifact_id}/download",
        tags=["Artifacts"],
        summary="Download a local Parquet artifact or return an object-store URI handoff",
    )
    def artifact_download(run_id: str, artifact_id: str) -> object:
        _require_run(result_store, run_id, http_exception_type)
        ref = require_artifact_ref(result_store, run_id, artifact_id, http_exception_type)
        path = artifact_download_path(result_store, ref, http_exception_type)
        if path is None:
            return {
                "artifact": _to_jsonable(ref),
                "mode": "s3_uri_handoff",
                "uri": ref.uri,
            }
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
            "regime_comparison": _to_jsonable(result_store.regime_comparison(run_group_id)),
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
