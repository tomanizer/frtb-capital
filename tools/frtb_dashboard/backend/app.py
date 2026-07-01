"""FastAPI application for the FRTB Capital Navigator dashboard."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from tools.frtb_dashboard.backend.demo_runs import (
    DEMO_RUN_ID,
    DashboardRun,
    build_demo_run,
    grid_view,
    ima_desk_view,
    inspector_view,
    list_demo_runs,
    metadata_view,
    node_detail,
    run_overview,
    sa_overview,
)
from tools.frtb_dashboard.backend.models import (
    GridView,
    ImaDeskView,
    InspectorView,
    MetadataView,
    NodeDetailView,
    RunOverviewView,
    RunSummary,
    SaOverviewView,
)

FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"

app = FastAPI(
    title="FRTB Capital Navigator Viewer",
    description="Read-only high-density viewer for fixture-backed FRTB capital results.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def _demo_run() -> DashboardRun:
    return build_demo_run()


def _resolve_run(run_id: str) -> DashboardRun:
    if run_id != DEMO_RUN_ID:
        raise HTTPException(status_code=404, detail=f"Unknown run {run_id}")
    return _demo_run()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "demo", "app": "frtb-capital-navigator"}


@app.get("/api/runs", response_model=list[RunSummary])
def get_runs() -> list[RunSummary]:
    return list_demo_runs()


@app.get("/api/runs/{run_id}", response_model=RunOverviewView)
def get_run(
    run_id: str,
    hierarchy_node_id: str = Query("toh", alias="hierarchyNodeId"),
) -> RunOverviewView:
    try:
        return run_overview(_resolve_run(run_id), hierarchy_node_id=hierarchy_node_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/runs/{run_id}/metadata", response_model=MetadataView)
def get_metadata(run_id: str) -> MetadataView:
    return metadata_view(_resolve_run(run_id))


@app.get("/api/runs/{run_id}/grid", response_model=GridView)
def get_grid(
    run_id: str,
    framework: str = Query("SA", pattern="^(SA|IMA|CVA|sa|ima|cva)$"),
    grouping: str | None = None,
    scenario: str = "Binding",
    hierarchy_node_id: str = Query("toh", alias="hierarchyNodeId"),
) -> GridView:
    try:
        return grid_view(
            _resolve_run(run_id),
            framework=framework,
            grouping=grouping,
            scenario=scenario,
            hierarchy_node_id=hierarchy_node_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/runs/{run_id}/inspector", response_model=InspectorView)
def get_inspector(
    run_id: str,
    row_id: str,
    scenario: str = "Binding",
    hierarchy_node_id: str = Query("toh", alias="hierarchyNodeId"),
) -> InspectorView:
    try:
        return inspector_view(
            _resolve_run(run_id),
            row_id,
            scenario=scenario,
            hierarchy_node_id=hierarchy_node_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/runs/{run_id}/nodes/{node_id}", response_model=NodeDetailView)
def get_node(run_id: str, node_id: str) -> NodeDetailView:
    try:
        return node_detail(_resolve_run(run_id), node_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/runs/{run_id}/ima/desks/{desk_id}", response_model=ImaDeskView)
def get_ima_desk(run_id: str, desk_id: str) -> ImaDeskView:
    try:
        return ima_desk_view(_resolve_run(run_id), desk_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/runs/{run_id}/sa", response_model=SaOverviewView)
def get_sa(run_id: str) -> SaOverviewView:
    return sa_overview(_resolve_run(run_id))


if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    def spa_index() -> FileResponse:
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = (FRONTEND_DIST / full_path).resolve()
        if (
            str(candidate).startswith(str(FRONTEND_DIST))
            and candidate.exists()
            and candidate.is_file()
        ):
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
