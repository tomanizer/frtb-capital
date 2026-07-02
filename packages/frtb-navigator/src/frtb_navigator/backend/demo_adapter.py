"""Demo-source adapter for the FRTB Navigator dashboard."""

from __future__ import annotations

from functools import lru_cache

from frtb_navigator.backend import demo_runs
from frtb_navigator.backend.models import (
    ArtifactCatalogRowView,
    ArtifactDetailView,
    ArtifactSummaryView,
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
        """Return the single in-memory demo run summary.

        Returns
        -------
        list[RunSummary]
            Demo run catalogue entries.
        """

        return [
            run.model_copy(update={"source": self.source}) for run in demo_runs.list_demo_runs()
        ]

    def run_overview(
        self,
        run_id: str,
        *,
        hierarchy_node_id: str = demo_runs.DEFAULT_HIERARCHY_NODE_ID,
    ) -> RunOverviewView:
        """Return demo overview totals scoped to a hierarchy node.

        Parameters
        ----------
        run_id
            Demo run identifier.
        hierarchy_node_id
            Requested hierarchy scope.

        Returns
        -------
        RunOverviewView
            Demo overview payload.
        """

        overview = demo_runs.run_overview(
            self._resolve_run(run_id),
            hierarchy_node_id=hierarchy_node_id,
        )
        return overview.model_copy(
            update={"run": overview.run.model_copy(update={"source": self.source})}
        )

    def metadata(self, run_id: str) -> MetadataView:
        """Return metadata for the in-memory demo run.

        Parameters
        ----------
        run_id
            Demo run identifier.

        Returns
        -------
        MetadataView
            Demo metadata payload.
        """

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
        """Return demo aggregate grid rows for the selected framework.

        Parameters
        ----------
        run_id
            Demo run identifier.
        framework
            Requested framework view.
        grouping
            Optional grouping selector.
        scenario
            Scenario selector.
        hierarchy_node_id
            Requested hierarchy scope.

        Returns
        -------
        GridView
            Demo aggregate grid payload.
        """

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
        """Return demo inspector payload for a selected aggregate row.

        Parameters
        ----------
        run_id
            Demo run identifier.
        row_id
            Selected grid row identifier.
        scenario
            Scenario selector.
        hierarchy_node_id
            Requested hierarchy scope.

        Returns
        -------
        InspectorView
            Demo inspector payload.
        """

        return demo_runs.inspector_view(
            self._resolve_run(run_id),
            row_id,
            scenario=scenario,
            hierarchy_node_id=hierarchy_node_id,
        )

    def artifact_summary(
        self,
        run_id: str,
        *,
        framework: str = "SA",
        scenario: str = "Binding",
        hierarchy_node_id: str = demo_runs.DEFAULT_HIERARCHY_NODE_ID,
        row_id: str | None = None,
    ) -> ArtifactSummaryView:
        """Return explicit artifact no-data state for the in-memory demo source.

        Parameters
        ----------
        run_id
            Demo run identifier.
        framework
            Requested framework view.
        scenario
            Scenario selector.
        hierarchy_node_id
            Requested hierarchy scope.
        row_id
            Optional selected row.

        Returns
        -------
        ArtifactSummaryView
            Empty artifact catalogue with an explicit no-data row.
        """

        self._resolve_run(run_id)
        artifact = ArtifactCatalogRowView(
            artifact_id="demo-artifact-evidence-no-data",
            artifact_type="OTHER",
            component=framework.upper(),
            label="Demo source artifact evidence",
            role="demo_artifact_evidence",
            status="NO_DATA",
            status_reason="Artifact evidence is available only from the result-store fixture.",
            linked_to_selection=True,
        )
        return ArtifactSummaryView(
            run_id=run_id,
            source=self.source,
            data_state="demo fixture",
            framework=framework.upper(),
            scenario=scenario,
            hierarchy_node_id=hierarchy_node_id,
            selected_row_id=row_id,
            status_counts={"AVAILABLE": 0, "NO_DATA": 1, "UNSUPPORTED": 0},
            no_data=[artifact],
            linked_artifact_ids=[artifact.artifact_id],
        )

    def artifact_detail(
        self,
        run_id: str,
        artifact_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> ArtifactDetailView:
        """Return the demo artifact no-data detail payload.

        Parameters
        ----------
        run_id
            Demo run identifier.
        artifact_id
            Demo artifact identifier.
        limit
            Requested row limit.
        offset
            Requested row offset.

        Returns
        -------
        ArtifactDetailView
            Explicit no-data artifact detail.
        """

        self._resolve_run(run_id)
        if artifact_id != "demo-artifact-evidence-no-data":
            raise KeyError(f"Unknown demo artifact {artifact_id}")
        artifact = ArtifactCatalogRowView(
            artifact_id=artifact_id,
            artifact_type="OTHER",
            component="DEMO",
            label="Demo source artifact evidence",
            role="demo_artifact_evidence",
            status="NO_DATA",
            status_reason="Artifact evidence is available only from the result-store fixture.",
        )
        return ArtifactDetailView(
            run_id=run_id,
            source=self.source,
            data_state="demo fixture",
            artifact=artifact,
            mode="artifact_unavailable",
            limit=limit,
            offset=offset,
            row_count=0,
            filtered_row_count=0,
            returned=0,
        )
