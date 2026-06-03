from __future__ import annotations

import shutil
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from frtb_common import CapitalContribution
from frtb_result_store import (
    ArtifactRef,
    ArtifactType,
    CalculationRun,
    CapitalAttributionRecord,
    CapitalEdge,
    CapitalMeasure,
    CapitalNode,
    DuckDbParquetResultStore,
    EdgeType,
    FrtbComponent,
    LineageRef,
    NodeType,
    ResultBundle,
    ResultStoreConfig,
    ResultStoreContractError,
    ResultStoreWriteError,
    StorageBackend,
)
from frtb_result_store.io import _float_value, _int_value, _json_mapping, _json_text_tuple


def test_duckdb_parquet_store_round_trips_frtb_result_bundle(tmp_path: Path) -> None:
    bundle = _bundle()
    store = DuckDbParquetResultStore(tmp_path / "result-store")

    store.write_bundle(bundle)

    assert store.list_runs() == (bundle.run,)
    assert store.get_run(bundle.run.run_id) == bundle.run
    assert [node.node_id for node in store.capital_tree(bundle.run.run_id)] == [
        "total",
        "ima-book-rates-core",
        "sa",
        "sbm-girr-usd",
    ]
    assert [node.node_id for node in store.child_nodes(bundle.run.run_id, "total")] == [
        "ima-book-rates-core",
        "sa",
    ]
    ima_node = store.child_nodes(bundle.run.run_id, "total")[0]
    assert ima_node.node_type is NodeType.BOOK
    assert ima_node.book_id == "rates-core"
    assert store.measures_for_node(bundle.run.run_id, "total")[0].amount == 42.0
    assert store.artifact_refs(
        bundle.run.run_id,
        artifact_type=ArtifactType.IMA_PNL_VECTOR,
    )[0].uri.startswith("s3://")
    assert store.lineage_for_result(bundle.run.run_id, "total")[0].source_id == "snapshot-001"
    assert store.attributions_for_node(bundle.run.run_id, "sbm-girr-usd")[0].contribution == 7.5

    manifest_path = (
        tmp_path / "result-store" / "manifests" / "frtb%2Frun%2F2026-06-03" / "run_manifest.json"
    )
    assert manifest_path.exists()
    assert (tmp_path / "result-store/catalog.duckdb").exists()


def test_store_is_append_only_by_run_id(tmp_path: Path) -> None:
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    bundle = _bundle()

    store.write_bundle(bundle)

    with pytest.raises(ResultStoreWriteError, match="run already exists"):
        store.write_bundle(bundle)


def test_failed_manifest_write_rolls_back_moved_run_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    bundle = _bundle()

    def fail_manifest(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("manifest failure")

    monkeypatch.setattr(store, "_write_manifest", fail_manifest)

    with pytest.raises(RuntimeError, match="manifest failure"):
        store.write_bundle(bundle)

    assert not store.run_exists(bundle.run.run_id)
    assert store.list_runs() == ()
    for table_name in (
        "runs",
        "capital_nodes",
        "capital_edges",
        "capital_measures",
        "artifact_refs",
        "lineage_refs",
        "capital_attributions",
    ):
        assert not store._run_table_path(table_name, bundle.run.run_id).exists()

    monkeypatch.undo()
    store.write_bundle(bundle)
    assert store.get_run(bundle.run.run_id) == bundle.run


def test_unmanifested_parquet_files_are_invisible_to_readers(tmp_path: Path) -> None:
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    bundle = _bundle()
    store.write_bundle(bundle)
    shutil.rmtree(tmp_path / "result-store" / "manifests")

    assert not store.run_exists(bundle.run.run_id)
    assert store.list_runs() == ()
    assert store.get_run(bundle.run.run_id) is None
    assert store.capital_tree(bundle.run.run_id) == ()
    assert store.artifact_refs(bundle.run.run_id) == ()


def test_catalog_refresh_failure_does_not_fail_manifested_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    bundle = _bundle()

    def fail_catalog() -> None:
        raise RuntimeError("catalog locked")

    monkeypatch.setattr(store, "refresh_catalog", fail_catalog)

    store.write_bundle(bundle)

    assert store.run_exists(bundle.run.run_id)
    assert store.get_run(bundle.run.run_id) == bundle.run


def test_reserved_backends_fail_closed(tmp_path: Path) -> None:
    config = ResultStoreConfig(
        root=tmp_path / "result-store",
        backend=StorageBackend.DUCKLAKE,
    )

    with pytest.raises(ValueError, match="reserved for a later implementation"):
        DuckDbParquetResultStore(config)


def test_malformed_stored_values_raise_contract_errors() -> None:
    with pytest.raises(ResultStoreContractError, match="malformed JSON object"):
        _json_mapping("{")
    with pytest.raises(ResultStoreContractError, match="malformed JSON text list"):
        _json_text_tuple("{")
    with pytest.raises(ResultStoreContractError, match="invalid numeric value"):
        _float_value("not-a-number")
    with pytest.raises(ResultStoreContractError, match="invalid integer value"):
        _int_value("not-an-integer")


def _bundle() -> ResultBundle:
    run = CalculationRun(
        run_id="frtb/run/2026-06-03",
        as_of_date=date(2026, 6, 3),
        regime_id="US_NPR_2_0",
        base_currency="USD",
        input_snapshot_id="snapshot-001",
        calculation_scope="FIRM",
        engine_version="frtb-suite-0.1",
        code_version="abc123",
        calculation_policy_id="policy-us-npr",
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
        metadata={"purpose": "analyst-dashboard-fixture"},
    )
    nodes = (
        CapitalNode(
            run_id=run.run_id,
            node_id="total",
            node_type=NodeType.ROOT,
            component=FrtbComponent.TOP_OF_HOUSE,
            label="Total capital",
            sort_key=0,
        ),
        CapitalNode(
            run_id=run.run_id,
            node_id="ima-book-rates-core",
            node_type=NodeType.BOOK,
            component=FrtbComponent.IMA,
            label="IMA rates core book",
            desk_id="rates",
            portfolio_id="rates-options",
            book_id="rates-core",
            calculation_branch="IMA_ES_PLUS_SES",
            regulatory_rule_id="US_NPR_325.207",
            sort_key=1,
        ),
        CapitalNode(
            run_id=run.run_id,
            node_id="sa",
            node_type=NodeType.COMPONENT,
            component=FrtbComponent.STANDARDISED_APPROACH,
            label="Standardised Approach",
            sort_key=2,
        ),
        CapitalNode(
            run_id=run.run_id,
            node_id="sbm-girr-usd",
            node_type=NodeType.BUCKET,
            component=FrtbComponent.SBM,
            label="SBM GIRR USD",
            risk_class="GIRR",
            bucket="USD",
            regulatory_rule_id="MAR21.4",
            sort_key=3,
        ),
    )
    edges = (
        CapitalEdge(
            run_id=run.run_id,
            parent_node_id="total",
            child_node_id="ima-book-rates-core",
            edge_type=EdgeType.AGGREGATES,
            sort_key=1,
        ),
        CapitalEdge(
            run_id=run.run_id,
            parent_node_id="total",
            child_node_id="sa",
            edge_type=EdgeType.AGGREGATES,
            sort_key=2,
        ),
        CapitalEdge(
            run_id=run.run_id,
            parent_node_id="sa",
            child_node_id="sbm-girr-usd",
            edge_type=EdgeType.DRILLDOWN,
            sort_key=1,
        ),
    )
    measures = (
        CapitalMeasure(
            run_id=run.run_id,
            node_id="total",
            measure_name="capital_amount",
            amount=42.0,
            currency="USD",
            citations=("US_NPR_325.207",),
        ),
        CapitalMeasure(
            run_id=run.run_id,
            node_id="sbm-girr-usd",
            measure_name="kb",
            amount=12.5,
            currency="USD",
            scenario="medium_correlation",
            methodology="SBM_DELTA",
            regulatory_rule_id="MAR21.4",
        ),
    )
    artifacts = (
        ArtifactRef(
            run_id=run.run_id,
            artifact_id="ima-pnl-rates",
            component=FrtbComponent.IMA,
            artifact_type=ArtifactType.IMA_PNL_VECTOR,
            uri="s3://frtb-results/as_of=2026-06-03/run=frtb-run/ima_pnl.parquet",
            format="parquet",
            row_count=2500,
            schema_fingerprint="ima-pnl-v1",
            partition_keys=("desk_id", "portfolio_id", "book_id", "scenario_id"),
        ),
    )
    lineage = (
        LineageRef(
            run_id=run.run_id,
            result_id="total",
            source_type="input_snapshot",
            source_id="snapshot-001",
            source_hash="abc123",
        ),
    )
    contribution = CapitalContribution(
        contribution_id="alloc-sbm-girr-usd",
        source_id="sensitivity-girr-usd-5y",
        source_level="SENSITIVITY",
        bucket_key="GIRR:USD",
        category="SBM_DELTA",
        base_amount=12.5,
        marginal_multiplier=0.6,
        contribution=7.5,
        method="ANALYTICAL_EULER",
    )
    attributions = (
        CapitalAttributionRecord.from_contribution(
            run_id=run.run_id,
            node_id="sbm-girr-usd",
            contribution=contribution,
        ),
    )
    return ResultBundle(
        run=run,
        nodes=nodes,
        edges=edges,
        measures=measures,
        artifacts=artifacts,
        lineage=lineage,
        attributions=attributions,
    )
