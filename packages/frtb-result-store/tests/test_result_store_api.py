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
    assert set(comparison["capital_summary"]) == {baseline.run_id, current.run_id}


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
    assert set(comparison.json()["capital_summary"]) == {run.run_id}


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


def _bundle(run: CalculationRun, *, baseline_run_id: str | None = None) -> ResultBundle:
    return ResultBundle(
        run=run,
        nodes=_nodes(run),
        edges=_edges(run),
        measures=_measures(run),
        artifacts=_artifacts(run),
        lineage=_lineage(run),
        attributions=_attributions(run),
        movement_results=_movement_results(run, baseline_run_id),
        events=_events(run),
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
            "risk_factor_set_id": [None, "set-1", "set-1"],
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
