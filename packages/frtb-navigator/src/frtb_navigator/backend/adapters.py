"""Dashboard data-source adapter contracts and source selection."""

from __future__ import annotations

from typing import Protocol

from fastapi import HTTPException

from frtb_navigator.backend.models import (
    GridView,
    InspectorView,
    MetadataView,
    RunOverviewView,
    RunSummary,
)


class DashboardDataAdapter(Protocol):
    """Read model boundary shared by demo and result-store Navigator sources."""

    source: str

    def list_runs(self) -> list[RunSummary]:
        """Return runs available to the Navigator source.

        Returns
        -------
        list[RunSummary]
            Run catalogue entries exposed by the adapter.
        """

    def run_overview(
        self,
        run_id: str,
        *,
        hierarchy_node_id: str = "toh",
    ) -> RunOverviewView:
        """Return top-of-house overview for one run.

        Parameters
        ----------
        run_id
            Source-local run identifier.
        hierarchy_node_id
            Requested hierarchy scope.

        Returns
        -------
        RunOverviewView
            Overview totals and capital tree nodes.
        """

    def metadata(self, run_id: str) -> MetadataView:
        """Return navigation metadata for one run.

        Parameters
        ----------
        run_id
            Source-local run identifier.

        Returns
        -------
        MetadataView
            Metadata dimensions and run context.
        """

    def grid(
        self,
        run_id: str,
        *,
        framework: str = "SA",
        grouping: str | None = None,
        scenario: str = "Binding",
        hierarchy_node_id: str = "toh",
    ) -> GridView:
        """Return aggregate grid rows for one run.

        Parameters
        ----------
        run_id
            Source-local run identifier.
        framework
            Requested framework view, such as SA, IMA, or CVA.
        grouping
            Optional grouping label.
        scenario
            Scenario selector for scenario-sensitive rows.
        hierarchy_node_id
            Requested hierarchy scope.

        Returns
        -------
        GridView
            Aggregate grid columns and rows.
        """

    def inspector(
        self,
        run_id: str,
        row_id: str,
        *,
        scenario: str = "Binding",
        hierarchy_node_id: str = "toh",
    ) -> InspectorView:
        """Return drill-through evidence for a grid row.

        Parameters
        ----------
        run_id
            Source-local run identifier.
        row_id
            Navigator grid row identifier.
        scenario
            Scenario selector for scenario-sensitive rows.
        hierarchy_node_id
            Requested hierarchy scope.

        Returns
        -------
        InspectorView
            Attribution, source rows, diagnostics, and inspector tab metadata.
        """


def normalize_source(source: str | None) -> str:
    """Normalize and validate a Navigator source selector.

    Parameters
    ----------
    source
        Raw source selector from an API query parameter.

    Returns
    -------
    str
        Canonical source key accepted by the adapter registry.
    """

    normalized = (source or "demo").strip().lower()
    if normalized in {"result_store", "resultstore"}:
        normalized = "result-store"
    if normalized not in {"demo", "result-store"}:
        raise HTTPException(
            status_code=422,
            detail="source must be one of: demo, result-store",
        )
    return normalized
