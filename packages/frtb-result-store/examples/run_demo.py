"""Demonstrate persisting a synthetic suite result into the result store."""

from __future__ import annotations

import sys
from datetime import UTC, date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

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
)


def build_suite_result_bundle() -> ResultBundle:
    """Return a synthetic post-calculation suite bundle for storage handoff."""

    run = CalculationRun.from_identity(
        as_of_date=date(2026, 6, 3),
        regime_id="US_NPR_2_0",
        base_currency="USD",
        input_snapshot_id="snapshot-demo-suite-001",
        calculation_scope="FIRM",
        engine_version="frtb-suite-demo",
        code_version="example",
        calculation_policy_id="policy-us-npr-demo",
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
        metadata={"purpose": "result-store-handoff-demo"},
    )
    nodes = (
        CapitalNode(
            run_id=run.run_id,
            node_id="total",
            node_type=NodeType.ROOT,
            component=FrtbComponent.TOP_OF_HOUSE,
            label="Total suite capital",
            sort_key=0,
        ),
        CapitalNode(
            run_id=run.run_id,
            node_id="ima-summary",
            node_type=NodeType.DESK,
            component=FrtbComponent.IMA,
            label="IMA rates desk summary",
            desk_id="rates",
            calculation_branch="IMA_SUMMARY_HANDOFF",
            sort_key=1,
        ),
        CapitalNode(
            run_id=run.run_id,
            node_id="sa-summary",
            node_type=NodeType.COMPONENT,
            component=FrtbComponent.STANDARDISED_APPROACH,
            label="Standardised Approach summary",
            sort_key=2,
        ),
        CapitalNode(
            run_id=run.run_id,
            node_id="cva-summary",
            node_type=NodeType.COMPONENT,
            component=FrtbComponent.CVA,
            label="CVA summary",
            sort_key=3,
        ),
    )
    component_node_ids = ("ima-summary", "sa-summary", "cva-summary")
    edges = tuple(
        CapitalEdge(
            run_id=run.run_id,
            parent_node_id="total",
            child_node_id=node_id,
            edge_type=EdgeType.AGGREGATES,
            sort_key=sort_key,
        )
        for sort_key, node_id in enumerate(component_node_ids, start=1)
    )
    measures = (
        _capital_measure(run.run_id, "total", 142.0, "Suite total capital"),
        _capital_measure(run.run_id, "ima-summary", 80.0, "IMA component capital"),
        _capital_measure(run.run_id, "sa-summary", 45.0, "SA component capital"),
        _capital_measure(run.run_id, "cva-summary", 17.0, "CVA component capital"),
    )
    artifacts = (
        ArtifactRef(
            run_id=run.run_id,
            artifact_id="ima-pnl-vector",
            component=FrtbComponent.IMA,
            artifact_type=ArtifactType.IMA_PNL_VECTOR,
            uri="s3://example-frtb-results/ima-pnl-vector.parquet",
            format="parquet",
            row_count=250,
            metadata={"source": "demo synthetic IMA P&L vector"},
        ),
        ArtifactRef(
            run_id=run.run_id,
            artifact_id="cva-exposure-table",
            component=FrtbComponent.CVA,
            artifact_type=ArtifactType.CVA_EXPOSURE_TABLE,
            uri="s3://example-frtb-results/cva-exposure-table.parquet",
            format="parquet",
            row_count=25,
            metadata={"source": "demo synthetic CVA exposure table"},
        ),
        ArtifactRef(
            run_id=run.run_id,
            artifact_id="suite-attribution-vector",
            component=FrtbComponent.TOP_OF_HOUSE,
            artifact_type=ArtifactType.ATTRIBUTION_VECTOR,
            uri="s3://example-frtb-results/suite-attribution-vector.parquet",
            format="parquet",
            row_count=3,
            metadata={"source": "demo synthetic attribution vector"},
        ),
    )
    lineage = (
        LineageRef(
            run_id=run.run_id,
            result_id="total",
            source_type="input_snapshot",
            source_id="snapshot-demo-suite-001",
            source_hash="demo-input-snapshot-hash",
        ),
        LineageRef(
            run_id=run.run_id,
            result_id="suite-attribution-vector",
            source_type="artifact_manifest",
            source_id="suite-attribution-vector",
        ),
    )
    attributions = tuple(
        CapitalAttributionRecord.from_contribution(
            run_id=run.run_id,
            node_id=node_id,
            contribution=CapitalContribution(
                contribution_id=f"standalone-{node_id}",
                source_id=source_id,
                source_level=source_level,
                bucket_key=None,
                category=category,
                base_amount=amount,
                marginal_multiplier=None,
                contribution=amount,
                method="STANDALONE",
            ),
            artifact_id="suite-attribution-vector",
        )
        for node_id, source_id, source_level, category, amount in (
            ("ima-summary", "desk-rates", "DESK", "IMA", 80.0),
            ("sa-summary", "sa-stack", "PORTFOLIO", "SA", 45.0),
            ("cva-summary", "counterparty-set", "COUNTERPARTY", "CVA", 17.0),
        )
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


def _capital_measure(run_id: str, node_id: str, amount: float, label: str) -> CapitalMeasure:
    return CapitalMeasure(
        run_id=run_id,
        node_id=node_id,
        measure_name="capital",
        amount=amount,
        currency="USD",
        metadata={"label": label, "synthetic_data": True},
    )


def run_demo(store_root: Path) -> None:
    """Write and read back the synthetic suite bundle."""

    bundle = build_suite_result_bundle()
    store = DuckDbParquetResultStore(store_root)
    store.write_bundle(bundle)

    summary = store.capital_summary(bundle.run.run_id)[0]
    components = store.component_breakdown(bundle.run.run_id)
    lineage = store.lineage_for_result(bundle.run.run_id, "total")
    attributions = tuple(
        attribution
        for node in ("ima-summary", "sa-summary", "cva-summary")
        for attribution in store.attributions_for_node(bundle.run.run_id, node)
    )

    component_text = ", ".join(
        f"{row.component.value}={row.amount:.2f} {row.currency}" for row in components
    )
    print("Result-store demo complete")
    print(f"run id: {bundle.run.run_id}")
    print(f"total capital: {summary.total_capital:.2f} {summary.currency}")
    print(f"component breakdown: {component_text}")
    print(f"attribution records: {len(attributions)}")
    print(f"lineage source: {lineage[0].source_id}")
    print(f"store root: {store.root}")


def main() -> int:
    """Run the result-store handoff demo."""

    with TemporaryDirectory(prefix="frtb-result-store-demo-") as tmp_dir:
        run_demo(Path(tmp_dir) / "result-store")
    return 0


if __name__ == "__main__":
    sys.exit(main())
