"""Tests for the FRTB onboarding mapper tool."""

from __future__ import annotations

import io

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.csv as pa_csv  # type: ignore[import-untyped]
import pytest
from fastapi.testclient import TestClient

from tools.onboarding_mapper.backend.app import app
from tools.onboarding_mapper.backend.catalog import resolve_catalog_entry
from tools.onboarding_mapper.backend.mapping import (
    build_mapping_document,
    serialize_mapping_document,
    suggest_column_mapping,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_list_tables_returns_catalog(client: TestClient) -> None:
    response = client.get("/api/tables")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) >= 20
    assert any(item["package"] == "frtb_rrao" for item in payload)


def test_suggest_mapping_uses_aliases() -> None:
    entry = resolve_catalog_entry("frtb_rrao", "positions")
    mapping = suggest_column_mapping(entry.column_specs, ["positionId", "deskId", "AmountUSD"])
    assert mapping["position_id"] == "positionId"
    assert mapping["desk_id"] == "deskId"


def test_upload_csv_and_export_mapping(client: TestClient) -> None:
    table = pa.table(
        {
            "positionId": ["pos-1"],
            "sourceRowId": ["1"],
            "deskId": ["desk-a"],
            "legalEntity": ["LE1"],
            "grossEffectiveNotional": [1_000_000.0],
            "currency": ["USD"],
            "evidenceType": ["EXOTIC"],
            "evidenceLabel": ["barrier"],
            "lineage_source_system": ["demo"],
            "lineage_source_file": ["demo.csv"],
        }
    )
    buffer = io.BytesIO()
    pa_csv.write_csv(table, buffer)
    payload = buffer.getvalue()

    upload = client.post(
        "/api/source/upload?filename=demo.csv",
        content=payload,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert upload.status_code == 200
    session_id = upload.json()["session_id"]

    suggest = client.post(
        "/api/mapping/suggest",
        json={
            "session_id": session_id,
            "target_package": "frtb_rrao",
            "target_table_id": "positions",
        },
    )
    assert suggest.status_code == 200
    mapping = suggest.json()["mapping"]

    export = client.post(
        "/api/mapping/export",
        json={
            "session_id": session_id,
            "target_package": "frtb_rrao",
            "target_table_id": "positions",
            "mapping": mapping,
            "format": "yaml",
            "lineage_source_system": "demo_etl",
        },
    )
    assert export.status_code == 200
    assert "column_mapping:" in export.json()["content"]


def test_upload_csv_validate_mapping(client: TestClient) -> None:
    """Exercise the /api/mapping/validate endpoint."""
    table = pa.table(
        {
            "positionId": ["pos-1"],
            "sourceRowId": ["1"],
            "deskId": ["desk-a"],
            "legalEntity": ["LE1"],
            "grossEffectiveNotional": [1_000_000.0],
            "currency": ["USD"],
            "evidenceType": ["EXOTIC"],
            "evidenceLabel": ["barrier"],
            "lineage_source_system": ["demo"],
            "lineage_source_file": ["demo.csv"],
        }
    )
    buffer = io.BytesIO()
    pa_csv.write_csv(table, buffer)
    payload = buffer.getvalue()

    upload = client.post(
        "/api/source/upload?filename=demo.csv",
        content=payload,
        headers={"Content-Type": "application/octet-stream"},
    )
    assert upload.status_code == 200
    session_id = upload.json()["session_id"]

    suggest = client.post(
        "/api/mapping/suggest",
        json={
            "session_id": session_id,
            "target_package": "frtb_rrao",
            "target_table_id": "positions",
        },
    )
    assert suggest.status_code == 200
    mapping = suggest.json()["mapping"]

    validate = client.post(
        "/api/mapping/validate",
        json={
            "session_id": session_id,
            "target_package": "frtb_rrao",
            "target_table_id": "positions",
            "mapping": mapping,
        },
    )
    assert validate.status_code == 200
    result = validate.json()
    assert result["accepted_rows"] >= 0
    assert "batch_built" in result
    assert isinstance(result["diagnostics"], list)


def test_mapping_document_serializers() -> None:
    entry = resolve_catalog_entry("frtb_rrao", "positions")
    document = build_mapping_document(
        entry=entry,
        mapping={"position_id": "POS"},
        source_connector="file",
        source_format="csv",
        source_path="/tmp/demo.csv",
        duckdb_database=None,
        duckdb_query=None,
        lineage_source_system="demo",
        lineage_source_file="demo.csv",
    )
    assert "version" in serialize_mapping_document(document, "json")
    assert "column_mapping:" in serialize_mapping_document(document, "yaml")
    assert "[target]" in serialize_mapping_document(document, "toml")
