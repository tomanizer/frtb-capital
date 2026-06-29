"""Pydantic models for the FRTB onboarding mapper API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ColumnSpecView(BaseModel):
    name: str
    aliases: list[str]
    logical_type: str
    required: bool
    null_policy: str


class InputTableSummary(BaseModel):
    id: str
    package: str
    component: str
    label: str
    description: str
    column_count: int
    required_column_count: int
    sbm_risk_class: str | None = None
    sbm_risk_measure: str | None = None


class InputTableDetail(InputTableSummary):
    columns: list[ColumnSpecView]


class SourceColumnPreview(BaseModel):
    name: str
    arrow_type: str
    sample_values: list[Any]
    null_count: int
    distinct_count: int | None = None


class SourcePreview(BaseModel):
    session_id: str
    row_count: int
    columns: list[SourceColumnPreview]
    preview_rows: list[dict[str, Any]]


class DuckDbSourceRequest(BaseModel):
    database_path: str = ":memory:"
    query: str
    attach_files: dict[str, str] = Field(default_factory=dict)


class PathSourceRequest(BaseModel):
    path: str


class SuggestMappingRequest(BaseModel):
    session_id: str
    target_package: str
    target_table_id: str


class ColumnMappingState(BaseModel):
    session_id: str
    target_package: str
    target_table_id: str
    mapping: dict[str, str | None]


class ValidateMappingRequest(ColumnMappingState):
    pass


class MappingDiagnostic(BaseModel):
    code: str
    message: str
    severity: str
    row_id: str | None = None
    column_name: str | None = None


class ValidationResult(BaseModel):
    accepted_rows: int
    rejected_rows: int
    batch_built: bool
    input_table_hash: str | None = None
    diagnostics: list[MappingDiagnostic]
    preview_rows: list[dict[str, Any]]
    preview_columns: list[str]


class ExportMappingRequest(ColumnMappingState):
    format: Literal["yaml", "toml", "json"] = "yaml"
    source_connector: Literal["file", "duckdb", "path"] = "file"
    source_format: Literal["parquet", "csv", "arrow"] | None = "parquet"
    source_path: str | None = None
    duckdb_database: str | None = None
    duckdb_query: str | None = None
    lineage_source_system: str = "client_etl"
    lineage_source_file: str | None = None


class ExportMappingResponse(BaseModel):
    format: str
    filename: str
    content: str
