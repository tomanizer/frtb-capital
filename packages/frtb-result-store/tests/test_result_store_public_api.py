from __future__ import annotations

import subprocess
import sys
from datetime import UTC, date, datetime

import pytest
from frtb_common import (
    CapitalContribution,
    ImplementationStatus,
    ValidationStatus,
)
from frtb_result_store import (
    PACKAGE_METADATA,
    ArtifactRef,
    ArtifactType,
    CalculationRun,
    CapitalAttributionRecord,
    CapitalEdge,
    CapitalNode,
    FrtbComponent,
    NodeType,
    ResultBundle,
    ResultStoreContractError,
)


def test_package_metadata_marks_result_store_as_partial_runtime_infrastructure() -> None:
    assert PACKAGE_METADATA.package_name == "frtb-result-store"
    assert PACKAGE_METADATA.import_name == "frtb_result_store"
    assert PACKAGE_METADATA.component_name == "FRTB result store"
    assert PACKAGE_METADATA.implementation_status is ImplementationStatus.PARTIAL
    assert PACKAGE_METADATA.validation_status is ValidationStatus.PENDING


def test_top_level_import_does_not_load_duckdb_backend() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import frtb_result_store, sys; print('duckdb' in sys.modules)",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "False"


def test_result_bundle_validates_graph_references() -> None:
    run = _run()
    root = CapitalNode(
        run_id=run.run_id,
        node_id="total",
        node_type=NodeType.ROOT,
        component=FrtbComponent.TOP_OF_HOUSE,
        label="Total capital",
    )
    missing_child = CapitalEdge(
        run_id=run.run_id,
        parent_node_id="total",
        child_node_id="ima",
    )

    with pytest.raises(ResultStoreContractError, match="edge child node not found"):
        ResultBundle(run=run, nodes=(root,), edges=(missing_child,))


def test_result_bundle_reports_duplicate_node_ids_deterministically() -> None:
    run = _run()
    nodes = (
        CapitalNode(
            run_id=run.run_id,
            node_id="z-duplicate",
            node_type=NodeType.ROOT,
            component=FrtbComponent.TOP_OF_HOUSE,
            label="Z duplicate 1",
        ),
        CapitalNode(
            run_id=run.run_id,
            node_id="a-duplicate",
            node_type=NodeType.COMPONENT,
            component=FrtbComponent.IMA,
            label="A duplicate 1",
        ),
        CapitalNode(
            run_id=run.run_id,
            node_id="z-duplicate",
            node_type=NodeType.COMPONENT,
            component=FrtbComponent.SBM,
            label="Z duplicate 2",
        ),
        CapitalNode(
            run_id=run.run_id,
            node_id="a-duplicate",
            node_type=NodeType.COMPONENT,
            component=FrtbComponent.DRC,
            label="A duplicate 2",
        ),
    )

    with pytest.raises(
        ResultStoreContractError,
        match="duplicate node ids: a-duplicate, z-duplicate",
    ):
        ResultBundle(run=run, nodes=nodes)


def test_attribution_record_reuses_common_capital_contribution_contract() -> None:
    contribution = CapitalContribution(
        contribution_id="alloc-girr-usd-5y",
        source_id="sensitivity-girr-usd-5y",
        source_level="SENSITIVITY",
        bucket_key="GIRR:USD",
        category="SBM_DELTA",
        base_amount=25.0,
        marginal_multiplier=0.4,
        contribution=10.0,
        method="ANALYTICAL_EULER",
    )

    record = CapitalAttributionRecord.from_contribution(
        run_id="run-001",
        node_id="sbm-girr-usd",
        contribution=contribution,
    )

    assert record.method == contribution.method
    assert record.contribution == 10.0
    assert record.source_id == "sensitivity-girr-usd-5y"


def test_artifact_ref_accepts_object_store_drillthrough_uri() -> None:
    artifact = ArtifactRef(
        run_id="run-001",
        artifact_id="ima-pnl-desk-a",
        component="IMA",
        artifact_type=ArtifactType.IMA_PNL_VECTOR,
        uri="s3://frtb-results/as_of=2026-06-03/run=run-001/ima_pnl.parquet",
        format="parquet",
        row_count=2500,
        partition_keys=("desk_id", "portfolio_id", "book_id", "scenario_id"),
    )

    assert artifact.component is FrtbComponent.IMA
    assert artifact.uri.startswith("s3://")


def _run() -> CalculationRun:
    return CalculationRun(
        run_id="run-001",
        as_of_date=date(2026, 6, 3),
        regime_id="US_NPR_2_0",
        base_currency="USD",
        input_snapshot_id="snapshot-001",
        calculation_scope="FIRM",
        engine_version="frtb-suite-0.1",
        code_version="abc123",
        calculation_policy_id="policy-us-npr",
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
    )
