"""Demo-source adapter for the FRTB Capital Navigator dashboard."""

from __future__ import annotations

from functools import lru_cache

from tools.frtb_dashboard.backend import demo_runs
from tools.frtb_dashboard.backend.models import (
    GridView,
    InspectorView,
    MetadataView,
    RunOverviewView,
    RunSummary,
)


class DemoRunAdapter:
    """Expose the existing in-memory fixture through the adapter protocol."""

    source = "demo"

    @lru_cache(maxsize=1)
    def _run(self) -> demo_runs.DashboardRun:
        return demo_runs.build_demo_run()

    def _resolve_run(self, run_id: str) -> demo_runs.DashboardRun:
        if run_id != demo_runs.DEMO_RUN_ID:
            raise KeyError(f"Unknown run {run_id}")
        return self._run()

    def list_runs(self) -> list[RunSummary]:
        return [
            run.model_copy(update={"source": self.source}) for run in demo_runs.list_demo_runs()
        ]

    def run_overview(
        self,
        run_id: str,
        *,
        hierarchy_node_id: str = demo_runs.DEFAULT_HIERARCHY_NODE_ID,
    ) -> RunOverviewView:
        overview = demo_runs.run_overview(
            self._resolve_run(run_id),
            hierarchy_node_id=hierarchy_node_id,
        )
        return overview.model_copy(
            update={"run": overview.run.model_copy(update={"source": self.source})}
        )

    def metadata(self, run_id: str) -> MetadataView:
        return demo_runs.metadata_view(self._resolve_run(run_id)).model_copy(
            update={"source": self.source, "data_state": "demo fixture"}
        )

    def grid(
        self,
        run_id: str,
        *,
        framework: str = "SA",
        grouping: str | None = None,
        scenario: str = "Binding",
        hierarchy_node_id: str = demo_runs.DEFAULT_HIERARCHY_NODE_ID,
    ) -> GridView:
        return demo_runs.grid_view(
            self._resolve_run(run_id),
            framework=framework,
            grouping=grouping,
            scenario=scenario,
            hierarchy_node_id=hierarchy_node_id,
        ).model_copy(update={"source": self.source, "data_state": "demo fixture"})

    def inspector(
        self,
        run_id: str,
        row_id: str,
        *,
        scenario: str = "Binding",
        hierarchy_node_id: str = demo_runs.DEFAULT_HIERARCHY_NODE_ID,
    ) -> InspectorView:
        return demo_runs.inspector_view(
            self._resolve_run(run_id),
            row_id,
            scenario=scenario,
            hierarchy_node_id=hierarchy_node_id,
        )
