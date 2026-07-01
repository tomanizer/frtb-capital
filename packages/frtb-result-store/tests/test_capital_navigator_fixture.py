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
    RRAO_ROWS,
    SBM_ROWS,
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
    assert all(artifact.uri.startswith("file://") for artifact in artifacts)
    assert {artifact.artifact_id: artifact.row_count for artifact in artifacts} == (
        _expected_artifact_row_counts()
    )
    assert {artifact.artifact_type for artifact in artifacts} >= {
        ArtifactType.IMA_PNL_VECTOR,
        ArtifactType.SBM_SENSITIVITY_TABLE,
        ArtifactType.DRC_JTD_TABLE,
        ArtifactType.RRAO_EXPOSURE_TABLE,
        ArtifactType.CVA_EXPOSURE_TABLE,
        ArtifactType.ATTRIBUTION_VECTOR,
    }

    assert len(store.input_snapshot_manifests(run_id)) == 5
    assert store.lineage_for_result(run_id, "total")[0].source_id == bundle.run.input_snapshot_id
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
    _assert_drc_artifact_page(client, run_id)
    _assert_cva_artifact_page(client, run_id)
    _assert_ima_artifact_page(client, run_id)
    _assert_sbm_artifact_page(client, run_id)
    _assert_rrao_artifact_page(client, run_id)
    _assert_attribution_artifact_page(client, run_id)


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
