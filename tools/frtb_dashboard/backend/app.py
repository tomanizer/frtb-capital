"""FastAPI application for the FRTB capital dashboard."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from tools.frtb_dashboard.backend.demo_runs import (
    DEMO_RUN_ID,
    DashboardRun,
    build_demo_run,
    ima_desk_view,
    list_demo_runs,
    node_detail,
    run_overview,
    sa_overview,
)
from tools.frtb_dashboard.backend.models import (
    ImaDeskView,
    NodeDetailView,
    RunOverviewView,
    RunSummary,
    SaOverviewView,
)

FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"

app = FastAPI(
    title="FRTB Capital Dashboard",
    description="Explore IMA and SA capital results with attribution drill-down.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
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
    return {"status": "ok", "mode": "demo"}


@app.get("/api/runs", response_model=list[RunSummary])
def get_runs() -> list[RunSummary]:
    return list_demo_runs()


@app.get("/api/runs/{run_id}", response_model=RunOverviewView)
def get_run(run_id: str) -> RunOverviewView:
    return run_overview(_resolve_run(run_id))


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
        candidate = (FRONTEND_DIST / full_path).resolve()
        if (
            str(candidate).startswith(str(FRONTEND_DIST))
            and candidate.exists()
            and candidate.is_file()
        ):
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
