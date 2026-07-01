from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from fixtures.capital_navigator_bundle import capital_navigator_bundle
from fixtures.result_store_bundle import run_with_id
from frtb_result_store import (
    ArtifactType,
    DuckDbParquetResultStore,
    FrtbComponent,
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

    unsupported = store.unsupported_attribution_records(run_id)
    assert {row["category"] for row in unsupported} >= {
        "CVA_UNSUPPORTED_BRANCH",
        "SES_NMRF_TYPE_A",
        "SES_NMRF_TYPE_B",
    }
    assert any(row["source_level"] == "UNSUPPORTED_BRANCH" for row in unsupported)
    assert any(row["source_level"] == "RISK_FACTOR" for row in unsupported)

    residual = store.residual_attribution_records(run_id)
    assert [row["attribution_id"] for row in residual] == ["suite-residual-zero"]
    assert residual[0]["source_level"] == "RESIDUAL_BRANCH"
    assert residual[0]["artifact_id"] == "navigator-suite-attribution"


def test_capital_navigator_fixture_serves_local_artifact_pages(tmp_path: Path) -> None:
    store, bundle = _write_capital_navigator_bundle(tmp_path, run_id="capital-navigator-api-run")
    run_id = bundle.run.run_id
    client = TestClient(create_result_store_app(store))

    artifacts = {artifact.artifact_id: artifact for artifact in store.artifact_refs(run_id)}
    assert artifacts["navigator-drc-jtd"].row_count == 4
    assert artifacts["navigator-cva-exposures"].row_count == 5

    drc_page = client.get(
        f"/runs/{run_id}/artifacts/navigator-drc-jtd/page",
        params={"columns": "issuer_id,net_jtd", "filter": "issuer_id=issuer-gamma"},
    ).json()
    assert drc_page["mode"] == "local_parquet"
    assert drc_page["rows"] == [{"issuer_id": "issuer-gamma", "net_jtd": 6.0}]

    cva_page = client.get(
        f"/runs/{run_id}/artifacts/navigator-cva-exposures/page",
        params={
            "columns": "counterparty_id,capital",
            "filter": "counterparty_id=counterparty-corp-c",
        },
    ).json()
    assert cva_page["mode"] == "local_parquet"
    assert [row["capital"] for row in cva_page["rows"]] == [5.0, 3.0]

    ima_page = client.get(
        f"/runs/{run_id}/artifacts/navigator-ima-pnl-vector/page",
        params={
            "columns": "desk_id,modellability_status,ses_component",
            "filter": "desk_id=credit",
        },
    ).json()
    assert {row["modellability_status"] for row in ima_page["rows"]} >= {
        "TYPE_A_NMRF",
        "TYPE_B_NMRF",
    }
    assert {row["ses_component"] for row in ima_page["rows"]} >= {
        "SES_NMRF_TYPE_A",
        "SES_NMRF_TYPE_B",
    }


def _write_capital_navigator_bundle(
    tmp_path: Path,
    *,
    run_id: str | None = None,
) -> tuple[DuckDbParquetResultStore, object]:
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    run = None if run_id is None else run_with_id(run_id)
    bundle = capital_navigator_bundle(run=run, artifact_root=store.root / "navigator-artifacts")
    store.write_bundle(bundle)
    return store, bundle
