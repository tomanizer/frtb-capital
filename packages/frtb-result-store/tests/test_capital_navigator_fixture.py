from __future__ import annotations

from pathlib import Path

from fixtures.capital_navigator_bundle import capital_navigator_bundle
from frtb_result_store import (
    ArtifactType,
    DuckDbParquetResultStore,
    FrtbComponent,
    RunStatus,
)


def test_capital_navigator_fixture_persists_full_suite_read_model(tmp_path: Path) -> None:
    bundle = capital_navigator_bundle()
    run_id = bundle.run.run_id
    store = DuckDbParquetResultStore(tmp_path / "result-store")

    store.write_bundle(bundle)

    summary = store.capital_summary(run_id)[0]
    assert summary.total_capital == 150.0
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
    assert len(store.capital_tree(run_id)) == 16

    artifacts = store.artifact_refs(run_id)
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
    bundle = capital_navigator_bundle()
    run_id = bundle.run.run_id
    store = DuckDbParquetResultStore(tmp_path / "result-store")

    store.write_bundle(bundle)

    breakdown = {row.component: row.amount for row in store.component_breakdown(run_id)}
    assert breakdown == {
        FrtbComponent.CVA: 30.0,
        FrtbComponent.DRC: 22.0,
        FrtbComponent.IMA: 42.0,
        FrtbComponent.RRAO: 6.0,
        FrtbComponent.STANDARDISED_APPROACH: 78.0,
        FrtbComponent.SBM: 50.0,
    }

    ima_rows = store.mart_rows(run_id, "ima_desk_dashboard")
    assert ima_rows == (
        {
            "run_id": run_id,
            "desk_id": "rates",
            "portfolio_count": 1,
            "book_count": 1,
            "node_count": 1,
            "capital": 42.0,
            "currency": "USD",
        },
    )

    sbm_rows = store.mart_rows(run_id, "sbm_bucket_ladder")
    assert {(row["risk_class"], row["bucket"], row["capital"]) for row in sbm_rows} == {
        ("CSR_NON_SEC", "IG", 15.0),
        ("GIRR", "USD", 35.0),
    }

    drc_rows = store.mart_rows(run_id, "drc_issuer_contributors")
    assert {(row["issuer_id"], row["capital"], row["artifact_id"]) for row in drc_rows} == {
        ("issuer-alpha", 18.0, "navigator-drc-jtd"),
        ("issuer-beta", 4.0, "navigator-drc-jtd"),
    }

    cva_rows = store.mart_rows(run_id, "cva_counterparty_contributors")
    assert {(row["counterparty_id"], row["capital"], row["artifact_id"]) for row in cva_rows} == {
        ("counterparty-bank-a", 20.0, "navigator-cva-exposures"),
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
    }
    assert any(row["exposure_class"] == "RRAO" and row["capital"] == 0.0 for row in rrao_rows)


def test_capital_navigator_fixture_populates_attribution_projections(
    tmp_path: Path,
) -> None:
    bundle = capital_navigator_bundle()
    run_id = bundle.run.run_id
    store = DuckDbParquetResultStore(tmp_path / "result-store")

    store.write_bundle(bundle)

    top = store.top_contributors(run_id, limit=20)
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
    assert len(unsupported) == 1
    assert unsupported[0]["attribution_id"] == "cva-unsupported-ba-reduced-sqrt"
    assert unsupported[0]["source_level"] == "UNSUPPORTED_BRANCH"
    assert unsupported[0]["artifact_id"] == "navigator-cva-exposures"

    residual = store.residual_attribution_records(run_id)
    assert [row["attribution_id"] for row in residual] == ["suite-residual-zero"]
    assert residual[0]["source_level"] == "RESIDUAL_BRANCH"
    assert residual[0]["artifact_id"] == "navigator-suite-attribution"
