"""Read-only FastAPI service for committed FRTB result-store runs."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, NoReturn, Protocol, cast

from frtb_common import jsonable

from frtb_result_store.api_artifacts import (
    artifact_download_path,
    artifact_page_payload,
    artifact_unavailable_payload,
    require_artifact_ref,
)
from frtb_result_store.api_metadata import register_artifact_metadata_routes
from frtb_result_store.io import DuckDbParquetResultStore, ResultStoreConfig
from frtb_result_store.model import (
    ArtifactType,
    CalculationRun,
    CapitalAttributionRecord,
    CapitalNode,
    ResultStoreContractError,
)
from frtb_result_store.org_hierarchy import (
    aggregate_org_node,
    list_org_hierarchy,
    org_node_children,
    sample_org_capital_rows,
    sample_org_hierarchy,
    source_rows_for_org_node,
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
    "Org Hierarchy",
    "Risk Factors",
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
    cors_allow_origins: Sequence[str] = (),
) -> Any:
    """Return a read-only FastAPI app over committed result-store data.
    Parameters
    ----------
    store : DuckDbParquetResultStore | ResultStoreConfig | Path | str
        Store.
    title : str, optional
        Title.

    Returns
    -------
    Any
        Result of the operation.
    """

    try:
        from fastapi import FastAPI, HTTPException, Query
        from fastapi.middleware.cors import CORSMiddleware
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
    if cors_allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cors_allow_origins),
            allow_methods=["GET"],
            allow_headers=["*"],
        )
    app.state.result_store = result_store

    routes = cast(_RouteRegistrar, app)
    _register_run_routes(routes, result_store, HTTPException)
    _register_org_hierarchy_routes(routes, result_store, HTTPException, Query)
    _register_capital_tree_routes(routes, result_store, HTTPException, Query)
    _register_risk_factor_routes(routes, result_store, HTTPException, Query)
    _register_attribution_projection_routes(routes, result_store, HTTPException)
    _register_artifact_routes(routes, result_store, HTTPException, Query, FileResponse)
    register_artifact_metadata_routes(
        routes,
        result_store,
        HTTPException,
        Query,
        require_run=_require_run,
        to_jsonable=_to_jsonable,
    )
    _register_run_group_routes(routes, result_store, HTTPException)
    _register_run_detail_route(routes, result_store, HTTPException)

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

    @app.get(
        "/runs/{run_id:path}/events", tags=["Events"], summary="Return result events for a run"
    )
    def result_events(run_id: str) -> dict[str, object]:
        _require_run(result_store, run_id, http_exception_type)
        return {"events": _to_jsonable(result_store.result_events(run_id))}

    @app.get(
        "/runs/{run_id:path}/movements",
        tags=["Movements"],
        summary="Return movement explanation rows for a run",
    )
    def movement_results(run_id: str) -> dict[str, object]:
        _require_run(result_store, run_id, http_exception_type)
        return {
            "movements": _to_jsonable(result_store.movement_results(run_id)),
            "summary": _to_jsonable(result_store.movement_summary(run_id)),
        }


def _register_attribution_projection_routes(
    app: _RouteRegistrar,
    result_store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
) -> None:
    @app.get(
        "/runs/{run_id:path}/top-contributors",
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
        "/runs/{run_id:path}/attribution/residual",
        tags=["Attribution"],
        summary="Return persisted residual attribution records for a run",
    )
    def residual_attribution_records(
        run_id: str,
        node_id: str | None = None,
    ) -> dict[str, object]:
        _require_run(result_store, run_id, http_exception_type)
        return {
            "residual_records": _to_jsonable(
                result_store.residual_attribution_records(run_id, node_id=node_id)
            )
        }

    @app.get(
        "/runs/{run_id:path}/attribution/unsupported",
        tags=["Attribution"],
        summary="Return persisted unsupported attribution records for a run",
    )
    def unsupported_attribution_records(
        run_id: str,
        node_id: str | None = None,
    ) -> dict[str, object]:
        _require_run(result_store, run_id, http_exception_type)
        return {
            "unsupported_records": _to_jsonable(
                result_store.unsupported_attribution_records(run_id, node_id=node_id)
            )
        }


def _register_risk_factor_routes(
    app: _RouteRegistrar,
    result_store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
    query: Any,
) -> None:
    _register_risk_factor_list_route(app, result_store, http_exception_type, query)
    _register_risk_factor_detail_route(app, result_store, http_exception_type)
    _register_risk_factor_lineage_route(app, result_store, http_exception_type)
    _register_risk_factor_capital_route(app, result_store, http_exception_type)
    _register_risk_factor_source_rows_route(app, result_store, http_exception_type, query)


def _register_risk_factor_list_route(
    app: _RouteRegistrar,
    result_store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
    query: Any,
) -> None:
    @app.get(
        "/runs/{run_id:path}/risk-factors",
        tags=["Risk Factors"],
        summary="List canonical risk-factor metadata records",
    )
    def list_risk_factors(
        run_id: str,
        search: str | None = None,
        risk_class: str | None = None,
        bucket_id: str | None = None,
        snapshot_id: str | None = None,
        limit: int = query(default=100, ge=1, le=1000),
        offset: int = query(default=0, ge=0),
    ) -> dict[str, object]:
        _require_run(result_store, run_id, http_exception_type)
        try:
            return _risk_factor_jsonable(
                result_store.list_risk_factors(
                    run_id,
                    search=search,
                    risk_class=risk_class,
                    bucket_id=bucket_id,
                    snapshot_id=snapshot_id,
                    limit=limit,
                    offset=offset,
                )
            )
        except ResultStoreContractError as exc:
            _raise_risk_factor_query_error(exc, http_exception_type)


def _register_risk_factor_detail_route(
    app: _RouteRegistrar,
    result_store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
) -> None:
    @app.get(
        "/runs/{run_id:path}/risk-factors/{risk_factor_id}",
        tags=["Risk Factors"],
        summary="Return canonical metadata for one risk factor",
    )
    def get_risk_factor(
        run_id: str,
        risk_factor_id: str,
        snapshot_id: str | None = None,
    ) -> dict[str, object]:
        _require_run(result_store, run_id, http_exception_type)
        try:
            return _risk_factor_jsonable(
                result_store.get_risk_factor(run_id, risk_factor_id, snapshot_id=snapshot_id)
            )
        except ResultStoreContractError as exc:
            _raise_risk_factor_query_error(exc, http_exception_type)


def _register_risk_factor_lineage_route(
    app: _RouteRegistrar,
    result_store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
) -> None:
    @app.get(
        "/runs/{run_id:path}/risk-factors/{risk_factor_id}/lineage",
        tags=["Risk Factors", "Lineage"],
        summary="Return source lineage for one risk factor",
    )
    def risk_factor_lineage(
        run_id: str,
        risk_factor_id: str,
        snapshot_id: str | None = None,
    ) -> dict[str, object]:
        _require_run(result_store, run_id, http_exception_type)
        try:
            return _risk_factor_jsonable(
                result_store.risk_factor_lineage(
                    run_id,
                    risk_factor_id,
                    snapshot_id=snapshot_id,
                )
            )
        except ResultStoreContractError as exc:
            _raise_risk_factor_query_error(exc, http_exception_type)


def _register_risk_factor_capital_route(
    app: _RouteRegistrar,
    result_store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
) -> None:
    @app.get(
        "/runs/{run_id:path}/risk-factors/{risk_factor_id}/capital",
        tags=["Risk Factors", "Attribution"],
        summary="Return stored risk-factor capital contribution aggregate",
    )
    def risk_factor_capital(
        run_id: str,
        risk_factor_id: str,
        framework: str | None = None,
    ) -> dict[str, object]:
        _require_run(result_store, run_id, http_exception_type)
        try:
            return _risk_factor_jsonable(
                result_store.risk_factor_capital(run_id, risk_factor_id, framework=framework)
            )
        except ResultStoreContractError as exc:
            _raise_risk_factor_query_error(exc, http_exception_type)


def _register_risk_factor_source_rows_route(
    app: _RouteRegistrar,
    result_store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
    query: Any,
) -> None:
    @app.get(
        "/runs/{run_id:path}/risk-factors/{risk_factor_id}/source-rows",
        tags=["Risk Factors"],
        summary="Return a bounded page of source rows for one risk factor",
    )
    def risk_factor_source_rows(
        run_id: str,
        risk_factor_id: str,
        snapshot_id: str | None = None,
        limit: int = query(default=100, ge=1, le=1000),
        offset: int = query(default=0, ge=0),
    ) -> dict[str, object]:
        _require_run(result_store, run_id, http_exception_type)
        try:
            return _risk_factor_jsonable(
                result_store.risk_factor_source_rows(
                    run_id,
                    risk_factor_id,
                    snapshot_id=snapshot_id,
                    limit=limit,
                    offset=offset,
                )
            )
        except ResultStoreContractError as exc:
            _raise_risk_factor_query_error(exc, http_exception_type)


def _risk_factor_jsonable(payload: object) -> dict[str, object]:
    return cast(dict[str, object], _collapse_value_wrappers(_to_jsonable(payload)))


def _collapse_value_wrappers(
    payload: object,
    *,
    preserve_value_wrappers: bool = False,
) -> object:
    if isinstance(payload, Mapping):
        if (
            not preserve_value_wrappers
            and set(payload) == {"value"}
            and isinstance(payload.get("value"), str)
        ):
            return payload["value"]
        return _collapse_mapping_value_wrappers(payload, preserve_value_wrappers)
    if isinstance(payload, Sequence) and not isinstance(payload, str | bytes | bytearray):
        return [
            _collapse_value_wrappers(
                value,
                preserve_value_wrappers=preserve_value_wrappers,
            )
            for value in payload
        ]
    return payload


def _collapse_mapping_value_wrappers(
    payload: Mapping[object, object],
    preserve_value_wrappers: bool,
) -> dict[str, object]:
    collapsed: dict[str, object] = {}
    for key, value in payload.items():
        key_text = str(key)
        preserve_child = preserve_value_wrappers or (
            key_text == "metadata" and not _looks_like_record_payload(value)
        )
        collapsed[key_text] = _collapse_value_wrappers(
            value,
            preserve_value_wrappers=preserve_child,
        )
    return collapsed


def _looks_like_record_payload(value: object) -> bool:
    return isinstance(value, Mapping) and "run_id" in value and "risk_factor_id" in value


def _register_capital_tree_routes(
    app: _RouteRegistrar,
    result_store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
    query: Any,
) -> None:
    @app.get(
        "/runs/{run_id:path}/capital-tree",
        tags=["Capital Tree"],
        summary="Return the flattened FRTB capital tree for a run",
    )
    def capital_tree(run_id: str) -> dict[str, object]:
        _require_run(result_store, run_id, http_exception_type)
        return {"nodes": _to_jsonable(result_store.capital_tree(run_id))}

    @app.get(
        "/runs/{run_id:path}/nodes/{node_id}",
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


    _register_node_detail_routes(app, result_store, http_exception_type, query)


def _register_node_detail_routes(
    app: _RouteRegistrar,
    result_store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
    query: Any,
) -> None:
    @app.get(
        "/runs/{run_id:path}/nodes/{node_id}/children",
        tags=["Capital Tree"],
        summary="Return direct child capital nodes",
    )
    def child_nodes(run_id: str, node_id: str) -> dict[str, object]:
        _require_run(result_store, run_id, http_exception_type)
        return {"nodes": _to_jsonable(result_store.child_nodes(run_id, node_id))}

    @app.get(
        "/runs/{run_id:path}/nodes/{node_id}/measures",
        tags=["Capital Tree"],
        summary="Return scalar measures attached to one capital node",
    )
    def measures_for_node(run_id: str, node_id: str) -> dict[str, object]:
        _require_run(result_store, run_id, http_exception_type)
        return {"measures": _to_jsonable(result_store.measures_for_node(run_id, node_id))}

    @app.get(
        "/runs/{run_id:path}/nodes/{node_id}/attribution",
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
        "/runs/{run_id:path}/nodes/{node_id}/lineage",
        tags=["Lineage"],
        summary="Return lineage rows for one stored result object",
    )
    def lineage_for_node(run_id: str, node_id: str) -> dict[str, object]:
        _require_run(result_store, run_id, http_exception_type)
        return {"lineage": _to_jsonable(result_store.lineage_for_result(run_id, node_id))}

    @app.get(
        "/runs/{run_id:path}/pivot",
        tags=["Pivot Analysis"],
        summary="Return a pivoted aggregate result set",
    )
    def pivot_query(
        run_id: str,
        rows: list[str] = query(default=...),
        cols: list[str] = query(default=[]),
        measures: list[str] = query(default=["capital"]),
        filters: list[str] = query(default=[]),
        limit: int = query(default=100, ge=1, le=1000),
        offset: int = query(default=0, ge=0),
    ) -> dict[str, object]:
        _require_run(result_store, run_id, http_exception_type)
        try:
            return result_store.pivot_query(
                run_id,
                rows=rows,
                cols=cols,
                measures=measures,
                filters=filters,
                limit=limit,
                offset=offset,
            )
        except ResultStoreContractError as exc:
            raise http_exception_type(  # type: ignore[call-arg]
                status_code=400,
                detail=f"Invalid pivot query: {exc!s}",
            )


def _register_org_hierarchy_routes(
    app: _RouteRegistrar,
    result_store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
    query: Any,
) -> None:
    _register_org_hierarchy_snapshot_routes(app, result_store, http_exception_type, query)
    _register_org_hierarchy_node_routes(app, result_store, http_exception_type, query)


def _register_org_hierarchy_snapshot_routes(
    app: _RouteRegistrar,
    result_store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
    query: Any,
) -> None:
    @app.get(
        "/runs/{run_id:path}/org-hierarchy",
        tags=["Org Hierarchy"],
        summary="Return effective organisation hierarchy nodes and edges for a run",
    )
    def org_hierarchy_snapshot(
        run_id: str,
        as_of_date: date | None = query(default=None),
    ) -> dict[str, object]:
        run = _require_run(result_store, run_id, http_exception_type)
        try:
            snapshot = list_org_hierarchy(
                sample_org_hierarchy(),
                as_of_date=as_of_date or run.as_of_date,
            )
        except ResultStoreContractError as exc:
            _raise_org_query_error(exc, http_exception_type)
        return cast(dict[str, object], _to_jsonable(snapshot))


def _register_org_hierarchy_node_routes(
    app: _RouteRegistrar,
    result_store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
    query: Any,
) -> None:
    @app.get(
        "/runs/{run_id:path}/org-hierarchy/nodes/{node_id}/children",
        tags=["Org Hierarchy"],
        summary="Return direct organisation hierarchy child nodes",
    )
    def org_hierarchy_children(
        run_id: str,
        node_id: str,
        as_of_date: date | None = query(default=None),
    ) -> dict[str, object]:
        run = _require_run(result_store, run_id, http_exception_type)
        try:
            children = org_node_children(
                sample_org_hierarchy(),
                node_id,
                as_of_date=as_of_date or run.as_of_date,
            )
        except ResultStoreContractError as exc:
            _raise_org_query_error(exc, http_exception_type)
        return {"nodes": _to_jsonable(children)}

    @app.get(
        "/runs/{run_id:path}/org-hierarchy/nodes/{node_id}/aggregate",
        tags=["Org Hierarchy"],
        summary="Return capital aggregate for one organisation hierarchy node",
    )
    def org_hierarchy_node_aggregate(
        run_id: str,
        node_id: str,
        as_of_date: date | None = query(default=None),
        framework: str | None = query(default=None),
        measure: str = query(default="capital"),
    ) -> dict[str, object]:
        run = _require_run(result_store, run_id, http_exception_type)
        try:
            result = aggregate_org_node(
                sample_org_capital_rows(run_id=run_id),
                sample_org_hierarchy(),
                run_id=run_id,
                node_id=node_id,
                as_of_date=as_of_date or run.as_of_date,
                framework=framework,
                measure=measure,
            )
        except ResultStoreContractError as exc:
            _raise_org_query_error(exc, http_exception_type)
        return cast(dict[str, object], _to_jsonable(result))

    @app.get(
        "/runs/{run_id:path}/org-hierarchy/nodes/{node_id}/source-rows",
        tags=["Org Hierarchy"],
        summary="Return paginated source rows backing an organisation hierarchy node",
    )
    def org_hierarchy_node_source_rows(
        run_id: str,
        node_id: str,
        as_of_date: date | None = query(default=None),
        framework: str | None = query(default=None),
        limit: int = query(default=100, ge=1, le=1000),
        offset: int = query(default=0, ge=0),
    ) -> dict[str, object]:
        run = _require_run(result_store, run_id, http_exception_type)
        try:
            page = source_rows_for_org_node(
                sample_org_capital_rows(run_id=run_id),
                sample_org_hierarchy(),
                run_id=run_id,
                node_id=node_id,
                as_of_date=as_of_date or run.as_of_date,
                framework=framework,
                limit=limit,
                offset=offset,
            )
        except ResultStoreContractError as exc:
            _raise_org_query_error(exc, http_exception_type)
        return cast(dict[str, object], _to_jsonable(page))


def _register_artifact_routes(
    app: _RouteRegistrar,
    result_store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
    query: Any,
    file_response_type: type[Any],
) -> None:
    @app.get(
        "/runs/{run_id:path}/artifacts",
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
        "/runs/{run_id:path}/artifacts/{artifact_id}/page",
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
        "/runs/{run_id:path}/artifacts/{artifact_id}/download",
        tags=["Artifacts"],
        summary="Download a local Parquet artifact or return an object-store URI handoff",
    )
    def artifact_download(run_id: str, artifact_id: str) -> object:
        _require_run(result_store, run_id, http_exception_type)
        ref = require_artifact_ref(result_store, run_id, artifact_id, http_exception_type)
        path = artifact_download_path(result_store, ref, http_exception_type)
        if path is None:
            unavailable = artifact_unavailable_payload(ref)
            if unavailable is not None:
                return {
                    "artifact": _to_jsonable(ref),
                    "mode": "artifact_unavailable",
                    **unavailable,
                }
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


def _register_run_detail_route(
    app: _RouteRegistrar,
    result_store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
) -> None:
    @app.get("/runs/{run_id:path}", tags=["Runs"], summary="Get one committed calculation run")
    def get_run(run_id: str) -> dict[str, object]:
        run = _require_run(result_store, run_id, http_exception_type)
        return _run_payload(result_store, run)


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


def _raise_org_query_error(
    exc: ResultStoreContractError,
    http_exception_type: type[Exception],
) -> NoReturn:
    status_code = 404 if exc.field == "node_id" else 422
    raise http_exception_type(status_code=status_code, detail=str(exc)) from exc  # type: ignore[call-arg]


def _raise_risk_factor_query_error(
    exc: ResultStoreContractError,
    http_exception_type: type[Exception],
) -> NoReturn:
    raise http_exception_type(status_code=422, detail=str(exc)) from exc  # type: ignore[call-arg]


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
