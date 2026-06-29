"""Tests for the FRTB capital dashboard."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tools.frtb_dashboard.backend.app import app
from tools.frtb_dashboard.backend.demo_runs import build_demo_run, ima_desk_view, run_overview


def test_demo_run_builds() -> None:
    run = build_demo_run()
    overview = run_overview(run)
    assert overview.suite_total is not None
    assert overview.suite_total > 0
    assert len(overview.nodes) >= 10


def test_ima_desk_has_attribution() -> None:
    run = build_demo_run()
    desk = ima_desk_view(run, run.desk_record.desk_id)
    assert desk.imcc
    assert desk.ses_nmrf.get("selected_stress_periods") is not None
    assert isinstance(desk.attributions, list)


def test_api_run_overview() -> None:
    client = TestClient(app)
    response = client.get("/api/runs/demo-suite-001")
    assert response.status_code == 200
    payload = response.json()
    assert payload["suite_total"] > 0
    assert len(payload["nodes"]) >= 10


def test_api_ima_desk() -> None:
    client = TestClient(app)
    run = build_demo_run()
    desk_id = run.desk_record.desk_id
    response = client.get(f"/api/runs/demo-suite-001/ima/desks/{desk_id}")
    assert response.status_code == 200
    assert response.json()["desk_id"] == desk_id


def test_api_sa_overview() -> None:
    client = TestClient(app)
    response = client.get("/api/runs/demo-suite-001/sa")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_capital"] > 0
    assert {component["component"] for component in payload["components"]} == {"DRC", "RRAO", "SBM"}
    drc = next(component for component in payload["components"] if component["component"] == "DRC")
    assert drc["top_attribution"]


def test_api_drc_node_detail_has_attribution() -> None:
    client = TestClient(app)
    response = client.get("/api/runs/demo-suite-001/nodes/sa-drc")
    assert response.status_code == 200
    payload = response.json()
    assert payload["node"]["component"] == "DRC"
    assert payload["attributions"]
