"""Capital Navigator fixture bundle for result-store integration tests."""

from __future__ import annotations

from datetime import UTC, datetime

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

from fixtures.result_store_bundle import run_with_id

_NAVIGATOR_RUN_ID = "frtb/capital-navigator/2026-06-03/us-npr"
_NAVIGATOR_BASELINE_RUN_ID = "frtb/capital-navigator/2026-06-02/us-npr"

_IMA_DESK = {
    "desk_id": "rates",
    "portfolio_id": "rates-options",
    "book_id": "rates-core",
    "calculation_branch": "IMA_ES_PLUS_SES",
}
_DRC_ALPHA = {
    "risk_class": "NON_SECURITISATION",
    "bucket": "corporate",
    "issuer_id": "issuer-alpha",
}
_DRC_BETA = {
    "risk_class": "NON_SECURITISATION",
    "bucket": "sovereign",
    "issuer_id": "issuer-beta",
}
_CVA_BANK_A = {
    "counterparty_id": "counterparty-bank-a",
    "calculation_branch": "BA_CVA_REDUCED",
}
_CVA_FUND_B = {
    "counterparty_id": "counterparty-fund-b",
    "calculation_branch": "SA_CVA",
}

_NAVIGATOR_NODE_SPECS = (
    ("total", "ROOT", "TOP_OF_HOUSE", "Total capital", 0, "US_NPR_325.201", {}),
    (
        "ima",
        "COMPONENT",
        "IMA",
        "IMA",
        10,
        "US_NPR_325.207",
        {"calculation_branch": "IMA_ES_PLUS_SES"},
    ),
    ("ima-rates-desk", "DESK", "IMA", "Rates desk", 11, "US_NPR_325.207", _IMA_DESK),
    ("sa", "COMPONENT", "SA", "Standardised Approach", 20, "US_NPR_325.204", {}),
    ("sbm", "COMPONENT", "SBM", "SBM", 21, "US_NPR_325.204", {}),
    (
        "sbm-girr-usd",
        "BUCKET",
        "SBM",
        "GIRR USD",
        22,
        "MAR21.4",
        {"risk_class": "GIRR", "bucket": "USD"},
    ),
    (
        "sbm-csr-ig",
        "BUCKET",
        "SBM",
        "CSR investment grade",
        23,
        "MAR21.4",
        {"risk_class": "CSR_NON_SEC", "bucket": "IG"},
    ),
    ("drc", "COMPONENT", "DRC", "DRC", 30, "MAR22.1", {}),
    ("drc-issuer-alpha", "ISSUER", "DRC", "Issuer Alpha", 31, "MAR22.1", _DRC_ALPHA),
    ("drc-issuer-beta", "ISSUER", "DRC", "Issuer Beta", 32, "MAR22.1", _DRC_BETA),
    ("rrao", "COMPONENT", "RRAO", "RRAO", 40, "MAR23.1", {}),
    (
        "rrao-exotic-underlier",
        "MEASURE_BRANCH",
        "RRAO",
        "Exotic underlier",
        41,
        "MAR23.1",
        {"calculation_branch": "EXOTIC_UNDERLIER"},
    ),
    (
        "rrao-cliff-risk",
        "MEASURE_BRANCH",
        "RRAO",
        "Cliff risk",
        42,
        "MAR23.1",
        {"calculation_branch": "CLIFF_RISK"},
    ),
    ("cva", "COMPONENT", "CVA", "CVA", 50, "MAR50.1", {}),
    ("cva-bank-a", "COUNTERPARTY", "CVA", "Bank A", 51, "MAR50.13", _CVA_BANK_A),
    ("cva-fund-b", "COUNTERPARTY", "CVA", "Fund B", 52, "MAR50.13", _CVA_FUND_B),
)

_NAVIGATOR_EDGE_SPECS = (
    ("total", "ima", "AGGREGATES"),
    ("ima", "ima-rates-desk", "DRILLDOWN"),
    ("total", "sa", "AGGREGATES"),
    ("sa", "sbm", "AGGREGATES"),
    ("sbm", "sbm-girr-usd", "DRILLDOWN"),
    ("sbm", "sbm-csr-ig", "DRILLDOWN"),
    ("sa", "drc", "AGGREGATES"),
    ("drc", "drc-issuer-alpha", "DRILLDOWN"),
    ("drc", "drc-issuer-beta", "DRILLDOWN"),
    ("sa", "rrao", "AGGREGATES"),
    ("rrao", "rrao-exotic-underlier", "DRILLDOWN"),
    ("rrao", "rrao-cliff-risk", "DRILLDOWN"),
    ("total", "cva", "AGGREGATES"),
    ("cva", "cva-bank-a", "DRILLDOWN"),
    ("cva", "cva-fund-b", "DRILLDOWN"),
)

_NAVIGATOR_MEASURE_SPECS = (
    ("total", 150.0, "US_NPR_325.201"),
    ("sa", 78.0, "US_NPR_325.204"),
    ("ima-rates-desk", 42.0, "US_NPR_325.207"),
    ("sbm-girr-usd", 35.0, "MAR21.4"),
    ("sbm-csr-ig", 15.0, "MAR21.4"),
    ("drc-issuer-alpha", 18.0, "MAR22.1"),
    ("drc-issuer-beta", 4.0, "MAR22.1"),
    ("rrao-exotic-underlier", 4.0, "MAR23.1"),
    ("rrao-cliff-risk", 2.0, "MAR23.1"),
    ("cva-bank-a", 20.0, "MAR50.13"),
    ("cva-fund-b", 10.0, "MAR50.13"),
)

_NAVIGATOR_ARTIFACT_SPECS = (
    (
        "navigator-ima-pnl-vector",
        "IMA",
        "IMA_PNL_VECTOR",
        6,
        ("desk_id", "portfolio_id", "book_id"),
    ),
    ("navigator-sbm-sensitivities", "SBM", "SBM_SENSITIVITY_TABLE", 4, ()),
    ("navigator-drc-jtd", "DRC", "DRC_JTD_TABLE", 3, ()),
    ("navigator-rrao-exposures", "RRAO", "RRAO_EXPOSURE_TABLE", 2, ()),
    ("navigator-cva-exposures", "CVA", "CVA_EXPOSURE_TABLE", 4, ()),
    ("navigator-suite-attribution", "TOP_OF_HOUSE", "ATTRIBUTION_VECTOR", 11, ()),
)

_NAVIGATOR_INPUT_MANIFEST_SPECS = (
    ("ima-pnl", "risk-engine-ima", 6),
    ("sbm-sensitivities", "risk-engine-sbm", 4),
    ("drc-positions", "risk-engine-drc", 3),
    ("rrao-positions", "risk-engine-rrao", 2),
    ("cva-exposures", "risk-engine-cva", 4),
)

_NAVIGATOR_LINEAGE_SPECS = (
    ("total", "input_snapshot", "", "suite-input-hash"),
    ("ima-rates-desk", "artifact", "navigator-ima-pnl-vector", None),
    ("sbm-girr-usd", "artifact", "navigator-sbm-sensitivities", None),
    ("drc-issuer-alpha", "artifact", "navigator-drc-jtd", None),
    ("rrao-exotic-underlier", "artifact", "navigator-rrao-exposures", None),
    ("cva-bank-a", "artifact", "navigator-cva-exposures", None),
)

_NAVIGATOR_ATTRIBUTION_SPECS = (
    (
        "ima-desk-rates",
        "ima-rates-desk",
        "desk-rates",
        "DESK",
        "IMA_DESK",
        42.0,
        "STANDALONE",
        "navigator-ima-pnl-vector",
    ),
    (
        "sbm-girr-usd-5y",
        "sbm-girr-usd",
        "sensitivity-girr-usd-5y",
        "SENSITIVITY",
        "SBM_DELTA",
        35.0,
        "ANALYTICAL_EULER",
        "navigator-sbm-sensitivities",
    ),
    (
        "sbm-csr-ig-spread",
        "sbm-csr-ig",
        "sensitivity-csr-ig-a",
        "SENSITIVITY",
        "SBM_DELTA",
        15.0,
        "ANALYTICAL_EULER",
        "navigator-sbm-sensitivities",
    ),
    (
        "drc-issuer-alpha-net-jtd",
        "drc-issuer-alpha",
        "issuer-alpha",
        "ISSUER",
        "DRC_NET_JTD",
        18.0,
        "STANDALONE",
        "navigator-drc-jtd",
    ),
    (
        "drc-issuer-beta-net-jtd",
        "drc-issuer-beta",
        "issuer-beta",
        "ISSUER",
        "DRC_NET_JTD",
        4.0,
        "STANDALONE",
        "navigator-drc-jtd",
    ),
    (
        "rrao-exotic-underlier-line",
        "rrao-exotic-underlier",
        "rrao-line-exotic-001",
        "POSITION",
        "RRAO_LINE",
        4.0,
        "STANDALONE",
        "navigator-rrao-exposures",
    ),
    (
        "rrao-cliff-risk-line",
        "rrao-cliff-risk",
        "rrao-line-cliff-001",
        "POSITION",
        "RRAO_LINE",
        2.0,
        "STANDALONE",
        "navigator-rrao-exposures",
    ),
    (
        "cva-bank-a-counterparty",
        "cva-bank-a",
        "counterparty-bank-a",
        "COUNTERPARTY",
        "CVA_COUNTERPARTY",
        20.0,
        "STANDALONE",
        "navigator-cva-exposures",
    ),
    (
        "cva-fund-b-counterparty",
        "cva-fund-b",
        "counterparty-fund-b",
        "COUNTERPARTY",
        "CVA_COUNTERPARTY",
        10.0,
        "STANDALONE",
        "navigator-cva-exposures",
    ),
)


def capital_navigator_bundle(
    run: CalculationRun | None = None,
    *,
    baseline_run_id: str = _NAVIGATOR_BASELINE_RUN_ID,
) -> ResultBundle:
    """Build a complete synthetic suite result for Capital Navigator tests."""

    if run is None:
        run = run_with_id(_NAVIGATOR_RUN_ID)
    return ResultBundle(
        run=run,
        nodes=_capital_navigator_nodes(run),
        edges=_capital_navigator_edges(run),
        measures=_capital_navigator_measures(run),
        artifacts=_capital_navigator_artifacts(run),
        input_manifests=_capital_navigator_input_manifests(run),
        lineage=_capital_navigator_lineage(run),
        attributions=_capital_navigator_attributions(run),
        movement_results=_capital_navigator_movements(run, baseline_run_id),
        events=(_capital_navigator_warning(run),),
    )


def _capital_navigator_nodes(run: CalculationRun) -> tuple[CapitalNode, ...]:
    return tuple(_capital_navigator_node(run.run_id, *spec) for spec in _NAVIGATOR_NODE_SPECS)


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
        for sort_key, (parent, child, edge_type) in enumerate(_NAVIGATOR_EDGE_SPECS, start=1)
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
        for node_id, amount, rule_id in _NAVIGATOR_MEASURE_SPECS
    )


def _capital_navigator_artifacts(run: CalculationRun) -> tuple[ArtifactRef, ...]:
    return tuple(
        ArtifactRef(
            run_id=run.run_id,
            artifact_id=artifact_id,
            component=component,
            artifact_type=artifact_type,
            uri=f"s3://frtb-results/capital-navigator/{run.run_id}/{artifact_id}.parquet",
            format="parquet",
            row_count=row_count,
            partition_keys=partition_keys,
        )
        for (
            artifact_id,
            component,
            artifact_type,
            row_count,
            partition_keys,
        ) in _NAVIGATOR_ARTIFACT_SPECS
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
        for handoff_key, source_system, row_count in _NAVIGATOR_INPUT_MANIFEST_SPECS
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
        for result_id, source_type, source_id, source_hash in _NAVIGATOR_LINEAGE_SPECS
    )


def _capital_navigator_attributions(
    run: CalculationRun,
) -> tuple[CapitalAttributionRecord, ...]:
    records = tuple(
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
        ) in _NAVIGATOR_ATTRIBUTION_SPECS
    )
    return (
        *records,
        _capital_navigator_attribution(
            run=run,
            contribution_id="cva-unsupported-ba-reduced-sqrt",
            node_id="cva",
            source_id="ba-cva-reduced-portfolio-sqrt",
            source_level="UNSUPPORTED_BRANCH",
            category="CVA_UNSUPPORTED_BRANCH",
            base_amount=0.0,
            method="UNSUPPORTED",
            contribution=None,
            residual=0.0,
            artifact_id="navigator-cva-exposures",
            reason="Reduced BA-CVA portfolio square-root aggregation is not exact Euler.",
        ),
        _capital_navigator_attribution(
            run=run,
            contribution_id="suite-residual-zero",
            node_id="total",
            source_id=run.run_id,
            source_level="RESIDUAL_BRANCH",
            category="SUITE_RESIDUAL",
            base_amount=150.0,
            method="RESIDUAL",
            contribution=None,
            residual=0.0,
            artifact_id="navigator-suite-attribution",
            reason="Suite residual retained for audit; component explain rows reconcile.",
        ),
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
            from_amount=144.0,
            to_amount=150.0,
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
