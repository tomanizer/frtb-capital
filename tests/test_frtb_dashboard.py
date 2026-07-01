"""Tests for the FRTB Capital Navigator dashboard."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tools.frtb_dashboard.backend.app import app
from tools.frtb_dashboard.backend.demo_runs import (
    build_demo_run,
    grid_view,
    ima_desk_view,
    inspector_view,
    jsonable_payload,
    list_demo_runs,
    metadata_view,
    node_detail,
    run_overview,
    sa_overview,
)


def test_demo_run_builds() -> None:
    run = build_demo_run()
    overview = run_overview(run)
    assert overview.binding_total is not None
    assert overview.binding_total > 0
    assert overview.binding_side in {"IMA", "FLOOR"}
    assert len(overview.nodes) >= 10


def test_metadata_exposes_business_hierarchy_coverage() -> None:
    run = build_demo_run()
    metadata = metadata_view(run)
    dimensions = {node.dimension for node in metadata.dimensions}
    assert {
        "Top of House",
        "Legal Entity",
        "Division",
        "Business Line",
        "Desk",
        "Volcker Desk",
        "Book",
    }.issubset(dimensions)


def test_hierarchy_scope_changes_totals_and_rows() -> None:
    run = build_demo_run()
    top = run_overview(run)
    rates = run_overview(run, hierarchy_node_id="book-rates-fixture")
    credit = run_overview(run, hierarchy_node_id="book-credit-fixture")
    residual = run_overview(run, hierarchy_node_id="book-residual-fixture")

    assert top.sa_total is not None and top.sa_total > rates.sa_total > 0
    assert credit.ima_total == 0
    assert credit.sa_total is not None and credit.sa_total > 0
    assert residual.sa_total is not None and residual.sa_total > 0

    rates_grid = grid_view(run, framework="SA", hierarchy_node_id="book-rates-fixture")
    credit_grid = grid_view(run, framework="SA", hierarchy_node_id="book-credit-fixture")
    residual_grid = grid_view(run, framework="SA", hierarchy_node_id="book-residual-fixture")

    assert {row.component for row in rates_grid.rows} == {"SA", "SBM"}
    assert {row.component for row in credit_grid.rows} == {"SA", "DRC"}
    assert {row.component for row in residual_grid.rows} == {"SA", "RRAO"}


def test_sa_grid_exposes_sbm_scenarios_and_drc_rows() -> None:
    run = build_demo_run()
    grid = grid_view(run, framework="SA", scenario="Binding")
    assert grid.rows
    assert any(row.component == "SBM" and row.base_rho is not None for row in grid.rows)
    assert any(row.component == "DRC" and row.row_type == "BUCKET" for row in grid.rows)


def test_sbm_scenario_changes_grid_amounts() -> None:
    run = build_demo_run()
    base = grid_view(run, framework="SA", scenario="Base", hierarchy_node_id="book-rates-fixture")
    high = grid_view(run, framework="SA", scenario="High", hierarchy_node_id="book-rates-fixture")
    low = grid_view(run, framework="SA", scenario="Low", hierarchy_node_id="book-rates-fixture")

    base_sbm = next(row for row in base.rows if row.row_id == "sa-sbm")
    high_sbm = next(row for row in high.rows if row.row_id == "sa-sbm")
    low_sbm = next(row for row in low.rows if row.row_id == "sa-sbm")

    assert high_sbm.capital != base_sbm.capital
    assert low_sbm.capital != base_sbm.capital


def test_ima_desk_has_attribution() -> None:
    run = build_demo_run()
    desk = ima_desk_view(run, run.desk_record.desk_id)
    assert desk.imcc
    assert desk.ses_nmrf.get("selected_stress_periods") is not None
    assert isinstance(desk.attributions, list)


def test_supporting_views_and_json_payloads() -> None:
    run = build_demo_run()
    runs = list_demo_runs()
    node = node_detail(run, "sa")
    sa = sa_overview(run)
    payload = jsonable_payload({"node_id": node.node.node_id, "measure_count": len(node.measures)})

    assert runs[0].run_id == run.summary.run_id
    assert node.node.node_id == "sa"
    assert node.measures
    assert sa.total_capital > 0
    assert sa.components
    assert isinstance(payload, dict)
    assert payload["node_id"] == "sa"


def test_inspector_links_aggregate_to_source_rows() -> None:
    run = build_demo_run()
    inspector = inspector_view(run, "sa-drc")
    assert inspector.attribution
    assert inspector.audit_rows
    assert inspector.tabs[0].key == "attribution"


def test_drc_bucket_inspector_filters_to_selected_bucket() -> None:
    run = build_demo_run()
    inspector = inspector_view(
        run,
        "sa-drc-drc-corporate",
        hierarchy_node_id="book-credit-fixture",
    )
    assert inspector.attribution
    assert {row.bucket for row in inspector.audit_rows} == {"CORPORATE"}
    assert all("corporate" in row.source_id.lower() for row in inspector.audit_rows)


def test_api_run_overview() -> None:
    client = TestClient(app)
    response = client.get("/api/runs/demo-suite-001?hierarchyNodeId=book-credit-fixture")
    assert response.status_code == 200
    payload = response.json()
    assert payload["binding_total"] > 0
    assert payload["suite_total"] == payload["binding_total"]
    assert payload["ima_total"] == 0


def test_api_supporting_endpoints() -> None:
    client = TestClient(app)

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    runs = client.get("/api/runs")
    assert runs.status_code == 200
    assert runs.json()[0]["run_id"] == "demo-suite-001"

    metadata = client.get("/api/runs/demo-suite-001/metadata")
    assert metadata.status_code == 200
    assert metadata.json()["dimensions"]

    node = client.get("/api/runs/demo-suite-001/nodes/sa")
    assert node.status_code == 200
    assert node.json()["node"]["node_id"] == "sa"

    ima = client.get("/api/runs/demo-suite-001/ima/desks/rates-credit-demo")
    assert ima.status_code == 200
    assert ima.json()["desk_id"] == "rates-credit-demo"

    sa = client.get("/api/runs/demo-suite-001/sa")
    assert sa.status_code == 200
    assert sa.json()["components"]


def test_api_grid_and_inspector() -> None:
    client = TestClient(app)
    grid_response = client.get(
        "/api/runs/demo-suite-001/grid"
        "?framework=SA&scenario=Binding&hierarchyNodeId=book-credit-fixture"
    )
    assert grid_response.status_code == 200
    grid_payload = grid_response.json()
    assert grid_payload["framework"] == "SA"
    assert grid_payload["row_count"] > 0

    row_id = next(row["row_id"] for row in grid_payload["rows"] if row["component"] == "DRC")
    inspector_response = client.get(
        f"/api/runs/demo-suite-001/inspector?row_id={row_id}"
        "&hierarchyNodeId=book-credit-fixture&scenario=Binding"
    )
    assert inspector_response.status_code == 200
    assert inspector_response.json()["audit_rows"]


def test_api_cva_no_data_state() -> None:
    client = TestClient(app)
    response = client.get("/api/runs/demo-suite-001/grid?framework=CVA")
    assert response.status_code == 200
    payload = response.json()
    assert payload["rows"][0]["status"] == "no_data"
