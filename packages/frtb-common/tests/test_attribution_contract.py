"""Suite-wide attribution and impact contract tests.

All tests in this module import only from ``frtb-common`` and use synthetic
data.  No capital-component package is imported.  This ensures the contract
can be verified without coupling to any component's internals.

See ADR 0038.
"""

from __future__ import annotations

import pytest
from frtb_common.attribution import (
    AttributionMethod,
    CapitalContribution,
    ReconciliationStatus,
)
from frtb_common.contribution_bundle import ComponentContributionBundle
from frtb_common.impact import CapitalImpact, ImpactMethod

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EULER_TOL = 1e-6


def _make_euler(
    contribution_id: str = "c1",
    source_id: str = "pos-1",
    base_amount: float = 100.0,
    marginal_multiplier: float = 1.5,
    contribution: float = 150.0,
    residual: float = 0.0,
    reconciliation_status: ReconciliationStatus = ReconciliationStatus.RECONCILED,
) -> CapitalContribution:
    return CapitalContribution(
        contribution_id=contribution_id,
        source_id=source_id,
        source_level="position",
        bucket_key="bucket-A",
        category="GIRR",
        base_amount=base_amount,
        marginal_multiplier=marginal_multiplier,
        contribution=contribution,
        method=AttributionMethod.ANALYTICAL_EULER,
        residual=residual,
        reconciliation_status=reconciliation_status,
    )


def _make_residual(
    contribution_id: str = "r1",
    residual: float = 10.0,
) -> CapitalContribution:
    return CapitalContribution(
        contribution_id=contribution_id,
        source_id="residual",
        source_level="bucket",
        bucket_key="bucket-A",
        category="GIRR",
        base_amount=0.0,
        marginal_multiplier=None,
        contribution=None,
        method=AttributionMethod.RESIDUAL,
        residual=residual,
        reconciliation_status=ReconciliationStatus.PARTIAL_RESIDUAL,
    )


# ---------------------------------------------------------------------------
# 1. ANALYTICAL_EULER enforcement
# ---------------------------------------------------------------------------


def test_euler_requires_marginal_multiplier() -> None:
    with pytest.raises(ValueError, match="marginal_multiplier must not be None"):
        CapitalContribution(
            contribution_id="c1",
            source_id="pos-1",
            source_level="position",
            bucket_key=None,
            category="GIRR",
            base_amount=100.0,
            marginal_multiplier=None,
            contribution=150.0,
            method=AttributionMethod.ANALYTICAL_EULER,
        )


def test_euler_requires_contribution() -> None:
    with pytest.raises(ValueError, match="contribution must not be None"):
        CapitalContribution(
            contribution_id="c1",
            source_id="pos-1",
            source_level="position",
            bucket_key=None,
            category="GIRR",
            base_amount=100.0,
            marginal_multiplier=1.5,
            contribution=None,
            method=AttributionMethod.ANALYTICAL_EULER,
        )


# ---------------------------------------------------------------------------
# 2. Projection from a mock package-local structure
# ---------------------------------------------------------------------------


def test_projection_from_package_local_structure() -> None:
    """A mock package-local dict can be projected to CapitalContribution."""

    local_record = {
        "id": "pos-42",
        "notional": 500.0,
        "risk_weight": 0.12,
        "capital_contribution": 60.0,
        "method": "ANALYTICAL_EULER",
    }

    projected = CapitalContribution(
        contribution_id=f"proj-{local_record['id']}",
        source_id=local_record["id"],
        source_level="position",
        bucket_key=None,
        category="GIRR",
        base_amount=local_record["notional"],
        marginal_multiplier=local_record["risk_weight"],
        contribution=local_record["capital_contribution"],
        method=local_record["method"],
        reconciliation_status=ReconciliationStatus.RECONCILED,
    )

    assert projected.source_id == "pos-42"
    assert projected.method == AttributionMethod.ANALYTICAL_EULER
    assert projected.contribution == 60.0
    assert projected.reconciliation_status == ReconciliationStatus.RECONCILED


# ---------------------------------------------------------------------------
# 3. Reconciliation invariant
# ---------------------------------------------------------------------------


def test_reconciliation_invariant_exact() -> None:
    """contributions + residuals must equal capital_total."""

    c1 = _make_euler("c1", contribution=120.0)
    c2 = _make_euler("c2", contribution=30.0)
    capital_total = 150.0

    total = sum((r.contribution or 0.0) + r.residual for r in (c1, c2))
    assert abs(total - capital_total) <= _EULER_TOL


def test_reconciliation_invariant_with_residual() -> None:
    """Contributions + explicit residual must equal capital_total."""

    c1 = _make_euler("c1", contribution=140.0)
    r1 = _make_residual("r1", residual=10.0)
    capital_total = 150.0

    total = sum((r.contribution or 0.0) + r.residual for r in (c1, r1))
    assert abs(total - capital_total) <= _EULER_TOL


# ---------------------------------------------------------------------------
# 4. ReconciliationStatus coercion
# ---------------------------------------------------------------------------


def test_reconciliation_status_coercion_from_string() -> None:
    c = CapitalContribution(
        contribution_id="c1",
        source_id="pos-1",
        source_level="position",
        bucket_key=None,
        category="GIRR",
        base_amount=100.0,
        marginal_multiplier=1.0,
        contribution=100.0,
        method="ANALYTICAL_EULER",
        reconciliation_status="RECONCILED",
    )
    assert c.reconciliation_status == ReconciliationStatus.RECONCILED


def test_reconciliation_status_invalid_string() -> None:
    with pytest.raises(ValueError, match="reconciliation_status must be one of"):
        CapitalContribution(
            contribution_id="c1",
            source_id="pos-1",
            source_level="position",
            bucket_key=None,
            category="GIRR",
            base_amount=100.0,
            marginal_multiplier=1.0,
            contribution=100.0,
            method="ANALYTICAL_EULER",
            reconciliation_status="INVALID",
        )


# ---------------------------------------------------------------------------
# 5. CapitalImpact contract
# ---------------------------------------------------------------------------


def test_capital_impact_delta_equals_difference() -> None:
    impact = CapitalImpact(
        baseline_run_id="run-A",
        candidate_run_id="run-B",
        component="frtb_sbm",
        baseline_total=1000.0,
        candidate_total=1050.0,
        delta=50.0,
        method=ImpactMethod.FINITE_DIFFERENCE,
        baseline_input_hash="abc123",
        candidate_input_hash="def456",
    )
    assert impact.delta == pytest.approx(50.0)


def test_capital_impact_delta_mismatch_raises() -> None:
    with pytest.raises(ValueError, match=r"delta.*does not equal"):
        CapitalImpact(
            baseline_run_id="run-A",
            candidate_run_id="run-B",
            component="frtb_sbm",
            baseline_total=1000.0,
            candidate_total=1050.0,
            delta=999.0,  # wrong
            method=ImpactMethod.FINITE_DIFFERENCE,
            baseline_input_hash="abc123",
            candidate_input_hash="def456",
        )


def test_capital_impact_delta_tolerance_scales_with_notional() -> None:
    impact = CapitalImpact(
        baseline_run_id="run-A",
        candidate_run_id="run-B",
        component="frtb_sbm",
        baseline_total=1_000_000_000.0,
        candidate_total=1_000_000_050.0,
        delta=50.0001,
        method=ImpactMethod.FINITE_DIFFERENCE,
        baseline_input_hash="abc123",
        candidate_input_hash="def456",
    )

    assert impact.delta == pytest.approx(50.0001)


def test_capital_impact_method_coercion() -> None:
    impact = CapitalImpact(
        baseline_run_id="run-A",
        candidate_run_id="run-B",
        component="frtb_cva",
        baseline_total=200.0,
        candidate_total=180.0,
        delta=-20.0,
        method="FINITE_DIFFERENCE",
        baseline_input_hash="h1",
        candidate_input_hash="h2",
    )
    assert impact.method == ImpactMethod.FINITE_DIFFERENCE


def test_capital_impact_as_dict() -> None:
    impact = CapitalImpact(
        baseline_run_id="run-A",
        candidate_run_id="run-B",
        component="frtb_drc",
        baseline_total=300.0,
        candidate_total=310.0,
        delta=10.0,
        method=ImpactMethod.FINITE_DIFFERENCE,
        baseline_input_hash="h1",
        candidate_input_hash="h2",
        notes=("note-1", "note-2"),
    )
    d = impact.as_dict()
    assert list(d) == [
        "baseline_run_id",
        "candidate_run_id",
        "component",
        "baseline_total",
        "candidate_total",
        "delta",
        "method",
        "baseline_input_hash",
        "candidate_input_hash",
        "baseline_profile_hash",
        "candidate_profile_hash",
        "notes",
    ]
    assert d["delta"] == 10.0
    assert d["method"] == "FINITE_DIFFERENCE"
    assert d["notes"] == ["note-1", "note-2"]


# ---------------------------------------------------------------------------
# 6. ComponentContributionBundle contract
# ---------------------------------------------------------------------------


def test_bundle_consistent_total() -> None:
    c1 = _make_euler("c1", contribution=90.0)
    c2 = _make_euler("c2", contribution=60.0)
    bundle = ComponentContributionBundle(
        component="frtb_sbm",
        contributions=(c1, c2),
        component_total=150.0,
        component_input_hash="h1",
        component_profile_hash="p1",
    )
    assert bundle.component == "frtb_sbm"
    assert len(bundle.contributions) == 2


def test_bundle_inconsistent_total_raises() -> None:
    c1 = _make_euler("c1", contribution=90.0)
    with pytest.raises(ValueError, match="does not match component_total"):
        ComponentContributionBundle(
            component="frtb_sbm",
            contributions=(c1,),
            component_total=999.0,  # wrong
            component_input_hash="h1",
            component_profile_hash="p1",
        )


def test_bundle_with_residual() -> None:
    c1 = _make_euler(
        "c1",
        contribution=140.0,
        reconciliation_status=ReconciliationStatus.PARTIAL_RESIDUAL,
    )
    r1 = _make_residual("r1", residual=10.0)
    bundle = ComponentContributionBundle(
        component="frtb_drc",
        contributions=(c1, r1),
        component_total=150.0,
        component_input_hash="h2",
        component_profile_hash="p2",
    )
    assert bundle.component_total == pytest.approx(150.0)


def test_bundle_as_dict() -> None:
    c1 = _make_euler("c1", contribution=100.0)
    bundle = ComponentContributionBundle(
        component="frtb_cva",
        contributions=(c1,),
        component_total=100.0,
        component_input_hash="h3",
        component_profile_hash="p3",
    )
    d = bundle.as_dict()
    assert list(d) == [
        "component",
        "contributions",
        "component_total",
        "component_input_hash",
        "component_profile_hash",
    ]
    assert d["component"] == "frtb_cva"
    assert isinstance(d["contributions"], list)
    assert len(d["contributions"]) == 1


def test_capital_contribution_as_dict_field_contract() -> None:
    c1 = _make_euler("c1", contribution=100.0)

    assert list(c1.as_dict()) == [
        "contribution_id",
        "source_id",
        "source_level",
        "bucket_key",
        "category",
        "base_amount",
        "marginal_multiplier",
        "contribution",
        "method",
        "residual",
        "reason",
        "citations",
        "input_hash",
        "profile_hash",
        "reconciliation_status",
    ]
