"""FastAPI application for the FRTB onboarding column mapper."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from tools.onboarding_mapper.backend.catalog import resolve_catalog_entry, table_catalog
from tools.onboarding_mapper.backend.loader import (
    column_preview,
    load_table_from_bytes,
    load_table_from_duckdb,
    load_table_from_path,
    table_preview,
)
from tools.onboarding_mapper.backend.mapping import (
    apply_column_mapping,
    build_mapping_document,
    mapping_filename,
    normalized_preview_hash,
    serialize_mapping_document,
    suggest_column_mapping,
    validate_mapped_table,
)
from tools.onboarding_mapper.backend.models import (
    ColumnMappingState,
    ColumnSpecView,
    DuckDbSourceRequest,
    ExportMappingRequest,
    ExportMappingResponse,
    InputTableDetail,
    InputTableSummary,
    MappingDiagnostic,
    PathSourceRequest,
    SourcePreview,
    SuggestMappingRequest,
    ValidateMappingRequest,
    ValidationResult,
)
from tools.onboarding_mapper.backend.sessions import SESSIONS

FRONTEND_DIST = Path(__file__).resolve().parents[1] / "frontend" / "dist"

app = FastAPI(
    title="FRTB Onboarding Mapper",
    description="Map client datasets to canonical FRTB Arrow input table contracts.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/tables", response_model=list[InputTableSummary])
def list_tables(component: str | None = None) -> list[InputTableSummary]:
    entries = table_catalog().values()
    if component:
        entries = [entry for entry in entries if entry.component.lower() == component.lower()]
    summaries = [
        InputTableSummary(
            id=entry.table_id,
            package=entry.package,
            component=entry.component,
            label=entry.label,
            description=entry.description,
            column_count=len(entry.column_specs),
            required_column_count=sum(1 for spec in entry.column_specs if spec.required),
            sbm_risk_class=entry.sbm_risk_class,
            sbm_risk_measure=entry.sbm_risk_measure,
        )
        for entry in sorted(entries, key=lambda item: (item.component, item.label))
    ]
    return summaries


@app.get("/api/tables/{package}/{table_id}", response_model=InputTableDetail)
def get_table(package: str, table_id: str) -> InputTableDetail:
    try:
        entry = resolve_catalog_entry(package, table_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return InputTableDetail(
        id=entry.table_id,
        package=entry.package,
        component=entry.component,
        label=entry.label,
        description=entry.description,
        column_count=len(entry.column_specs),
        required_column_count=sum(1 for spec in entry.column_specs if spec.required),
        sbm_risk_class=entry.sbm_risk_class,
        sbm_risk_measure=entry.sbm_risk_measure,
        columns=[
            ColumnSpecView(
                name=spec.name,
                aliases=list(spec.aliases),
                logical_type=spec.logical_type.value,
                required=spec.required,
                null_policy=spec.null_policy.value,
            )
            for spec in entry.column_specs
        ],
    )


@app.post("/api/source/upload", response_model=SourcePreview)
async def upload_source(request: Request, filename: str = Query(...)) -> SourcePreview:
    payload = await request.body()
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded file body is empty")
    try:
        table = load_table_from_bytes(payload, filename)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session_id = SESSIONS.create(
        table,
        source_name=filename,
        source_kind="upload",
        raw_bytes=payload,
    )
    return _source_preview(session_id, table)


@app.post("/api/source/path", response_model=SourcePreview)
def load_source_path(request: PathSourceRequest) -> SourcePreview:
    path = Path(request.path).expanduser()
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")
    try:
        table = load_table_from_path(path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session_id = SESSIONS.create(
        table,
        source_name=path.name,
        source_kind="path",
        source_meta={"path": str(path)},
        raw_bytes=path.read_bytes(),
    )
    return _source_preview(session_id, table)


@app.post("/api/source/duckdb", response_model=SourcePreview)
def load_source_duckdb(request: DuckDbSourceRequest) -> SourcePreview:
    try:
        table = load_table_from_duckdb(
            request.query,
            database_path=request.database_path,
            attach_files=request.attach_files,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session_id = SESSIONS.create(
        table,
        source_name="duckdb_query",
        source_kind="duckdb",
        source_meta={
            "database_path": request.database_path,
            "query": request.query,
            "attach_files": request.attach_files,
        },
    )
    return _source_preview(session_id, table)


@app.post("/api/mapping/suggest", response_model=ColumnMappingState)
def suggest_mapping(request: SuggestMappingRequest) -> ColumnMappingState:
    try:
        entry = resolve_catalog_entry(request.target_package, request.target_table_id)
        session = SESSIONS.get(request.session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    mapping = suggest_column_mapping(entry.column_specs, session.table.column_names)
    return ColumnMappingState(
        session_id=request.session_id,
        target_package=request.target_package,
        target_table_id=request.target_table_id,
        mapping=mapping,
    )


@app.post("/api/mapping/validate", response_model=ValidationResult)
def validate_mapping(request: ValidateMappingRequest) -> ValidationResult:
    try:
        entry = resolve_catalog_entry(request.target_package, request.target_table_id)
        session = SESSIONS.get(request.session_id)
        mapped = apply_column_mapping(session.table, request.mapping)
        normalized, batch_built, diagnostics = validate_mapped_table(
            entry,
            mapped,
            source_bytes=session.raw_bytes,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    preview_rows, preview_columns = table_preview(normalized.accepted, row_limit=25)
    return ValidationResult(
        accepted_rows=normalized.accepted.num_rows,
        rejected_rows=normalized.rejected.num_rows if normalized.rejected is not None else 0,
        batch_built=batch_built,
        input_table_hash=normalized_preview_hash(normalized),
        diagnostics=[MappingDiagnostic(**item) for item in diagnostics],
        preview_rows=preview_rows,
        preview_columns=preview_columns,
    )


@app.post("/api/mapping/export", response_model=ExportMappingResponse)
def export_mapping(request: ExportMappingRequest) -> ExportMappingResponse:
    try:
        entry = resolve_catalog_entry(request.target_package, request.target_table_id)
        session = SESSIONS.get(request.session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    source_path = request.source_path or session.source_meta.get("path") or session.source_name
    document = build_mapping_document(
        entry=entry,
        mapping=request.mapping,
        source_connector=request.source_connector,
        source_format=request.source_format,
        source_path=source_path,
        duckdb_database=request.duckdb_database or session.source_meta.get("database_path"),
        duckdb_query=request.duckdb_query or session.source_meta.get("query"),
        lineage_source_system=request.lineage_source_system,
        lineage_source_file=request.lineage_source_file or session.source_name,
    )
    content = serialize_mapping_document(document, request.format)
    return ExportMappingResponse(
        format=request.format,
        filename=mapping_filename(entry, request.format),
        content=content,
    )


def _source_preview(session_id: str, table) -> SourcePreview:
    rows, _ = table_preview(table, row_limit=20)
    return SourcePreview(
        session_id=session_id,
        row_count=table.num_rows,
        columns=[column_preview(table, name) for name in table.column_names],
        preview_rows=rows,
    )


if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/")
    def spa_index() -> FileResponse:
        return FileResponse(FRONTEND_DIST / "index.html")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        candidate = FRONTEND_DIST / full_path
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
