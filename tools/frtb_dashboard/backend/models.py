"""Pydantic view models for the FRTB capital dashboard API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RunSummary(BaseModel):
    run_id: str
    label: str
    calculation_date: str
    profile_id: str
    base_currency: str
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
    suite_total: float | None
    currency: str
    nodes: list[CapitalNodeView]
