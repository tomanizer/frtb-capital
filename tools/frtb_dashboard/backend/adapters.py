"""Dashboard data-source adapter contracts and source selection."""

from __future__ import annotations

from typing import Protocol

from fastapi import HTTPException

from tools.frtb_dashboard.backend.models import (
    GridView,
    InspectorView,
    MetadataView,
    RunOverviewView,
    RunSummary,
)


class DashboardDataAdapter(Protocol):
    """Read model boundary shared by demo and result-store dashboard sources."""

    source: str

    def list_runs(self) -> list[RunSummary]:
        """Return runs available to the dashboard source."""

    def run_overview(
        self,
        run_id: str,
        *,
        hierarchy_node_id: str = "toh",
    ) -> RunOverviewView:
        """Return top-of-house overview for one run."""

    def metadata(self, run_id: str) -> MetadataView:
        """Return navigation metadata for one run."""

    def grid(
        self,
        run_id: str,
        *,
        framework: str = "SA",
        grouping: str | None = None,
        scenario: str = "Binding",
        hierarchy_node_id: str = "toh",
    ) -> GridView:
        """Return aggregate grid rows for one run."""

    def inspector(
        self,
        run_id: str,
        row_id: str,
        *,
        scenario: str = "Binding",
        hierarchy_node_id: str = "toh",
    ) -> InspectorView:
        """Return drill-through evidence for a grid row."""


def normalize_source(source: str | None) -> str:
    """Normalize and validate a dashboard source selector."""

    normalized = (source or "demo").strip().lower()
    if normalized in {"result_store", "resultstore"}:
        normalized = "result-store"
    if normalized not in {"demo", "result-store"}:
        raise HTTPException(
            status_code=422,
            detail="source must be one of: demo, result-store",
        )
    return normalized
