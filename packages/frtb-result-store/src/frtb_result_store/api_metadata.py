"""Artifact metadata routes for time-series, shocks, scenarios, and surfaces."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol

from frtb_result_store.api_metadata_helpers import (
    artifact_ref_for_partition_value,
    filtered_artifact_page,
    metadata_refs_payload,
)
from frtb_result_store.io import DuckDbParquetResultStore
from frtb_result_store.model import ArtifactType

_Endpoint = Callable[..., Any]
_RunGuard = Callable[[DuckDbParquetResultStore, str, type[Exception]], object]
_Jsonable = Callable[[object], object]


class _RouteRegistrar(Protocol):
    def get(
        self,
        path: str,
        *,
        tags: list[str] | None = None,
        summary: str | None = None,
        **kwargs: Any,
    ) -> Callable[[_Endpoint], _Endpoint]: ...


def register_artifact_metadata_routes(
    app: _RouteRegistrar,
    result_store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
    query: Any,
    *,
    require_run: _RunGuard,
    to_jsonable: _Jsonable,
) -> None:
    """Register typed artifact metadata routes on a read-only result-store app."""
    _register_time_series_metadata_routes(
        app, result_store, http_exception_type, query, require_run, to_jsonable
    )
    _register_shock_metadata_routes(
        app, result_store, http_exception_type, query, require_run, to_jsonable
    )
    _register_scenario_vector_metadata_routes(
        app, result_store, http_exception_type, query, require_run, to_jsonable
    )
    _register_surface_metadata_routes(
        app, result_store, http_exception_type, query, require_run, to_jsonable
    )


def _register_time_series_metadata_routes(
    app: _RouteRegistrar,
    result_store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
    query: Any,
    require_run: _RunGuard,
    to_jsonable: _Jsonable,
) -> None:
    @app.get(
        "/runs/{run_id:path}/time-series",
        tags=["Artifacts"],
        summary="Return time-series artifact references for a run",
    )
    def time_series_refs(run_id: str) -> dict[str, object]:
        require_run(result_store, run_id, http_exception_type)
        refs = result_store.artifact_refs(run_id, artifact_type=ArtifactType.TIME_SERIES)
        return metadata_refs_payload("time_series", refs, ("time_series_id",), to_jsonable)

    @app.get(
        "/runs/{run_id:path}/time-series/{time_series_id}/points",
        tags=["Artifacts"],
        summary="Return a deterministic page of time-series points",
    )
    def time_series_points(
        run_id: str,
        time_series_id: str,
        limit: int = query(default=100, ge=1, le=1000),
        offset: int = query(default=0, ge=0),
    ) -> dict[str, object]:
        require_run(result_store, run_id, http_exception_type)
        ref = artifact_ref_for_partition_value(
            result_store,
            run_id,
            ArtifactType.TIME_SERIES,
            "time_series_id",
            time_series_id,
            http_exception_type,
        )
        return filtered_artifact_page(
            result_store,
            ref,
            (f"time_series_id={time_series_id}",),
            limit,
            offset,
            http_exception_type,
            to_jsonable,
        )


def _register_shock_metadata_routes(
    app: _RouteRegistrar,
    result_store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
    query: Any,
    require_run: _RunGuard,
    to_jsonable: _Jsonable,
) -> None:
    @app.get(
        "/runs/{run_id:path}/shocks",
        tags=["Artifacts"],
        summary="Return shock definition artifact references for a run",
    )
    def shock_refs(run_id: str) -> dict[str, object]:
        require_run(result_store, run_id, http_exception_type)
        refs = result_store.artifact_refs(run_id, artifact_type=ArtifactType.SHOCK_DEFINITION)
        return metadata_refs_payload("shocks", refs, ("shock_id",), to_jsonable)

    @app.get(
        "/runs/{run_id:path}/shocks/{shock_id}",
        tags=["Artifacts"],
        summary="Return one shock definition page",
    )
    def shock_definition(
        run_id: str,
        shock_id: str,
        limit: int = query(default=100, ge=1, le=1000),
        offset: int = query(default=0, ge=0),
    ) -> dict[str, object]:
        require_run(result_store, run_id, http_exception_type)
        ref = artifact_ref_for_partition_value(
            result_store,
            run_id,
            ArtifactType.SHOCK_DEFINITION,
            "shock_id",
            shock_id,
            http_exception_type,
        )
        return filtered_artifact_page(
            result_store,
            ref,
            (f"shock_id={shock_id}",),
            limit,
            offset,
            http_exception_type,
            to_jsonable,
        )


def _register_scenario_vector_metadata_routes(
    app: _RouteRegistrar,
    result_store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
    query: Any,
    require_run: _RunGuard,
    to_jsonable: _Jsonable,
) -> None:
    @app.get(
        "/runs/{run_id:path}/scenario-vectors",
        tags=["Artifacts"],
        summary="Return scenario-vector metadata artifact references for a run",
    )
    def scenario_vector_refs(run_id: str) -> dict[str, object]:
        require_run(result_store, run_id, http_exception_type)
        refs = result_store.artifact_refs(
            run_id,
            artifact_type=ArtifactType.SCENARIO_VECTOR_METADATA,
        )
        return metadata_refs_payload(
            "scenario_vectors",
            refs,
            ("scenario_set_id", "scenario_vector_id"),
            to_jsonable,
        )

    @app.get(
        "/runs/{run_id:path}/scenario-vectors/{scenario_vector_id}/metadata",
        tags=["Artifacts"],
        summary="Return one scenario-vector metadata page",
    )
    def scenario_vector_metadata(
        run_id: str,
        scenario_vector_id: str,
        limit: int = query(default=100, ge=1, le=1000),
        offset: int = query(default=0, ge=0),
    ) -> dict[str, object]:
        require_run(result_store, run_id, http_exception_type)
        ref = artifact_ref_for_partition_value(
            result_store,
            run_id,
            ArtifactType.SCENARIO_VECTOR_METADATA,
            "scenario_vector_id",
            scenario_vector_id,
            http_exception_type,
        )
        return filtered_artifact_page(
            result_store,
            ref,
            (f"scenario_vector_id={scenario_vector_id}",),
            limit,
            offset,
            http_exception_type,
            to_jsonable,
        )


def _register_surface_metadata_routes(
    app: _RouteRegistrar,
    result_store: DuckDbParquetResultStore,
    http_exception_type: type[Exception],
    query: Any,
    require_run: _RunGuard,
    to_jsonable: _Jsonable,
) -> None:
    @app.get(
        "/runs/{run_id:path}/surfaces",
        tags=["Artifacts"],
        summary="Return surface-grid artifact references for a run",
    )
    def surface_refs(run_id: str) -> dict[str, object]:
        require_run(result_store, run_id, http_exception_type)
        refs = result_store.artifact_refs(run_id, artifact_type=ArtifactType.SURFACE_GRID)
        return metadata_refs_payload("surfaces", refs, ("surface_id",), to_jsonable)

    @app.get(
        "/runs/{run_id:path}/surfaces/{surface_id}/slice",
        tags=["Artifacts"],
        summary="Return one deterministic surface-grid slice",
    )
    def surface_slice(
        run_id: str,
        surface_id: str,
        axis_1_value: str | None = None,
        axis_2_value: str | None = None,
        limit: int = query(default=100, ge=1, le=1000),
        offset: int = query(default=0, ge=0),
    ) -> dict[str, object]:
        require_run(result_store, run_id, http_exception_type)
        ref = artifact_ref_for_partition_value(
            result_store,
            run_id,
            ArtifactType.SURFACE_GRID,
            "surface_id",
            surface_id,
            http_exception_type,
        )
        filters = [f"surface_id={surface_id}"]
        if axis_1_value is not None:
            filters.append(f"axis_1_value={axis_1_value}")
        if axis_2_value is not None:
            filters.append(f"axis_2_value={axis_2_value}")
        return filtered_artifact_page(
            result_store,
            ref,
            tuple(filters),
            limit,
            offset,
            http_exception_type,
            to_jsonable,
        )
