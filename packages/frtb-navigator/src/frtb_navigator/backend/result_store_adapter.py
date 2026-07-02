"""Result-store backed adapter for the FRTB Navigator dashboard."""

from __future__ import annotations

import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
from functools import cached_property, lru_cache
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from frtb_result_store import ArtifactRef, ArtifactType, DuckDbParquetResultStore
from frtb_result_store.api_artifacts import artifact_page_payload

from frtb_navigator.backend.models import (
    ArtifactCatalogRowView,
    ArtifactDetailView,
    ArtifactSummaryView,
    AttributionRowView,
    AuditRowView,
    CapitalNodeView,
    DiagnosticView,
    DimensionNodeView,
    GridColumnView,
    GridRowView,
    GridView,
    InspectorTabView,
    InspectorView,
    MetadataView,
    RunOverviewView,
    RunSummary,
)

SOURCE = "result-store"
DATA_STATE = "result-store fixture"
_DASHBOARD_RUN_ID = "capital-navigator-2026-06-03-us-npr"
_STORE_RUN_ID = "frtb/capital-navigator/2026-06-03/us-npr"
_DEFAULT_NODE_ID = "toh"
_COMPONENT_LABELS = {
    "SA": "Standardised Approach",
    "SBM": "SBM",
    "DRC": "DRC",
    "RRAO": "RRAO",
    "IMA": "IMA",
    "CVA": "CVA",
}
_SA_NODE_IDS = {"sa", "sbm", "drc", "rrao"}
_IMA_NODE_IDS = {"ima"}
_ARTIFACT_KIND_BY_TYPE = {
    ArtifactType.TIME_SERIES.value: "timelines",
    ArtifactType.SHOCK_DEFINITION.value: "shocks",
    ArtifactType.SCENARIO_VECTOR_METADATA.value: "scenarios",
    ArtifactType.SURFACE_GRID.value: "surfaces",
}
_ARTIFACT_LABELS = {
    "rfet_observations": "RFET observations",
    "rfet_extended_observations": "Extended RFET history",
    "plat_upl": "UPL time series",
    "stress_period_losses": "Stress-period losses",
    "sbm_curvature_shock": "SBM curvature shock",
    "ima_scenario_vector": "IMA scenario metadata",
    "sbm_vega_surface": "USD swaption vol surface",
    "cva_full_vol_surface": "CVA volatility surface",
}


@dataclass(frozen=True)
class _RowContext:
    row: GridRowView
    store_node_id: str | None
    source_rows: tuple[dict[str, object], ...] = ()


class ResultStoreAdapter:
    """Map committed result-store fixtures into Navigator view models."""

    source = SOURCE

    @cached_property
    def store(self) -> DuckDbParquetResultStore:
        """Return the fixture-backed result store used by the adapter.

        Returns
        -------
        DuckDbParquetResultStore
            Local store populated from the committed Navigator fixture.
        """

        return _fixture_store()

    def _store_run_id(self, run_id: str) -> str:
        if run_id != _DASHBOARD_RUN_ID and run_id != _STORE_RUN_ID:
            raise KeyError(f"Unknown result-store run {run_id}")
        return _STORE_RUN_ID

    def list_runs(self) -> list[RunSummary]:
        """Return result-store runs exposed to Navigator.

        Returns
        -------
        list[RunSummary]
            Result-store run catalogue entries.
        """

        return [self._summary_for_run(run) for run in self.store.list_runs()]

    def run_overview(
        self,
        run_id: str,
        *,
        hierarchy_node_id: str = _DEFAULT_NODE_ID,
    ) -> RunOverviewView:
        """Return suite overview totals and capital nodes from result-store marts.

        Parameters
        ----------
        run_id
            Navigator or result-store run identifier.
        hierarchy_node_id
            Requested hierarchy scope.

        Returns
        -------
        RunOverviewView
            Overview payload mapped from persisted marts.
        """

        del hierarchy_node_id
        store_run_id = self._store_run_id(run_id)
        summary = self._summary_by_id(store_run_id)
        nodes = self._capital_nodes(store_run_id)
        amounts = self._component_amounts(store_run_id)
        suite_total = _float_or_none(summary.total_capital)
        sa_total = amounts.get("SA")
        ima_total = amounts.get("IMA")
        cva_total = amounts.get("CVA")
        return RunOverviewView(
            run=self._summary_for_run(self._run_by_id(store_run_id)),
            ima_total=ima_total,
            sa_total=sa_total,
            cva_total=cva_total,
            output_floor_total=None,
            binding_total=max(
                value for value in (sa_total, ima_total, cva_total) if value is not None
            ),
            binding_side="STORE",
            suite_total=suite_total,
            currency=summary.currency,
            nodes=nodes,
        )

    def metadata(self, run_id: str) -> MetadataView:
        """Return hierarchy and run metadata derived from persisted marts.

        Parameters
        ----------
        run_id
            Navigator or result-store run identifier.

        Returns
        -------
        MetadataView
            Metadata payload derived from result-store rows.
        """

        store_run_id = self._store_run_id(run_id)
        run = self._run_by_id(store_run_id)
        dimensions = [
            DimensionNodeView(
                node_id=_DEFAULT_NODE_ID,
                label="Top of house",
                dimension="Top of House",
                level=0,
                components=["IMA", "SA", "CVA"],
                child_ids=[],
            )
        ]
        tree = self.store.capital_tree_mart(store_run_id)
        seen: set[tuple[str, str, str | None]] = set()
        for row in tree:
            for dimension, attr in (
                ("Legal Entity", "metadata"),
                ("Desk", "desk_id"),
                ("Book", "book_id"),
            ):
                value = _dimension_value(row, dimension, attr)
                if not value:
                    continue
                key = (dimension, value, _component(row.component))
                if key in seen:
                    continue
                seen.add(key)
                dimensions.append(
                    DimensionNodeView(
                        node_id=_slug(f"{dimension}-{value}"),
                        parent_id=_DEFAULT_NODE_ID,
                        label=value,
                        dimension=dimension,
                        level=1,
                        filter={dimension.lower().replace(" ", "_"): value},
                        components=[_component(row.component)],
                    )
                )
        return MetadataView(
            run_id=_DASHBOARD_RUN_ID,
            source=self.source,
            data_state=DATA_STATE,
            dimensions=dimensions,
            reporting_dates=[run.as_of_date.isoformat()],
            baseline_dates=[],
            currencies=[run.base_currency],
        )

    def grid(
        self,
        run_id: str,
        *,
        framework: str = "SA",
        grouping: str | None = None,
        scenario: str = "Binding",
        hierarchy_node_id: str = _DEFAULT_NODE_ID,
    ) -> GridView:
        """Return result-store mart rows mapped into a Navigator grid.

        Parameters
        ----------
        run_id
            Navigator or result-store run identifier.
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
            Result-store-backed aggregate grid.
        """

        del hierarchy_node_id
        store_run_id = self._store_run_id(run_id)
        framework_key = framework.upper()
        if framework_key == "IMA":
            rows = self._ima_rows(store_run_id)
            columns = _ima_columns()
            grouping_label = grouping or "Desk > Evidence"
        elif framework_key == "CVA":
            rows = [
                _no_data_row(
                    "result-store-cva",
                    "CVA",
                    "CVA",
                    "CVA drill-through is not mapped in this issue.",
                )
            ]
            columns = _cva_columns()
            grouping_label = grouping or "Counterparty > Method"
        else:
            framework_key = "SA"
            rows = self._sa_rows(store_run_id, scenario=scenario)
            columns = _sa_columns()
            grouping_label = grouping or "Component > Risk Class / Bucket"
        return GridView(
            run_id=_DASHBOARD_RUN_ID,
            source=self.source,
            framework=framework_key,
            grouping=grouping_label,
            scenario=scenario,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            data_state=DATA_STATE,
        )

    def inspector(
        self,
        run_id: str,
        row_id: str,
        *,
        scenario: str = "Binding",
        hierarchy_node_id: str = _DEFAULT_NODE_ID,
    ) -> InspectorView:
        """Return drill-through details for a result-store-backed grid row.

        Parameters
        ----------
        run_id
            Navigator or result-store run identifier.
        row_id
            Selected grid row identifier.
        scenario
            Scenario selector.
        hierarchy_node_id
            Requested hierarchy scope.

        Returns
        -------
        InspectorView
            Inspector payload mapped from result-store evidence rows.
        """

        del hierarchy_node_id
        store_run_id = self._store_run_id(run_id)
        context = self._row_context(store_run_id, row_id, scenario=scenario)
        row = context.row
        node_id = context.store_node_id
        attribution = self._attribution_rows(store_run_id, node_id)
        audit_rows = self._audit_rows(store_run_id, context)
        diagnostics = self._diagnostics(store_run_id, context)
        reconciled = sum(1 for item in attribution if item.reconciliation_status == "reconciled")
        total = len(attribution)
        tabs = [
            InspectorTabView(key="attribution", label="Attribution", badge=str(total)),
            InspectorTabView(key="source", label="Source rows", badge=str(len(audit_rows))),
        ]
        if diagnostics:
            tabs.append(
                InspectorTabView(
                    key="diagnostics",
                    label="Diagnostics",
                    badge=str(len(diagnostics)),
                )
            )
        if row.framework == "IMA":
            tabs.append(InspectorTabView(key="backtesting", label="Backtesting"))
        return InspectorView(
            row_id=row.row_id,
            label=row.label,
            framework=row.framework,
            component=row.component,
            reconciliation={
                "coverage": 1.0 if total == 0 else reconciled / total,
                "rows_needing_review": total - reconciled,
                "status": "reconciled" if total == 0 or total == reconciled else "review",
            },
            tabs=tabs,
            attribution=attribution,
            audit_rows=audit_rows,
            diagnostics=diagnostics,
            extras={
                "source": self.source,
                "data_state": DATA_STATE,
                "store_run_id": store_run_id,
                "scenario_detail": {
                    "requested": scenario,
                    "persisted_binding": row.selected_scenario,
                },
                "backtesting": _ima_backtesting_extras(row),
            },
        )

    def artifact_summary(
        self,
        run_id: str,
        *,
        framework: str = "SA",
        scenario: str = "Binding",
        hierarchy_node_id: str = _DEFAULT_NODE_ID,
        row_id: str | None = None,
    ) -> ArtifactSummaryView:
        """Return result-store artifact evidence grouped for Navigator panes.

        Parameters
        ----------
        run_id
            Navigator or result-store run identifier.
        framework
            Requested framework view.
        scenario
            Scenario selector.
        hierarchy_node_id
            Requested hierarchy scope.
        row_id
            Optional selected aggregate row used for lineage highlighting.

        Returns
        -------
        ArtifactSummaryView
            Grouped artifact catalogue and status counts.
        """

        del hierarchy_node_id
        store_run_id = self._store_run_id(run_id)
        context = self._optional_row_context(store_run_id, row_id, scenario=scenario)
        refs = tuple(
            ref
            for ref in self.store.artifact_refs(store_run_id)
            if ArtifactType(ref.artifact_type).value in _ARTIFACT_KIND_BY_TYPE
        )
        catalog = [self._artifact_catalog_row(ref, context) for ref in refs]
        grouped: dict[str, list[ArtifactCatalogRowView]] = {
            "timelines": [],
            "shocks": [],
            "scenarios": [],
            "surfaces": [],
        }
        no_data: list[ArtifactCatalogRowView] = []
        for row in catalog:
            if row.status != "AVAILABLE":
                no_data.append(row)
            kind = _ARTIFACT_KIND_BY_TYPE.get(row.artifact_type)
            if kind is not None:
                grouped[kind].append(row)
        linked = [row.artifact_id for row in catalog if row.linked_to_selection]
        return ArtifactSummaryView(
            run_id=_DASHBOARD_RUN_ID,
            source=self.source,
            data_state=DATA_STATE,
            framework=framework.upper(),
            scenario=scenario,
            hierarchy_node_id=_DEFAULT_NODE_ID,
            selected_row_id=row_id,
            status_counts=_artifact_status_counts(catalog),
            timelines=grouped["timelines"],
            shocks=grouped["shocks"],
            scenarios=grouped["scenarios"],
            surfaces=grouped["surfaces"],
            no_data=no_data,
            linked_artifact_ids=linked,
        )

    def artifact_detail(
        self,
        run_id: str,
        artifact_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> ArtifactDetailView:
        """Return one bounded artifact page for Navigator rendering.

        Parameters
        ----------
        run_id
            Navigator or result-store run identifier.
        artifact_id
            Artifact identifier selected by the UI.
        limit
            Maximum number of rows to return.
        offset
            Zero-based row offset for paging.

        Returns
        -------
        ArtifactDetailView
            Artifact metadata and bounded page rows.
        """

        store_run_id = self._store_run_id(run_id)
        ref = self._artifact_ref(store_run_id, artifact_id)
        page = artifact_page_payload(
            self.store,
            ref,
            columns=None,
            filters=_default_artifact_filters(ref),
            limit=limit,
            offset=offset,
            http_exception_type=HTTPException,
            to_jsonable=_jsonable,
        )
        artifact = self._artifact_catalog_row(ref, None)
        return ArtifactDetailView(
            run_id=_DASHBOARD_RUN_ID,
            source=self.source,
            data_state=DATA_STATE,
            artifact=artifact,
            mode=str(page.get("mode", "")),
            limit=int(page.get("limit", limit)),
            offset=int(page.get("offset", offset)),
            row_count=_int_or_none(page.get("row_count")),
            filtered_row_count=_int_or_none(page.get("filtered_row_count")),
            returned=int(page.get("returned", 0)),
            next_offset=_int_or_none(page.get("next_offset")),
            columns=[str(column) for column in page.get("columns", [])],
            filters={str(key): str(value) for key, value in dict(page.get("filters", {})).items()},
            rows=[
                {str(key): _jsonable(value) for key, value in row.items()}
                for row in page.get("rows", [])
                if isinstance(row, dict)
            ],
        )

    def _summary_for_run(self, run: Any) -> RunSummary:
        components = sorted(self._component_amounts(run.run_id))
        return RunSummary(
            run_id=_DASHBOARD_RUN_ID,
            label="FRTB Navigator result-store fixture",
            calculation_date=run.as_of_date.isoformat(),
            profile_id=run.regime_id,
            base_currency=run.base_currency,
            source=self.source,
            jurisdiction_family=run.regime_id,
            components=components,
            input_hash=run.input_snapshot_id,
            prototype=False,
        )

    def _optional_row_context(
        self,
        store_run_id: str,
        row_id: str | None,
        *,
        scenario: str,
    ) -> _RowContext | None:
        if not row_id:
            return None
        try:
            return self._row_context(store_run_id, row_id, scenario=scenario)
        except KeyError:
            return None

    def _artifact_ref(self, store_run_id: str, artifact_id: str) -> ArtifactRef:
        for ref in self.store.artifact_refs(store_run_id):
            if ref.artifact_id == artifact_id:
                return ref
        raise KeyError(f"Unknown artifact {artifact_id}")

    def _artifact_catalog_row(
        self,
        ref: ArtifactRef,
        context: _RowContext | None,
    ) -> ArtifactCatalogRowView:
        artifact_type = ArtifactType(ref.artifact_type).value
        status = str(ref.metadata.get("artifact_status", "AVAILABLE"))
        partitions = _partition_values(ref)
        role = str(ref.metadata.get("navigator_role", ""))
        lineage = _artifact_lineage(self.store, ref.run_id, ref.artifact_id)
        return ArtifactCatalogRowView(
            artifact_id=ref.artifact_id,
            artifact_type=artifact_type,
            component=_component(ref.component),
            label=_artifact_label(ref, role, partitions),
            role=role,
            status=status,
            status_reason=str(ref.metadata.get("status_reason", "")),
            row_count=int(ref.row_count),
            schema_id=_str_or_none(ref.metadata.get("schema_id")),
            partition_values=partitions,
            lineage=lineage,
            linked_to_selection=_artifact_matches_context(ref, context, lineage),
        )

    def _run_by_id(self, store_run_id: str) -> Any:
        for run in self.store.list_runs():
            if run.run_id == store_run_id:
                return run
        raise KeyError(f"Unknown result-store run {store_run_id}")

    def _summary_by_id(self, store_run_id: str) -> Any:
        summaries = self.store.capital_summary(store_run_id)
        if not summaries:
            raise KeyError(f"Missing capital summary for {store_run_id}")
        return summaries[0]

    def _component_amounts(self, store_run_id: str) -> dict[str, float]:
        return {
            _component(row.component): float(row.amount)
            for row in self.store.component_breakdown(store_run_id)
        }

    def _capital_nodes(self, store_run_id: str) -> list[CapitalNodeView]:
        rows = list(self.store.capital_tree_mart(store_run_id))
        amounts = {
            measure.node_id: float(measure.amount)
            for row in rows
            for measure in self.store.measures_for_node(store_run_id, row.node_id)
            if measure.measure_name == "capital"
        }
        component_amounts = self._component_amounts(store_run_id)
        children: dict[str, list[str]] = {}
        for row in rows:
            if row.parent_node_id:
                children.setdefault(row.parent_node_id, []).append(row.node_id)
        return [
            CapitalNodeView(
                node_id=row.node_id,
                parent_id=row.parent_node_id,
                label=row.label,
                node_type=_enum_value(row.node_type),
                component=_component(row.component),
                amount=amounts.get(row.node_id, component_amounts.get(_component(row.component))),
                currency=self._summary_by_id(store_run_id).currency,
                child_ids=children.get(row.node_id, []),
            )
            for row in rows
        ]

    def _sa_rows(self, store_run_id: str, *, scenario: str) -> list[GridRowView]:
        tree = list(self.store.capital_tree_mart(store_run_id))
        amounts = _amounts_for_nodes(self.store, store_run_id)
        component_amounts = self._component_amounts(store_run_id)
        parent_amounts = {
            **amounts,
            **{key.lower(): value for key, value in component_amounts.items()},
        }
        rows: list[GridRowView] = []
        for node in tree:
            component = _component(node.component)
            if node.node_id not in _SA_NODE_IDS and component not in {"SBM", "DRC", "RRAO"}:
                continue
            amount = amounts.get(node.node_id, component_amounts.get(component))
            parent_amount = parent_amounts.get(node.parent_node_id or "")
            rows.append(
                GridRowView(
                    row_id=node.node_id,
                    parent_id=None if node.parent_node_id == "total" else node.parent_node_id,
                    label=node.label,
                    framework="SA",
                    component=component,
                    row_type=_enum_value(node.node_type),
                    level=max(0, int(node.depth) - 1),
                    group_path=_group_path(node),
                    currency=self._summary_by_id(store_run_id).currency,
                    capital=amount,
                    delta=_sbm_metric(self.store, store_run_id, node, "delta"),
                    vega=_sbm_metric(self.store, store_run_id, node, "vega"),
                    curvature=_sbm_metric(self.store, store_run_id, node, "curvature"),
                    base_rho=(
                        amount if component == "SBM" and scenario in {"Binding", "Base"} else None
                    ),
                    high_rho=amount if component == "SBM" else None,
                    low_rho=amount if component == "SBM" else None,
                    selected_scenario="Base" if component == "SBM" and amount is not None else None,
                    net_jtd=_drc_metric(self.store, store_run_id, node, "net_jtd"),
                    gross_jtd=None,
                    lgd=None,
                    pct_parent=_pct(amount, parent_amount),
                    status="ok" if amount is not None else "no_data",
                    no_data_reason=(
                        None
                        if amount is not None
                        else "Persisted fixture has no capital measure for this row."
                    ),
                    filter={
                        key: value
                        for key, value in {
                            "risk_class": node.risk_class,
                            "bucket": node.bucket,
                            "issuer_id": node.issuer_id,
                            "calculation_branch": node.calculation_branch,
                        }.items()
                        if value
                    },
                )
            )
        return rows

    def _ima_rows(self, store_run_id: str) -> list[GridRowView]:
        tree = list(self.store.capital_tree_mart(store_run_id))
        amounts = _amounts_for_nodes(self.store, store_run_id)
        component_amounts = self._component_amounts(store_run_id)
        rows: list[GridRowView] = []
        for node in tree:
            component = _component(node.component)
            if node.node_id not in _IMA_NODE_IDS and component != "IMA":
                continue
            amount = amounts.get(node.node_id, component_amounts.get(component))
            desk_row = _ima_mart_row(self.store, store_run_id, node)
            rows.append(
                GridRowView(
                    row_id=node.node_id,
                    parent_id=None if node.parent_node_id == "total" else node.parent_node_id,
                    label=node.label,
                    framework="IMA",
                    component="IMA",
                    row_type=_enum_value(node.node_type),
                    level=max(0, int(node.depth) - 1),
                    group_path=_group_path(node),
                    currency=self._summary_by_id(store_run_id).currency,
                    capital=amount,
                    imcc=amount if node.calculation_branch == "IMCC_CURRENT_ES" else None,
                    ses=(
                        amount
                        if node.calculation_branch and node.calculation_branch.startswith("SES_")
                        else None
                    ),
                    multiplier=(
                        _float_or_none(desk_row.get("supervisory_multiplier")) if desk_row else None
                    ),
                    pla_zone=_str_or_none(desk_row.get("pla_zone")) if desk_row else None,
                    backtest_zone=(
                        _str_or_none(desk_row.get("backtesting_zone")) if desk_row else None
                    ),
                    pct_parent=_pct(amount, component_amounts.get("IMA")),
                    filter={
                        key: value
                        for key, value in {
                            "desk_id": node.desk_id,
                            "book_id": node.book_id,
                            "calculation_branch": node.calculation_branch,
                        }.items()
                        if value
                    },
                )
            )
        if not rows:
            rows.append(
                _no_data_row(
                    "result-store-ima",
                    "IMA",
                    "IMA",
                    "No IMA fixture rows are available.",
                )
            )
        return rows

    def _row_context(self, store_run_id: str, row_id: str, *, scenario: str) -> _RowContext:
        for row in self._sa_rows(store_run_id, scenario=scenario) + self._ima_rows(store_run_id):
            if row.row_id == row_id:
                return _RowContext(
                    row=row,
                    store_node_id=row_id,
                    source_rows=self._source_rows_for_grid_row(store_run_id, row),
                )
        if row_id == "result-store-cva":
            return _RowContext(
                row=_no_data_row(
                    row_id,
                    "CVA",
                    "CVA",
                    "CVA drill-through is not mapped in this issue.",
                ),
                store_node_id="cva",
            )
        raise KeyError(f"Unknown grid row {row_id}")

    def _source_rows_for_grid_row(
        self,
        store_run_id: str,
        row: GridRowView,
    ) -> tuple[dict[str, object], ...]:
        if row.component == "SBM":
            rows = self.store.mart_rows(store_run_id, "sbm_bucket_ladder")
            return tuple(item for item in rows if _matches(item, row, ("risk_class", "bucket")))
        if row.component == "DRC":
            rows = self.store.mart_rows(store_run_id, "drc_issuer_contributors")
            issuer_id = row.filter.get("issuer_id")
            return tuple(
                item for item in rows if not issuer_id or item.get("issuer_id") == issuer_id
            )
        if row.component == "RRAO":
            rows = self.store.mart_rows(store_run_id, "rrao_exposure_summary")
            branch = row.filter.get("calculation_branch")
            return tuple(
                item for item in rows if not branch or item.get("exposure_class") == branch
            )
        if row.framework == "IMA":
            rows = self.store.mart_rows(store_run_id, "ima_desk_dashboard")
            desk_id = row.filter.get("desk_id")
            return tuple(item for item in rows if not desk_id or item.get("desk_id") == desk_id)
        return ()

    def _attribution_rows(
        self,
        store_run_id: str,
        node_id: str | None,
    ) -> list[AttributionRowView]:
        if node_id is None:
            return []
        rows = list(self.store.attributions_for_node(store_run_id, node_id))
        residual = self.store.residual_attribution_records(store_run_id, node_id=node_id)
        unsupported = self.store.unsupported_attribution_records(store_run_id, node_id=node_id)
        result = [
            AttributionRowView(
                contribution_id=row.attribution_id,
                component=_component(row.metadata.get("component", "")) or "",
                category=row.category,
                source_level=row.source_level,
                source_id=row.source_id,
                method=row.method,
                amount=_float_or_none(row.base_amount),
                contribution=_float_or_none(row.contribution),
                reconciliation_status="reconciled" if row.contribution is not None else "residual",
                reason=row.unsupported_reason or "",
            )
            for row in rows
        ]
        for projection in (*residual, *unsupported):
            result.append(
                AttributionRowView(
                    contribution_id=str(projection.get("attribution_id")),
                    component=str(projection.get("component", "")),
                    category=str(projection.get("category", "")),
                    source_level=str(projection.get("source_level", "")),
                    source_id=str(projection.get("source_id", "")),
                    method=str(projection.get("method", "")),
                    amount=_float_or_none(projection.get("base_amount")),
                    contribution=_float_or_none(projection.get("contribution")),
                    reconciliation_status=str(
                        projection.get("reconciliation_status", "no-data")
                    ).lower(),
                    reason=str(
                        projection.get("unsupported_reason") or projection.get("reason") or ""
                    ),
                )
            )
        return result

    def _audit_rows(self, store_run_id: str, context: _RowContext) -> list[AuditRowView]:
        if not context.source_rows:
            return []
        run = self._run_by_id(store_run_id)
        audit_rows = []
        for index, source_row in enumerate(context.source_rows[:100], start=1):
            audit_rows.append(
                AuditRowView(
                    row_id=f"{context.row.row_id}-source-{index}",
                    source_system=SOURCE,
                    source_id=str(
                        source_row.get("source_row_id")
                        or source_row.get("artifact_id")
                        or source_row.get("issuer_id")
                        or source_row.get("desk_id")
                        or index
                    ),
                    desk_id=_str_or_none(source_row.get("desk_id")),
                    book_id=_str_or_none(source_row.get("book_id")),
                    legal_entity=None,
                    risk_class=_str_or_none(source_row.get("risk_class")),
                    bucket=_str_or_none(
                        source_row.get("bucket") or source_row.get("exposure_class")
                    ),
                    metric=_source_metric(context.row, source_row),
                    value=_source_value(source_row),
                    currency=_str_or_none(source_row.get("currency")) or run.base_currency,
                    calculation_timestamp=run.created_at.isoformat(),
                    status="ok",
                    provenance="persisted result-store mart",
                )
            )
        return audit_rows

    def _diagnostics(self, store_run_id: str, context: _RowContext) -> list[DiagnosticView]:
        diagnostics = []
        if not context.source_rows:
            diagnostics.append(
                DiagnosticView(
                    code="NO_LINE_DETAIL",
                    severity="info",
                    message=(
                        "The fixture exposes aggregate capital for this row but no "
                        "bounded source-row mart detail."
                    ),
                )
            )
        for artifact in self.store.artifact_refs(store_run_id):
            status = artifact.metadata.get("artifact_status")
            if status in {"NO_DATA", "UNSUPPORTED"}:
                diagnostics.append(
                    DiagnosticView(
                        code=str(status),
                        severity="info",
                        message=(
                            f"{artifact.artifact_id}: "
                            f"{artifact.metadata.get('status_reason', 'artifact unavailable')}"
                        ),
                    )
                )
        return diagnostics


@lru_cache(maxsize=1)
def _fixture_store() -> DuckDbParquetResultStore:
    fixture_root = Path(tempfile.gettempdir()) / "frtb-navigator-result-store-fixture"
    store = DuckDbParquetResultStore(fixture_root)
    if any(run.run_id == _STORE_RUN_ID for run in store.list_runs()):
        return store
    if store.run_exists(_STORE_RUN_ID):
        shutil.rmtree(fixture_root, ignore_errors=True)
        store = DuckDbParquetResultStore(fixture_root)
    repo_root = Path(__file__).resolve().parents[5]
    fixture_tests = repo_root / "packages" / "frtb-result-store" / "tests"
    if str(fixture_tests) not in sys.path:
        sys.path.insert(0, str(fixture_tests))
    from fixtures.capital_navigator_bundle import capital_navigator_bundle

    bundle = capital_navigator_bundle(artifact_root=store.root / "navigator-artifacts")
    store.write_bundle(bundle)
    return store


def _amounts_for_nodes(store: DuckDbParquetResultStore, store_run_id: str) -> dict[str, float]:
    return {
        row.node_id: float(measure.amount)
        for row in store.capital_tree_mart(store_run_id)
        for measure in store.measures_for_node(store_run_id, row.node_id)
        if measure.measure_name == "capital"
    }


def _component(value: Any) -> str:
    text = _enum_value(value)
    return "SA" if text == "STANDARDISED_APPROACH" else text


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _str_or_none(value: Any) -> str | None:
    return None if value is None or value == "" else str(value)


def _pct(amount: float | None, parent_amount: float | None) -> float | None:
    if amount is None or parent_amount in (None, 0):
        return None
    return amount / parent_amount


def _group_path(row: Any) -> list[str]:
    return [
        item for item in (_component(row.component), row.risk_class, row.bucket, row.label) if item
    ]


def _slug(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


def _partition_values(ref: ArtifactRef) -> dict[str, str]:
    partitions = ref.metadata.get("partition_values")
    if not isinstance(partitions, dict):
        return {}
    return {str(key): str(value) for key, value in partitions.items()}


def _default_artifact_filters(ref: ArtifactRef) -> tuple[str, ...]:
    partitions = _partition_values(ref)
    return tuple(f"{key}={partitions[key]}" for key in ref.partition_keys if key in partitions)


def _artifact_label(
    ref: ArtifactRef,
    role: str,
    partitions: dict[str, str],
) -> str:
    base = _ARTIFACT_LABELS.get(role)
    if base:
        suffix = next(iter(partitions.values()), "")
        return f"{base} ({suffix})" if suffix else base
    artifact_type = ArtifactType(ref.artifact_type).value.replace("_", " ").title()
    suffix = next(iter(partitions.values()), ref.artifact_id)
    return f"{artifact_type} ({suffix})"


def _artifact_lineage(
    store: DuckDbParquetResultStore,
    store_run_id: str,
    artifact_id: str,
) -> dict[str, str]:
    for node in store.capital_tree_mart(store_run_id):
        for lineage in store.lineage_for_result(store_run_id, node.node_id):
            if lineage.source_type == "artifact" and lineage.source_id == artifact_id:
                return {
                    "result_id": lineage.result_id,
                    "relationship": lineage.relationship,
                    "source_type": lineage.source_type,
                    "source_id": lineage.source_id,
                }
    return {}


def _artifact_matches_context(
    ref: ArtifactRef,
    context: _RowContext | None,
    lineage: dict[str, str],
) -> bool:
    if context is None:
        return False
    if lineage.get("result_id") == context.store_node_id:
        return True
    component = _component(ref.component)
    if component in {context.row.component, context.row.framework}:
        return True
    rows = context.source_rows
    if not rows:
        return False
    partitions = _partition_values(ref)
    for source_row in rows:
        if source_row.get("artifact_id") == ref.artifact_id:
            return True
        for key in ("risk_factor_id", "source_row_id", "mapping_version"):
            if key in partitions and str(source_row.get(key)) == partitions[key]:
                return True
    return False


def _artifact_status_counts(rows: list[ArtifactCatalogRowView]) -> dict[str, int]:
    counts = {"AVAILABLE": 0, "NO_DATA": 0, "UNSUPPORTED": 0}
    for row in rows:
        counts.setdefault(row.status, 0)
        counts[row.status] += 1
    return counts


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "value"):
        return getattr(value, "value")
    if hasattr(value, "__dict__"):
        return _jsonable(value.__dict__)
    return value


def _dimension_value(row: Any, dimension: str, attr: str) -> str | None:
    if dimension == "Legal Entity":
        metadata = getattr(row, "metadata", {})
        value = metadata.get("legal_entity") if isinstance(metadata, dict) else None
        return _str_or_none(value)
    return _str_or_none(getattr(row, attr))


def _sa_columns() -> list[GridColumnView]:
    return [
        GridColumnView(key="capital", label="Capital"),
        GridColumnView(key="delta", label="Delta"),
        GridColumnView(key="vega", label="Vega"),
        GridColumnView(key="curvature", label="Curvature"),
        GridColumnView(key="base_rho", label="Base rho"),
        GridColumnView(key="high_rho", label="High rho"),
        GridColumnView(key="low_rho", label="Low rho"),
        GridColumnView(key="net_jtd", label="Net JTD"),
        GridColumnView(key="pct_parent", label="% parent", kind="percent"),
        GridColumnView(key="status", label="Status", kind="text"),
    ]


def _ima_columns() -> list[GridColumnView]:
    return [
        GridColumnView(key="capital", label="Capital"),
        GridColumnView(key="imcc", label="IMCC"),
        GridColumnView(key="ses", label="SES/NMRF"),
        GridColumnView(key="multiplier", label="Multiplier", kind="decimal"),
        GridColumnView(key="pla_zone", label="PLA zone", kind="text"),
        GridColumnView(key="backtest_zone", label="BT zone", kind="text"),
        GridColumnView(key="pct_parent", label="% IMA", kind="percent"),
    ]


def _cva_columns() -> list[GridColumnView]:
    return [
        GridColumnView(key="capital", label="Capital"),
        GridColumnView(key="status", label="Status", kind="text"),
    ]


def _no_data_row(row_id: str, framework: str, component: str, reason: str) -> GridRowView:
    return GridRowView(
        row_id=row_id,
        label=_COMPONENT_LABELS.get(component, component),
        framework=framework,
        component=component,
        row_type="NO_DATA",
        status="no_data",
        no_data_reason=reason,
    )


def _sbm_metric(
    store: DuckDbParquetResultStore,
    store_run_id: str,
    node: Any,
    metric: str,
) -> float | None:
    if _component(node.component) != "SBM":
        return None
    rows = store.mart_rows(store_run_id, "sbm_bucket_ladder")
    matching = [
        row for row in rows if _matches(row, _node_filter_proxy(node), ("risk_class", "bucket"))
    ]
    values = [_float_or_none(row.get(metric)) for row in matching]
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def _drc_metric(
    store: DuckDbParquetResultStore,
    store_run_id: str,
    node: Any,
    metric: str,
) -> float | None:
    if _component(node.component) != "DRC":
        return None
    rows = store.mart_rows(store_run_id, "drc_issuer_contributors")
    matching = [row for row in rows if not node.issuer_id or row.get("issuer_id") == node.issuer_id]
    values = [_float_or_none(row.get(metric)) for row in matching]
    present = [value for value in values if value is not None]
    return sum(present) if present else None


def _node_filter_proxy(node: Any) -> GridRowView:
    return GridRowView(
        row_id=node.node_id,
        label=node.label,
        framework="SA",
        component=_component(node.component),
        row_type=_enum_value(node.node_type),
        filter={
            key: value
            for key, value in {
                "risk_class": node.risk_class,
                "bucket": node.bucket,
                "issuer_id": node.issuer_id,
                "calculation_branch": node.calculation_branch,
                "desk_id": node.desk_id,
            }.items()
            if value
        },
    )


def _matches(row: dict[str, object], grid_row: GridRowView, keys: tuple[str, ...]) -> bool:
    return all(not grid_row.filter.get(key) or row.get(key) == grid_row.filter[key] for key in keys)


def _ima_mart_row(
    store: DuckDbParquetResultStore,
    store_run_id: str,
    node: Any,
) -> dict[str, object] | None:
    if not node.desk_id:
        return None
    for row in store.mart_rows(store_run_id, "ima_desk_dashboard"):
        if row.get("desk_id") == node.desk_id:
            return row
    return None


def _source_metric(row: GridRowView, source_row: dict[str, object]) -> str:
    if row.component == "DRC":
        return "net_jtd"
    if row.component == "RRAO":
        return "capital"
    if row.framework == "IMA":
        return "capital"
    if row.component == "SBM":
        return "capital"
    return str(next(iter(source_row), "value"))


def _source_value(source_row: dict[str, object]) -> float | None:
    for key in ("capital", "net_jtd", "pnl_amount", "sensitivity_amount", "amount"):
        value = _float_or_none(source_row.get(key))
        if value is not None:
            return value
    return None


def _ima_backtesting_extras(row: GridRowView) -> dict[str, object]:
    return {
        "pla_zone": row.pla_zone,
        "backtesting_zone": row.backtest_zone,
        "rfet_observation_ledger": "no-data diagnostic when not present in fixture",
        "es_liquidity_horizon_matrix": "no-data diagnostic when not present in fixture",
        "upl_time_series": "no-data diagnostic when not present in fixture",
    }
