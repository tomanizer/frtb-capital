from __future__ import annotations

import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import quote, unquote, urlparse

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from fixtures.result_store_bundle import (
    default_artifacts,
    ima_pnl_chunks,
    run_with_id,
    sample_bundle,
)
from frtb_common import AttributionMethod, CapitalContribution
from frtb_result_store import (
    ArtifactRef,
    ArtifactType,
    ArtifactWriteRequest,
    CalculationRun,
    CapitalAttributionRecord,
    CapitalEdge,
    CapitalNodeFamily,
    CapitalNodeSpec,
    CapitalSummaryRow,
    DuckDbParquetResultStore,
    EdgeType,
    FrtbComponent,
    InputSnapshotManifest,
    MovementResult,
    MovementSummaryRow,
    NodeType,
    RequiredArtifactExpectation,
    ResultBundle,
    ResultEvent,
    ResultEventSeverity,
    ResultEventType,
    ResultStoreCompatibilityError,
    ResultStoreConfig,
    ResultStoreContractError,
    ResultStoreWriteError,
    RunStatus,
    RunStatusEvent,
    RunTelemetry,
    StorageBackend,
    TelemetryPhase,
    artifact_schema_for,
    build_hierarchy_nodes,
    build_standard_capital_graph,
    canonical_run_group_identity_payload,
    default_hierarchy_definition,
    generate_run_group_id,
)
from frtb_result_store._row_codecs import (
    float_value as _float_value,
)
from frtb_result_store._row_codecs import (
    int_value as _int_value,
)
from frtb_result_store._row_codecs import (
    json_mapping as _json_mapping,
)
from frtb_result_store._row_codecs import (
    json_text_tuple as _json_text_tuple,
)
from frtb_result_store.mart_schemas import MART_NAMES
from frtb_result_store.store_row_io import (
    _hierarchy_level_from_mapping,
    _hierarchy_path_item_from_mapping,
)


def test_duckdb_parquet_store_round_trips_frtb_result_bundle(tmp_path: Path) -> None:
    bundle = sample_bundle()
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
    attribution = store.attributions_for_node(bundle.run.run_id, "sbm-girr-usd")[0]
    assert attribution.attribution_id == "sbm-girr-usd-5y"
    assert attribution.target_type == "SENSITIVITY"
    assert attribution.target_id == "sensitivity-girr-usd-5y"
    assert attribution.category == "SBM_DELTA"
    assert attribution.bucket_key == "GIRR:USD"
    assert attribution.marginal_multiplier == 0.3
    assert attribution.contribution == 7.5
    assert attribution.artifact_id == "sbm-sensitivity-table"
    assert store.latest_status(bundle.run.run_id) is RunStatus.CANDIDATE
    assert store.capital_summary(bundle.run.run_id)[0].total_capital == 42.0
    assert store.component_breakdown(bundle.run.run_id)[0].component is FrtbComponent.IMA

    manifest_path = (
        tmp_path / "result-store" / "manifests" / "frtb%2Frun%2F2026-06-03" / "run_manifest.json"
    )
    assert manifest_path.exists()
    assert (tmp_path / "result-store/catalog.duckdb").exists()


def test_duckdb_parquet_store_resolves_relative_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    store = DuckDbParquetResultStore(Path("result-store"))

    assert store.root == (tmp_path / "result-store").resolve()
    assert store.parquet_root == store.root / "parquet"
    assert store.artifact_root == store.root / "artifacts"
    assert store.catalog_path == store.root / "catalog.duckdb"


def test_store_round_trips_hierarchy_definition_nodes_and_standard_graph(
    tmp_path: Path,
) -> None:
    run = run_with_id("run-with-hierarchy")
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
        artifacts=(
            ArtifactRef(
                run_id=run.run_id,
                artifact_id="sbm-sensitivity-table",
                component=FrtbComponent.SBM,
                artifact_type=ArtifactType.SBM_SENSITIVITY_TABLE,
                uri="s3://frtb-results/sbm-sensitivity-table.parquet",
                format="parquet",
                row_count=1,
            ),
        ),
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
    run = run_with_id("run-with-artifact")
    tail_artifact = ArtifactRef(
        run_id=run.run_id,
        artifact_id="ima-tail-observations",
        component=FrtbComponent.IMA,
        artifact_type=ArtifactType.IMA_TAIL_OBSERVATION,
        uri="s3://frtb-results/ima-tail-observations.parquet",
        format="parquet",
        row_count=3,
    )
    bundle = sample_bundle(run, artifacts=(*default_artifacts(run), tail_artifact))
    schema = artifact_schema_for("ima.pnl_vector.v1")
    request = ArtifactWriteRequest(
        artifact_id_hint="ima-desk-a-pnl",
        artifact_type=ArtifactType.IMA_PNL_VECTOR,
        component="IMA",
        schema_id=schema.schema_id,
        chunks=ima_pnl_chunks(schema.arrow_schema, run.run_id),
        partition_values={
            "desk_id": "rates",
            "portfolio_id": "rates-options",
            "book_id": "rates-core",
        },
        metadata={"source": "unit-test"},
        conditional_expectations=(
            RequiredArtifactExpectation(
                component=FrtbComponent.IMA,
                artifact_type=ArtifactType.IMA_TAIL_OBSERVATION,
                trigger_name="IMA_ES_TAIL_EVIDENCE",
                required=True,
                reason="ES tail evidence declared by writer",
            ),
        ),
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
    expectation_path = store._run_table_path("artifact_expectations", run.run_id)
    expectation = pq.read_table(expectation_path).to_pylist()[0]
    assert expectation["trigger_name"] == "IMA_ES_TAIL_EVIDENCE"
    manifest = json.loads(store._manifest_path(run.run_id).read_text(encoding="utf-8"))
    assert manifest["tables"]["artifact_expectations"] == 1
    assert schema.schema_fingerprint in manifest["artifact_schema_fingerprints"]


def test_missing_required_artifact_rejects_before_manifest_commit(tmp_path: Path) -> None:
    run = run_with_id("run-missing-required-artifact")
    store = DuckDbParquetResultStore(tmp_path / "result-store")

    with pytest.raises(ResultStoreContractError, match="missing required artifacts"):
        store.write_bundle(sample_bundle(run, artifacts=()))

    assert not store.run_exists(run.run_id)
    assert store.list_runs() == ()


def test_declared_conditional_artifact_expectation_requires_evidence(tmp_path: Path) -> None:
    run = run_with_id("run-missing-conditional-artifact")
    schema = artifact_schema_for("ima.pnl_vector.v1")
    request = ArtifactWriteRequest(
        artifact_id_hint="ima-desk-a-pnl",
        artifact_type=ArtifactType.IMA_PNL_VECTOR,
        component="IMA",
        schema_id=schema.schema_id,
        chunks=ima_pnl_chunks(schema.arrow_schema, run.run_id),
        partition_values={
            "desk_id": "rates",
            "portfolio_id": "rates-options",
            "book_id": "rates-core",
        },
        conditional_expectations=(
            RequiredArtifactExpectation(
                component=FrtbComponent.IMA,
                artifact_type=ArtifactType.IMA_TAIL_OBSERVATION,
                trigger_name="IMA_ES_TAIL_EVIDENCE",
                required=True,
                reason="ES tail evidence declared by writer",
            ),
        ),
    )
    store = DuckDbParquetResultStore(tmp_path / "result-store")

    with pytest.raises(ResultStoreContractError, match="IMA_ES_TAIL_EVIDENCE"):
        store.write_bundle(sample_bundle(run), artifact_requests=(request,))

    assert not store.run_exists(run.run_id)
    assert not (
        tmp_path / "result-store" / "_staging" / "run-missing-conditional-artifact"
    ).exists()


def test_invalid_local_artifact_ref_rejects_commit(tmp_path: Path) -> None:
    run = run_with_id("run-invalid-artifact-ref")
    invalid_artifact = ArtifactRef(
        run_id=run.run_id,
        artifact_id="missing-local-artifact",
        component=FrtbComponent.IMA,
        artifact_type=ArtifactType.IMA_TAIL_OBSERVATION,
        uri=(tmp_path / "missing-artifact.parquet").as_uri(),
        format="parquet",
        row_count=1,
    )
    store = DuckDbParquetResultStore(tmp_path / "result-store")

    with pytest.raises(ResultStoreContractError, match="missing local file"):
        store.write_bundle(
            sample_bundle(run, artifacts=(*default_artifacts(run), invalid_artifact))
        )

    assert not store.run_exists(run.run_id)


def test_abandoned_staging_is_cleaned_before_successful_commit(tmp_path: Path) -> None:
    run = run_with_id("run-abandoned-staging")
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    stale_staging = tmp_path / "result-store" / "_staging" / "run-abandoned-staging"
    stale_staging.mkdir(parents=True)
    (stale_staging / "orphan.parquet").write_text("stale", encoding="utf-8")

    store.write_bundle(sample_bundle(run))

    assert store.run_exists(run.run_id)
    assert not stale_staging.exists()


def test_artifact_schema_mismatch_fails_before_manifest_commit(tmp_path: Path) -> None:
    run = run_with_id("run-with-bad-artifact")
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
        store.write_bundle(sample_bundle(run), artifact_requests=(request,))

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
    bundle = sample_bundle(run)
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
    bundle = sample_bundle()
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
    first_run = run_with_id("abcdef" + ("0" * 58))
    second_run = run_with_id("abc123" + ("1" * 58))
    store.write_bundle(sample_bundle(first_run))
    store.write_bundle(sample_bundle(second_run))

    assert store.resolve_run_id_prefix("abcdef") == first_run.run_id
    assert store.resolve_run_id_prefix("missing") is None
    with pytest.raises(ResultStoreContractError, match="ambiguous run_id prefix"):
        store.resolve_run_id_prefix("abc")


def test_store_is_append_only_by_run_id(tmp_path: Path) -> None:
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    bundle = sample_bundle()

    store.write_bundle(bundle)

    with pytest.raises(ResultStoreWriteError, match="run already exists"):
        store.write_bundle(bundle)


def test_failed_manifest_write_rolls_back_moved_run_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    bundle = sample_bundle()

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
        "artifact_expectations",
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
    bundle = sample_bundle()
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
    bundle = sample_bundle()

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


def test_s3_parquet_backend_uses_manifest_gated_logical_layout(tmp_path: Path) -> None:
    run = run_with_id("s3/run/2026-06-03")
    schema = artifact_schema_for("ima.pnl_vector.v1")
    request = ArtifactWriteRequest(
        artifact_id_hint="ima-desk-a-pnl",
        artifact_type=ArtifactType.IMA_PNL_VECTOR,
        component=FrtbComponent.IMA,
        schema_id=schema.schema_id,
        chunks=ima_pnl_chunks(schema.arrow_schema, run.run_id),
        partition_values={
            "desk_id": "rates",
            "portfolio_id": "rates-options",
            "book_id": "rates-core",
        },
        metadata={"source": "s3-mock-test"},
    )
    config = ResultStoreConfig(
        root="s3://frtb-results/prod",
        backend=StorageBackend.S3_PARQUET,
        s3_mock_root=tmp_path / "mock-s3",
        duckdb_settings={"threads": 1},
    )
    store = DuckDbParquetResultStore(config)
    bundle = sample_bundle(run)

    store.write_bundle(bundle, artifact_requests=(request,))

    assert store.root == (tmp_path / "mock-s3" / "frtb-results" / "prod").resolve()
    assert store.root_uri == "s3://frtb-results/prod"
    assert store.get_run(run.run_id) == run
    assert store.capital_summary(run.run_id)[0].total_capital == 42.0
    manifest = json.loads(store._manifest_path(run.run_id).read_text(encoding="utf-8"))
    assert manifest["backend"] == StorageBackend.S3_PARQUET.value
    assert manifest["root_uri"] == "s3://frtb-results/prod"
    assert manifest["paths"] == {
        "parquet": "s3://frtb-results/prod/parquet",
        "artifacts": "s3://frtb-results/prod/artifacts",
        "manifests": "s3://frtb-results/prod/manifests",
    }
    generated = next(
        ref
        for ref in store.artifact_refs(run.run_id, artifact_type=ArtifactType.IMA_PNL_VECTOR)
        if ref.metadata.get("source") == "s3-mock-test"
    )
    assert generated.uri.startswith(
        "s3://frtb-results/prod/artifacts/"
        "artifact_type=IMA_PNL_VECTOR/run_id=s3%2Frun%2F2026-06-03/"
    )
    artifact_paths = tuple(
        store.artifact_root.glob("artifact_type=IMA_PNL_VECTOR/run_id=*/artifact_id=*/data.parquet")
    )
    assert len(artifact_paths) == 1
    assert pq.ParquetFile(artifact_paths[0]).metadata.row_group(0).column(0).compression == "ZSTD"


def test_s3_parquet_readers_ignore_orphaned_objects_without_manifest(tmp_path: Path) -> None:
    run = run_with_id("orphan/s3/run")
    store = DuckDbParquetResultStore(
        ResultStoreConfig(
            root="s3://frtb-results/prod",
            backend=StorageBackend.S3_PARQUET,
            s3_mock_root=tmp_path / "mock-s3",
        )
    )
    orphan_path = store._run_table_path("runs", run.run_id)
    orphan_path.parent.mkdir(parents=True)
    pq.write_table(pa.table({"run_id": [run.run_id]}), orphan_path)
    staging_path = store.root / "_staging" / quote(run.run_id, safe="")
    staging_path.mkdir(parents=True)
    (staging_path / "runs.parquet").write_bytes(b"staged")

    assert store.run_exists(run.run_id) is False
    assert store.list_runs() == ()
    assert store.get_run(run.run_id) is None
    assert store.cleanup_orphaned_staging() == (run.run_id,)
    assert not staging_path.exists()


def test_s3_parquet_config_requires_uri_and_explicit_mock_root(tmp_path: Path) -> None:
    with pytest.raises(ResultStoreContractError, match="requires s3_mock_root"):
        ResultStoreConfig(root="s3://frtb-results/prod", backend=StorageBackend.S3_PARQUET)
    with pytest.raises(ResultStoreContractError, match="s3:// roots require"):
        ResultStoreConfig(root="s3://frtb-results/prod")
    with pytest.raises(ResultStoreContractError, match="s3:// URI string"):
        ResultStoreConfig(
            root=tmp_path / "result-store",
            backend=StorageBackend.S3_PARQUET,
            s3_mock_root=tmp_path / "mock-s3",
        )
    with pytest.raises(ResultStoreContractError, match="relative components"):
        ResultStoreConfig(
            root="s3://frtb-results/prod/../other",
            backend=StorageBackend.S3_PARQUET,
            s3_mock_root=tmp_path / "mock-s3",
        )
    with pytest.raises(ResultStoreContractError, match="relative components"):
        ResultStoreConfig(
            root="s3://frtb-results/prod/%2E%2E/other",
            backend=StorageBackend.S3_PARQUET,
            s3_mock_root=tmp_path / "mock-s3",
        )
    with pytest.raises(ResultStoreContractError, match="relative components"):
        ResultStoreConfig(
            root="s3://../prod",
            backend=StorageBackend.S3_PARQUET,
            s3_mock_root=tmp_path / "mock-s3",
        )
    with pytest.raises(ResultStoreContractError, match="relative components"):
        ResultStoreConfig(
            root="s3://%2E/prod",
            backend=StorageBackend.S3_PARQUET,
            s3_mock_root=tmp_path / "mock-s3",
        )


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


def test_store_persists_input_events_telemetry_and_manifest_fingerprints(
    tmp_path: Path,
) -> None:
    run = run_with_id("run-with-events")
    input_manifest = InputSnapshotManifest(
        run_id=run.run_id,
        input_snapshot_id=run.input_snapshot_id,
        input_snapshot_hash="input-hash-001",
        as_of_date=run.as_of_date,
        source_system="risk-engine",
        handoff_key="ima.pnl",
        row_count=10,
        accepted_row_count=9,
        rejected_row_count=1,
        source_uri="s3://inputs/snapshot-001.parquet",
        source_hash="source-hash-001",
        schema_fingerprint="input-schema-001",
    )
    event = ResultEvent(
        event_id="event-001",
        run_id=run.run_id,
        event_time=run.created_at,
        severity=ResultEventSeverity.ERROR,
        event_type=ResultEventType.DATA_QUALITY,
        message="Rejected input row count is non-zero",
        component=FrtbComponent.IMA,
    )
    export_telemetry = RunTelemetry(
        run_id=run.run_id,
        phase=TelemetryPhase.EXPORT,
        duration_ms=12.5,
        created_at=run.created_at,
        row_count=2,
        byte_count=128,
    )
    store = DuckDbParquetResultStore(tmp_path / "result-store")

    store.write_bundle(
        sample_bundle(
            run,
            input_manifests=(input_manifest,),
            events=(event,),
            telemetry=(export_telemetry,),
        )
    )

    assert store.input_snapshot_manifests(run.run_id) == (input_manifest,)
    assert store.result_events(run.run_id) == (event,)
    assert store.suggested_status(run.run_id) is RunStatus.REJECTED
    telemetry_phases = {row.phase for row in store.run_telemetry(run.run_id)}
    assert {
        TelemetryPhase.ARTIFACT_WRITE,
        TelemetryPhase.BASE_TABLE_WRITE,
        TelemetryPhase.MART_GENERATION,
        TelemetryPhase.CATALOG_REFRESH,
        TelemetryPhase.EXPORT,
    } <= telemetry_phases
    manifest = json.loads(store._manifest_path(run.run_id).read_text(encoding="utf-8"))
    assert manifest["result_store_schema_version"] == 2
    assert manifest["writer_version"]
    assert "runs" in manifest["base_table_schema_fingerprints"]
    assert sorted(manifest["mart_schema_fingerprints"]) == sorted(MART_NAMES)


def test_store_persists_dashboard_marts_and_manifest_fingerprints(tmp_path: Path) -> None:
    bundle = sample_bundle()
    store = DuckDbParquetResultStore(tmp_path / "result-store")

    store.write_bundle(bundle)

    assert store.capital_summary(bundle.run.run_id) == (
        CapitalSummaryRow(
            run_id=bundle.run.run_id,
            as_of_date=bundle.run.as_of_date,
            regime_id=bundle.run.regime_id,
            base_currency="USD",
            lifecycle_status=RunStatus.CANDIDATE,
            suggested_status=RunStatus.VALIDATED,
            total_capital=42.0,
            currency="USD",
            node_count=4,
            measure_count=4,
            component_count=3,
        ),
    )
    assert [
        (row.node_id, row.parent_node_id, row.depth)
        for row in store.capital_tree_mart(bundle.run.run_id)
    ] == [
        ("total", None, 0),
        ("ima-book-rates-core", "total", 1),
        ("sa", "total", 1),
        ("sbm-girr-usd", "sa", 2),
    ]
    assert [node.node_id for node in store.capital_tree(bundle.run.run_id)] == [
        "total",
        "ima-book-rates-core",
        "sa",
        "sbm-girr-usd",
    ]
    component_amounts = {
        row.component: row.amount for row in store.component_breakdown(bundle.run.run_id)
    }
    assert component_amounts == {
        FrtbComponent.IMA: 17.0,
        FrtbComponent.SBM: 25.0,
        FrtbComponent.STANDARDISED_APPROACH: 25.0,
    }
    assert store.top_contributors(bundle.run.run_id, limit=1)[0]["attribution_id"] == (
        "sbm-girr-usd-5y"
    )
    assert store.mart_rows(bundle.run.run_id, "ima_desk_dashboard")[0]["desk_id"] == "rates"
    assert store.mart_rows(bundle.run.run_id, "sbm_bucket_ladder")[0]["bucket"] == "USD"
    assert store.regime_comparison(f"run:{bundle.run.run_id}")[0]["run_id"] == bundle.run.run_id
    manifest = json.loads(store._manifest_path(bundle.run.run_id).read_text(encoding="utf-8"))
    assert manifest["marts"] == {
        "capital_summary": 1,
        "capital_tree": 4,
        "top_contributors": 1,
        "movement_summary": 0,
        "regime_comparison": 1,
        "component_breakdown": 3,
        "ima_desk_dashboard": 1,
        "sbm_bucket_ladder": 1,
        "drc_issuer_contributors": 0,
        "cva_counterparty_contributors": 0,
        "rrao_exposure_summary": 0,
    }
    assert sorted(manifest["mart_schema_fingerprints"]) == sorted(MART_NAMES)


def test_mart_generation_rejects_cyclic_capital_tree(tmp_path: Path) -> None:
    bundle = sample_bundle()
    cyclic_bundle = ResultBundle(
        run=bundle.run,
        nodes=bundle.nodes,
        edges=tuple(
            CapitalEdge(
                run_id=bundle.run.run_id,
                parent_node_id=parent,
                child_node_id=child,
                edge_type=EdgeType.DRILLDOWN,
                sort_key=index,
            )
            for index, (parent, child) in enumerate(
                (("sa", "sbm-girr-usd"), ("sbm-girr-usd", "sa")),
                start=1,
            )
        ),
        measures=bundle.measures,
        artifacts=bundle.artifacts,
    )
    store = DuckDbParquetResultStore(tmp_path / "result-store")

    with pytest.raises(ResultStoreContractError, match="cycle detected in capital tree"):
        store.write_bundle(cyclic_bundle)


def test_store_persists_day_over_day_movement_results_and_summary_mart(
    tmp_path: Path,
) -> None:
    run = run_with_id("run-dod-current")
    baseline_run_id = "run-dod-baseline"
    movement = MovementResult(
        run_id=run.run_id,
        baseline_run_id=baseline_run_id,
        movement_id="dod-total-capital",
        node_id="total",
        movement_type="DAY_OVER_DAY",
        from_amount=40.0,
        to_amount=42.0,
        delta_amount=2.0,
        base_currency="USD",
        driver_type="NODE",
        driver_id="total",
        explanation="Total capital increased from the prior business day.",
        attribution_method=AttributionMethod.ANALYTICAL_EULER,
        artifact_id="ima-pnl-vector",
    )
    store = DuckDbParquetResultStore(tmp_path / "result-store")

    store.write_bundle(sample_bundle(run, movement_results=(movement,)))

    assert store.movement_results(run.run_id) == (movement,)
    assert store.movement_results(run.run_id, baseline_run_id=baseline_run_id) == (movement,)
    assert store.movement_summary(run.run_id, node_id="total") == (
        MovementSummaryRow(
            run_id=run.run_id,
            baseline_run_id=baseline_run_id,
            movement_id="dod-total-capital",
            node_id="total",
            movement_type="DAY_OVER_DAY",
            from_amount=40.0,
            to_amount=42.0,
            delta_amount=2.0,
            base_currency="USD",
            driver_type="NODE",
            driver_id="total",
            attribution_method=AttributionMethod.ANALYTICAL_EULER,
            artifact_id="ima-pnl-vector",
        ),
    )
    manifest = json.loads(store._manifest_path(run.run_id).read_text(encoding="utf-8"))
    assert manifest["marts"]["movement_summary"] == 1


def test_store_persists_regime_over_regime_movement_results(
    tmp_path: Path,
) -> None:
    run = run_with_id("run-us-npr-current")
    movement = MovementResult(
        run_id=run.run_id,
        baseline_run_id="run-basel-baseline",
        movement_id="regime-sbm-girr-usd",
        node_id="sbm-girr-usd",
        movement_type="REGIME_OVER_REGIME",
        from_amount=22.0,
        to_amount=25.0,
        delta_amount=3.0,
        base_currency="USD",
        driver_type="REGIME",
        driver_id="US_NPR_325.201",
        explanation="US NPR regime capital exceeds the Basel comparator for this bucket.",
        attribution_method=AttributionMethod.RESIDUAL,
        artifact_id="sbm-sensitivity-table",
        metadata={"comparison_regime_id": "BASEL_MAR21"},
    )
    store = DuckDbParquetResultStore(tmp_path / "result-store")

    store.write_bundle(sample_bundle(run, movement_results=(movement,)))

    assert store.movement_results(run.run_id, node_id="sbm-girr-usd") == (movement,)
    summary = store.movement_summary(run.run_id, node_id="sbm-girr-usd")
    assert len(summary) == 1
    assert summary[0].baseline_run_id == "run-basel-baseline"
    assert summary[0].movement_type == "REGIME_OVER_REGIME"
    assert summary[0].base_currency == "USD"
    assert summary[0].delta_amount == 3.0


def test_store_preserves_distinct_attribution_source_and_target(
    tmp_path: Path,
) -> None:
    run = run_with_id("run-attribution-target-override")
    attribution = CapitalAttributionRecord.from_contribution(
        run_id=run.run_id,
        node_id="total",
        contribution=CapitalContribution(
            contribution_id="residual-total",
            source_id="residual-total-source",
            source_level="RESIDUAL_BRANCH",
            bucket_key=None,
            category="RESIDUAL",
            base_amount=1.0,
            marginal_multiplier=None,
            contribution=None,
            method="RESIDUAL",
            residual=1.0,
            reason="Non-homogeneous branch held as residual.",
        ),
        target_type="UNSUPPORTED_BRANCH",
        target_id="unsupported-total-target",
    )
    store = DuckDbParquetResultStore(tmp_path / "result-store")

    store.write_bundle(sample_bundle(run, attributions=(attribution,)))

    stored = store.attributions_for_node(run.run_id, "total")[0]
    assert stored.source_id == "residual-total-source"
    assert stored.source_level == "RESIDUAL_BRANCH"
    assert stored.target_type == "UNSUPPORTED_BRANCH"
    assert stored.target_id == "unsupported-total-target"
    assert stored.unsupported_reason == "Non-homogeneous branch held as residual."


def test_incompatible_run_fails_closed_without_blocking_other_runs(tmp_path: Path) -> None:
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    incompatible_run = run_with_id("run-incompatible")
    compatible_run = run_with_id("run-compatible")
    store.write_bundle(sample_bundle(incompatible_run))
    store.write_bundle(sample_bundle(compatible_run))
    manifest_path = store._manifest_path(incompatible_run.run_id)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["result_store_schema_version"] = 999
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ResultStoreCompatibilityError, match="incompatible result-store run"):
        store.get_run(incompatible_run.run_id)
    with pytest.raises(ResultStoreCompatibilityError, match="incompatible result-store run"):
        store.child_nodes(incompatible_run.run_id, "total")
    assert store.get_run(compatible_run.run_id) == compatible_run
    assert [run.run_id for run in store.list_runs()] == [compatible_run.run_id]

    manifest_path.write_text("{", encoding="utf-8")
    with pytest.raises(ResultStoreCompatibilityError, match="malformed run manifest JSON"):
        store.get_run(incompatible_run.run_id)
    assert [run.run_id for run in store.list_runs()] == [compatible_run.run_id]
