"""Pydantic view models for the FRTB Navigator API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RunSummary(BaseModel):
    """Catalogue row for one Navigator run exposed by a backend source."""

    run_id: str
    label: str
    calculation_date: str
    profile_id: str
    base_currency: str
    source: str = "demo"
    jurisdiction_family: str | None = None
    components: list[str]
    input_hash: str | None = None
    prototype: bool = True


class CapitalNodeView(BaseModel):
    """Capital tree node rendered in the overview and inspector navigation."""

    node_id: str
    parent_id: str | None
    label: str
    node_type: str
    component: str
    amount: float | None
    currency: str
    child_ids: list[str] = Field(default_factory=list)


class AttributionRowView(BaseModel):
    """Attribution contribution row attached to a capital tree or grid row."""

    contribution_id: str
    component: str
    category: str
    source_level: str
    source_id: str
    method: str
    amount: float | None
    contribution: float | None
    reconciliation_status: str
    reason: str = ""


class MeasureView(BaseModel):
    """Name/value measure displayed in a node detail panel."""

    name: str
    value: Any
    unit: str | None = None


class NodeDetailView(BaseModel):
    """Detail payload for a selected capital tree node."""

    node: CapitalNodeView
    measures: list[MeasureView]
    attributions: list[AttributionRowView]


class ImaDeskView(BaseModel):
    """Desk-level IMA evidence payload for the demo Navigator source."""

    desk_id: str
    regime: str
    eligibility: str
    summary: dict[str, Any]
    imcc: dict[str, Any]
    ses_nmrf: dict[str, Any]
    pla: dict[str, Any]
    backtesting: dict[str, Any]
    attributions: list[AttributionRowView]


class SaComponentView(BaseModel):
    """Standardised Approach component summary shown in SA overview panels."""

    component: str
    total_capital: float
    profile_id: str
    input_hash: str | None = None
    line_count: int | None = None
    breakdown: dict[str, Any] = Field(default_factory=dict)
    top_attribution: list[AttributionRowView] = Field(default_factory=list)


class SaOverviewView(BaseModel):
    """Top-level Standardised Approach overview for one Navigator run."""

    total_capital: float
    jurisdiction_family: str
    components: list[SaComponentView]


class RunOverviewView(BaseModel):
    """Top-of-house overview payload combining totals and capital tree rows."""

    run: RunSummary
    ima_total: float | None
    sa_total: float | None
    cva_total: float | None = None
    output_floor_total: float | None = None
    binding_total: float | None = None
    binding_side: str | None = None
    suite_total: float | None
    currency: str
    nodes: list[CapitalNodeView]


class DimensionNodeView(BaseModel):
    """Hierarchy or filter dimension node advertised in Navigator metadata."""

    node_id: str
    parent_id: str | None = None
    label: str
    dimension: str
    level: int = 0
    filter: dict[str, str] = Field(default_factory=dict)
    components: list[str] = Field(default_factory=list)
    child_ids: list[str] = Field(default_factory=list)


class MetadataView(BaseModel):
    """Run metadata payload used to seed Navigator filters and context controls."""

    run_id: str
    source: str = "demo"
    data_state: str = "fixture"
    dimensions: list[DimensionNodeView]
    reporting_dates: list[str]
    baseline_dates: list[str] = Field(default_factory=list)
    currencies: list[str]


class GridColumnView(BaseModel):
    """Column descriptor for a Navigator aggregate grid."""

    key: str
    label: str
    kind: str = "number"


class GridRowView(BaseModel):
    """Aggregate grid row for capital, evidence, no-data, or unsupported states."""

    row_id: str
    parent_id: str | None = None
    label: str
    framework: str
    component: str
    row_type: str
    level: int = 0
    group_path: list[str] = Field(default_factory=list)
    currency: str = "USD"
    capital: float | None = None
    delta: float | None = None
    vega: float | None = None
    curvature: float | None = None
    base_rho: float | None = None
    high_rho: float | None = None
    low_rho: float | None = None
    selected_scenario: str | None = None
    net_jtd: float | None = None
    gross_jtd: float | None = None
    lgd: float | None = None
    imcc: float | None = None
    ses: float | None = None
    multiplier: float | None = None
    pla_zone: str | None = None
    backtest_zone: str | None = None
    pct_parent: float | None = None
    delta_vs_baseline: float | None = None
    status: str = "ok"
    no_data_reason: str | None = None
    filter: dict[str, str] = Field(default_factory=dict)


class GridView(BaseModel):
    """Aggregate grid payload for a framework view such as SA, IMA, or CVA."""

    run_id: str
    source: str = "demo"
    framework: str
    grouping: str
    scenario: str
    columns: list[GridColumnView]
    rows: list[GridRowView]
    row_count: int
    data_state: str = "fixture"


class AuditRowView(BaseModel):
    """Bounded synthetic source row or audit row linked to an aggregate row."""

    row_id: str
    source_system: str
    source_id: str
    desk_id: str | None = None
    book_id: str | None = None
    legal_entity: str | None = None
    risk_class: str | None = None
    bucket: str | None = None
    metric: str
    value: float | None = None
    currency: str | None = None
    calculation_timestamp: str | None = None
    status: str = "ok"
    provenance: str = "synthetic fixture"


class InspectorTabView(BaseModel):
    """Inspector tab descriptor, including enabled state and count badge."""

    key: str
    label: str
    enabled: bool = True
    badge: str | None = None


class DiagnosticView(BaseModel):
    """Data-honesty diagnostic displayed for unavailable or partial evidence."""

    code: str
    severity: str
    message: str


class InspectorView(BaseModel):
    """Inspector payload for one selected aggregate grid row."""

    row_id: str
    label: str
    framework: str
    component: str
    reconciliation: dict[str, Any]
    tabs: list[InspectorTabView]
    attribution: list[AttributionRowView]
    audit_rows: list[AuditRowView]
    diagnostics: list[DiagnosticView] = Field(default_factory=list)
    extras: dict[str, Any] = Field(default_factory=dict)
