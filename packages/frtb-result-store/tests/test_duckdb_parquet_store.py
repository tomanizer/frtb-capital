from __future__ import annotations

import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from frtb_common import CapitalContribution
from frtb_result_store import (
    ArtifactRef,
    ArtifactType,
    ArtifactWriteRequest,
    CalculationRun,
    CapitalAttributionRecord,
    CapitalEdge,
    CapitalMeasure,
    CapitalNode,
    CapitalNodeFamily,
    CapitalNodeSpec,
    DuckDbParquetResultStore,
    EdgeType,
    FrtbComponent,
    LineageRef,
    NodeType,
    ResultBundle,
    ResultStoreConfig,
    ResultStoreContractError,
    ResultStoreWriteError,
    RunStatus,
    RunStatusEvent,
    StorageBackend,
    artifact_schema_for,
    build_hierarchy_nodes,
    build_standard_capital_graph,
    canonical_run_group_identity_payload,
    default_hierarchy_definition,
    generate_run_group_id,
)
from frtb_result_store.io import (
    _float_value,
    _hierarchy_level_from_mapping,
    _hierarchy_path_item_from_mapping,
    _int_value,
    _json_mapping,
    _json_text_tuple,
)


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
    assert store.latest_status(bundle.run.run_id) is RunStatus.CANDIDATE

    manifest_path = (
        tmp_path / "result-store" / "manifests" / "frtb%2Frun%2F2026-06-03" / "run_manifest.json"
    )
    assert manifest_path.exists()
    assert (tmp_path / "result-store/catalog.duckdb").exists()


def test_store_round_trips_hierarchy_definition_nodes_and_standard_graph(
    tmp_path: Path,
) -> None:
    run = _run_with_id("run-with-hierarchy")
    definition = default_hierarchy_definition(created_at=run.created_at)
    hierarchy_nodes = build_hierarchy_nodes(
        definition,
        {
            "firm_id": "Firm",
            "legal_entity_id": "LE",
            "business_line_id": "Markets",
            "desk_id": "Rates",
            "portfolio_id": "Options",
            "book_id": "Book:USD",
        },
    )
    leaf_id = hierarchy_nodes[-1].hierarchy_node_id
    nodes, edges = build_standard_capital_graph(
        run_id=run.run_id,
        hierarchy_leaf_node_id=leaf_id,
        hierarchy_leaf_path=hierarchy_nodes[-1].path,
        specs=(
            CapitalNodeSpec(
                node_family=CapitalNodeFamily.COMPONENT,
                component=FrtbComponent.SBM,
                label="SBM",
                sort_key=0,
            ),
            CapitalNodeSpec(
                node_family=CapitalNodeFamily.RISK_CLASS,
                component=FrtbComponent.SBM,
                risk_class="GIRR",
                risk_measure="DELTA",
                label="GIRR delta",
                sort_key=1,
            ),
            CapitalNodeSpec(
                node_family=CapitalNodeFamily.BUCKET,
                component=FrtbComponent.SBM,
                risk_class="GIRR",
                risk_measure="DELTA",
                bucket="USD",
                label="GIRR USD",
                sort_key=2,
            ),
        ),
    )
    bundle = ResultBundle(
        run=run,
        hierarchy_definition=definition,
        hierarchy_nodes=hierarchy_nodes,
        nodes=nodes,
        edges=edges,
    )
    store = DuckDbParquetResultStore(tmp_path / "result-store")

    store.write_bundle(bundle)

    assert store.hierarchy_definition(run.run_id) == definition
    assert store.hierarchy_nodes(run.run_id) == hierarchy_nodes
    assert [node.node_id for node in store.child_nodes(run.run_id, leaf_id)] == [nodes[0].node_id]
    assert [node.node_id for node in store.child_nodes(run.run_id, nodes[0].node_id)] == [
        nodes[1].node_id
    ]
    assert [node.node_id for node in store.child_nodes(run.run_id, nodes[1].node_id)] == [
        nodes[2].node_id
    ]


def test_write_bundle_streams_strict_ima_pnl_artifact_chunks(tmp_path: Path) -> None:
    run = _run_with_id("run-with-artifact")
    bundle = _bundle(run)
    schema = artifact_schema_for("ima.pnl_vector.v1")
    request = ArtifactWriteRequest(
        artifact_id_hint="ima-desk-a-pnl",
        artifact_type=ArtifactType.IMA_PNL_VECTOR,
        component="IMA",
        schema_id=schema.schema_id,
        chunks=_ima_pnl_chunks(schema.arrow_schema, run.run_id),
        partition_values={
            "desk_id": "rates",
            "portfolio_id": "rates-options",
            "book_id": "rates-core",
        },
        metadata={"source": "unit-test"},
    )
    store = DuckDbParquetResultStore(tmp_path / "result-store")

    store.write_bundle(bundle, artifact_requests=(request,))

    refs = store.artifact_refs(run.run_id, artifact_type=ArtifactType.IMA_PNL_VECTOR)
    assert len(refs) == 2
    generated = next(ref for ref in refs if ref.metadata.get("source") == "unit-test")
    assert generated.row_count == 2
    assert generated.schema_fingerprint == schema.schema_fingerprint
    assert generated.partition_keys == ("desk_id", "portfolio_id", "book_id")
    assert generated.metadata["compression"] == "zstd"
    assert generated.metadata["chunk_count"] == 2
    assert generated.metadata["byte_count"] > 0
    artifact_path = Path(unquote(urlparse(generated.uri).path))
    assert artifact_path.exists()
    assert pq.ParquetFile(artifact_path).metadata.row_group(0).column(0).compression == "ZSTD"


def test_artifact_schema_mismatch_fails_before_manifest_commit(tmp_path: Path) -> None:
    run = _run_with_id("run-with-bad-artifact")
    schema = artifact_schema_for("ima.pnl_vector.v1")
    bad_chunk = pa.Table.from_pylist(
        [{"run_id": run.run_id, "desk_id": "rates"}],
        schema=pa.schema([("run_id", pa.string()), ("desk_id", pa.string())]),
    )
    request = ArtifactWriteRequest(
        artifact_id_hint="bad-ima-pnl",
        artifact_type=ArtifactType.IMA_PNL_VECTOR,
        component="IMA",
        schema_id=schema.schema_id,
        chunks=(bad_chunk,),
        partition_values={
            "desk_id": "rates",
            "portfolio_id": "rates-options",
            "book_id": "rates-core",
        },
    )
    store = DuckDbParquetResultStore(tmp_path / "result-store")

    with pytest.raises(ResultStoreContractError, match="artifact chunk schema"):
        store.write_bundle(_bundle(run), artifact_requests=(request,))

    assert not store.run_exists(run.run_id)
    assert store.artifact_refs(run.run_id) == ()


def test_store_persists_canonical_identity_payloads_and_status_history(tmp_path: Path) -> None:
    group_payload = canonical_run_group_identity_payload(
        as_of_date=date(2026, 6, 3),
        calculation_scope="FIRM",
        input_snapshot_id="snapshot-001",
        calculation_policy_group_id="policy-comparison",
        engine_version="frtb-suite-0.1",
        code_version="abc123",
        group_purpose="regime-comparison",
    )
    run = CalculationRun.from_identity(
        as_of_date=date(2026, 6, 3),
        regime_id="US_NPR_2_0",
        base_currency="USD",
        input_snapshot_id="snapshot-001",
        calculation_scope="FIRM",
        engine_version="frtb-suite-0.1",
        code_version="abc123",
        calculation_policy_id="policy-us-npr",
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
        run_group_id=generate_run_group_id(group_payload),
        run_group_identity_payload=group_payload,
    )
    bundle = _bundle(run)
    store = DuckDbParquetResultStore(tmp_path / "result-store")

    store.write_bundle(bundle)

    stored = store.get_run(run.run_id)
    assert stored == run
    assert stored is not None
    assert dict(stored.identity_payload)["regime_id"] == "US_NPR_2_0"
    assert dict(stored.run_group_identity_payload)["group_purpose"] == "regime-comparison"
    assert store.status_history(run.run_id)[0].to_status is RunStatus.CANDIDATE

    validated = RunStatusEvent.transition(
        run_id=run.run_id,
        from_status=RunStatus.CANDIDATE,
        to_status=RunStatus.VALIDATED,
        event_time=datetime(2026, 6, 3, 12, 5, tzinfo=UTC),
        actor="validator",
        reason_code="CHECKS_PASSED",
        reason_text="Package-local checks passed",
    )
    store.append_status_event(validated)

    assert [event.to_status for event in store.status_history(run.run_id)] == [
        RunStatus.CANDIDATE,
        RunStatus.VALIDATED,
    ]
    assert store.latest_status(run.run_id) is RunStatus.VALIDATED

    manifest_path = tmp_path / "result-store" / "manifests" / run.run_id / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["identity_payload"] == dict(run.identity_payload)
    assert manifest["run_group_identity_payload"] == dict(run.run_group_identity_payload)


def test_status_transitions_are_append_only_and_ordered(tmp_path: Path) -> None:
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    bundle = _bundle()
    store.write_bundle(bundle)

    with pytest.raises(ResultStoreWriteError, match="status transition expected"):
        store.append_status_event(
            RunStatusEvent.transition(
                run_id=bundle.run.run_id,
                from_status=RunStatus.OFFICIAL,
                to_status=RunStatus.SUPERSEDED,
                event_time=datetime(2026, 6, 3, 12, 5, tzinfo=UTC),
                actor="validator",
                reason_code="WRONG_FROM_STATUS",
                reason_text="Wrong transition",
            )
        )

    validated = RunStatusEvent.transition(
        run_id=bundle.run.run_id,
        from_status=RunStatus.CANDIDATE,
        to_status=RunStatus.VALIDATED,
        event_time=datetime(2026, 6, 3, 12, 5, tzinfo=UTC),
        actor="validator",
        reason_code="CHECKS_PASSED",
        reason_text="Package-local checks passed",
    )
    store.append_status_event(validated)

    with pytest.raises(ResultStoreWriteError, match="status event already exists"):
        store.append_status_event(validated)


def test_run_id_prefix_lookup_fails_closed_when_ambiguous(tmp_path: Path) -> None:
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    first_run = _run_with_id("abcdef" + ("0" * 58))
    second_run = _run_with_id("abc123" + ("1" * 58))
    store.write_bundle(_bundle(first_run))
    store.write_bundle(_bundle(second_run))

    assert store.resolve_run_id_prefix("abcdef") == first_run.run_id
    assert store.resolve_run_id_prefix("missing") is None
    with pytest.raises(ResultStoreContractError, match="ambiguous run_id prefix"):
        store.resolve_run_id_prefix("abc")


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
        "hierarchy_definitions",
        "hierarchy_nodes",
        "capital_nodes",
        "capital_edges",
        "capital_measures",
        "artifact_refs",
        "lineage_refs",
        "capital_attributions",
    ):
        assert not store._run_table_path(table_name, bundle.run.run_id).exists()
    assert not (
        tmp_path / "result-store" / "parquet" / "run_status_events" / "frtb%2Frun%2F2026-06-03"
    ).exists()

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
    with pytest.raises(ResultStoreContractError, match="missing key in hierarchy level"):
        _hierarchy_level_from_mapping({"level_name": "book", "level_order": 5})
    with pytest.raises(ResultStoreContractError, match="missing key in hierarchy node path"):
        _hierarchy_path_item_from_mapping({"level_name": "book"})


def _bundle(run: CalculationRun | None = None) -> ResultBundle:
    if run is None:
        run = _run_with_id("frtb/run/2026-06-03")
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
            sort_key=3,
        ),
    )
    measures = (
        CapitalMeasure(
            run_id=run.run_id,
            node_id="total",
            measure_name="capital",
            amount=42.0,
            currency="USD",
            regulatory_rule_id="US_NPR_325.201",
        ),
    )
    artifacts = (
        ArtifactRef(
            run_id=run.run_id,
            artifact_id="ima-pnl-vector",
            component=FrtbComponent.IMA,
            artifact_type=ArtifactType.IMA_PNL_VECTOR,
            uri="s3://frtb-results/ima-pnl-vector.parquet",
            format="parquet",
            row_count=1,
            partition_keys=("desk_id", "portfolio_id", "book_id"),
        ),
    )
    lineage = (
        LineageRef(
            run_id=run.run_id,
            result_id="total",
            source_type="input_snapshot",
            source_id="snapshot-001",
        ),
    )
    attributions = (
        CapitalAttributionRecord.from_contribution(
            run_id=run.run_id,
            node_id="sbm-girr-usd",
            contribution=CapitalContribution(
                contribution_id="sbm-girr-usd-5y",
                source_id="sensitivity-girr-usd-5y",
                source_level="SENSITIVITY",
                bucket_key="GIRR:USD",
                category="SBM_DELTA",
                base_amount=25.0,
                marginal_multiplier=0.3,
                contribution=7.5,
                method="ANALYTICAL_EULER",
            ),
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


def _ima_pnl_chunks(schema: pa.Schema, run_id: str) -> tuple[pa.Table, pa.Table]:
    rows = [
        {
            "run_id": run_id,
            "desk_id": "rates",
            "portfolio_id": "rates-options",
            "book_id": "rates-core",
            "position_id": "pos-001",
            "risk_factor_id": "rf-girr-usd-5y",
            "risk_factor_set_id": None,
            "scenario_id": "s-001",
            "observation_date": date(2026, 6, 1),
            "liquidity_horizon": 20,
            "pnl_amount": 1.25,
            "currency": "USD",
            "tail_flag": False,
            "source_row_id": "row-001",
        },
        {
            "run_id": run_id,
            "desk_id": "rates",
            "portfolio_id": "rates-options",
            "book_id": "rates-core",
            "position_id": "pos-002",
            "risk_factor_id": "rf-girr-usd-10y",
            "risk_factor_set_id": "girr-usd",
            "scenario_id": "s-002",
            "observation_date": date(2026, 6, 2),
            "liquidity_horizon": 40,
            "pnl_amount": -0.5,
            "currency": "USD",
            "tail_flag": True,
            "source_row_id": "row-002",
        },
    ]
    return tuple(pa.Table.from_pylist([row], schema=schema) for row in rows)


def _run_with_id(run_id: str) -> CalculationRun:
    return CalculationRun(
        run_id=run_id,
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
