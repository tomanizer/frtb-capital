"""Capital Navigator fixture bundle for result-store integration tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from frtb_common import CapitalContribution
from frtb_result_store import (
    ArtifactRef,
    CalculationRun,
    CapitalAttributionRecord,
    CapitalEdge,
    CapitalMeasure,
    CapitalNode,
    InputSnapshotManifest,
    LineageRef,
    MovementResult,
    ResultBundle,
    ResultEvent,
)

from fixtures.capital_navigator_drillthrough import write_capital_navigator_artifacts
from fixtures.capital_navigator_record_specs import (
    NAVIGATOR_ARTIFACT_SPECS,
    NAVIGATOR_ATTRIBUTION_SPECS,
    NAVIGATOR_INPUT_MANIFEST_SPECS,
    NAVIGATOR_LINEAGE_SPECS,
    NAVIGATOR_RESIDUAL_ATTRIBUTION_SPEC,
    NAVIGATOR_UNSUPPORTED_ATTRIBUTION_SPECS,
)
from fixtures.capital_navigator_tree_specs import (
    NAVIGATOR_EDGE_SPECS,
    NAVIGATOR_MEASURE_SPECS,
    NAVIGATOR_NODE_SPECS,
)
from fixtures.result_store_bundle import run_with_id

_NAVIGATOR_RUN_ID = "frtb/capital-navigator/2026-06-03/us-npr"
_NAVIGATOR_BASELINE_RUN_ID = "frtb/capital-navigator/2026-06-02/us-npr"


def capital_navigator_bundle(
    run: CalculationRun | None = None,
    *,
    baseline_run_id: str = _NAVIGATOR_BASELINE_RUN_ID,
    artifact_root: Path | None = None,
) -> ResultBundle:
    """Build a complete synthetic suite result for Capital Navigator tests."""

    if run is None:
        run = run_with_id(_NAVIGATOR_RUN_ID)
    local_artifacts = write_capital_navigator_artifacts(run.run_id, artifact_root)
    return ResultBundle(
        run=run,
        nodes=_capital_navigator_nodes(run),
        edges=_capital_navigator_edges(run),
        measures=_capital_navigator_measures(run),
        artifacts=_capital_navigator_artifacts(run, local_artifacts),
        input_manifests=_capital_navigator_input_manifests(run),
        lineage=_capital_navigator_lineage(run),
        attributions=_capital_navigator_attributions(run),
        movement_results=_capital_navigator_movements(run, baseline_run_id),
        events=(_capital_navigator_warning(run),),
    )


def _capital_navigator_nodes(run: CalculationRun) -> tuple[CapitalNode, ...]:
    return tuple(_capital_navigator_node(run.run_id, *spec) for spec in NAVIGATOR_NODE_SPECS)


def _capital_navigator_node(
    run_id: str,
    node_id: str,
    node_type: str,
    component: str,
    label: str,
    sort_key: int,
    regulatory_rule_id: str,
    extra: dict[str, str],
) -> CapitalNode:
    return CapitalNode(
        run_id=run_id,
        node_id=node_id,
        node_type=node_type,
        component=component,
        label=label,
        regulatory_rule_id=regulatory_rule_id,
        sort_key=sort_key,
        **extra,
    )


def _capital_navigator_edges(run: CalculationRun) -> tuple[CapitalEdge, ...]:
    return tuple(
        CapitalEdge(
            run_id=run.run_id,
            parent_node_id=parent,
            child_node_id=child,
            edge_type=edge_type,
            sort_key=sort_key,
        )
        for sort_key, (parent, child, edge_type) in enumerate(NAVIGATOR_EDGE_SPECS, start=1)
    )


def _capital_navigator_measures(run: CalculationRun) -> tuple[CapitalMeasure, ...]:
    return tuple(
        CapitalMeasure(
            run_id=run.run_id,
            node_id=node_id,
            measure_name="capital",
            amount=amount,
            currency="USD",
            regulatory_rule_id=rule_id,
            citations=(rule_id,),
        )
        for node_id, amount, rule_id in NAVIGATOR_MEASURE_SPECS
    )


def _capital_navigator_artifacts(
    run: CalculationRun,
    local_artifacts: dict[str, tuple[str, int]],
) -> tuple[ArtifactRef, ...]:
    return tuple(
        ArtifactRef(
            run_id=run.run_id,
            artifact_id=artifact_id,
            component=component,
            artifact_type=artifact_type,
            uri=local_artifacts.get(
                artifact_id,
                (f"s3://frtb-results/capital-navigator/{run.run_id}/{artifact_id}.parquet", 0),
            )[0],
            format="parquet",
            row_count=local_artifacts.get(artifact_id, ("", row_count))[1],
            partition_keys=partition_keys,
        )
        for (
            artifact_id,
            component,
            artifact_type,
            row_count,
            partition_keys,
        ) in NAVIGATOR_ARTIFACT_SPECS
    )


def _capital_navigator_input_manifests(run: CalculationRun) -> tuple[InputSnapshotManifest, ...]:
    return tuple(
        InputSnapshotManifest(
            run_id=run.run_id,
            input_snapshot_id=f"{run.input_snapshot_id}:{handoff_key}",
            input_snapshot_hash=f"hash-{handoff_key}",
            as_of_date=run.as_of_date,
            source_system=source_system,
            handoff_key=handoff_key,
            row_count=row_count,
            accepted_row_count=row_count,
            rejected_row_count=0,
            source_uri=f"s3://frtb-inputs/capital-navigator/{handoff_key}.parquet",
            source_hash=f"source-hash-{handoff_key}",
            schema_fingerprint=f"schema-{handoff_key}-v1",
        )
        for handoff_key, source_system, row_count in NAVIGATOR_INPUT_MANIFEST_SPECS
    )


def _capital_navigator_lineage(run: CalculationRun) -> tuple[LineageRef, ...]:
    return tuple(
        LineageRef(
            run_id=run.run_id,
            result_id=result_id,
            source_type=source_type,
            source_id=run.input_snapshot_id if not source_id else source_id,
            source_hash=source_hash,
        )
        for result_id, source_type, source_id, source_hash in NAVIGATOR_LINEAGE_SPECS
    )


def _capital_navigator_attributions(
    run: CalculationRun,
) -> tuple[CapitalAttributionRecord, ...]:
    records = tuple(_capital_navigator_direct_attributions(run))
    unsupported = tuple(_capital_navigator_unsupported_attributions(run))
    residual = _capital_navigator_residual_attribution(run)
    return (*records, *unsupported, residual)


def _capital_navigator_direct_attributions(
    run: CalculationRun,
) -> tuple[CapitalAttributionRecord, ...]:
    return tuple(
        _capital_navigator_attribution(
            run=run,
            contribution_id=contribution_id,
            node_id=node_id,
            source_id=source_id,
            source_level=source_level,
            category=category,
            base_amount=base_amount,
            method=method,
            contribution=base_amount,
            residual=0.0,
            artifact_id=artifact_id,
            reason=_attribution_reason(method, category),
        )
        for (
            contribution_id,
            node_id,
            source_id,
            source_level,
            category,
            base_amount,
            method,
            artifact_id,
        ) in NAVIGATOR_ATTRIBUTION_SPECS
    )


def _capital_navigator_unsupported_attributions(
    run: CalculationRun,
) -> tuple[CapitalAttributionRecord, ...]:
    return tuple(
        _capital_navigator_attribution(
            run=run,
            contribution_id=contribution_id,
            node_id=node_id,
            source_id=source_id,
            source_level=source_level,
            category=category,
            base_amount=base_amount,
            method="UNSUPPORTED",
            contribution=None,
            residual=0.0,
            artifact_id=artifact_id,
            reason=reason,
        )
        for (
            contribution_id,
            node_id,
            source_id,
            source_level,
            category,
            base_amount,
            artifact_id,
            reason,
        ) in NAVIGATOR_UNSUPPORTED_ATTRIBUTION_SPECS
    )


def _capital_navigator_residual_attribution(run: CalculationRun) -> CapitalAttributionRecord:
    (
        contribution_id,
        node_id,
        source_level,
        category,
        base_amount,
        artifact_id,
        reason,
    ) = NAVIGATOR_RESIDUAL_ATTRIBUTION_SPEC
    return _capital_navigator_attribution(
        run=run,
        contribution_id=contribution_id,
        node_id=node_id,
        source_id=run.run_id,
        source_level=source_level,
        category=category,
        base_amount=base_amount,
        method="RESIDUAL",
        contribution=None,
        residual=0.0,
        artifact_id=artifact_id,
        reason=reason,
    )


def _capital_navigator_attribution(
    *,
    run: CalculationRun,
    contribution_id: str,
    node_id: str,
    source_id: str,
    source_level: str,
    category: str,
    base_amount: float,
    method: str,
    contribution: float | None,
    residual: float,
    artifact_id: str,
    reason: str,
) -> CapitalAttributionRecord:
    marginal_multiplier = 1.0 if method == "ANALYTICAL_EULER" else None
    return CapitalAttributionRecord.from_contribution(
        run_id=run.run_id,
        node_id=node_id,
        contribution=CapitalContribution(
            contribution_id=contribution_id,
            source_id=source_id,
            source_level=source_level,
            bucket_key=None,
            category=category,
            base_amount=base_amount,
            marginal_multiplier=marginal_multiplier,
            contribution=contribution,
            method=method,
            residual=residual,
            reason=reason,
        ),
        artifact_id=artifact_id,
    )


def _capital_navigator_movements(
    run: CalculationRun,
    baseline_run_id: str,
) -> tuple[MovementResult, ...]:
    return (
        MovementResult(
            run_id=run.run_id,
            baseline_run_id=baseline_run_id,
            movement_id="total-capital-day-over-day",
            node_id="total",
            movement_type="DAY_OVER_DAY",
            from_amount=204.0,
            to_amount=210.0,
            delta_amount=6.0,
            base_currency="USD",
            driver_type="COMPONENT",
            driver_id="SBM",
            explanation="Synthetic SBM bucket increase drives most day-over-day movement.",
            attribution_method="RESIDUAL",
            artifact_id="navigator-suite-attribution",
        ),
    )


def _capital_navigator_warning(run: CalculationRun) -> ResultEvent:
    return ResultEvent(
        event_id="capital-navigator-warning-rrao",
        run_id=run.run_id,
        event_time=datetime(2026, 6, 3, 12, 3, tzinfo=UTC),
        severity="WARNING",
        event_type="CALCULATION_WARNING",
        message="Synthetic RRAO line retained for navigator unsupported-branch display.",
        component="RRAO",
    )


def _attribution_reason(method: str, category: str) -> str:
    if method == "ANALYTICAL_EULER":
        return ""
    return f"Synthetic {category} standalone explain amount."
