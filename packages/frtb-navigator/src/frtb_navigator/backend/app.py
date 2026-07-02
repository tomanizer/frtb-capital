"""FastAPI application for the FRTB Navigator dashboard."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from frtb_navigator.backend.adapters import DashboardDataAdapter, normalize_source
from frtb_navigator.backend.demo_adapter import DemoRunAdapter
from frtb_navigator.backend.demo_runs import ima_desk_view, node_detail, sa_overview
from frtb_navigator.backend.models import (
    ArtifactDetailView,
    ArtifactSummaryView,
    GridView,
    ImaDeskView,
    InspectorView,
    MetadataView,
    NodeDetailView,
    RunOverviewView,
    RunSummary,
    SaOverviewView,
)
from frtb_navigator.backend.result_store_adapter import ResultStoreAdapter

FRONTEND_DIST = Path(__file__).resolve().parents[3] / "frontend" / "dist"

app = FastAPI(
    title="FRTB Navigator Viewer",
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


_DEMO_ADAPTER = DemoRunAdapter()
_ADAPTERS: dict[str, DashboardDataAdapter] = {
    "demo": _DEMO_ADAPTER,
    "result-store": ResultStoreAdapter(),
}


def _adapter(source: str | None) -> DashboardDataAdapter:
    return _ADAPTERS[normalize_source(source)]


@app.get("/api/health")
def health() -> dict[str, str]:
    """Return a lightweight health payload for the Navigator backend.

    Returns
    -------
    dict[str, str]
        Backend status and application mode.
    """

    return {"status": "ok", "mode": "multi-source", "app": "frtb-navigator"}


@app.get("/api/runs", response_model=list[RunSummary])
def get_runs(source: str = "demo") -> list[RunSummary]:
    """List runs available from the selected read-only source.

    Parameters
    ----------
    source
        Source selector, such as ``demo`` or ``result-store``.

    Returns
    -------
    list[RunSummary]
        Runs available from the selected source.
    """

    return _adapter(source).list_runs()


@app.get("/api/runs/{run_id}", response_model=RunOverviewView)
def get_run(
    run_id: str,
    source: str = "demo",
    hierarchy_node_id: str = Query("toh", alias="hierarchyNodeId"),
) -> RunOverviewView:
    """Return top-of-house overview totals and capital tree nodes for a run.

    Parameters
    ----------
    run_id
        Navigator run identifier.
    source
        Source selector, such as ``demo`` or ``result-store``.
    hierarchy_node_id
        Requested hierarchy scope.

    Returns
    -------
    RunOverviewView
        Overview totals and capital tree nodes.
    """

    try:
        return _adapter(source).run_overview(run_id, hierarchy_node_id=hierarchy_node_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/runs/{run_id}/metadata", response_model=MetadataView)
def get_metadata(run_id: str, source: str = "demo") -> MetadataView:
    """Return run metadata used by Navigator filters and context controls.

    Parameters
    ----------
    run_id
        Navigator run identifier.
    source
        Source selector, such as ``demo`` or ``result-store``.

    Returns
    -------
    MetadataView
        Metadata dimensions and context options.
    """

    try:
        return _adapter(source).metadata(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/runs/{run_id}/grid", response_model=GridView)
def get_grid(
    run_id: str,
    source: str = "demo",
    framework: str = Query("SA", pattern="^(SA|IMA|CVA|sa|ima|cva)$"),
    grouping: str | None = None,
    scenario: str = "Binding",
    hierarchy_node_id: str = Query("toh", alias="hierarchyNodeId"),
) -> GridView:
    """Return aggregate grid rows for one framework and scenario selection.

    Parameters
    ----------
    run_id
        Navigator run identifier.
    source
        Source selector, such as ``demo`` or ``result-store``.
    framework
        Requested framework view.
    grouping
        Optional grouping selector.
    scenario
        Scenario selector for scenario-sensitive rows.
    hierarchy_node_id
        Requested hierarchy scope.

    Returns
    -------
    GridView
        Aggregate grid payload.
    """

    try:
        return _adapter(source).grid(
            run_id,
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
    source: str = "demo",
    scenario: str = "Binding",
    hierarchy_node_id: str = Query("toh", alias="hierarchyNodeId"),
) -> InspectorView:
    """Return attribution, source rows, and diagnostics for one grid row.

    Parameters
    ----------
    run_id
        Navigator run identifier.
    row_id
        Selected grid row identifier.
    source
        Source selector, such as ``demo`` or ``result-store``.
    scenario
        Scenario selector for scenario-sensitive rows.
    hierarchy_node_id
        Requested hierarchy scope.

    Returns
    -------
    InspectorView
        Inspector tabs, attribution rows, source rows, and diagnostics.
    """

    try:
        return _adapter(source).inspector(
            run_id,
            row_id,
            scenario=scenario,
            hierarchy_node_id=hierarchy_node_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/runs/{run_id}/artifacts", response_model=ArtifactSummaryView)
def get_artifacts(
    run_id: str,
    source: str = "demo",
    framework: str = Query("SA", pattern="^(SA|IMA|CVA|sa|ima|cva)$"),
    scenario: str = "Binding",
    hierarchy_node_id: str = Query("toh", alias="hierarchyNodeId"),
    row_id: str | None = None,
) -> ArtifactSummaryView:
    """Return artifact evidence grouped for the Navigator evidence pane.

    Parameters
    ----------
    run_id
        Navigator run identifier.
    source
        Source selector, such as ``demo`` or ``result-store``.
    framework
        Requested framework view.
    scenario
        Scenario selector for scenario-sensitive rows.
    hierarchy_node_id
        Requested hierarchy scope.
    row_id
        Optional selected aggregate row.

    Returns
    -------
    ArtifactSummaryView
        Grouped artifact catalogue, no-data states, and selected-row links.
    """

    try:
        return _adapter(source).artifact_summary(
            run_id,
            framework=framework,
            scenario=scenario,
            hierarchy_node_id=hierarchy_node_id,
            row_id=row_id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/runs/{run_id}/artifacts/{artifact_id}", response_model=ArtifactDetailView)
def get_artifact_detail(
    run_id: str,
    artifact_id: str,
    source: str = "demo",
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> ArtifactDetailView:
    """Return a bounded artifact page through the Navigator backend.

    Parameters
    ----------
    run_id
        Navigator run identifier.
    artifact_id
        Artifact selected by the UI.
    source
        Source selector, such as ``demo`` or ``result-store``.
    limit
        Maximum rows to return.
    offset
        Zero-based row offset.

    Returns
    -------
    ArtifactDetailView
        Artifact metadata and bounded page rows.
    """

    try:
        return _adapter(source).artifact_detail(
            run_id,
            artifact_id,
            limit=limit,
            offset=offset,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/runs/{run_id}/nodes/{node_id}", response_model=NodeDetailView)
def get_node(run_id: str, node_id: str) -> NodeDetailView:
    """Return detail measures for a demo-source capital tree node.

    Parameters
    ----------
    run_id
        Navigator run identifier.
    node_id
        Capital tree node identifier.

    Returns
    -------
    NodeDetailView
        Node measures and attribution rows.
    """

    try:
        return node_detail(_DEMO_ADAPTER._resolve_run(run_id), node_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/runs/{run_id}/ima/desks/{desk_id}", response_model=ImaDeskView)
def get_ima_desk(run_id: str, desk_id: str) -> ImaDeskView:
    """Return demo-source IMA desk evidence for a selected desk.

    Parameters
    ----------
    run_id
        Navigator run identifier.
    desk_id
        IMA desk identifier.

    Returns
    -------
    ImaDeskView
        Desk-level IMA evidence.
    """

    try:
        return ima_desk_view(_DEMO_ADAPTER._resolve_run(run_id), desk_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/runs/{run_id}/sa", response_model=SaOverviewView)
def get_sa(run_id: str) -> SaOverviewView:
    """Return demo-source Standardised Approach component overview.

    Parameters
    ----------
    run_id
        Navigator run identifier.

    Returns
    -------
    SaOverviewView
        Standardised Approach component overview.
    """

    return sa_overview(_DEMO_ADAPTER._resolve_run(run_id))


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
        if candidate.is_relative_to(FRONTEND_DIST) and candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
