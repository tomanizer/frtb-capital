"""Reusable result-store bundle builders for DuckDB/Parquet integration tests."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pyarrow as pa
from frtb_common import CapitalContribution
from frtb_result_store import (
    ArtifactRef,
    ArtifactType,
    CalculationRun,
    CapitalAttributionRecord,
    CapitalEdge,
    CapitalMeasure,
    CapitalNode,
    EdgeType,
    FrtbComponent,
    InputSnapshotManifest,
    LineageRef,
    MovementResult,
    NodeType,
    ResultBundle,
    ResultEvent,
    RunTelemetry,
)


def run_with_id(run_id: str) -> CalculationRun:
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


def default_artifacts(run: CalculationRun) -> tuple[ArtifactRef, ...]:
    return (
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
        ArtifactRef(
            run_id=run.run_id,
            artifact_id="sbm-sensitivity-table",
            component=FrtbComponent.SBM,
            artifact_type=ArtifactType.SBM_SENSITIVITY_TABLE,
            uri="s3://frtb-results/sbm-sensitivity-table.parquet",
            format="parquet",
            row_count=1,
        ),
    )


def default_measures(run: CalculationRun) -> tuple[CapitalMeasure, ...]:
    return (
        CapitalMeasure(
            run_id=run.run_id,
            node_id="total",
            measure_name="capital",
            amount=42.0,
            currency="USD",
            regulatory_rule_id="US_NPR_325.201",
        ),
        CapitalMeasure(
            run_id=run.run_id,
            node_id="ima-book-rates-core",
            measure_name="capital",
            amount=17.0,
            currency="USD",
            regulatory_rule_id="US_NPR_325.207",
        ),
        CapitalMeasure(
            run_id=run.run_id,
            node_id="sa",
            measure_name="capital",
            amount=25.0,
            currency="USD",
            regulatory_rule_id="US_NPR_325.204",
        ),
        CapitalMeasure(
            run_id=run.run_id,
            node_id="sbm-girr-usd",
            measure_name="capital",
            amount=25.0,
            currency="USD",
            regulatory_rule_id="MAR21.4",
        ),
    )


def ima_pnl_chunks(schema: pa.Schema, run_id: str) -> tuple[pa.Table, pa.Table]:
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


def sample_bundle(
    run: CalculationRun | None = None,
    *,
    artifacts: tuple[ArtifactRef, ...] | None = None,
    input_manifests: tuple[InputSnapshotManifest, ...] = (),
    attributions: tuple[CapitalAttributionRecord, ...] | None = None,
    movement_results: tuple[MovementResult, ...] = (),
    events: tuple[ResultEvent, ...] = (),
    telemetry: tuple[RunTelemetry, ...] = (),
) -> ResultBundle:
    if run is None:
        run = run_with_id("frtb/run/2026-06-03")
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
    measures = default_measures(run)
    artifacts = default_artifacts(run) if artifacts is None else artifacts
    lineage = (
        LineageRef(
            run_id=run.run_id,
            result_id="total",
            source_type="input_snapshot",
            source_id="snapshot-001",
        ),
    )
    default_attributions = (
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
            artifact_id="sbm-sensitivity-table",
        ),
    )
    attributions = default_attributions if attributions is None else attributions
    return ResultBundle(
        run=run,
        nodes=nodes,
        edges=edges,
        measures=measures,
        artifacts=artifacts,
        input_manifests=input_manifests,
        lineage=lineage,
        attributions=attributions,
        movement_results=movement_results,
        events=events,
        telemetry=telemetry,
    )
