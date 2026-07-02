"""Build fixture-backed Navigator views from public package demos."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

import frtb_drc
import frtb_rrao
from frtb_common import jsonable
from frtb_common.attribution import CapitalContribution
from frtb_drc.demo_fixture import load_drc_nonsec_v2_fixture
from frtb_drc.demo_fixture import run_fixture_workflow as run_drc_fixture_workflow
from frtb_ima import desk_contributions
from frtb_ima.audit import DeskAuditRecord
from frtb_ima.capital_run_fixture import (
    input_hash_for_capital_run_fixture,
    load_capital_run_v1_fixture,
    run_capital_run_fixture_workflow,
)
from frtb_orchestration import compose_standardised_approach_capital
from frtb_sbm import (
    SbmCalculationContext,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    calculate_sbm_attribution,
    calculate_sbm_capital,
)
from frtb_sbm import to_component_summary as sbm_to_component_summary

from frtb_navigator.backend._rrao_fixture import load_rrao_context, load_rrao_positions
from frtb_navigator.backend.models import (
    AttributionRowView,
    AuditRowView,
    CapitalNodeView,
    DiagnosticView,
    DimensionNodeView,
    GridColumnView,
    GridRowView,
    GridView,
    ImaDeskView,
    InspectorTabView,
    InspectorView,
    MeasureView,
    MetadataView,
    NodeDetailView,
    RunOverviewView,
    RunSummary,
    SaComponentView,
    SaOverviewView,
)

DEMO_RUN_ID = "demo-suite-001"
# Non-regulatory demo display multiplier. It matches the current
# frtb-orchestration scope-view default so the dashboard fixture and
# orchestration examples tell the same synthetic story; production Navigator
# views should consume the resolved floor multiplier from result-store or
# orchestration payloads rather than hard-coding this value.
OUTPUT_FLOOR_MULTIPLIER = 0.725
DEFAULT_HIERARCHY_NODE_ID = "toh"


@dataclass(frozen=True)
class HierarchyNodeSpec:
    """Synthetic hierarchy node used by the demo Navigator source."""

    node_id: str
    parent_id: str | None
    label: str
    dimension: str
    level: int
    components: tuple[str, ...]
    filter: Mapping[str, str]


HIERARCHY_SPECS: tuple[HierarchyNodeSpec, ...] = (
    HierarchyNodeSpec(
        "toh",
        None,
        "Top of house",
        "Top of House",
        0,
        ("IMA", "SBM", "DRC", "RRAO"),
        {"scope": "firm"},
    ),
    HierarchyNodeSpec(
        "le-demo",
        "toh",
        "LE-DEMO",
        "Legal Entity",
        1,
        ("IMA", "SBM", "DRC", "RRAO"),
        {"legal_entity": "LE-DEMO"},
    ),
    HierarchyNodeSpec(
        "division-ficc",
        "le-demo",
        "FICC",
        "Division",
        2,
        ("IMA", "SBM", "DRC", "RRAO"),
        {"division": "FICC"},
    ),
    HierarchyNodeSpec(
        "business-line-rates",
        "division-ficc",
        "Rates",
        "Business Line",
        3,
        ("IMA", "SBM"),
        {"business_line": "Rates"},
    ),
    HierarchyNodeSpec(
        "desk-rates-credit-demo",
        "business-line-rates",
        "Rates credit demo",
        "Desk",
        4,
        ("IMA", "SBM"),
        {"desk_id": "rates-credit-demo"},
    ),
    HierarchyNodeSpec(
        "volcker-rates-credit-demo",
        "desk-rates-credit-demo",
        "Volcker rates credit",
        "Volcker Desk",
        5,
        ("IMA", "SBM"),
        {"volcker_desk_id": "volcker-rates-credit-demo"},
    ),
    HierarchyNodeSpec(
        "book-rates-fixture",
        "volcker-rates-credit-demo",
        "Rates fixture book",
        "Book",
        6,
        ("IMA", "SBM"),
        {"book_id": "BOOK-RATES-FIXTURE"},
    ),
    HierarchyNodeSpec(
        "business-line-credit",
        "division-ficc",
        "Credit",
        "Business Line",
        3,
        ("DRC",),
        {"business_line": "Credit"},
    ),
    HierarchyNodeSpec(
        "desk-credit-default-risk",
        "business-line-credit",
        "Credit default risk",
        "Desk",
        4,
        ("DRC",),
        {"desk_id": "credit-default-risk"},
    ),
    HierarchyNodeSpec(
        "book-credit-fixture",
        "desk-credit-default-risk",
        "Credit fixture book",
        "Book",
        5,
        ("DRC",),
        {"book_id": "BOOK-CREDIT-FIXTURE"},
    ),
    HierarchyNodeSpec(
        "business-line-residual",
        "division-ficc",
        "Residual risk",
        "Business Line",
        3,
        ("RRAO",),
        {"business_line": "Residual Risk"},
    ),
    HierarchyNodeSpec(
        "desk-residual-risk",
        "business-line-residual",
        "Residual risk desk",
        "Desk",
        4,
        ("RRAO",),
        {"desk_id": "residual-risk"},
    ),
    HierarchyNodeSpec(
        "book-residual-fixture",
        "desk-residual-risk",
        "Residual fixture book",
        "Book",
        5,
        ("RRAO",),
        {"book_id": "BOOK-RESIDUAL-FIXTURE"},
    ),
)


@dataclass(frozen=True)
class ScopeTotals:
    """Scoped IMA and Standardised Approach totals for demo hierarchy nodes."""

    ima: float
    sbm: float
    drc: float
    rrao: float

    @property
    def sa(self) -> float:
        """Return the Standardised Approach total for the scope.

        Returns
        -------
        float
            SBM, DRC, and RRAO total.
        """

        return self.sbm + self.drc + self.rrao

    @property
    def output_floor(self) -> float:
        """Return the demo output-floor amount for the scope.

        Returns
        -------
        float
            Demo output-floor amount.
        """

        return OUTPUT_FLOOR_MULTIPLIER * self.sa

    @property
    def binding(self) -> float:
        """Return the binding demo capital amount for the scope.

        Returns
        -------
        float
            Binding amount between IMA and the demo output floor.
        """

        return max(self.ima, self.output_floor)


@dataclass(frozen=True)
class DashboardRun:
    """In-memory synthetic run and component results backing the demo source."""

    summary: RunSummary
    nodes: tuple[CapitalNodeView, ...]
    desk_record: DeskAuditRecord
    ima_workflow: dict[str, object]
    drc_result: frtb_drc.DrcCapitalResult
    rrao_result: frtb_rrao.RraoCapitalResult
    sbm_result: Any
    sa_result: Any


def list_demo_runs() -> list[RunSummary]:
    """Return the catalogue of synthetic demo runs.

    Returns
    -------
    list[RunSummary]
        Demo run summaries.
    """

    run = build_demo_run()
    return [run.summary]


def build_demo_run() -> DashboardRun:
    """Build the synthetic cross-component demo run for Navigator views.

    Returns
    -------
    DashboardRun
        In-memory demo run containing component results and tree nodes.
    """

    fixture = load_capital_run_v1_fixture()
    workflow = run_capital_run_fixture_workflow(fixture)
    params = fixture.params
    run_id = DEMO_RUN_ID
    desk_id = str(params["desk_id"])
    as_of = date.fromisoformat(str(params["as_of_date"]))
    regime = str(params["regime"])
    inputs_hash = input_hash_for_capital_run_fixture(fixture)

    scalars = workflow["scalars"]
    assert isinstance(scalars, dict)
    pla_workflow = workflow.get("pla")
    capital_workflow = workflow.get("capital")
    if isinstance(pla_workflow, dict):
        if "zone" not in pla_workflow:
            raise ValueError("Missing 'zone' in 'pla' workflow data")
        if "window_size" not in pla_workflow:
            raise ValueError("Missing 'window_size' in 'pla' workflow data")
        pla_zone = pla_workflow["zone"]
        pla_window_size = pla_workflow["window_size"]
    else:
        pla_zone = ""
        pla_window_size = None
    if isinstance(capital_workflow, dict):
        if "binding_term" not in capital_workflow:
            raise ValueError("Missing 'binding_term' in 'capital' workflow data")
        capital_binding_term = capital_workflow["binding_term"]
    else:
        capital_binding_term = ""

    desk_record = DeskAuditRecord(
        run_id=run_id,
        desk_id=desk_id,
        regime=regime,
        inputs_hash=inputs_hash,
        as_of_date=as_of,
        imcc={
            "imcc": scalars["imcc"],
            "unconstrained_lha_es": scalars["unconstrained_lha_es"],
            "constrained_lha_es": scalars["constrained_lha_es"],
        },
        ses={"total_ses": scalars["total_ses"]},
        pla={
            "zone": pla_zone,
            "ks_statistic": scalars["pla_ks_statistic"],
            "window_size": pla_window_size,
        },
        backtesting=workflow["backtesting"]
        if isinstance(workflow.get("backtesting"), dict)
        else {},
        capital={
            "models_based_capital": scalars["models_based_capital"],
            "supervisory_multiplier": scalars["supervisory_multiplier"],
            "binding_term": capital_binding_term,
        },
        nmrf_valuation={
            "classifications": workflow.get("classifications", {}),
            "methods": workflow.get("nmrf_methods", {}),
            "selected_stress_periods": workflow.get("selected_stress_periods", {}),
            "reconciliation": workflow.get("reconciliation", {}),
        },
        elapsed_seconds=0.0,
        notes=("Synthetic capital-run v1 fixture workflow for Navigator demo.",),
    )

    drc_fixture = load_drc_nonsec_v2_fixture()
    drc_summary = run_drc_fixture_workflow(drc_fixture)
    drc_result = frtb_drc.calculate_drc_capital(drc_fixture.positions, context=drc_fixture.context)
    calc_date = drc_fixture.context.calculation_date

    rrao_ctx = load_rrao_context()
    rrao_ctx = frtb_rrao.RraoCalculationContext(
        run_id=run_id,
        calculation_date=calc_date,
        base_currency=rrao_ctx.base_currency,
        profile=rrao_ctx.profile,
        desk_id=rrao_ctx.desk_id,
        legal_entity=rrao_ctx.legal_entity,
    )
    rrao_result = frtb_rrao.calculate_rrao_capital(load_rrao_positions(), context=rrao_ctx)

    sbm_ctx = SbmCalculationContext(
        run_id=run_id,
        calculation_date=calc_date,
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.US_NPR_2_0.value,
        desk_id=desk_id,
        legal_entity=str(params.get("legal_entity", "LE-DEMO")),
    )
    sbm_sensitivities = (
        SbmSensitivity(
            sensitivity_id="eur-1y",
            source_row_id="row-girr-001",
            desk_id=desk_id,
            legal_entity=sbm_ctx.legal_entity,
            risk_class=SbmRiskClass.GIRR,
            risk_measure=SbmRiskMeasure.DELTA,
            bucket="1",
            risk_factor="EUR",
            amount=2_500_000.0,
            amount_currency="USD",
            sign_convention=SbmSignConvention.RECEIVE,
            tenor="1y",
            lineage=SbmSourceLineage(
                source_system="frtb-navigator-demo",
                source_file="demo_runs.py",
                source_row_id="row-girr-001",
                source_column_map=(("amount", "amount"),),
            ),
        ),
        SbmSensitivity(
            sensitivity_id="usd-5y",
            source_row_id="row-girr-002",
            desk_id=desk_id,
            legal_entity=sbm_ctx.legal_entity,
            risk_class=SbmRiskClass.GIRR,
            risk_measure=SbmRiskMeasure.DELTA,
            bucket="2",
            risk_factor="USD",
            amount=1_800_000.0,
            amount_currency="USD",
            sign_convention=SbmSignConvention.RECEIVE,
            tenor="5y",
            lineage=SbmSourceLineage(
                source_system="frtb-navigator-demo",
                source_file="demo_runs.py",
                source_row_id="row-girr-002",
                source_column_map=(("amount", "amount"),),
            ),
        ),
    )
    sbm_result = calculate_sbm_capital(sbm_sensitivities, context=sbm_ctx)

    sa_result = compose_standardised_approach_capital(
        sbm_summary=sbm_to_component_summary(sbm_result),
        drc_summary=frtb_drc.to_component_summary(drc_result),
        rrao_summary=frtb_rrao.to_component_summary(rrao_result),
        run_id=run_id,
    )

    ima_total = float(scalars["models_based_capital"])
    sa_total = float(sa_result.total_capital)
    profile_id = drc_result.profile_id

    summary = RunSummary(
        run_id=DEMO_RUN_ID,
        label="Synthetic suite demo",
        calculation_date=calc_date.isoformat(),
        profile_id=profile_id,
        base_currency="USD",
        jurisdiction_family=str(sa_result.jurisdiction_family),
        components=["IMA", "SA"],
        input_hash=inputs_hash,
        prototype=True,
    )

    nodes = _build_capital_tree(
        currency="USD",
        ima_total=ima_total,
        sa_total=sa_total,
        desk_id=desk_id,
        imcc_total=float(scalars["imcc"]),
        ses_total=float(scalars["total_ses"]),
        pla_total=0.0,
        sbm_total=float(sbm_result.total_capital),
        drc_total=float(drc_result.total_drc),
        rrao_total=float(rrao_result.total_rrao),
        drc_buckets=drc_summary.get("buckets", {}) if isinstance(drc_summary, dict) else {},
    )

    return DashboardRun(
        summary=summary,
        nodes=nodes,
        desk_record=desk_record,
        ima_workflow=workflow,
        drc_result=drc_result,
        rrao_result=rrao_result,
        sbm_result=sbm_result,
        sa_result=sa_result,
    )


def run_overview(
    run: DashboardRun,
    *,
    hierarchy_node_id: str = DEFAULT_HIERARCHY_NODE_ID,
) -> RunOverviewView:
    """Build the overview view for a demo run and hierarchy scope.

    Parameters
    ----------
    run
        Demo run to render.
    hierarchy_node_id
        Requested hierarchy scope.

    Returns
    -------
    RunOverviewView
        Overview totals and capital nodes.
    """

    totals = _scope_totals(run, _require_scope(hierarchy_node_id), scenario="Binding")
    binding_side = "IMA" if totals.ima >= totals.output_floor else "FLOOR"
    return RunOverviewView(
        run=run.summary,
        ima_total=totals.ima,
        sa_total=totals.sa,
        cva_total=None,
        output_floor_total=totals.output_floor,
        binding_total=totals.binding,
        binding_side=binding_side,
        suite_total=totals.binding,
        currency=run.summary.base_currency,
        nodes=list(run.nodes),
    )


def metadata_view(run: DashboardRun) -> MetadataView:
    """Build metadata dimensions for the demo hierarchy.

    Parameters
    ----------
    run
        Demo run to render.

    Returns
    -------
    MetadataView
        Metadata dimensions and run context.
    """

    children_by_parent: dict[str | None, list[str]] = {}
    for spec in HIERARCHY_SPECS:
        children_by_parent.setdefault(spec.parent_id, []).append(spec.node_id)
    dimensions = [
        DimensionNodeView(
            node_id=spec.node_id,
            parent_id=spec.parent_id,
            label=spec.label,
            dimension=spec.dimension,
            level=spec.level,
            filter=dict(spec.filter),
            components=list(spec.components),
            child_ids=children_by_parent.get(spec.node_id, []),
        )
        for spec in HIERARCHY_SPECS
    ]
    return MetadataView(
        run_id=run.summary.run_id,
        dimensions=dimensions,
        reporting_dates=[run.summary.calculation_date],
        baseline_dates=[],
        currencies=[run.summary.base_currency],
    )


def node_detail(run: DashboardRun, node_id: str) -> NodeDetailView:
    """Build capital tree node detail for the demo source.

    Parameters
    ----------
    run
        Demo run to inspect.
    node_id
        Capital tree node identifier.

    Returns
    -------
    NodeDetailView
        Node detail payload.
    """

    node = _require_node(run, node_id)
    measures = _measures_for_node(run, node_id)
    attributions = _attributions_for_node(run, node_id)
    return NodeDetailView(node=node, measures=measures, attributions=attributions)


def ima_desk_view(run: DashboardRun, desk_id: str) -> ImaDeskView:
    """Build IMA desk evidence for the selected demo desk.

    Parameters
    ----------
    run
        Demo run to inspect.
    desk_id
        IMA desk identifier.

    Returns
    -------
    ImaDeskView
        Desk-level IMA evidence.
    """

    if desk_id != run.desk_record.desk_id:
        raise KeyError(f"Unknown desk {desk_id}")
    record = run.desk_record
    workflow = run.ima_workflow
    scalars = workflow.get("scalars", {})
    return ImaDeskView(
        desk_id=record.desk_id,
        regime=record.regime,
        eligibility=record.desk_eligibility,
        summary={
            "models_based_capital": record.capital.get("models_based_capital"),
            "supervisory_multiplier": record.capital.get("supervisory_multiplier"),
            "binding_term": record.capital.get("binding_term"),
            "imcc": scalars.get("imcc") if isinstance(scalars, dict) else None,
            "total_ses": scalars.get("total_ses") if isinstance(scalars, dict) else None,
        },
        imcc=dict(record.imcc),
        ses_nmrf={
            "total_ses": record.ses.get("total_ses"),
            **dict(record.nmrf_valuation),
        },
        pla=dict(record.pla),
        backtesting=dict(record.backtesting),
        attributions=_contributions_to_rows(desk_contributions(record), component="frtb_ima"),
    )


def sa_overview(run: DashboardRun) -> SaOverviewView:
    """Build Standardised Approach component overview for the demo run.

    Parameters
    ----------
    run
        Demo run to summarize.

    Returns
    -------
    SaOverviewView
        Standardised Approach overview payload.
    """

    components = [
        _sa_component_from_drc(run.drc_result),
        _sa_component_from_rrao(run.rrao_result),
        _sa_component_from_sbm(run.sbm_result),
    ]
    return SaOverviewView(
        total_capital=float(run.sa_result.total_capital),
        jurisdiction_family=str(run.sa_result.jurisdiction_family),
        components=components,
    )


def grid_view(
    run: DashboardRun,
    *,
    framework: str = "SA",
    grouping: str | None = None,
    scenario: str = "Binding",
    hierarchy_node_id: str = DEFAULT_HIERARCHY_NODE_ID,
) -> GridView:
    """Build the aggregate grid for a demo framework selection.

    Parameters
    ----------
    run
        Demo run to render.
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
        Aggregate grid payload.
    """

    framework_key = framework.upper()
    scope = _require_scope(hierarchy_node_id)
    if framework_key == "IMA":
        rows = (
            _ima_grid_rows(run, scope=scope)
            if _scope_includes(scope, "IMA")
            else _framework_no_data_rows(
                run,
                framework="IMA",
                reason=f"{scope.label} has no IMA payload in the fixture hierarchy.",
            )
        )
        columns = _ima_columns()
        grouping_label = grouping or "Desk > Measure"
    elif framework_key == "CVA":
        rows = _cva_grid_rows(run)
        columns = _cva_columns()
        grouping_label = grouping or "Counterparty > Method"
    else:
        framework_key = "SA"
        rows = _sa_grid_rows(run, scenario=scenario, scope=scope)
        columns = _sa_columns()
        grouping_label = grouping or "Component > Risk Class / Bucket"
    return GridView(
        run_id=run.summary.run_id,
        framework=framework_key,
        grouping=grouping_label,
        scenario=scenario,
        columns=columns,
        rows=rows,
        row_count=len(rows),
    )


def inspector_view(
    run: DashboardRun,
    row_id: str,
    *,
    scenario: str = "Binding",
    hierarchy_node_id: str = DEFAULT_HIERARCHY_NODE_ID,
) -> InspectorView:
    """Build inspector detail for a selected demo aggregate row.

    Parameters
    ----------
    run
        Demo run to inspect.
    row_id
        Selected grid row identifier.
    scenario
        Scenario selector.
    hierarchy_node_id
        Requested hierarchy scope.

    Returns
    -------
    InspectorView
        Inspector payload for the selected row.
    """

    scope = _require_scope(hierarchy_node_id)
    row = _find_grid_row(run, row_id, scenario=scenario, scope=scope)
    if row is None:
        raise KeyError(f"Unknown grid row {row_id}")
    attribution = _attributions_for_grid_row(run, row)
    audit_rows = _audit_rows_from_attribution(
        attribution,
        currency=row.currency,
        desk_id=run.desk_record.desk_id,
        legal_entity=_safe_str(
            getattr(getattr(run.sbm_result, "context", None), "legal_entity", "LE-DEMO")
        ),
        row=row,
    )
    diagnostics = _diagnostics_for_row(row, attribution)
    extras = _extras_for_row(run, row)
    reconciled = sum(
        1 for item in attribution if item.reconciliation_status.upper() == "RECONCILED"
    )
    total = len(attribution)
    coverage = 1.0 if total == 0 else reconciled / total
    tabs = [
        InspectorTabView(key="attribution", label="Attribution", badge=str(total)),
        InspectorTabView(key="source", label="Source rows", badge=str(len(audit_rows))),
    ]
    if diagnostics:
        tabs.append(
            InspectorTabView(key="diagnostics", label="Diagnostics", badge=str(len(diagnostics)))
        )
    if row.component == "SBM" and extras.get("scenario_detail"):
        tabs.append(InspectorTabView(key="scenario", label="Scenario detail"))
    if row.framework == "IMA" and extras.get("backtesting"):
        tabs.append(InspectorTabView(key="backtesting", label="Backtesting"))
    return InspectorView(
        row_id=row.row_id,
        label=row.label,
        framework=row.framework,
        component=row.component,
        reconciliation={
            "coverage": coverage,
            "rows_needing_review": total - reconciled,
            "status": "reconciled" if total == 0 or reconciled == total else "review",
        },
        tabs=tabs,
        attribution=attribution,
        audit_rows=audit_rows,
        diagnostics=diagnostics,
        extras=extras,
    )


def _sa_component_from_drc(result: frtb_drc.DrcCapitalResult) -> SaComponentView:
    buckets = {
        bucket.bucket_key: bucket.capital
        for category in result.categories
        for bucket in category.bucket_results
    }
    records = result.attribution_records
    top = sorted(records, key=lambda item: abs(item.contribution or 0.0), reverse=True)[:8]
    return SaComponentView(
        component="DRC",
        total_capital=float(result.total_drc),
        profile_id=result.profile_id,
        input_hash=result.input_hash,
        line_count=result.input_count,
        breakdown={"buckets": buckets},
        top_attribution=_contributions_to_rows(top, component="frtb_drc"),
    )


def _sa_component_from_rrao(result: frtb_rrao.RraoCapitalResult) -> SaComponentView:
    records = frtb_rrao.calculate_rrao_attribution(result)
    top = sorted(records, key=lambda item: abs(item.contribution or 0.0), reverse=True)[:8]
    breakdown = {
        _enum_value(line.evidence_type): line.add_on
        for line in result.lines
        if not line.is_excluded
    }
    return SaComponentView(
        component="RRAO",
        total_capital=float(result.total_rrao),
        profile_id=result.profile_id,
        input_hash=result.input_hash,
        line_count=len(result.lines),
        breakdown={"lines": breakdown},
        top_attribution=_contributions_to_rows(top, component="frtb_rrao"),
    )


def _sa_component_from_sbm(result: Any) -> SaComponentView:
    records = calculate_sbm_attribution(result)
    top = sorted(records, key=lambda item: abs(item.contribution or 0.0), reverse=True)[:8]
    breakdown = {
        (
            f"{_enum_value(item.risk_class)}:{_enum_value(item.risk_measure or 'DELTA')}"
        ): item.selected_capital
        for item in result.risk_classes
    }
    portfolio_scenarios = _scenario_values_from_mapping(
        getattr(result, "portfolio_scenario_totals", {})
    )
    return SaComponentView(
        component="SBM",
        total_capital=float(result.total_capital),
        profile_id=result.profile_id,
        input_hash=result.input_hash,
        line_count=len(result.risk_classes),
        breakdown={"risk_classes": breakdown, "portfolio_scenario_totals": portfolio_scenarios},
        top_attribution=_contributions_to_rows(top, component="frtb_sbm"),
    )


def _sa_grid_rows(
    run: DashboardRun,
    *,
    scenario: str,
    scope: HierarchyNodeSpec,
) -> list[GridRowView]:
    currency = run.summary.base_currency
    totals = _scope_totals(run, scope, scenario=scenario)
    if totals.sa == 0.0:
        return _framework_no_data_rows(
            run,
            framework="SA",
            reason=f"{scope.label} has no SA component payload in the fixture hierarchy.",
        )
    rows = [
        _grid_row(
            "sa",
            None,
            "Standardised Approach",
            "SA",
            "SA",
            "FRAMEWORK",
            0,
            currency,
            capital=totals.sa,
        ),
    ]
    if _scope_includes(scope, "SBM"):
        rows.append(
            _grid_row(
                "sa-sbm",
                "sa",
                "SBM",
                "SA",
                "SBM",
                "COMPONENT",
                1,
                currency,
                capital=totals.sbm,
                pct_parent=_pct(totals.sbm, totals.sa),
            )
        )
        rows.extend(_sbm_rows(run, parent_id="sa-sbm", parent_total=totals.sbm, scenario=scenario))
    if _scope_includes(scope, "DRC"):
        rows.append(
            _grid_row(
                "sa-drc",
                "sa",
                "DRC",
                "SA",
                "DRC",
                "COMPONENT",
                1,
                currency,
                capital=totals.drc,
                pct_parent=_pct(totals.drc, totals.sa),
            )
        )
        rows.extend(_drc_rows(run, parent_id="sa-drc", parent_total=totals.drc))
    if _scope_includes(scope, "RRAO"):
        rows.append(
            _grid_row(
                "sa-rrao",
                "sa",
                "RRAO",
                "SA",
                "RRAO",
                "COMPONENT",
                1,
                currency,
                capital=totals.rrao,
                pct_parent=_pct(totals.rrao, totals.sa),
            )
        )
        rows.extend(_rrao_rows(run, parent_id="sa-rrao", parent_total=totals.rrao))
    return rows


def _sbm_rows(
    run: DashboardRun,
    *,
    parent_id: str,
    parent_total: float,
    scenario: str,
) -> list[GridRowView]:
    rows: list[GridRowView] = []
    for item in getattr(run.sbm_result, "risk_classes", ()):
        risk_class = _enum_value(getattr(item, "risk_class", "SBM"))
        measure = _enum_value(getattr(item, "risk_measure", "DELTA"))
        selected_capital = _float_or_none(getattr(item, "selected_capital", None))
        scenarios = _sbm_scenario_values(item, selected_capital)
        row_capital = _scenario_amount(scenarios, scenario, selected_capital)
        row_id = f"sa-sbm-{_slug(risk_class)}-{_slug(measure)}"
        kwargs: dict[str, Any] = {
            "base_rho": scenarios.get("Base"),
            "high_rho": scenarios.get("High"),
            "low_rho": scenarios.get("Low"),
            "selected_scenario": scenarios.get("SelectedScenario"),
            "pct_parent": _pct(row_capital, parent_total),
        }
        if measure.upper() == "DELTA":
            kwargs["delta"] = row_capital
        elif measure.upper() == "VEGA":
            kwargs["vega"] = row_capital
        elif measure.upper() == "CURVATURE":
            kwargs["curvature"] = row_capital
        rows.append(
            _grid_row(
                row_id,
                parent_id,
                f"{risk_class}:{measure}",
                "SA",
                "SBM",
                "RISK_CLASS",
                2,
                run.summary.base_currency,
                capital=row_capital,
                group_path=["SA", "SBM", risk_class, measure],
                filter={"component": "SBM", "risk_class": risk_class, "risk_measure": measure},
                **kwargs,
            )
        )
    return rows


def _drc_rows(run: DashboardRun, *, parent_id: str, parent_total: float) -> list[GridRowView]:
    rows: list[GridRowView] = []
    for category in run.drc_result.categories:
        category_label = _enum_value(getattr(category, "category", "DRC"))
        category_total = sum(float(bucket.capital) for bucket in category.bucket_results)
        category_id = f"{parent_id}-{_slug(category_label)}"
        rows.append(
            _grid_row(
                category_id,
                parent_id,
                category_label,
                "SA",
                "DRC",
                "CATEGORY",
                2,
                run.summary.base_currency,
                capital=category_total,
                net_jtd=_float_or_none(getattr(category, "net_jtd", None)),
                pct_parent=_pct(category_total, parent_total),
                group_path=["SA", "DRC", category_label],
                filter={"component": "DRC", "category": category_label},
            )
        )
        for bucket in category.bucket_results:
            bucket_key = _safe_str(bucket.bucket_key)
            bucket_capital = float(bucket.capital)
            rows.append(
                _grid_row(
                    f"{category_id}-{_slug(bucket_key)}",
                    category_id,
                    f"Bucket {bucket_key}",
                    "SA",
                    "DRC",
                    "BUCKET",
                    3,
                    run.summary.base_currency,
                    capital=bucket_capital,
                    net_jtd=_float_or_none(getattr(bucket, "net_jtd", None)),
                    gross_jtd=_float_or_none(getattr(bucket, "gross_jtd", None)),
                    lgd=_float_or_none(getattr(bucket, "lgd", None)),
                    pct_parent=_pct(bucket_capital, category_total),
                    group_path=["SA", "DRC", category_label, bucket_key],
                    filter={"component": "DRC", "category": category_label, "bucket": bucket_key},
                )
            )
    return rows


def _rrao_rows(run: DashboardRun, *, parent_id: str, parent_total: float) -> list[GridRowView]:
    evidence_totals: dict[str, float] = {}
    for line in run.rrao_result.lines:
        if line.is_excluded:
            continue
        evidence = _enum_value(line.evidence_type)
        evidence_totals[evidence] = evidence_totals.get(evidence, 0.0) + float(line.add_on)
    return [
        _grid_row(
            f"{parent_id}-{_slug(evidence)}",
            parent_id,
            evidence,
            "SA",
            "RRAO",
            "EVIDENCE_TYPE",
            2,
            run.summary.base_currency,
            capital=amount,
            pct_parent=_pct(amount, parent_total),
            group_path=["SA", "RRAO", evidence],
            filter={"component": "RRAO", "evidence_type": evidence},
        )
        for evidence, amount in sorted(evidence_totals.items())
    ]


def _ima_grid_rows(run: DashboardRun, *, scope: HierarchyNodeSpec) -> list[GridRowView]:
    record = run.desk_record
    currency = run.summary.base_currency
    total = _float_or_none(record.capital.get("models_based_capital")) or 0.0
    imcc = _float_or_none(record.imcc.get("imcc"))
    ses = _float_or_none(record.ses.get("total_ses"))
    multiplier = _float_or_none(record.capital.get("supervisory_multiplier"))
    rows = [
        _grid_row("ima", None, "IMA", "IMA", "IMA", "FRAMEWORK", 0, currency, capital=total),
        _grid_row(
            f"ima-desk-{_slug(record.desk_id)}",
            "ima",
            f"Desk {record.desk_id}",
            "IMA",
            "IMA",
            "DESK",
            1,
            currency,
            capital=total,
            imcc=imcc,
            ses=ses,
            multiplier=multiplier,
            pla_zone=_safe_str(record.pla.get("zone")),
            backtest_zone=_backtesting_zone(record.backtesting),
            pct_parent=1.0,
            group_path=["IMA", record.desk_id],
            filter={"desk_id": record.desk_id},
        ),
        _grid_row(
            "ima-imcc",
            f"ima-desk-{_slug(record.desk_id)}",
            "IMCC",
            "IMA",
            "IMA",
            "MEASURE",
            2,
            currency,
            capital=imcc,
            imcc=imcc,
            pct_parent=_pct(imcc, total),
            group_path=["IMA", record.desk_id, "IMCC"],
        ),
        _grid_row(
            "ima-ses",
            f"ima-desk-{_slug(record.desk_id)}",
            "SES / NMRF",
            "IMA",
            "IMA",
            "MEASURE",
            2,
            currency,
            capital=ses,
            ses=ses,
            pct_parent=_pct(ses, total),
            group_path=["IMA", record.desk_id, "SES / NMRF"],
        ),
        _grid_row(
            "ima-pla",
            f"ima-desk-{_slug(record.desk_id)}",
            "PLA",
            "IMA",
            "IMA",
            "DIAGNOSTIC",
            2,
            currency,
            pla_zone=_safe_str(record.pla.get("zone")),
            group_path=["IMA", record.desk_id, "PLA"],
        ),
        _grid_row(
            "ima-backtesting",
            f"ima-desk-{_slug(record.desk_id)}",
            "Backtesting",
            "IMA",
            "IMA",
            "DIAGNOSTIC",
            2,
            currency,
            backtest_zone=_backtesting_zone(record.backtesting),
            group_path=["IMA", record.desk_id, "Backtesting"],
        ),
    ]
    return rows


def _cva_grid_rows(run: DashboardRun) -> list[GridRowView]:
    return [
        _grid_row(
            "cva-no-data",
            None,
            "CVA not present in this run",
            "CVA",
            "CVA",
            "NO_DATA",
            0,
            run.summary.base_currency,
            status="no_data",
            no_data_reason=(
                "The synthetic suite run exposes IMA and SA only; "
                "BA-CVA and SA-CVA payloads are absent."
            ),
        )
    ]


def _find_grid_row(
    run: DashboardRun,
    row_id: str,
    *,
    scenario: str,
    scope: HierarchyNodeSpec,
) -> GridRowView | None:
    if row_id.startswith("ima"):
        frameworks = ("IMA",)
    elif row_id.startswith("cva"):
        frameworks = ("CVA",)
    else:
        frameworks = ("SA",)
    for framework in frameworks:
        for row in grid_view(
            run,
            framework=framework,
            scenario=scenario,
            hierarchy_node_id=scope.node_id,
        ).rows:
            if row.row_id == row_id:
                return row
    return None


def _attributions_for_grid_row(run: DashboardRun, row: GridRowView) -> list[AttributionRowView]:
    if row.framework == "IMA":
        return ima_desk_view(run, run.desk_record.desk_id).attributions
    if row.component == "DRC":
        return _drc_attributions_for_row(run, row)
    if row.component == "SBM":
        return _sbm_attributions_for_row(run, row)
    if row.component == "RRAO":
        return _rrao_attributions_for_row(run, row)
    if row.row_id == "sa":
        rows: list[AttributionRowView] = []
        for component in sa_overview(run).components:
            rows.extend(component.top_attribution[:3])
        return rows
    return []


def _require_scope(node_id: str) -> HierarchyNodeSpec:
    for spec in HIERARCHY_SPECS:
        if spec.node_id == node_id:
            return spec
    raise KeyError(f"Unknown hierarchy node {node_id}")


def _scope_includes(scope: HierarchyNodeSpec, component: str) -> bool:
    return component.upper() in {item.upper() for item in scope.components}


def _scope_totals(run: DashboardRun, scope: HierarchyNodeSpec, *, scenario: str) -> ScopeTotals:
    return ScopeTotals(
        ima=float(run.desk_record.capital.get("models_based_capital", 0.0))
        if _scope_includes(scope, "IMA")
        else 0.0,
        sbm=_sbm_total_for_scenario(run, scenario) if _scope_includes(scope, "SBM") else 0.0,
        drc=float(run.drc_result.total_drc) if _scope_includes(scope, "DRC") else 0.0,
        rrao=float(run.rrao_result.total_rrao) if _scope_includes(scope, "RRAO") else 0.0,
    )


def _sbm_total_for_scenario(run: DashboardRun, scenario: str) -> float:
    scenarios = _scenario_values_from_mapping(
        getattr(run.sbm_result, "portfolio_scenario_totals", {})
    )
    return _scenario_amount(scenarios, scenario, float(run.sbm_result.total_capital)) or 0.0


def _scenario_amount(
    scenarios: Mapping[str, float | None],
    scenario: str,
    selected_capital: float | None,
) -> float | None:
    scenario_label = scenario.strip().lower()
    if scenario_label == "binding":
        return selected_capital
    if scenario_label == "base":
        return scenarios.get("Base") if scenarios.get("Base") is not None else selected_capital
    if scenario_label == "high":
        return scenarios.get("High") if scenarios.get("High") is not None else selected_capital
    if scenario_label == "low":
        return scenarios.get("Low") if scenarios.get("Low") is not None else selected_capital
    return selected_capital


def _framework_no_data_rows(
    run: DashboardRun,
    *,
    framework: str,
    reason: str,
) -> list[GridRowView]:
    return [
        _grid_row(
            f"{framework.lower()}-no-data",
            None,
            f"{framework} not present in selected hierarchy node",
            framework,
            framework,
            "NO_DATA",
            0,
            run.summary.base_currency,
            status="no_data",
            no_data_reason=reason,
        )
    ]


def _drc_attributions_for_row(run: DashboardRun, row: GridRowView) -> list[AttributionRowView]:
    records = list(run.drc_result.attribution_records)
    bucket = row.filter.get("bucket")
    if bucket:
        records = [
            record for record in records if _safe_str(getattr(record, "bucket_key", "")) == bucket
        ]
    elif row.row_id == "sa-drc":
        records = sorted(records, key=lambda item: abs(item.contribution or 0.0), reverse=True)[:8]
    return _contributions_to_rows(records, component="frtb_drc")


def _sbm_attributions_for_row(run: DashboardRun, row: GridRowView) -> list[AttributionRowView]:
    records = calculate_sbm_attribution(run.sbm_result)
    risk_class = row.filter.get("risk_class")
    if risk_class:
        records = [
            record for record in records if _safe_str(getattr(record, "category", "")) == risk_class
        ]
    elif row.row_id == "sa-sbm":
        records = sorted(records, key=lambda item: abs(item.contribution or 0.0), reverse=True)[:8]
    return _contributions_to_rows(records, component="frtb_sbm")


def _rrao_attributions_for_row(run: DashboardRun, row: GridRowView) -> list[AttributionRowView]:
    records = frtb_rrao.calculate_rrao_attribution(run.rrao_result)
    evidence_type = row.filter.get("evidence_type")
    if evidence_type:
        records = [
            record
            for record in records
            if _safe_str(getattr(record, "category", "")) == evidence_type
        ]
    elif row.row_id == "sa-rrao":
        records = sorted(records, key=lambda item: abs(item.contribution or 0.0), reverse=True)[:8]
    return _contributions_to_rows(records, component="frtb_rrao")


def _audit_rows_from_attribution(
    attribution: Sequence[AttributionRowView],
    *,
    currency: str,
    desk_id: str,
    legal_entity: str,
    row: GridRowView,
) -> list[AuditRowView]:
    if not attribution:
        return [
            AuditRowView(
                row_id=f"{row.row_id}-empty",
                source_system=row.component,
                source_id=row.row_id,
                desk_id=desk_id,
                legal_entity=legal_entity,
                risk_class=row.filter.get("risk_class"),
                bucket=row.filter.get("bucket"),
                metric=row.row_type,
                value=row.capital,
                currency=currency,
                status=row.status,
                provenance=row.no_data_reason
                or "aggregate row has no line-level attribution in the fixture",
            )
        ]
    return [
        AuditRowView(
            row_id=item.contribution_id,
            source_system=item.component,
            source_id=item.source_id,
            desk_id=desk_id,
            legal_entity=legal_entity,
            risk_class=row.filter.get("risk_class"),
            bucket=row.filter.get("bucket"),
            metric=item.category,
            value=item.contribution,
            currency=currency,
            status=item.reconciliation_status,
            provenance=item.reason or "synthetic fixture attribution",
        )
        for item in attribution
    ]


def _diagnostics_for_row(
    row: GridRowView, attribution: Sequence[AttributionRowView]
) -> list[DiagnosticView]:
    diagnostics = [
        DiagnosticView(
            code="ATTRIBUTION_REVIEW",
            severity="review",
            message=f"{item.source_id}: {item.reason or item.reconciliation_status}",
        )
        for item in attribution
        if item.reconciliation_status.upper() != "RECONCILED"
    ]
    if row.status == "no_data" and row.no_data_reason:
        diagnostics.append(
            DiagnosticView(code="NO_DATA", severity="info", message=row.no_data_reason)
        )
    if row.framework == "CVA":
        diagnostics.append(
            DiagnosticView(
                code="CVA_ABSENT",
                severity="info",
                message="CVA BA-CVA / SA-CVA charges are not present in the demo run.",
            )
        )
    if row.framework == "IMA":
        diagnostics.extend(
            [
                DiagnosticView(
                    code="RFET_ABSENT",
                    severity="info",
                    message="RFET real-price observation counters are not exposed by this fixture.",
                ),
                DiagnosticView(
                    code="ES_LH_MATRIX_ABSENT",
                    severity="info",
                    message="Liquidity-horizon ES matrix is not exposed by this fixture.",
                ),
                DiagnosticView(
                    code="UPL_ABSENT",
                    severity="info",
                    message="PLAT UPL time series is not exposed by this fixture.",
                ),
            ]
        )
    if row.component == "DRC" and (row.gross_jtd is None or row.lgd is None):
        diagnostics.append(
            DiagnosticView(
                code="JTD_DETAIL_LIMITED",
                severity="info",
                message=(
                    "Fixture exposes DRC bucket capital; gross JTD and LGD override detail "
                    "are not available."
                ),
            )
        )
    return diagnostics


def _extras_for_row(run: DashboardRun, row: GridRowView) -> dict[str, Any]:
    extras: dict[str, Any] = {}
    if row.component == "SBM":
        extras["scenario_detail"] = [
            item.model_dump()
            for item in _sbm_rows(
                run,
                parent_id="sa-sbm",
                parent_total=float(run.sbm_result.total_capital),
                scenario="Binding",
            )
            if item.row_id == row.row_id or row.row_id == "sa-sbm"
        ]
    if row.framework == "IMA":
        extras["imcc"] = dict(run.desk_record.imcc)
        extras["ses_nmrf"] = {
            "total_ses": run.desk_record.ses.get("total_ses"),
            **dict(run.desk_record.nmrf_valuation),
        }
        extras["pla"] = dict(run.desk_record.pla)
        extras["backtesting"] = dict(run.desk_record.backtesting)
    if row.component == "DRC":
        extras["jtd_available"] = {
            "net_jtd": row.net_jtd is not None,
            "gross_jtd": row.gross_jtd is not None,
            "lgd": row.lgd is not None,
        }
    return extras


def _build_capital_tree(
    *,
    currency: str,
    ima_total: float,
    sa_total: float,
    desk_id: str,
    imcc_total: float,
    ses_total: float,
    pla_total: float,
    sbm_total: float,
    drc_total: float,
    rrao_total: float,
    drc_buckets: Mapping[str, object],
) -> tuple[CapitalNodeView, ...]:
    suite_total = max(ima_total, OUTPUT_FLOOR_MULTIPLIER * sa_total)
    nodes: list[CapitalNodeView] = [
        CapitalNodeView(
            node_id="total",
            parent_id=None,
            label="Binding capital",
            node_type="TOTAL",
            component="SUITE",
            amount=suite_total,
            currency=currency,
            child_ids=["ima", "sa"],
        ),
        CapitalNodeView(
            node_id="ima",
            parent_id="total",
            label="IMA",
            node_type="COMPONENT",
            component="IMA",
            amount=ima_total,
            currency=currency,
            child_ids=[f"ima-desk-{desk_id}"],
        ),
        CapitalNodeView(
            node_id=f"ima-desk-{desk_id}",
            parent_id="ima",
            label=f"Desk {desk_id}",
            node_type="DESK",
            component="IMA",
            amount=ima_total,
            currency=currency,
            child_ids=["ima-imcc", "ima-ses", "ima-pla"],
        ),
        CapitalNodeView(
            node_id="ima-imcc",
            parent_id=f"ima-desk-{desk_id}",
            label="IMCC",
            node_type="MEASURE",
            component="IMA",
            amount=imcc_total,
            currency=currency,
        ),
        CapitalNodeView(
            node_id="ima-ses",
            parent_id=f"ima-desk-{desk_id}",
            label="SES / NMRF",
            node_type="MEASURE",
            component="IMA",
            amount=ses_total,
            currency=currency,
        ),
        CapitalNodeView(
            node_id="ima-pla",
            parent_id=f"ima-desk-{desk_id}",
            label="PLA add-on",
            node_type="MEASURE",
            component="IMA",
            amount=pla_total,
            currency=currency,
        ),
        CapitalNodeView(
            node_id="sa",
            parent_id="total",
            label="Standardised Approach",
            node_type="COMPONENT",
            component="SA",
            amount=sa_total,
            currency=currency,
            child_ids=["sa-sbm", "sa-drc", "sa-rrao"],
        ),
        CapitalNodeView(
            node_id="sa-sbm",
            parent_id="sa",
            label="SBM",
            node_type="COMPONENT",
            component="SBM",
            amount=sbm_total,
            currency=currency,
        ),
        CapitalNodeView(
            node_id="sa-drc",
            parent_id="sa",
            label="DRC",
            node_type="COMPONENT",
            component="DRC",
            amount=drc_total,
            currency=currency,
            child_ids=[f"sa-drc-{key}" for key in sorted(drc_buckets)][:6],
        ),
        CapitalNodeView(
            node_id="sa-rrao",
            parent_id="sa",
            label="RRAO",
            node_type="COMPONENT",
            component="RRAO",
            amount=rrao_total,
            currency=currency,
        ),
    ]
    for key in sorted(drc_buckets)[:6]:
        bucket = drc_buckets[key]
        amount = float(bucket.get("capital", 0.0)) if isinstance(bucket, dict) else 0.0
        nodes.append(
            CapitalNodeView(
                node_id=f"sa-drc-{key}",
                parent_id="sa-drc",
                label=f"Bucket {key}",
                node_type="BUCKET",
                component="DRC",
                amount=amount,
                currency=currency,
            )
        )
    return tuple(nodes)


def _require_node(run: DashboardRun, node_id: str) -> CapitalNodeView:
    for node in run.nodes:
        if node.node_id == node_id:
            return node
    raise KeyError(f"Unknown node {node_id}")


def _measures_for_node(run: DashboardRun, node_id: str) -> list[MeasureView]:
    if node_id.startswith("ima-desk"):
        desk = ima_desk_view(run, run.desk_record.desk_id)
        return [
            MeasureView(name="IMCC", value=desk.imcc.get("imcc")),
            MeasureView(name="Unconstrained LHA ES", value=desk.imcc.get("unconstrained_lha_es")),
            MeasureView(name="Constrained LHA ES", value=desk.imcc.get("constrained_lha_es")),
            MeasureView(name="Total SES", value=desk.ses_nmrf.get("total_ses")),
            MeasureView(name="PLA KS", value=desk.pla.get("ks_statistic")),
            MeasureView(name="PLA zone", value=desk.pla.get("zone")),
        ]
    if node_id == "sa":
        sa = sa_overview(run)
        return [MeasureView(name="SA total", value=sa.total_capital)]
    node = _require_node(run, node_id)
    return [MeasureView(name="Capital", value=node.amount, unit=node.currency)]


def _attributions_for_node(run: DashboardRun, node_id: str) -> list[AttributionRowView]:
    if node_id.startswith("ima-desk") or node_id.startswith("ima-"):
        return ima_desk_view(run, run.desk_record.desk_id).attributions
    row = _find_grid_row(
        run,
        node_id,
        scenario="Binding",
        scope=_require_scope(DEFAULT_HIERARCHY_NODE_ID),
    )
    return _attributions_for_grid_row(run, row) if row is not None else []


def _contributions_to_rows(
    records: Sequence[CapitalContribution], *, component: str
) -> list[AttributionRowView]:
    rows: list[AttributionRowView] = []
    for index, record in enumerate(records):
        rows.append(
            AttributionRowView(
                contribution_id=record.contribution_id or f"{component}-{index}",
                component=component,
                category=record.category,
                source_level=record.source_level,
                source_id=record.source_id,
                method=record.method.value,
                amount=record.base_amount,
                contribution=record.contribution,
                reconciliation_status=record.reconciliation_status.value,
                reason=record.reason,
            )
        )
    return rows


def _grid_row(
    row_id: str,
    parent_id: str | None,
    label: str,
    framework: str,
    component: str,
    row_type: str,
    level: int,
    currency: str,
    **kwargs: Any,
) -> GridRowView:
    group_path = kwargs.pop("group_path", [label])
    row_filter = kwargs.pop("filter", {})
    return GridRowView(
        row_id=row_id,
        parent_id=parent_id,
        label=label,
        framework=framework,
        component=component,
        row_type=row_type,
        level=level,
        group_path=group_path,
        currency=currency,
        filter=row_filter,
        **kwargs,
    )


def _sa_columns() -> list[GridColumnView]:
    return [
        GridColumnView(key="capital", label="Capital"),
        GridColumnView(key="delta", label="Delta"),
        GridColumnView(key="vega", label="Vega"),
        GridColumnView(key="curvature", label="Curv"),
        GridColumnView(key="base_rho", label="Base rho"),
        GridColumnView(key="high_rho", label="High rho"),
        GridColumnView(key="low_rho", label="Low rho"),
        GridColumnView(key="net_jtd", label="Net JTD"),
        GridColumnView(key="pct_parent", label="% parent", kind="percent"),
        GridColumnView(key="delta_vs_baseline", label="Delta base", kind="signed"),
    ]


def _ima_columns() -> list[GridColumnView]:
    return [
        GridColumnView(key="capital", label="Capital"),
        GridColumnView(key="imcc", label="IMCC"),
        GridColumnView(key="ses", label="SES"),
        GridColumnView(key="multiplier", label="Mult.", kind="decimal"),
        GridColumnView(key="pla_zone", label="PLA", kind="text"),
        GridColumnView(key="backtest_zone", label="Backtest", kind="text"),
        GridColumnView(key="pct_parent", label="% parent", kind="percent"),
        GridColumnView(key="delta_vs_baseline", label="Delta base", kind="signed"),
    ]


def _cva_columns() -> list[GridColumnView]:
    return [
        GridColumnView(key="capital", label="Capital"),
        GridColumnView(key="status", label="Status", kind="text"),
        GridColumnView(key="no_data_reason", label="Data state", kind="text"),
    ]


def _sbm_scenario_values(item: object, selected_capital: float | None) -> dict[str, Any]:
    values = _scenario_values_from_mapping(getattr(item, "scenario_totals", {}))
    if values.get("Base") is None and selected_capital is not None:
        values["Base"] = selected_capital
    selected = _scenario_label(getattr(item, "selected_scenario", None))
    if selected is None:
        numeric = {
            name: amount for name, amount in values.items() if isinstance(amount, (float, int))
        }
        selected = max(numeric, key=numeric.get) if numeric else None
    values["SelectedScenario"] = selected
    return values


def _scenario_values_from_mapping(raw: object) -> dict[str, float | None]:
    values: dict[str, float | None] = {"Base": None, "High": None, "Low": None}
    if not isinstance(raw, Mapping):
        return values
    for key, value in raw.items():
        label = _scenario_label(key)
        if label in values:
            values[label] = _float_or_none(value)
    return values


def _scenario_label(value: object) -> str | None:
    text = _enum_value(value).lower()
    if "high" in text:
        return "High"
    if "low" in text:
        return "Low"
    if "medium" in text or "base" in text or text == "rho":
        return "Base"
    return None


def _backtesting_zone(backtesting: Mapping[str, object]) -> str | None:
    text = " ".join(str(value).upper() for value in backtesting.values())
    if "RED" in text:
        return "RED"
    if "AMBER" in text or "YELLOW" in text:
        return "AMBER"
    if "GREEN" in text:
        return "GREEN"
    return None


def _pct(value: float | None, total: float | None) -> float | None:
    if value is None or total in (None, 0):
        return None
    return value / total


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _enum_value(value: object) -> str:
    return _safe_str(getattr(value, "value", value))


def _safe_str(value: object) -> str:
    return "" if value is None else str(value)


def _slug(value: object) -> str:
    text = _safe_str(value).strip().lower()
    return (
        "".join(character if character.isalnum() else "-" for character in text).strip("-") or "row"
    )


def jsonable_payload(value: object) -> object:
    """Return a JSON-compatible representation of a Navigator payload.

    Parameters
    ----------
    value
        Payload or nested value to normalize.

    Returns
    -------
    object
        JSON-compatible representation.
    """

    return jsonable(value)
