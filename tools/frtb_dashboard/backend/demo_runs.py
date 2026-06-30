"""Build synthetic dashboard runs from public package demos and fixtures."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
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
from frtb_sbm import (
    to_component_summary as sbm_to_component_summary,
)

from tools.frtb_dashboard.backend._rrao_fixture import load_rrao_context, load_rrao_positions
from tools.frtb_dashboard.backend.models import (
    AttributionRowView,
    CapitalNodeView,
    ImaDeskView,
    MeasureView,
    NodeDetailView,
    RunOverviewView,
    RunSummary,
    SaComponentView,
    SaOverviewView,
)

DEMO_RUN_ID = "demo-suite-001"


@dataclass(frozen=True)
class DashboardRun:
    summary: RunSummary
    nodes: tuple[CapitalNodeView, ...]
    desk_record: DeskAuditRecord
    ima_workflow: dict[str, object]
    drc_result: frtb_drc.DrcCapitalResult
    rrao_result: frtb_rrao.RraoCapitalResult
    sbm_result: Any
    sa_result: Any


def list_demo_runs() -> list[RunSummary]:
    return [build_demo_run().summary]


@lru_cache(maxsize=1)
def build_demo_run() -> DashboardRun:
    fixture = load_capital_run_v1_fixture()
    workflow = run_capital_run_fixture_workflow(fixture)
    params = fixture.params
    run_id = str(params["run_id"])
    desk_id = str(params["desk_id"])
    as_of = date.fromisoformat(str(params["as_of_date"]))
    regime = str(params["regime"])
    inputs_hash = input_hash_for_capital_run_fixture(fixture)

    scalars = workflow["scalars"]
    assert isinstance(scalars, dict)

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
            "zone": workflow["pla"]["zone"] if isinstance(workflow.get("pla"), dict) else "",
            "ks_statistic": scalars["pla_ks_statistic"],
            "window_size": workflow["pla"]["window_size"]
            if isinstance(workflow.get("pla"), dict)
            else None,
            # Zone is assessed but the capital add-on itself is not modelled here.
            "add_on_status": "NOT_MODELLED",
        },
        backtesting=workflow["backtesting"]
        if isinstance(workflow.get("backtesting"), dict)
        else {},
        capital={
            "models_based_capital": scalars["models_based_capital"],
            "supervisory_multiplier": scalars["supervisory_multiplier"],
            "binding_term": workflow["capital"]["binding_term"]
            if isinstance(workflow.get("capital"), dict)
            else "",
        },
        nmrf_valuation={
            "classifications": workflow.get("classifications", {}),
            "methods": workflow.get("nmrf_methods", {}),
            "selected_stress_periods": workflow.get("selected_stress_periods", {}),
            "reconciliation": workflow.get("reconciliation", {}),
        },
        elapsed_seconds=0.0,
        notes=("Synthetic capital-run v1 fixture workflow for dashboard demo.",),
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
                source_system="frtb-dashboard-demo",
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
                source_system="frtb-dashboard-demo",
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


def run_overview(run: DashboardRun) -> RunOverviewView:
    ima_total = float(run.desk_record.capital.get("models_based_capital", 0.0))
    sa_total = float(run.sa_result.total_capital)
    return RunOverviewView(
        run=run.summary,
        ima_total=ima_total,
        sa_total=sa_total,
        suite_total=ima_total + sa_total,
        currency=run.summary.base_currency,
        nodes=list(run.nodes),
    )


def node_detail(run: DashboardRun, node_id: str) -> NodeDetailView:
    node = _require_node(run, node_id)
    measures = _measures_for_node(run, node_id)
    attributions = _attributions_for_node(run, node_id)
    return NodeDetailView(node=node, measures=measures, attributions=attributions)


def ima_desk_view(run: DashboardRun, desk_id: str) -> ImaDeskView:
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
        line.evidence_type.value: line.add_on for line in result.lines if not line.is_excluded
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
            f"{item.risk_class.value}:{item.risk_measure.value if item.risk_measure else 'DELTA'}"
        ): item.selected_capital
        for item in result.risk_classes
    }
    return SaComponentView(
        component="SBM",
        total_capital=float(result.total_capital),
        profile_id=result.profile_id,
        input_hash=result.input_hash,
        line_count=len(result.risk_classes),
        breakdown={"risk_classes": breakdown},
        top_attribution=_contributions_to_rows(top, component="frtb_sbm"),
    )


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
    suite_total = ima_total + sa_total
    nodes: list[CapitalNodeView] = [
        CapitalNodeView(
            node_id="total",
            parent_id=None,
            label="Total capital",
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
            # The PLA capital add-on is not derived in this demo; the zone is
            # assessed but the resulting charge is an indicative placeholder.
            provisional=True,
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
        amount = float(bucket["capital"]) if isinstance(bucket, dict) else 0.0
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
    if node_id == "sa-drc" or node_id.startswith("sa-drc-"):
        return _sa_component_from_drc(run.drc_result).top_attribution
    if node_id == "sa-sbm":
        return _sa_component_from_sbm(run.sbm_result).top_attribution
    if node_id == "sa-rrao":
        return _sa_component_from_rrao(run.rrao_result).top_attribution
    if node_id == "sa":
        rows: list[AttributionRowView] = []
        for component in sa_overview(run).components:
            rows.extend(component.top_attribution[:3])
        return rows
    return []


def _contributions_to_rows(
    records: Sequence[CapitalContribution],
    *,
    component: str,
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


def jsonable_payload(value: object) -> object:
    return jsonable(value)
