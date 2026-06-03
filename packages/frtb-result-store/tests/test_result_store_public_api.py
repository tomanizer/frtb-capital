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
    ArtifactWriteRequest,
    CalculationRun,
    CapitalAttributionRecord,
    CapitalEdge,
    CapitalMeasure,
    CapitalNode,
    CapitalNodeFamily,
    CapitalNodeSpec,
    FrtbComponent,
    HierarchyDefinition,
    HierarchyLevel,
    NodeType,
    RequiredArtifactExpectation,
    ResultBundle,
    ResultStoreContractError,
    RunStatus,
    RunStatusEvent,
    artifact_schema_for,
    build_hierarchy_nodes,
    build_standard_capital_graph,
    canonical_run_group_identity_payload,
    canonical_run_identity_payload,
    capital_node_identity_payload,
    default_hierarchy_definition,
    generate_capital_node_id,
    generate_run_group_id,
    generate_run_id,
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


def test_canonical_run_identity_uses_full_stable_digest() -> None:
    payload = canonical_run_identity_payload(
        as_of_date=date(2026, 6, 3),
        regime_id="US_NPR_2_0",
        calculation_scope="FIRM",
        input_snapshot_id="snapshot-001",
        calculation_policy_id="policy-us-npr",
        engine_version="frtb-suite-0.1",
        code_version="abc123",
    )
    same_payload = canonical_run_identity_payload(
        as_of_date=date(2026, 6, 3),
        regime_id="US_NPR_2_0",
        calculation_scope="FIRM",
        input_snapshot_id="snapshot-001",
        calculation_policy_id="policy-us-npr",
        engine_version="frtb-suite-0.1",
        code_version="abc123",
    )
    different_regime = canonical_run_identity_payload(
        as_of_date=date(2026, 6, 3),
        regime_id="EU_CRR3",
        calculation_scope="FIRM",
        input_snapshot_id="snapshot-001",
        calculation_policy_id="policy-eu-crr3",
        engine_version="frtb-suite-0.1",
        code_version="abc123",
    )
    different_snapshot = canonical_run_identity_payload(
        as_of_date=date(2026, 6, 3),
        regime_id="US_NPR_2_0",
        calculation_scope="FIRM",
        input_snapshot_id="snapshot-002",
        calculation_policy_id="policy-us-npr",
        engine_version="frtb-suite-0.1",
        code_version="abc123",
    )

    run_id = generate_run_id(payload)

    assert run_id == generate_run_id(same_payload)
    assert len(run_id) == 64
    assert run_id != generate_run_id(different_regime)
    assert run_id != generate_run_id(different_snapshot)


def test_run_group_identity_links_comparable_regime_runs() -> None:
    group_payload = canonical_run_group_identity_payload(
        as_of_date=date(2026, 6, 3),
        calculation_scope="FIRM",
        input_snapshot_id="snapshot-001",
        calculation_policy_group_id="global-policy-comparison",
        engine_version="frtb-suite-0.1",
        code_version="abc123",
        group_purpose="regime-comparison",
    )
    group_id = generate_run_group_id(group_payload)
    us_run = CalculationRun.from_identity(
        as_of_date=date(2026, 6, 3),
        regime_id="US_NPR_2_0",
        base_currency="USD",
        input_snapshot_id="snapshot-001",
        calculation_scope="FIRM",
        engine_version="frtb-suite-0.1",
        code_version="abc123",
        calculation_policy_id="policy-us-npr",
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
        run_group_id=group_id,
        run_group_identity_payload=group_payload,
    )
    eu_run = CalculationRun.from_identity(
        as_of_date=date(2026, 6, 3),
        regime_id="EU_CRR3",
        base_currency="USD",
        input_snapshot_id="snapshot-001",
        calculation_scope="FIRM",
        engine_version="frtb-suite-0.1",
        code_version="abc123",
        calculation_policy_id="policy-eu-crr3",
        created_at=datetime(2026, 6, 3, 12, 1, tzinfo=UTC),
        run_group_identity_payload=group_payload,
    )

    assert us_run.run_group_id == eu_run.run_group_id
    assert us_run.run_id != eu_run.run_id


def test_run_identity_rejects_mismatched_canonical_payload() -> None:
    payload = canonical_run_identity_payload(
        as_of_date=date(2026, 6, 3),
        regime_id="US_NPR_2_0",
        calculation_scope="FIRM",
        input_snapshot_id="snapshot-001",
        calculation_policy_id="policy-us-npr",
        engine_version="frtb-suite-0.1",
        code_version="abc123",
    )

    with pytest.raises(ResultStoreContractError, match="run_id does not match"):
        CalculationRun(
            run_id="not-the-generated-id",
            as_of_date=date(2026, 6, 3),
            regime_id="US_NPR_2_0",
            base_currency="USD",
            input_snapshot_id="snapshot-001",
            calculation_scope="FIRM",
            engine_version="frtb-suite-0.1",
            code_version="abc123",
            calculation_policy_id="policy-us-npr",
            created_at=datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
            identity_payload=payload,
        )


def test_status_event_requires_valid_transition_payload() -> None:
    event = RunStatusEvent.transition(
        run_id="run-001",
        from_status=None,
        to_status=RunStatus.CANDIDATE,
        event_time=datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
        actor="result-store",
        reason_code="RUN_COMMITTED",
        reason_text="Run committed",
    )

    assert len(event.event_id) == 64
    assert event.to_status is RunStatus.CANDIDATE


def test_default_hierarchy_generates_stable_leaf_ids_with_structured_payloads() -> None:
    definition = default_hierarchy_definition(
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
    )
    dimensions = {
        "firm_id": "Firm:Å",
        "legal_entity_id": "LE:London",
        "business_line_id": "Markets",
        "desk_id": "Rates",
        "portfolio_id": "Options",
        "book_id": "Book:Alpha",
    }
    equivalent_dimensions = {
        **dimensions,
        "firm_id": "Firm:A\u030a",
    }

    nodes = build_hierarchy_nodes(definition, dimensions)
    equivalent_nodes = build_hierarchy_nodes(definition, equivalent_dimensions)
    case_variant_nodes = build_hierarchy_nodes(
        definition,
        {**dimensions, "book_id": "book:alpha"},
    )

    assert [node.level_name for node in nodes] == [
        "firm",
        "legal_entity",
        "business_line",
        "desk",
        "portfolio",
        "book",
    ]
    assert nodes[-1].hierarchy_node_id == equivalent_nodes[-1].hierarchy_node_id
    assert nodes[-1].hierarchy_node_id != case_variant_nodes[-1].hierarchy_node_id
    assert nodes[-1].hierarchy_node_id.startswith("hierarchy:")
    assert nodes[-1].parent_hierarchy_node_id == nodes[-2].hierarchy_node_id


def test_client_defined_hierarchy_levels_keep_custom_leaf_semantics() -> None:
    definition = HierarchyDefinition(
        hierarchy_id="risk-management",
        hierarchy_version="2026-06",
        hierarchy_name="Risk management hierarchy",
        leaf_level="strategy",
        levels=(
            HierarchyLevel("region", "region_id", 0),
            HierarchyLevel("desk", "desk_id", 1),
            HierarchyLevel("strategy", "strategy_id", 2),
        ),
        created_at=datetime(2026, 6, 3, 12, 0, tzinfo=UTC),
    )

    nodes = build_hierarchy_nodes(
        definition,
        {
            "region_id": "EMEA",
            "desk_id": "Rates",
            "strategy_id": "Inflation:RV",
        },
    )

    assert definition.leaf_dimension == "strategy_id"
    assert [node.level_name for node in nodes] == ["region", "desk", "strategy"]
    assert nodes[-1].business_key == "Inflation:RV"


def test_capital_node_identity_registry_and_standard_edges_are_deterministic() -> None:
    run_id = "run-001"
    hierarchy_leaf_node_id = "hierarchy:leaf"
    hierarchy_leaf_path = (
        ("firm", "Firm:Å"),
        ("legal_entity", "LE:London"),
        ("business_line", "Markets"),
        ("desk", "Rates"),
        ("portfolio", "Options"),
        ("book", "Book:Alpha"),
    )
    specs = (
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
            label="SBM GIRR delta",
            sort_key=1,
        ),
        CapitalNodeSpec(
            node_family=CapitalNodeFamily.BUCKET,
            component=FrtbComponent.SBM,
            risk_class="GIRR",
            risk_measure="DELTA",
            bucket="USD:OIS",
            label="SBM GIRR USD OIS",
            regulatory_rule_id="MAR21.4",
            sort_key=2,
        ),
    )

    nodes, edges = build_standard_capital_graph(
        run_id=run_id,
        hierarchy_leaf_node_id=hierarchy_leaf_node_id,
        hierarchy_leaf_path=hierarchy_leaf_path,
        specs=specs,
    )
    repeated_nodes, repeated_edges = build_standard_capital_graph(
        run_id="run-002",
        hierarchy_leaf_node_id=hierarchy_leaf_node_id,
        hierarchy_leaf_path=hierarchy_leaf_path,
        specs=specs,
    )

    assert [node.node_type for node in nodes] == [
        NodeType.COMPONENT,
        NodeType.RISK_CLASS,
        NodeType.BUCKET,
    ]
    assert [node.node_id for node in nodes] == [node.node_id for node in repeated_nodes]
    assert [(edge.parent_node_id, edge.child_node_id) for edge in edges] == [
        (hierarchy_leaf_node_id, nodes[0].node_id),
        (nodes[0].node_id, nodes[1].node_id),
        (nodes[1].node_id, nodes[2].node_id),
    ]
    assert [edge.parent_node_id for edge in edges] == [
        edge.parent_node_id for edge in repeated_edges
    ]
    payload = capital_node_identity_payload(
        CapitalNodeFamily.BUCKET,
        hierarchy_leaf_path=hierarchy_leaf_path,
        component=FrtbComponent.SBM,
        risk_class="GIRR",
        risk_measure="DELTA",
        bucket="USD:OIS",
        calculation_branch=None,
    )
    assert set(payload) == {
        "node_family",
        "schema_version",
        "hierarchy_leaf_path",
        "component",
        "risk_class",
        "risk_measure",
        "bucket",
    }
    assert generate_capital_node_id(payload) == nodes[2].node_id


def test_issuer_edges_match_measured_bucket_parent() -> None:
    nodes, edges = build_standard_capital_graph(
        run_id="run-001",
        hierarchy_leaf_node_id="hierarchy:leaf",
        hierarchy_leaf_path=(("book", "Book:Alpha"),),
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
                label="SBM GIRR delta",
                sort_key=1,
            ),
            CapitalNodeSpec(
                node_family=CapitalNodeFamily.BUCKET,
                component=FrtbComponent.SBM,
                risk_class="GIRR",
                risk_measure="DELTA",
                bucket="USD:OIS",
                label="SBM GIRR USD OIS",
                sort_key=2,
            ),
            CapitalNodeSpec(
                node_family=CapitalNodeFamily.ISSUER,
                component=FrtbComponent.SBM,
                risk_class="GIRR",
                risk_measure="DELTA",
                bucket="USD:OIS",
                issuer_id="US-TREASURY",
                label="US Treasury",
                sort_key=3,
            ),
        ),
    )

    assert nodes[3].node_type is NodeType.ISSUER
    assert (nodes[2].node_id, nodes[3].node_id) in {
        (edge.parent_node_id, edge.child_node_id) for edge in edges
    }


def test_capital_node_ids_are_stable_across_hierarchy_versions() -> None:
    created_at = datetime(2026, 6, 3, 12, 0, tzinfo=UTC)
    v1 = default_hierarchy_definition(created_at=created_at)
    v2 = HierarchyDefinition(
        hierarchy_id=v1.hierarchy_id,
        hierarchy_version="2",
        hierarchy_name=v1.hierarchy_name,
        leaf_level=v1.leaf_level,
        levels=v1.levels,
        created_at=created_at,
    )
    dimensions = {
        "firm_id": "Firm",
        "legal_entity_id": "LE",
        "business_line_id": "Markets",
        "desk_id": "Rates",
        "portfolio_id": "Options",
        "book_id": "Book:USD",
    }
    v1_leaf = build_hierarchy_nodes(v1, dimensions)[-1]
    v2_leaf = build_hierarchy_nodes(v2, dimensions)[-1]
    spec = CapitalNodeSpec(
        node_family=CapitalNodeFamily.COMPONENT,
        component=FrtbComponent.SBM,
        label="SBM",
    )

    v1_nodes, _ = build_standard_capital_graph(
        run_id="run-v1",
        hierarchy_leaf_node_id=v1_leaf.hierarchy_node_id,
        hierarchy_leaf_path=v1_leaf.path,
        specs=(spec,),
    )
    v2_nodes, _ = build_standard_capital_graph(
        run_id="run-v2",
        hierarchy_leaf_node_id=v2_leaf.hierarchy_node_id,
        hierarchy_leaf_path=v2_leaf.path,
        specs=(spec,),
    )

    assert v1_leaf.hierarchy_node_id != v2_leaf.hierarchy_node_id
    assert v1_nodes[0].node_id == v2_nodes[0].node_id


def test_capital_graph_rejects_custom_frtb_edges() -> None:
    with pytest.raises(ResultStoreContractError, match="custom FRTB capital edges"):
        build_standard_capital_graph(
            run_id="run-001",
            hierarchy_leaf_node_id="hierarchy:leaf",
            hierarchy_leaf_path=(("book", "Book"),),
            specs=(
                CapitalNodeSpec(
                    node_family=CapitalNodeFamily.COMPONENT,
                    component=FrtbComponent.SBM,
                    label="SBM",
                ),
            ),
            custom_edges=(
                CapitalEdge(
                    run_id="run-001",
                    parent_node_id="custom-parent",
                    child_node_id="custom-child",
                ),
            ),
        )


def test_capital_node_identity_rejects_missing_required_dimensions() -> None:
    with pytest.raises(ResultStoreContractError, match="missing capital node identity field"):
        capital_node_identity_payload(
            CapitalNodeFamily.BUCKET,
            hierarchy_leaf_path=(("book", "Book"),),
            component=FrtbComponent.SBM,
            risk_class="GIRR",
        )


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


def test_measure_names_and_attribution_targets_fail_closed() -> None:
    run = _run()
    node = CapitalNode(
        run_id=run.run_id,
        node_id="total",
        node_type=NodeType.ROOT,
        component=FrtbComponent.TOP_OF_HOUSE,
        label="Total capital",
    )

    CapitalMeasure(
        run_id=run.run_id,
        node_id=node.node_id,
        measure_name="capital",
        amount=42.0,
        currency="USD",
    )
    with pytest.raises(ResultStoreContractError, match="measure_name must be one of"):
        CapitalMeasure(
            run_id=run.run_id,
            node_id=node.node_id,
            measure_name="ad_hoc_total",
            amount=42.0,
            currency="USD",
        )
    with pytest.raises(ResultStoreContractError, match="source_level must be one of"):
        CapitalAttributionRecord(
            run_id=run.run_id,
            node_id=node.node_id,
            contribution_id="bad-target",
            source_id="target-001",
            source_level="unregistered",
            category="CAPITAL",
            base_amount=1.0,
            method="RESIDUAL",
        )


def test_artifact_schema_registry_and_expectation_contracts() -> None:
    schema = artifact_schema_for("ima.pnl_vector.v1")
    expectation = RequiredArtifactExpectation(
        component="IMA",
        artifact_type=ArtifactType.IMA_TAIL_OBSERVATION,
        trigger_name="IMA_ES_TAIL_EVIDENCE",
        required=True,
        reason="ES tail evidence declared by writer",
    )
    request = ArtifactWriteRequest(
        artifact_id_hint="ima-pnl",
        artifact_type=ArtifactType.IMA_PNL_VECTOR,
        component="IMA",
        schema_id=schema.schema_id,
        chunks=(),
        partition_values={
            "desk_id": "rates",
            "portfolio_id": "rates-options",
            "book_id": "rates-core",
        },
        conditional_expectations=(expectation,),
    )

    assert schema.schema_fingerprint == artifact_schema_for(schema.schema_id).schema_fingerprint
    assert schema.arrow_schema.names == [
        "run_id",
        "desk_id",
        "portfolio_id",
        "book_id",
        "position_id",
        "risk_factor_id",
        "risk_factor_set_id",
        "scenario_id",
        "observation_date",
        "liquidity_horizon",
        "pnl_amount",
        "currency",
        "tail_flag",
        "source_row_id",
    ]
    assert request.conditional_expectations == (expectation,)
    with pytest.raises(ResultStoreContractError, match="unknown artifact schema"):
        artifact_schema_for("missing.schema")


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
