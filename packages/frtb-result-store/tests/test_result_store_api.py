from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path

import pyarrow as pa  # type: ignore[import-untyped]
from fastapi.testclient import TestClient
from frtb_common import AttributionMethod, CapitalContribution
from frtb_result_store import (
    ArtifactRef,
    ArtifactType,
    ArtifactWriteRequest,
    CalculationRun,
    CapitalAttributionRecord,
    CapitalEdge,
    CapitalMeasure,
    CapitalNode,
    DuckDbParquetResultStore,
    EdgeType,
    FrtbComponent,
    LineageRef,
    MovementResult,
    NodeType,
    ResultBundle,
    ResultEvent,
    ResultEventSeverity,
    ResultEventType,
    RiskFactorEvidenceState,
    RiskFactorMetadataRecord,
    RiskFactorMetadataSnapshot,
    RiskFactorRecordStatus,
    RiskFactorSourceMapping,
    artifact_schema_for,
    canonical_run_group_identity_payload,
    create_result_store_app,
    generate_run_group_id,
)


def test_result_store_api_serves_committed_runs_without_catalog_access(
    tmp_path: Path,
    monkeypatch,
) -> None:
    group_payload = canonical_run_group_identity_payload(
        as_of_date=date(2026, 6, 3),
        calculation_scope="FIRM",
        input_snapshot_id="snapshot-001",
        calculation_policy_group_id="global-policy",
        engine_version="engine-v1",
        code_version="code-v1",
        group_purpose="regime-comparison",
    )
    group_id = generate_run_group_id(group_payload)
    baseline = _run("US_NPR_2_0", group_id, group_payload)
    current = _run("EU_CRR3", group_id, group_payload)
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    store.write_bundle(_bundle(baseline))
    store.write_bundle(_bundle(current, baseline_run_id=baseline.run_id))

    def fail_catalog() -> object:
        raise AssertionError("API must not use catalog.duckdb")

    monkeypatch.setattr(store, "_connect_catalog", fail_catalog)
    client = TestClient(create_result_store_app(store))

    runs = client.get("/runs").json()["runs"]
    assert [run["run_id"] for run in runs] == sorted([baseline.run_id, current.run_id])
    assert runs[0]["latest_status"] == "CANDIDATE"
    assert client.get(f"/runs/{current.run_id}").json()["regime_id"] == "EU_CRR3"
    assert client.get("/run-groups").json()["run_groups"][0]["run_group_id"] == group_id

    tree = client.get(f"/runs/{current.run_id}/capital-tree").json()["nodes"]
    assert [node["node_id"] for node in tree] == ["total", "ima"]
    assert client.get(f"/runs/{current.run_id}/nodes/ima").json()["component"] == "IMA"
    assert (
        client.get(f"/runs/{current.run_id}/nodes/total/children").json()["nodes"][0]["node_id"]
        == "ima"
    )
    assert (
        client.get(f"/runs/{current.run_id}/nodes/total/measures").json()["measures"][0]["amount"]
        == 42.0
    )
    assert (
        client.get(f"/runs/{current.run_id}/nodes/ima/attribution").json()["attributions"][0][
            "attribution_id"
        ]
        == "ima-desk"
    )
    assert (
        client.get(f"/runs/{current.run_id}/nodes/total/lineage").json()["lineage"][0]["source_id"]
        == "snapshot-001"
    )
    assert client.get(f"/runs/{current.run_id}/events").json()["events"][0]["event_type"] == (
        "CALCULATION_WARNING"
    )
    assert (
        client.get(f"/runs/{current.run_id}/movements").json()["movements"][0]["baseline_run_id"]
        == baseline.run_id
    )
    artifacts = client.get(
        f"/runs/{current.run_id}/artifacts",
        params={"artifact_type": ArtifactType.IMA_PNL_VECTOR.value},
    ).json()["artifacts"]
    assert artifacts[0]["uri"].startswith("s3://")
    handoff = client.get(
        f"/runs/{current.run_id}/artifacts/{artifacts[0]['artifact_id']}/download"
    ).json()
    assert handoff["mode"] == "s3_uri_handoff"
    assert handoff["uri"].startswith("s3://")
    assert (
        client.get(
            f"/runs/{current.run_id}/artifacts",
            params={"artifact_type": "not-an-artifact-type"},
        ).status_code
        == 422
    )
    comparison = client.get(f"/run-groups/{group_id}/regime-comparison").json()
    assert comparison["run_group_id"] == group_id
    assert {row["run_id"] for row in comparison["regime_comparison"]} == {
        baseline.run_id,
        current.run_id,
    }


def test_result_store_api_serves_org_hierarchy_queries_with_slash_run_id(
    tmp_path: Path,
) -> None:
    run = _run("US_NPR_2_0", None, None)
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    store.write_bundle(_bundle(run))
    client = TestClient(create_result_store_app(store))

    org_hierarchy = client.get(f"/runs/{run.run_id}/org-hierarchy").json()
    assert org_hierarchy["version_id"] == "2026-01"
    assert org_hierarchy["nodes"][0]["node_id"] == "GLOBAL_GROUP"
    assert ("GLOBAL_GROUP", "US_BANK_NA") in {
        (edge["parent_node_id"], edge["child_node_id"]) for edge in org_hierarchy["edges"]
    }

    org_children = client.get(f"/runs/{run.run_id}/org-hierarchy/nodes/MARKETS/children").json()[
        "nodes"
    ]
    org_aggregate = client.get(
        f"/runs/{run.run_id}/org-hierarchy/nodes/GLOBAL_GROUP/aggregate"
    ).json()
    org_sources = client.get(
        f"/runs/{run.run_id}/org-hierarchy/nodes/USD_RATES_VOLCKER/source-rows",
        params={"limit": 1},
    ).json()

    assert [node["node_id"] for node in org_children] == ["EQUITIES", "FICC", "FX"]
    assert org_aggregate["status"] == "OK"
    assert org_aggregate["aggregate"]["capital"] == 114.0
    assert org_sources["total_row_count"] == 2
    assert org_sources["next_offset"] == 1
    assert org_sources["rows"][0]["source_row_id"] == "org-row-ima-rates-desk"
    assert (
        client.get(
            f"/runs/{run.run_id}/org-hierarchy/nodes/USD_RATES_VOLCKER/aggregate",
            params={"framework": "CVA"},
        ).json()["status"]
        == "NO_DATA"
    )
    assert (
        client.get(
            f"/runs/{run.run_id}/org-hierarchy/nodes/GLOBAL_GROUP/source-rows",
            params={"framework": "RFET"},
        ).json()["status"]
        == "UNSUPPORTED"
    )
    missing = client.get(f"/runs/{run.run_id}/org-hierarchy/nodes/MISSING/aggregate")
    assert missing.status_code == 404


def test_top_contributors_api_validates_limit(tmp_path: Path) -> None:
    run = _run("US_NPR_2_0", None, None)
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    store.write_bundle(_bundle(run))
    client = TestClient(create_result_store_app(store))

    contributors = client.get(f"/runs/{run.run_id}/top-contributors").json()["contributors"]
    assert contributors[0]["attribution_id"] == "ima-desk"
    assert contributors[0]["source_id"] == "desk-rates"
    assert contributors[0]["unsupported_reason"] == ""
    assert (
        client.get(f"/runs/{run.run_id}/top-contributors", params={"limit": 0}).status_code == 422
    )
    assert (
        client.get(f"/runs/{run.run_id}/top-contributors", params={"limit": 1001}).status_code
        == 422
    )


def test_risk_factor_api_serves_metadata_lineage_and_drilldown_states(tmp_path: Path) -> None:
    run = _run("US_NPR_2_0", None, None)
    snapshot, records, mappings = _risk_factor_metadata_fixture(run)
    attributions = (
        CapitalAttributionRecord.from_contribution(
            run_id=run.run_id,
            node_id="ima",
            contribution=CapitalContribution(
                contribution_id="rf-1-capital",
                source_id="rf-1",
                source_level="RISK_FACTOR",
                bucket_key="GIRR:USD",
                category="IMA_RISK_FACTOR",
                base_amount=4.0,
                marginal_multiplier=0.25,
                contribution=1.0,
                method=AttributionMethod.ANALYTICAL_EULER,
            ),
        ),
    )
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    store.write_bundle(
        _bundle(
            run,
            attributions=attributions,
            risk_factor_snapshots=(snapshot,),
            risk_factor_metadata=records,
            risk_factor_source_mappings=mappings,
        )
    )
    client = TestClient(create_result_store_app(store))

    listing = client.get(
        f"/runs/{run.run_id}/risk-factors",
        params={"search": "usd", "risk_class": "girr", "limit": 1},
    ).json()
    assert listing["state"] == "available"
    assert listing["total_count"] == 2
    assert listing["next_offset"] == 1
    assert listing["items"][0]["risk_factor_id"] == "rf-1"

    detail = client.get(f"/runs/{run.run_id}/risk-factors/rf-1").json()
    assert detail["state"] == "available"
    assert detail["metadata"]["mapping_version"] == "synthetic-taxonomy-v1"
    assert detail["lineage_count"] == 2

    lineage = client.get(f"/runs/{run.run_id}/risk-factors/rf-1/lineage").json()
    assert [row["source_row_id"] for row in lineage["lineage"]] == ["row-1", "row-1-rfet"]

    source_page = client.get(
        f"/runs/{run.run_id}/risk-factors/rf-1/source-rows",
        params={"limit": 1, "offset": 1},
    ).json()
    assert source_page["rows"][0]["source_system"] == "rfet-vendor"
    assert source_page["next_offset"] is None

    capital = client.get(
        f"/runs/{run.run_id}/risk-factors/rf-1/capital",
        params={"framework": "IMA"},
    ).json()
    assert capital["state"] == "available"
    assert capital["contribution"] == 1.0
    assert capital["attribution_count"] == 1

    missing_capital = client.get(f"/runs/{run.run_id}/risk-factors/rf-2/capital").json()
    assert missing_capital["state"] == "no_data"
    assert missing_capital["contribution"] is None

    bad_limit = client.get(
        f"/runs/{run.run_id}/risk-factors/rf-1/source-rows",
        params={"limit": 0},
    )
    assert bad_limit.status_code == 422


def test_attribution_explain_projection_api_serves_residual_and_unsupported(
    tmp_path: Path,
) -> None:
    run = _run("US_NPR_2_0", None, None)
    attributions = (
        *_attributions(run),
        CapitalAttributionRecord.from_contribution(
            run_id=run.run_id,
            node_id="total",
            contribution=CapitalContribution(
                contribution_id="suite-residual",
                source_id="suite-residual-source",
                source_level="RESIDUAL_BRANCH",
                bucket_key=None,
                category="SUITE_RESIDUAL",
                base_amount=1.75,
                marginal_multiplier=None,
                contribution=None,
                method=AttributionMethod.RESIDUAL,
                residual=1.75,
                reason="Suite branch retained as residual.",
            ),
            target_type="RESIDUAL_BRANCH",
            target_id="suite-residual-target",
        ),
        CapitalAttributionRecord.from_contribution(
            run_id=run.run_id,
            node_id="ima",
            contribution=CapitalContribution(
                contribution_id="unsupported-nmrf",
                source_id="nmrf-branch",
                source_level="UNSUPPORTED_BRANCH",
                bucket_key="NMRF",
                category="UNSUPPORTED_NMRF",
                base_amount=0.5,
                marginal_multiplier=None,
                contribution=None,
                method=AttributionMethod.UNSUPPORTED,
                residual=0.5,
                reason="NMRF fallback is unsupported for exact Euler.",
            ),
            target_type="UNSUPPORTED_BRANCH",
            target_id="nmrf-branch-target",
        ),
    )
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    store.write_bundle(_bundle(run, attributions=attributions))
    client = TestClient(create_result_store_app(store))

    residual = client.get(f"/runs/{run.run_id}/attribution/residual").json()["residual_records"]
    assert [row["attribution_id"] for row in residual] == ["suite-residual", "unsupported-nmrf"]
    assert residual[0]["contribution"] is None
    assert residual[0]["residual"] == 1.75
    assert residual[0]["method"] == "RESIDUAL"
    assert residual[0]["source_level"] == "RESIDUAL_BRANCH"
    assert residual[0]["target_id"] == "suite-residual-target"
    assert residual[0]["unsupported_reason"] == "Suite branch retained as residual."

    unsupported = client.get(
        f"/runs/{run.run_id}/attribution/unsupported",
        params={"node_id": "ima"},
    ).json()["unsupported_records"]
    assert len(unsupported) == 1
    assert unsupported[0]["attribution_id"] == "unsupported-nmrf"
    assert unsupported[0]["source_id"] == "nmrf-branch"
    assert unsupported[0]["method"] == "UNSUPPORTED"
    assert unsupported[0]["target_id"] == "nmrf-branch-target"
    assert "unsupported for exact Euler" in unsupported[0]["unsupported_reason"]


def test_result_store_api_is_read_only_and_has_domain_openapi_tags(tmp_path: Path) -> None:
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    group_payload = canonical_run_group_identity_payload(
        as_of_date=date(2026, 6, 3),
        calculation_scope="FIRM",
        input_snapshot_id="snapshot-001",
        calculation_policy_group_id="global-policy",
        engine_version="engine-v1",
        code_version="code-v1",
        group_purpose="regime-comparison",
    )
    run = _run("US_NPR_2_0", generate_run_group_id(group_payload), group_payload)
    store.write_bundle(_bundle(run))
    client = TestClient(create_result_store_app(store))

    assert client.post("/runs").status_code == 405
    openapi = client.get("/openapi.json").json()
    expected_tags = {
        "Runs",
        "Run Groups",
        "Capital Tree",
        "Artifacts",
        "Attribution",
        "Lineage",
        "Events",
        "Movements",
        "Regime Comparison",
        "Org Hierarchy",
    }
    assert expected_tags <= {tag["name"] for tag in openapi["tags"]}
    path_methods = {
        method
        for path, methods in openapi["paths"].items()
        if path not in {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}
        for method in methods
    }
    assert path_methods == {"get"}
    assert not any("/tables" in path for path in openapi["paths"])
    operation_tags = {
        tag
        for path, methods in openapi["paths"].items()
        if not path.startswith("/docs")
        for operation in methods.values()
        for tag in operation.get("tags", ())
    }
    assert expected_tags <= operation_tags


def test_regime_comparison_accepts_single_run_group_fallback(tmp_path: Path) -> None:
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    run = _run("US_NPR_2_0", None, None)
    store.write_bundle(_bundle(run))
    client = TestClient(create_result_store_app(store))

    fallback_group_id = f"run:{run.run_id}"
    assert client.get("/run-groups").json()["run_groups"][0]["run_group_id"] == fallback_group_id
    comparison = client.get(f"/run-groups/{fallback_group_id}/regime-comparison")
    assert comparison.status_code == 200
    assert comparison.json()["run_group_id"] == fallback_group_id
    assert comparison.json()["regime_comparison"][0]["run_id"] == run.run_id


def test_artifact_drillthrough_pages_and_downloads_local_parquet(tmp_path: Path) -> None:
    store, run, artifact = _store_with_drillthrough_artifact(tmp_path)
    client = TestClient(create_result_store_app(store))

    first_page = client.get(
        f"/runs/{run.run_id}/artifacts/{artifact.artifact_id}/page",
        params={
            "columns": "source_row_id,pnl_amount",
            "filter": "desk_id=rates",
            "limit": 1,
        },
    ).json()
    assert first_page["mode"] == "local_parquet"
    assert first_page["columns"] == ["source_row_id", "pnl_amount"]
    assert first_page["filtered_row_count"] == 3
    assert first_page["next_offset"] == 1
    assert first_page["rows"] == [{"source_row_id": "row-1", "pnl_amount": 1.25}]

    second_page = client.get(
        f"/runs/{run.run_id}/artifacts/{artifact.artifact_id}/page",
        params={
            "columns": ["source_row_id", "pnl_amount"],
            "filter": "desk_id=rates",
            "limit": 2,
            "offset": 1,
        },
    ).json()
    assert second_page["next_offset"] is None
    assert [row["source_row_id"] for row in second_page["rows"]] == ["row-2", "row-3"]

    comma_filter = client.get(
        f"/runs/{run.run_id}/artifacts/{artifact.artifact_id}/page",
        params={
            "columns": "source_row_id",
            "filter": "risk_factor_set_id=set,2",
        },
    ).json()
    assert comma_filter["rows"] == [{"source_row_id": "row-3"}]

    bad_column = client.get(
        f"/runs/{run.run_id}/artifacts/{artifact.artifact_id}/page",
        params={"columns": "missing_column"},
    )
    assert bad_column.status_code == 422
    assert "missing_column" in bad_column.json()["detail"]

    missing = client.get(f"/runs/{run.run_id}/artifacts/missing-artifact/page")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "artifact not found: missing-artifact"

    download = client.get(f"/runs/{run.run_id}/artifacts/{artifact.artifact_id}/download")
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/vnd.apache.parquet"
    assert download.content.startswith(b"PAR1")


def test_artifact_download_rejects_local_file_outside_store_root(tmp_path: Path) -> None:
    run = _run("US_NPR_2_0", None, None)
    outside = tmp_path / "outside.parquet"
    outside.write_bytes(b"PAR1")
    external_artifact = ArtifactRef(
        run_id=run.run_id,
        artifact_id="outside-store-root",
        component=FrtbComponent.IMA,
        artifact_type=ArtifactType.OTHER,
        uri=outside.resolve().as_uri(),
        format="parquet",
        row_count=0,
    )
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    store.write_bundle(_bundle(run, artifacts=(*_artifacts(run), external_artifact)))
    client = TestClient(create_result_store_app(store))

    response = client.get(f"/runs/{run.run_id}/artifacts/outside-store-root/download")
    assert response.status_code == 404
    assert response.json()["detail"] == "artifact file not found: outside-store-root"


def _run(
    regime_id: str,
    run_group_id: str | None,
    run_group_identity_payload: Mapping[str, object] | None,
) -> CalculationRun:
    return CalculationRun.from_identity(
        as_of_date=date(2026, 6, 3),
        regime_id=regime_id,
        base_currency="USD",
        input_snapshot_id="snapshot-001",
        calculation_scope="FIRM",
        engine_version="engine-v1",
        code_version="code-v1",
        calculation_policy_id=f"policy-{regime_id.lower()}",
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
        run_group_id=run_group_id,
        run_group_identity_payload=run_group_identity_payload,
    )


def _bundle(
    run: CalculationRun,
    *,
    baseline_run_id: str | None = None,
    artifacts: tuple[ArtifactRef, ...] | None = None,
    attributions: tuple[CapitalAttributionRecord, ...] | None = None,
    risk_factor_snapshots: tuple[RiskFactorMetadataSnapshot, ...] = (),
    risk_factor_metadata: tuple[RiskFactorMetadataRecord, ...] = (),
    risk_factor_source_mappings: tuple[RiskFactorSourceMapping, ...] = (),
) -> ResultBundle:
    return ResultBundle(
        run=run,
        nodes=_nodes(run),
        edges=_edges(run),
        measures=_measures(run),
        artifacts=_artifacts(run) if artifacts is None else artifacts,
        lineage=_lineage(run),
        attributions=_attributions(run) if attributions is None else attributions,
        risk_factor_snapshots=risk_factor_snapshots,
        risk_factor_metadata=risk_factor_metadata,
        risk_factor_source_mappings=risk_factor_source_mappings,
        movement_results=_movement_results(run, baseline_run_id),
        events=_events(run),
    )


def _risk_factor_metadata_fixture(
    run: CalculationRun,
) -> tuple[
    RiskFactorMetadataSnapshot,
    tuple[RiskFactorMetadataRecord, ...],
    tuple[RiskFactorSourceMapping, ...],
]:
    snapshot = _risk_factor_snapshot(run)
    return snapshot, _risk_factor_records(run, snapshot), _risk_factor_mappings(run, snapshot)


def _risk_factor_snapshot(run: CalculationRun) -> RiskFactorMetadataSnapshot:
    return RiskFactorMetadataSnapshot(
        run_id=run.run_id,
        snapshot_id="risk-factor-snapshot",
        mapping_version="synthetic-taxonomy-v1",
        effective_date=run.as_of_date,
        source_system="fixture-risk-engine",
        created_at=run.created_at,
    )


def _risk_factor_records(
    run: CalculationRun,
    snapshot: RiskFactorMetadataSnapshot,
) -> tuple[RiskFactorMetadataRecord, ...]:
    common = {
        "run_id": run.run_id,
        "snapshot_id": snapshot.snapshot_id,
        "risk_class": "GIRR",
        "risk_factor_type": "curve",
        "mapping_version": snapshot.mapping_version,
        "bucket_id": "USD",
        "bucket_label": "US dollar",
        "sensitivity_type": "delta",
        "currency": "USD",
        "curve_id": "USD-OIS",
        "source_system": "fixture-risk-engine",
    }
    return (
        RiskFactorMetadataRecord(
            **common,
            risk_factor_id="rf-1",
            display_name="USD OIS 5Y",
            tenor="5Y",
            status=RiskFactorRecordStatus.ACTIVE,
            rfet_evidence_state=RiskFactorEvidenceState.AVAILABLE,
            rfet_evidence_id="rfet-rf-1",
            modellability_state=RiskFactorEvidenceState.AVAILABLE,
            liquidity_horizon_days=20,
            nmrf_state=RiskFactorEvidenceState.NO_DATA,
            source_row_id="row-1",
        ),
        RiskFactorMetadataRecord(
            **common,
            risk_factor_id="rf-2",
            display_name="USD OIS 10Y",
            tenor="10Y",
            status=RiskFactorRecordStatus.NO_DATA,
            rfet_evidence_state=RiskFactorEvidenceState.NO_DATA,
            modellability_state=RiskFactorEvidenceState.NO_DATA,
            nmrf_state=RiskFactorEvidenceState.NO_DATA,
            source_row_id="row-2",
        ),
    )


def _risk_factor_mappings(
    run: CalculationRun,
    snapshot: RiskFactorMetadataSnapshot,
) -> tuple[RiskFactorSourceMapping, ...]:
    mapping_args = {
        "run_id": run.run_id,
        "snapshot_id": snapshot.snapshot_id,
        "mapping_version": snapshot.mapping_version,
    }
    return (
        RiskFactorSourceMapping(
            **mapping_args,
            risk_factor_id="rf-1",
            source_system="fixture-risk-engine",
            source_row_id="row-1",
            source_hash="source-hash-1",
        ),
        RiskFactorSourceMapping(
            **mapping_args,
            risk_factor_id="rf-1",
            source_system="rfet-vendor",
            source_row_id="row-1-rfet",
            relationship="rfet-evidence",
            source_hash="source-hash-rfet-1",
        ),
        RiskFactorSourceMapping(
            **mapping_args,
            risk_factor_id="rf-2",
            source_system="fixture-risk-engine",
            source_row_id="row-2",
            source_hash="source-hash-2",
        ),
    )


def _store_with_drillthrough_artifact(
    tmp_path: Path,
) -> tuple[DuckDbParquetResultStore, CalculationRun, ArtifactRef]:
    run = _run("US_NPR_2_0", None, None)
    schema = artifact_schema_for("ima.pnl_vector.v1")
    request = ArtifactWriteRequest(
        artifact_id_hint="ima-desk-a-pnl",
        artifact_type=ArtifactType.IMA_PNL_VECTOR,
        component=FrtbComponent.IMA,
        schema_id=schema.schema_id,
        chunks=(_ima_pnl_table(schema.arrow_schema, run.run_id),),
        partition_values={
            "desk_id": "rates",
            "portfolio_id": "rates-options",
            "book_id": "rates-core",
        },
        metadata={"source": "api-drillthrough-test"},
    )
    store = DuckDbParquetResultStore(tmp_path / "result-store")
    store.write_bundle(_bundle(run), artifact_requests=(request,))
    artifact = next(
        ref
        for ref in store.artifact_refs(run.run_id)
        if ref.metadata.get("source") == "api-drillthrough-test"
    )
    return store, run, artifact


def _ima_pnl_table(schema: pa.Schema, run_id: str) -> pa.Table:
    return pa.table(
        {
            "run_id": [run_id, run_id, run_id],
            "desk_id": ["rates", "rates", "rates"],
            "portfolio_id": ["rates-options", "rates-options", "rates-options"],
            "book_id": ["rates-core", "rates-core", "rates-core"],
            "position_id": ["pos-1", "pos-2", "pos-3"],
            "risk_factor_id": ["rf-1", "rf-2", "rf-3"],
            "risk_factor_set_id": [None, "set-1", "set,2"],
            "scenario_id": ["scenario-1", "scenario-2", "scenario-3"],
            "observation_date": [date(2026, 6, 1), date(2026, 6, 2), date(2026, 6, 3)],
            "liquidity_horizon": [10, 20, 40],
            "pnl_amount": [1.25, -2.5, 3.75],
            "currency": ["USD", "USD", "USD"],
            "tail_flag": [False, True, False],
            "source_row_id": ["row-1", "row-2", "row-3"],
        },
        schema=schema,
    )


def _nodes(run: CalculationRun) -> tuple[CapitalNode, ...]:
    return (
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
            node_id="ima",
            node_type=NodeType.DESK,
            component=FrtbComponent.IMA,
            label="IMA desk",
            desk_id="rates",
            sort_key=1,
        ),
    )


def _edges(run: CalculationRun) -> tuple[CapitalEdge, ...]:
    return (
        CapitalEdge(
            run_id=run.run_id,
            parent_node_id="total",
            child_node_id="ima",
            edge_type=EdgeType.AGGREGATES,
            sort_key=1,
        ),
    )


def _measures(run: CalculationRun) -> tuple[CapitalMeasure, ...]:
    return (
        CapitalMeasure(
            run_id=run.run_id,
            node_id="total",
            measure_name="capital",
            amount=42.0,
            currency="USD",
        ),
        CapitalMeasure(
            run_id=run.run_id,
            node_id="ima",
            measure_name="capital",
            amount=17.0,
            currency="USD",
        ),
    )


def _artifacts(run: CalculationRun) -> tuple[ArtifactRef, ...]:
    return (
        ArtifactRef(
            run_id=run.run_id,
            artifact_id="ima-pnl-vector",
            component=FrtbComponent.IMA,
            artifact_type=ArtifactType.IMA_PNL_VECTOR,
            uri="s3://frtb-results/ima-pnl-vector.parquet",
            format="parquet",
            row_count=2,
        ),
    )


def _lineage(run: CalculationRun) -> tuple[LineageRef, ...]:
    return (
        LineageRef(
            run_id=run.run_id,
            result_id="total",
            source_type="input_snapshot",
            source_id="snapshot-001",
        ),
    )


def _attributions(run: CalculationRun) -> tuple[CapitalAttributionRecord, ...]:
    return (
        CapitalAttributionRecord.from_contribution(
            run_id=run.run_id,
            node_id="ima",
            contribution=CapitalContribution(
                contribution_id="ima-desk",
                source_id="desk-rates",
                source_level="DESK",
                bucket_key="IMA",
                category="IMA_DESK",
                base_amount=17.0,
                marginal_multiplier=1.0,
                contribution=17.0,
                method=AttributionMethod.ANALYTICAL_EULER,
            ),
        ),
    )


def _movement_results(
    run: CalculationRun,
    baseline_run_id: str | None,
) -> tuple[MovementResult, ...]:
    if baseline_run_id is None:
        return ()
    return (
        MovementResult(
            run_id=run.run_id,
            baseline_run_id=baseline_run_id,
            movement_id="total-capital-delta",
            node_id="total",
            movement_type="REGIME_OVER_REGIME",
            from_amount=39.0,
            to_amount=42.0,
            delta_amount=3.0,
            base_currency="USD",
            driver_type="REGIME",
            driver_id=run.regime_id,
            explanation="Regime parameter difference",
            attribution_method=AttributionMethod.RESIDUAL,
        ),
    )


def _events(run: CalculationRun) -> tuple[ResultEvent, ...]:
    return (
        ResultEvent(
            event_id=f"event-{run.regime_id}",
            run_id=run.run_id,
            event_time=datetime(2026, 6, 3, 12, 1, tzinfo=UTC),
            severity=ResultEventSeverity.WARNING,
            event_type=ResultEventType.CALCULATION_WARNING,
            message="Synthetic API fixture warning",
            component=FrtbComponent.IMA,
        ),
    )
