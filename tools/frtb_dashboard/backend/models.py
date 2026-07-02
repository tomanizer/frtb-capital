"""Pydantic view models for the FRTB Capital Navigator API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RunSummary(BaseModel):
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
    node_id: str
    parent_id: str | None
    label: str
    node_type: str
    component: str
    amount: float | None
    currency: str
    child_ids: list[str] = Field(default_factory=list)


class AttributionRowView(BaseModel):
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
    name: str
    value: Any
    unit: str | None = None


class NodeDetailView(BaseModel):
    node: CapitalNodeView
    measures: list[MeasureView]
    attributions: list[AttributionRowView]


class ImaDeskView(BaseModel):
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
    component: str
    total_capital: float
    profile_id: str
    input_hash: str | None = None
    line_count: int | None = None
    breakdown: dict[str, Any] = Field(default_factory=dict)
    top_attribution: list[AttributionRowView] = Field(default_factory=list)


class SaOverviewView(BaseModel):
    total_capital: float
    jurisdiction_family: str
    components: list[SaComponentView]


class RunOverviewView(BaseModel):
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
    node_id: str
    parent_id: str | None = None
    label: str
    dimension: str
    level: int = 0
    filter: dict[str, str] = Field(default_factory=dict)
    components: list[str] = Field(default_factory=list)
    child_ids: list[str] = Field(default_factory=list)


class MetadataView(BaseModel):
    run_id: str
    source: str = "demo"
    data_state: str = "fixture"
    dimensions: list[DimensionNodeView]
    reporting_dates: list[str]
    baseline_dates: list[str] = Field(default_factory=list)
    currencies: list[str]


class GridColumnView(BaseModel):
    key: str
    label: str
    kind: str = "number"


class GridRowView(BaseModel):
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
    key: str
    label: str
    enabled: bool = True
    badge: str | None = None


class DiagnosticView(BaseModel):
    code: str
    severity: str
    message: str


class InspectorView(BaseModel):
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
