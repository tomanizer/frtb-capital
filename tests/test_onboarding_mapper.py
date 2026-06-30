"""Tests for the FRTB onboarding mapper tool."""

from __future__ import annotations

import io
import json

import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.csv as pa_csv  # type: ignore[import-untyped]
import pytest
from fastapi.testclient import TestClient
from frtb_common import ColumnSpec, TabularLogicalType

from tools.onboarding_mapper.backend.app import app
from tools.onboarding_mapper.backend.catalog import resolve_catalog_entry
from tools.onboarding_mapper.backend.config import Settings
from tools.onboarding_mapper.backend.mapping import (
    build_mapping_document,
    parse_mapping_document,
    serialize_mapping_document,
    suggest_column_mapping,
)
from tools.onboarding_mapper.backend.sessions import SessionStore


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


def test_suggest_mapping_normalizes_separators_and_case() -> None:
    specs = [
        ColumnSpec("position_id", aliases=(), logical_type=TabularLogicalType.STRING),
        ColumnSpec("desk_id", aliases=(), logical_type=TabularLogicalType.STRING),
        ColumnSpec("legal_entity", aliases=(), logical_type=TabularLogicalType.STRING),
    ]
    # Separator/case-style differences resolve even without declared aliases.
    mapping = suggest_column_mapping(specs, ["POSITION-ID", "Desk Id", "legalEntity"])
    assert mapping["position_id"] == "POSITION-ID"
    assert mapping["desk_id"] == "Desk Id"
    assert mapping["legal_entity"] == "legalEntity"


def test_suggest_mapping_matches_reordered_tokens() -> None:
    specs = [ColumnSpec("position_id", aliases=(), logical_type=TabularLogicalType.STRING)]
    mapping = suggest_column_mapping(specs, ["id_position"])
    assert mapping["position_id"] == "id_position"


def test_suggest_mapping_does_not_expand_abbreviations() -> None:
    # POS is a defensible no-match against ``position``; the matcher stays
    # conservative rather than guessing.
    specs = [ColumnSpec("position_id", aliases=(), logical_type=TabularLogicalType.STRING)]
    mapping = suggest_column_mapping(specs, ["POS_ID"])
    assert mapping["position_id"] is None


def test_suggest_mapping_consumes_each_source_once() -> None:
    specs = [
        ColumnSpec("position_id", aliases=(), logical_type=TabularLogicalType.STRING),
        ColumnSpec("desk_id", aliases=("position_id",), logical_type=TabularLogicalType.STRING),
    ]
    mapping = suggest_column_mapping(specs, ["position_id"])
    assert mapping["position_id"] == "position_id"
    # The single source column is already consumed, so the alias collision on the
    # second spec finds nothing left.
    assert mapping["desk_id"] is None


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


@pytest.mark.parametrize("fmt", ["yaml", "toml", "json"])
def test_mapping_document_round_trips_through_parser(fmt: str) -> None:
    entry = resolve_catalog_entry("frtb_rrao", "positions")
    document = build_mapping_document(
        entry=entry,
        mapping={"position_id": "POS", "desk_id": "DESK"},
        source_connector="file",
        source_format="csv",
        source_path="/tmp/demo.csv",
        duckdb_database=None,
        duckdb_query=None,
        lineage_source_system="demo",
        lineage_source_file="demo.csv",
    )
    content = serialize_mapping_document(document, fmt)
    parsed = parse_mapping_document(content, fmt)
    assert parsed["target"]["package"] == "frtb_rrao"
    assert parsed["target"]["input_table"] == "positions"
    assert parsed["column_mapping"]["position_id"] == "POS"
    # Format auto-detection succeeds without an explicit format hint.
    assert parse_mapping_document(content)["column_mapping"]["desk_id"] == "DESK"


def test_import_endpoint_filters_unknown_columns(client: TestClient) -> None:
    artifact = {
        "version": "1",
        "target": {"package": "frtb_rrao", "input_table": "positions"},
        "column_mapping": {"position_id": "POS", "not_a_real_field": "X"},
    }
    response = client.post(
        "/api/mapping/import",
        json={"content": json.dumps(artifact), "format": "json"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["target_package"] == "frtb_rrao"
    assert payload["mapping"]["position_id"] == "POS"
    assert payload["unknown_columns"] == ["not_a_real_field"]


def test_import_endpoint_rejects_malformed_artifact(client: TestClient) -> None:
    response = client.post(
        "/api/mapping/import",
        json={"content": "not a mapping document", "format": "json"},
    )
    assert response.status_code == 400


def test_path_source_rejects_paths_outside_data_roots(client: TestClient) -> None:
    response = client.post("/api/source/path", json={"path": "/etc/passwd"})
    assert response.status_code == 403
    assert "permitted data roots" in response.json()["detail"]


def test_upload_rejects_oversized_body(client: TestClient, monkeypatch) -> None:
    from tools.onboarding_mapper.backend import app as app_module

    tiny = Settings(
        allowed_origins=app_module.SETTINGS.allowed_origins,
        data_roots=app_module.SETTINGS.data_roots,
        max_upload_bytes=4,
        max_sessions=app_module.SETTINGS.max_sessions,
        session_ttl_seconds=app_module.SETTINGS.session_ttl_seconds,
    )
    monkeypatch.setattr(app_module, "SETTINGS", tiny)
    response = client.post(
        "/api/source/upload?filename=demo.csv",
        content=b"abcdefghij",
        headers={"Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 413


def test_session_store_evicts_lru_and_expired() -> None:
    table = pa.table({"a": [1]})
    settings = Settings(
        allowed_origins=("http://localhost",),
        data_roots=(),
        max_upload_bytes=1024,
        max_sessions=2,
        session_ttl_seconds=3600.0,
    )
    store = SessionStore(settings)
    first = store.create(table, source_name="a", source_kind="upload")
    store.create(table, source_name="b", source_kind="upload")
    store.create(table, source_name="c", source_kind="upload")
    # Oldest session evicted once the cap is exceeded.
    assert len(store) == 2
    with pytest.raises(KeyError):
        store.get(first)

    expiring = Settings(
        allowed_origins=("http://localhost",),
        data_roots=(),
        max_upload_bytes=1024,
        max_sessions=8,
        session_ttl_seconds=-1.0,
    )
    expiring_store = SessionStore(expiring)
    stale = expiring_store.create(table, source_name="d", source_kind="upload")
    with pytest.raises(KeyError):
        expiring_store.get(stale)
