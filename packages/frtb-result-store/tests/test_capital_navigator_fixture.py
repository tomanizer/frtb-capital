from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi.testclient import TestClient
from fixtures.capital_navigator_bundle import capital_navigator_bundle
from fixtures.capital_navigator_drillthrough_attribution_rows import ATTRIBUTION_ROWS
from fixtures.capital_navigator_drillthrough_component_rows import (
    CVA_ROWS,
    DRC_ROWS,
    IMA_ROWS,
    IMA_SCENARIO_VECTOR_ROWS,
    RFET_OBSERVATION_TIMELINE_ROWS,
    RRAO_ROWS,
    SBM_ROWS,
    SBM_CURVATURE_SHOCK_DOWN_ROWS,
    SBM_CURVATURE_SHOCK_UP_ROWS,
    USD_SWAPTION_VOL_SURFACE_ROWS,
)
from fixtures.result_store_bundle import run_with_id
from frtb_result_store import (
    ArtifactType,
    DuckDbParquetResultStore,
    FrtbComponent,
    ResultBundle,
    RunStatus,
    create_result_store_app,
)


def test_capital_navigator_fixture_persists_full_suite_read_model(tmp_path: Path) -> None:
    store, bundle = _write_capital_navigator_bundle(tmp_path)
    run_id = bundle.run.run_id

    summary = store.capital_summary(run_id)[0]
    assert summary.total_capital == 210.0
    assert summary.currency == "USD"
    assert summary.lifecycle_status is RunStatus.CANDIDATE
    assert summary.suggested_status is RunStatus.VALIDATED

    assert [node.node_id for node in store.child_nodes(run_id, "total")] == [
        "ima",
        "sa",
        "cva",
    ]
    assert [node.node_id for node in store.child_nodes(run_id, "sa")] == [
        "sbm",
        "drc",
        "rrao",
    ]
    assert [node.node_id for node in store.child_nodes(run_id, "ima")] == [
        "ima-rates-desk",
        "ima-credit-desk",
    ]
    assert len(store.capital_tree(run_id)) == 28

    artifacts = store.artifact_refs(run_id)
    available_artifacts = [
        artifact
        for artifact in artifacts
        if artifact.metadata.get("artifact_status", "AVAILABLE") == "AVAILABLE"
    ]
    unavailable_artifacts = {
        artifact.artifact_id: artifact
        for artifact in artifacts
        if artifact.metadata.get("artifact_status") in {"NO_DATA", "UNSUPPORTED"}
    }
    assert all(artifact.uri.startswith("file://") for artifact in available_artifacts)
    assert {artifact.artifact_id: artifact.row_count for artifact in available_artifacts} == (
        _expected_artifact_row_counts()
    )
    assert {
        artifact_id: artifact.metadata["artifact_status"]
        for artifact_id, artifact in unavailable_artifacts.items()
    } == {
        "navigator-cva-full-vol-surface-unsupported": "UNSUPPORTED",
        "navigator-crif-lines-unsupported": "UNSUPPORTED",
        "navigator-rfet-observation-timeline-no-data": "NO_DATA",
        "navigator-stress-loss-series-no-data": "NO_DATA",
        "navigator-upl-time-series-no-data": "NO_DATA",
    }
    assert all(artifact.row_count == 0 for artifact in unavailable_artifacts.values())
    assert all(artifact.format == "none" for artifact in unavailable_artifacts.values())
    assert {artifact.artifact_type for artifact in artifacts} >= {
        ArtifactType.IMA_PNL_VECTOR,
        ArtifactType.SBM_SENSITIVITY_TABLE,
        ArtifactType.DRC_JTD_TABLE,
        ArtifactType.RRAO_EXPOSURE_TABLE,
        ArtifactType.CVA_EXPOSURE_TABLE,
        ArtifactType.ATTRIBUTION_VECTOR,
        ArtifactType.TIME_SERIES,
        ArtifactType.SHOCK_DEFINITION,
        ArtifactType.SCENARIO_VECTOR_METADATA,
        ArtifactType.SURFACE_GRID,
    }

    assert len(store.input_snapshot_manifests(run_id)) == 5
    assert store.lineage_for_result(run_id, "total")[0].source_id == bundle.run.input_snapshot_id
    assert {row.source_id for row in store.lineage_for_result(run_id, "ima-rates-desk")} >= {
        "navigator-ima-pnl-vector",
        "navigator-rfet-observation-timeline",
        "navigator-ima-scenario-vector",
    }
    assert {row.source_id for row in store.lineage_for_result(run_id, "sbm-girr-usd")} >= {
        "navigator-sbm-sensitivities",
        "navigator-sbm-curvature-shock-up",
        "navigator-sbm-curvature-shock-down",
        "navigator-usd-swaption-vol-surface",
    }
    assert store.movement_summary(run_id)[0].delta_amount == 6.0


def test_capital_navigator_fixture_populates_component_marts(tmp_path: Path) -> None:
    store, bundle = _write_capital_navigator_bundle(tmp_path)
    run_id = bundle.run.run_id

    breakdown = {row.component: row.amount for row in store.component_breakdown(run_id)}
    assert breakdown == {
        FrtbComponent.CVA: 38.0,
        FrtbComponent.DRC: 28.0,
        FrtbComponent.IMA: 70.0,
        FrtbComponent.RRAO: 9.0,
        FrtbComponent.STANDARDISED_APPROACH: 102.0,
        FrtbComponent.SBM: 65.0,
    }

    ima_rows = store.mart_rows(run_id, "ima_desk_dashboard")
    assert {
        (row["desk_id"], row["portfolio_count"], row["book_count"], row["capital"])
        for row in ima_rows
    } == {
        ("credit", 1, 1, 28.0),
        ("rates", 1, 1, 42.0),
    }

    sbm_rows = store.mart_rows(run_id, "sbm_bucket_ladder")
    assert {(row["risk_class"], row["bucket"], row["capital"]) for row in sbm_rows} == {
        ("CSR_NON_SEC", "IG", 15.0),
        ("EQ", "LARGE_CAP", 8.0),
        ("GIRR", "EUR", 7.0),
        ("GIRR", "USD", 35.0),
    }

    drc_rows = store.mart_rows(run_id, "drc_issuer_contributors")
    assert {(row["issuer_id"], row["capital"], row["artifact_id"]) for row in drc_rows} == {
        ("issuer-alpha", 18.0, "navigator-drc-jtd"),
        ("issuer-beta", 4.0, "navigator-drc-jtd"),
        ("issuer-gamma", 6.0, "navigator-drc-jtd"),
    }

    cva_rows = store.mart_rows(run_id, "cva_counterparty_contributors")
    assert {(row["counterparty_id"], row["capital"], row["artifact_id"]) for row in cva_rows} == {
        ("counterparty-bank-a", 20.0, "navigator-cva-exposures"),
        ("counterparty-corp-c", 8.0, "navigator-cva-exposures"),
        ("counterparty-fund-b", 10.0, "navigator-cva-exposures"),
    }

    rrao_rows = store.mart_rows(run_id, "rrao_exposure_summary")
    assert {
        (row["exposure_class"], row["capital"], row["artifact_id"])
        for row in rrao_rows
        if row["capital"] > 0.0
    } == {
        ("CLIFF_RISK", 2.0, "navigator-rrao-exposures"),
        ("EXOTIC_UNDERLIER", 4.0, "navigator-rrao-exposures"),
        ("GAP_RISK", 3.0, "navigator-rrao-exposures"),
    }
    assert all(row["exposure_class"] != "RRAO" for row in rrao_rows)


def test_capital_navigator_fixture_populates_attribution_projections(
    tmp_path: Path,
) -> None:
    store, bundle = _write_capital_navigator_bundle(tmp_path)
    run_id = bundle.run.run_id

    top = store.top_contributors(run_id, limit=30)
    assert top[0]["attribution_id"] == "ima-desk-rates"
    assert {row["component"] for row in top} >= {"IMA", "SBM", "DRC", "RRAO", "CVA"}
    assert any(
        row["method"] == "ANALYTICAL_EULER" and row["artifact_id"] == "navigator-sbm-sensitivities"
        for row in top
    )
    assert any(
        row["method"] == "STANDALONE" and row["artifact_id"] == "navigator-rrao-exposures"
        for row in top
    )
    assert _bundle_attribution_rows_by_id(bundle) == _parquet_attribution_rows_by_id()

    unsupported = store.unsupported_attribution_records(run_id)
    assert {row["category"] for row in unsupported} >= {
        "CVA_UNSUPPORTED_BRANCH",
        "SES_NMRF_TYPE_A",
        "SES_NMRF_TYPE_B",
    }
    assert any(row["source_level"] == "UNSUPPORTED_BRANCH" for row in unsupported)
    assert any(row["source_level"] == "RISK_FACTOR" for row in unsupported)

    residual = store.residual_attribution_records(run_id)
    assert [row["attribution_id"] for row in residual] == ["suite-unreconciled-residual"]
    assert residual[0]["source_id"] == "navigator-suite-residual"
    assert residual[0]["source_level"] == "RESIDUAL_BRANCH"
    assert residual[0]["residual"] == 1.25
    assert residual[0]["target_type"] == "RESIDUAL_BRANCH"
    assert residual[0]["target_id"] == "navigator-suite-residual-target"
    assert residual[0]["artifact_id"] == "navigator-suite-attribution"


def test_capital_navigator_fixture_serves_local_artifact_pages(tmp_path: Path) -> None:
    store, bundle = _write_capital_navigator_bundle(tmp_path)
    run_id = bundle.run.run_id
    client = TestClient(create_result_store_app(store))

    assert run_id == "frtb/capital-navigator/2026-06-03/us-npr"
    _assert_run_detail_routes(client, run_id)
    _assert_artifact_row_counts(client, store, run_id)
    _assert_metadata_catalog_routes(client, run_id)
    _assert_metadata_lineage_routes(client, run_id)
    _assert_drc_artifact_page(client, run_id)
    _assert_cva_artifact_page(client, run_id)
    _assert_ima_artifact_page(client, run_id)
    _assert_sbm_artifact_page(client, run_id)
    _assert_rrao_artifact_page(client, run_id)
    _assert_attribution_artifact_page(client, run_id)
    _assert_metadata_artifact_pages(client, run_id)
    _assert_unavailable_artifacts_listed(client, run_id)


def _assert_run_detail_routes(client: TestClient, run_id: str) -> None:
    raw_run_response = client.get(f"/runs/{run_id}")
    assert raw_run_response.status_code == 200, raw_run_response.text
    assert raw_run_response.json()["run_id"] == run_id
    encoded_run_response = client.get(f"/runs/{quote(run_id, safe='')}")
    assert encoded_run_response.status_code == 200, encoded_run_response.text
    assert encoded_run_response.json()["run_id"] == run_id


def _assert_artifact_row_counts(
    client: TestClient,
    store: DuckDbParquetResultStore,
    run_id: str,
) -> None:
    artifacts = {artifact.artifact_id: artifact for artifact in store.artifact_refs(run_id)}
    assert artifacts["navigator-drc-jtd"].row_count == 4
    assert artifacts["navigator-cva-exposures"].row_count == 5
    for artifact_id, expected_count in _expected_artifact_row_counts().items():
        page = _artifact_page(client, run_id, artifact_id, params={"limit": 1000})
        assert page["mode"] == "local_parquet"
        assert page["row_count"] == expected_count
        assert page["returned"] == expected_count


def _assert_metadata_catalog_routes(client: TestClient, run_id: str) -> None:
    time_series = client.get(f"/runs/{run_id}/time-series")
    assert time_series.status_code == 200, time_series.text
    assert time_series.json()["status_counts"] == {
        "AVAILABLE": 1,
        "NO_DATA": 3,
        "UNSUPPORTED": 0,
    }
    time_series_catalog = {
        row["partition_values"].get("time_series_id"): row for row in time_series.json()["catalog"]
    }
    assert time_series_catalog["ts-rfet-usd-5y"]["artifact_status"] == "AVAILABLE"
    assert time_series_catalog["ts-rfet-usd-5y"]["row_count"] == len(
        RFET_OBSERVATION_TIMELINE_ROWS
    )
    assert time_series_catalog["ts-plat-upl"]["artifact_status"] == "NO_DATA"
    assert time_series_catalog["ts-plat-upl"]["navigator_role"] == "plat_upl"

    shocks = client.get(f"/runs/{run_id}/shocks")
    assert shocks.status_code == 200, shocks.text
    assert shocks.json()["status_counts"] == {"AVAILABLE": 2, "NO_DATA": 0, "UNSUPPORTED": 0}
    shock_catalog = {
        row["partition_values"].get("shock_id"): row for row in shocks.json()["catalog"]
    }
    assert shock_catalog["shock-sbm-curvature-up"]["artifact_status"] == "AVAILABLE"
    assert shock_catalog["shock-sbm-curvature-down"]["row_count"] == len(
        SBM_CURVATURE_SHOCK_DOWN_ROWS
    )

    scenario_vectors = client.get(f"/runs/{run_id}/scenario-vectors")
    assert scenario_vectors.status_code == 200, scenario_vectors.text
    assert scenario_vectors.json()["status_counts"] == {
        "AVAILABLE": 1,
        "NO_DATA": 0,
        "UNSUPPORTED": 0,
    }
    assert scenario_vectors.json()["catalog"][0]["partition_values"] == {
        "scenario_set_id": "scenario-set-250d",
        "scenario_vector_id": "scenario-vector-rtpl",
    }

    surfaces = client.get(f"/runs/{run_id}/surfaces")
    assert surfaces.status_code == 200, surfaces.text
    assert surfaces.json()["status_counts"] == {"AVAILABLE": 1, "NO_DATA": 0, "UNSUPPORTED": 1}
    surface_catalog = {
        row["partition_values"].get("surface_id"): row for row in surfaces.json()["catalog"]
    }
    assert surface_catalog["surface-usd-swaption-vol"]["navigator_role"] == "sbm_vega_surface"
    assert surface_catalog["surface-cva-full-vol-cube"]["artifact_status"] == "UNSUPPORTED"


def _assert_metadata_lineage_routes(client: TestClient, run_id: str) -> None:
    ima_lineage = client.get(f"/runs/{run_id}/nodes/ima-rates-desk/lineage")
    assert ima_lineage.status_code == 200, ima_lineage.text
    assert {row["source_id"] for row in ima_lineage.json()["lineage"]} >= {
        "navigator-rfet-observation-timeline",
        "navigator-ima-scenario-vector",
    }

    sbm_lineage = client.get(f"/runs/{run_id}/nodes/sbm-girr-usd/lineage")
    assert sbm_lineage.status_code == 200, sbm_lineage.text
    assert {row["source_id"] for row in sbm_lineage.json()["lineage"]} >= {
        "navigator-sbm-curvature-shock-up",
        "navigator-sbm-curvature-shock-down",
        "navigator-usd-swaption-vol-surface",
    }


def _assert_drc_artifact_page(client: TestClient, run_id: str) -> None:
    drc_page = _artifact_page(
        client,
        run_id,
        "navigator-drc-jtd",
        params={"columns": "issuer_id,net_jtd", "filter": "issuer_id=issuer-gamma"},
    )
    assert drc_page["mode"] == "local_parquet"
    assert drc_page["rows"] == [{"issuer_id": "issuer-gamma", "net_jtd": 6.0}]


def _assert_cva_artifact_page(client: TestClient, run_id: str) -> None:
    cva_page = _artifact_page(
        client,
        run_id,
        "navigator-cva-exposures",
        params={
            "columns": "counterparty_id,capital",
            "filter": "counterparty_id=counterparty-corp-c",
        },
    )
    assert cva_page["mode"] == "local_parquet"
    assert [row["capital"] for row in cva_page["rows"]] == [5.0, 3.0]


def _assert_ima_artifact_page(client: TestClient, run_id: str) -> None:
    ima_page = _artifact_page(
        client,
        run_id,
        "navigator-ima-pnl-vector",
        params={
            "columns": "desk_id,modellability_status,ses_component",
            "filter": "desk_id=credit",
        },
    )
    assert ima_page["mode"] == "local_parquet"
    assert {row["modellability_status"] for row in ima_page["rows"]} >= {
        "TYPE_A_NMRF",
        "TYPE_B_NMRF",
    }
    assert {row["ses_component"] for row in ima_page["rows"]} >= {
        "SES_NMRF_TYPE_A",
        "SES_NMRF_TYPE_B",
    }


def _assert_sbm_artifact_page(client: TestClient, run_id: str) -> None:
    sbm_page = _artifact_page(
        client,
        run_id,
        "navigator-sbm-sensitivities",
        params={"columns": "risk_class,bucket,sensitivity_id", "filter": "risk_class=EQ"},
    )
    assert sbm_page["mode"] == "local_parquet"
    assert sbm_page["rows"] == [
        {
            "risk_class": "EQ",
            "bucket": "LARGE_CAP",
            "sensitivity_id": "sensitivity-equity-large-a",
        },
        {
            "risk_class": "EQ",
            "bucket": "LARGE_CAP",
            "sensitivity_id": "sensitivity-equity-large-b",
        },
    ]


def _assert_rrao_artifact_page(client: TestClient, run_id: str) -> None:
    rrao_page = _artifact_page(
        client,
        run_id,
        "navigator-rrao-exposures",
        params={
            "columns": "exposure_class,exposure_id,capital",
            "filter": "exposure_class=GAP_RISK",
        },
    )
    assert rrao_page["mode"] == "local_parquet"
    assert rrao_page["rows"] == [
        {
            "exposure_class": "GAP_RISK",
            "exposure_id": "rrao-line-gap-001",
            "capital": 3.0,
        },
    ]


def _assert_attribution_artifact_page(client: TestClient, run_id: str) -> None:
    attribution_page = _artifact_page(
        client,
        run_id,
        "navigator-suite-attribution",
        params={
            "columns": "attribution_id,method,residual,target_id",
            "filter": "attribution_id=suite-unreconciled-residual",
        },
    )
    assert attribution_page["mode"] == "local_parquet"
    assert attribution_page["rows"] == [
        {
            "attribution_id": "suite-unreconciled-residual",
            "method": "RESIDUAL",
            "residual": 1.25,
            "target_id": "navigator-suite-residual-target",
        },
    ]


def _assert_metadata_artifact_pages(client: TestClient, run_id: str) -> None:
    timeline = client.get(f"/runs/{run_id}/time-series/ts-rfet-usd-5y/points")
    assert timeline.status_code == 200, timeline.text
    timeline_payload = timeline.json()
    assert timeline_payload["row_count"] == len(RFET_OBSERVATION_TIMELINE_ROWS)
    assert timeline_payload["filtered_row_count"] == len(RFET_OBSERVATION_TIMELINE_ROWS)
    assert timeline_payload["returned"] == len(RFET_OBSERVATION_TIMELINE_ROWS)
    assert [row["source_row_id"] for row in timeline_payload["rows"]] == [
        "rfet-row-001",
        "rfet-row-002",
    ]
    assert {row["mapping_version"] for row in timeline_payload["rows"]} == {
        "risk-factor-map-v1"
    }

    shock = client.get(f"/runs/{run_id}/shocks/shock-sbm-curvature-up")
    assert shock.status_code == 200, shock.text
    shock_payload = shock.json()
    assert shock_payload["row_count"] == len(SBM_CURVATURE_SHOCK_UP_ROWS)
    assert shock_payload["filtered_row_count"] == len(SBM_CURVATURE_SHOCK_UP_ROWS)
    assert shock_payload["returned"] == len(SBM_CURVATURE_SHOCK_UP_ROWS)
    assert shock_payload["rows"] == [
        {
            "run_id": run_id,
            "shock_id": "shock-sbm-curvature-up",
            "shock_direction": "UP",
            "shock_type": "ABSOLUTE",
            "magnitude": 125.0,
            "unit": "bp",
            "risk_factor_id": "rf-girr-usd-5y",
            "scenario_id": None,
            "mapping_version": "shock-map-v1",
            "regulatory_rule_id": "MAR21.96",
            "source_row_id": "shock-row-up-001",
        }
    ]

    scenario = client.get(
        f"/runs/{run_id}/scenario-vectors/scenario-set-250d/scenario-vector-rtpl/metadata"
    )
    assert scenario.status_code == 200, scenario.text
    scenario_payload = scenario.json()
    assert scenario_payload["row_count"] == len(IMA_SCENARIO_VECTOR_ROWS)
    assert scenario_payload["filtered_row_count"] == len(IMA_SCENARIO_VECTOR_ROWS)
    assert scenario_payload["returned"] == len(IMA_SCENARIO_VECTOR_ROWS)
    assert [row["scenario_label"] for row in scenario_payload["rows"]] == [
        "RTPL day 1",
        "RTPL day 2",
    ]
    assert {row["mapping_version"] for row in scenario_payload["rows"]} == {
        "scenario-map-v1"
    }

    surface = client.get(
        f"/runs/{run_id}/surfaces/surface-usd-swaption-vol/slice",
        params={"axis_1_value": "3M"},
    )
    assert surface.status_code == 200, surface.text
    surface_payload = surface.json()
    assert surface_payload["row_count"] == len(USD_SWAPTION_VOL_SURFACE_ROWS)
    assert surface_payload["filtered_row_count"] == 1
    assert surface_payload["returned"] == 1
    assert surface_payload["rows"][0]["surface_point_id"] == "surface-usd-swaption-vol:3m:5y"
    assert surface_payload["rows"][0]["mapping_version"] == "surface-map-v1"


def _assert_unavailable_artifacts_listed(client: TestClient, run_id: str) -> None:
    response = client.get(f"/runs/{run_id}/artifacts")
    assert response.status_code == 200, response.text
    artifacts = {artifact["artifact_id"]: artifact for artifact in response.json()["artifacts"]}

    assert artifacts["navigator-upl-time-series-no-data"]["metadata"]["artifact_status"] == (
        "NO_DATA"
    )
    assert artifacts["navigator-upl-time-series-no-data"]["metadata"]["partition_values"] == {
        "time_series_id": "ts-plat-upl"
    }
    assert artifacts["navigator-crif-lines-unsupported"]["metadata"]["artifact_status"] == (
        "UNSUPPORTED"
    )
    assert artifacts["navigator-upl-time-series-no-data"]["format"] == "none"
    assert artifacts["navigator-upl-time-series-no-data"]["partition_keys"] == ["time_series_id"]
    assert artifacts["navigator-crif-lines-unsupported"]["row_count"] == 0

    page = _artifact_page(client, run_id, "navigator-upl-time-series-no-data")
    assert page["mode"] == "artifact_unavailable"
    assert page["artifact_status"] == "NO_DATA"
    assert page["row_count"] == 0
    assert page["filtered_row_count"] == 0
    assert page["returned"] == 0
    assert page["rows"] == []

    semantic_timeline = client.get(f"/runs/{run_id}/time-series/ts-plat-upl/points")
    assert semantic_timeline.status_code == 200, semantic_timeline.text
    assert semantic_timeline.json()["mode"] == "artifact_unavailable"
    assert semantic_timeline.json()["artifact_status"] == "NO_DATA"
    assert semantic_timeline.json()["row_count"] == 0
    assert semantic_timeline.json()["filtered_row_count"] == 0
    assert semantic_timeline.json()["returned"] == 0
    assert semantic_timeline.json()["status_reason"].startswith("UPL time series")

    download = client.get(f"/runs/{run_id}/artifacts/navigator-crif-lines-unsupported/download")
    assert download.status_code == 200, download.text
    assert download.json()["mode"] == "artifact_unavailable"
    assert download.json()["artifact_status"] == "UNSUPPORTED"

    unsupported_surface = client.get(
        f"/runs/{run_id}/surfaces/surface-cva-full-vol-cube/slice"
    )
    assert unsupported_surface.status_code == 200, unsupported_surface.text
    assert unsupported_surface.json()["mode"] == "artifact_unavailable"
    assert unsupported_surface.json()["artifact_status"] == "UNSUPPORTED"
    assert unsupported_surface.json()["row_count"] == 0


def _write_capital_navigator_bundle(
    tmp_path: Path,
    *,
    run_id: str | None = None,
) -> tuple[DuckDbParquetResultStore, ResultBundle]:
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    run = None if run_id is None else run_with_id(run_id)
    bundle = capital_navigator_bundle(run=run, artifact_root=store.root / "navigator-artifacts")
    store.write_bundle(bundle)
    return store, bundle


def _artifact_page(
    client: TestClient,
    run_id: str,
    artifact_id: str,
    *,
    params: dict[str, object] | None = None,
) -> dict[str, object]:
    response = client.get(
        f"/runs/{run_id}/artifacts/{artifact_id}/page",
        params={} if params is None else params,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _expected_artifact_row_counts() -> dict[str, int]:
    return {
        "navigator-ima-pnl-vector": len(IMA_ROWS),
        "navigator-sbm-sensitivities": len(SBM_ROWS),
        "navigator-drc-jtd": len(DRC_ROWS),
        "navigator-rrao-exposures": len(RRAO_ROWS),
        "navigator-cva-exposures": len(CVA_ROWS),
        "navigator-suite-attribution": len(ATTRIBUTION_ROWS),
        "navigator-rfet-observation-timeline": len(RFET_OBSERVATION_TIMELINE_ROWS),
        "navigator-sbm-curvature-shock-up": len(SBM_CURVATURE_SHOCK_UP_ROWS),
        "navigator-sbm-curvature-shock-down": len(SBM_CURVATURE_SHOCK_DOWN_ROWS),
        "navigator-ima-scenario-vector": len(IMA_SCENARIO_VECTOR_ROWS),
        "navigator-usd-swaption-vol-surface": len(USD_SWAPTION_VOL_SURFACE_ROWS),
    }


def _bundle_attribution_rows_by_id(bundle: ResultBundle) -> dict[str, dict[str, object]]:
    return {
        record.attribution_id: {
            "node_id": record.node_id,
            "source_id": record.source_id,
            "source_level": record.source_level,
            "target_type": record.target_type,
            "target_id": record.target_id,
            "category": record.category,
            "base_amount": record.base_amount,
            "contribution": record.contribution,
            "residual": record.residual,
            "method": record.method.value,
            "artifact_id": record.artifact_id,
        }
        for record in bundle.attributions
    }


def _parquet_attribution_rows_by_id() -> dict[str, dict[str, object]]:
    return {
        str(row["attribution_id"]): {
            "node_id": row["node_id"],
            "source_id": row["source_id"],
            "source_level": row["source_level"],
            "target_type": row["target_type"],
            "target_id": row["target_id"],
            "category": row["category"],
            "base_amount": row["base_amount"],
            "contribution": row["contribution"],
            "residual": row["residual"],
            "method": row["method"],
            "artifact_id": row["artifact_id"],
        }
        for row in ATTRIBUTION_ROWS
    }
