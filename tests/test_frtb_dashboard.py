"""Tests for the FRTB capital dashboard."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tools.frtb_dashboard.backend.app import _cors_origins, app
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


def test_api_drc_bucket_node_is_scoped_to_its_own_bucket() -> None:
    # A DRC bucket node must not be aliased to the whole DRC component: its
    # capital and attribution rows must reflect only that bucket.
    client = TestClient(app)
    overview = client.get("/api/runs/demo-suite-001").json()
    drc = next(node for node in overview["nodes"] if node["node_id"] == "sa-drc")
    bucket_node = next(node for node in overview["nodes"] if node["node_type"] == "BUCKET")

    detail = client.get(f"/api/runs/demo-suite-001/nodes/{bucket_node['node_id']}").json()
    assert detail["node"]["amount"] == bucket_node["amount"]
    assert detail["node"]["amount"] < drc["amount"]

    assert detail["attributions"]
    bucket_attribution_total = sum(
        abs(row["contribution"] or 0.0) for row in detail["attributions"]
    )
    drc_detail = client.get("/api/runs/demo-suite-001/nodes/sa-drc").json()
    drc_attribution_total = sum(
        abs(row["contribution"] or 0.0) for row in drc_detail["attributions"]
    )
    assert bucket_attribution_total < drc_attribution_total


def test_api_unknown_route_returns_json_404() -> None:
    # The SPA fallback must not swallow unmatched API routes with the HTML shell.
    client = TestClient(app)
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")


def test_api_unknown_run_returns_404() -> None:
    client = TestClient(app)
    response = client.get("/api/runs/not-a-real-run")
    assert response.status_code == 404


def test_pla_node_is_provisional() -> None:
    # The PLA add-on amount is an indicative placeholder, not a modelled figure.
    client = TestClient(app)
    payload = client.get("/api/runs/demo-suite-001").json()
    pla = next(node for node in payload["nodes"] if node["node_id"] == "ima-pla")
    assert pla["provisional"] is True


def test_pla_desk_panel_flags_add_on_not_modelled() -> None:
    run = build_demo_run()
    desk = ima_desk_view(run, run.desk_record.desk_id)
    assert desk.pla.get("add_on_status") == "NOT_MODELLED"


def test_cors_origins_default_and_override(monkeypatch) -> None:
    monkeypatch.delenv("FRTB_DASHBOARD_CORS_ORIGINS", raising=False)
    assert "http://127.0.0.1:5174" in _cors_origins()
    monkeypatch.setenv("FRTB_DASHBOARD_CORS_ORIGINS", "https://a.example, https://b.example")
    assert _cors_origins() == ["https://a.example", "https://b.example"]
