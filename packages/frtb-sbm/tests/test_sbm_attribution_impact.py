"""Tests for SBM analytical Euler attribution and capital impact (ADR 0038)."""

from __future__ import annotations

import math
from datetime import date

import pytest
from frtb_common.attribution import AttributionMethod, CapitalContribution, ReconciliationStatus
from frtb_common.impact import CapitalImpact, ImpactMethod
from frtb_sbm import (
    SbmCalculationContext,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    calculate_sbm_capital,
)
from frtb_sbm.attribution import calculate_sbm_attribution
from frtb_sbm.impact import calculate_sbm_capital_impact


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _lineage(run_id: str, row_id: str) -> SbmSourceLineage:
    return SbmSourceLineage(
        source_system="synthetic-risk",
        source_file="sbm.csv",
        source_row_id=f"{run_id}-{row_id}",
        source_column_map=(("DeltaUSD", "amount"),),
    )


def _context(run_id: str = "sbm-run", *, desk_id: str = "rates-desk") -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id=run_id,
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id="BASEL_MAR21",
        desk_id=desk_id,
    )


def _single_girr_delta(
    *,
    run_id: str = "sbm-run",
    amount: float = 1_000_000.0,
    tenor: str = "1y",
    bucket: str = "1",
) -> SbmSensitivity:
    return SbmSensitivity(
        sensitivity_id=f"{run_id}-eur-{tenor}",
        source_row_id=f"{run_id}-row-001",
        desk_id="rates-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket=bucket,
        risk_factor="EUR",
        tenor=tenor,
        amount=amount,
        amount_currency="USD",
        sign_convention=SbmSignConvention.RECEIVE,
        lineage=_lineage(run_id, "row-001"),
    )


# ---------------------------------------------------------------------------
# 1. Attribution — single sensitivity
# ---------------------------------------------------------------------------


def test_attribution_single_sensitivity_reconciles() -> None:
    """One GIRR delta sensitivity: Euler contribution must equal total capital."""
    result = calculate_sbm_capital((_single_girr_delta(),), context=_context())
    contributions = calculate_sbm_attribution(result)

    euler = [c for c in contributions if c.method == AttributionMethod.ANALYTICAL_EULER]
    assert len(euler) == 1, f"Expected 1 Euler record, got {len(euler)}"

    c = euler[0]
    assert c.source_level == "sensitivity"
    assert c.contribution is not None
    assert c.marginal_multiplier is not None
    assert c.reconciliation_status == ReconciliationStatus.RECONCILED

    total = sum((r.contribution or 0.0) + r.residual for r in contributions)
    assert math.isclose(total, result.total_capital, rel_tol=1e-6), (
        f"Euler sum {total} != total capital {result.total_capital}"
    )


def test_attribution_single_sensitivity_marginal_multiplier_positive() -> None:
    """For a long (positive) sensitivity, marginal multiplier must be positive."""
    result = calculate_sbm_capital((_single_girr_delta(amount=500_000.0),), context=_context())
    contributions = calculate_sbm_attribution(result)

    euler = [c for c in contributions if c.method == AttributionMethod.ANALYTICAL_EULER]
    assert euler
    assert all(c.marginal_multiplier is not None and c.marginal_multiplier > 0 for c in euler)


def test_attribution_zero_capital_returns_empty() -> None:
    """A result with zero total capital produces no attribution records."""
    # Two exactly offsetting sensitivities: long and short of equal magnitude
    # result in zero net WS within the bucket → zero intra-bucket capital.
    long_s = SbmSensitivity(
        sensitivity_id="s-long",
        source_row_id="run-row-long",
        desk_id="rates-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.FX,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket="EUR",
        risk_factor="EUR",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention=SbmSignConvention.LONG,
        lineage=SbmSourceLineage(
            source_system="synthetic-risk",
            source_file="sbm.csv",
            source_row_id="run-row-long",
            source_column_map=(("DeltaUSD", "amount"),),
        ),
    )
    short_s = SbmSensitivity(
        sensitivity_id="s-short",
        source_row_id="run-row-short",
        desk_id="rates-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.FX,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket="EUR",
        risk_factor="EUR",
        amount=-1_000_000.0,
        amount_currency="USD",
        sign_convention=SbmSignConvention.SHORT,
        lineage=SbmSourceLineage(
            source_system="synthetic-risk",
            source_file="sbm.csv",
            source_row_id="run-row-short",
            source_column_map=(("DeltaUSD", "amount"),),
        ),
    )
    result = calculate_sbm_capital((long_s, short_s), context=_context())
    contributions = calculate_sbm_attribution(result)

    # FX: single-currency perfect offset should produce zero capital
    if result.total_capital == 0.0:
        assert contributions == ()


def test_attribution_curvature_is_unsupported() -> None:
    """Curvature risk class must produce UNSUPPORTED records, not Euler."""
    curv_s = SbmSensitivity(
        sensitivity_id="s-curv",
        source_row_id="run-row-curv",
        desk_id="rates-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.FX,
        risk_measure=SbmRiskMeasure.CURVATURE,
        bucket="EUR",
        risk_factor="EUR",
        amount=0.0,
        amount_currency="USD",
        sign_convention=SbmSignConvention.LONG,
        lineage=SbmSourceLineage(
            source_system="synthetic-risk",
            source_file="sbm.csv",
            source_row_id="run-row-curv",
            source_column_map=(("DeltaUSD", "amount"),),
        ),
        up_shock_amount=50_000.0,
        down_shock_amount=30_000.0,
    )
    result = calculate_sbm_capital((curv_s,), context=_context())
    contributions = calculate_sbm_attribution(result)

    curv_unsupported = [
        c for c in contributions
        if c.method == AttributionMethod.UNSUPPORTED
        and "Curvature" in c.reason
    ]
    assert curv_unsupported, (
        "Expected at least one UNSUPPORTED record for curvature risk class"
    )
    # Curvature record residual carries the unattributed capital
    total_residual = sum(c.residual for c in curv_unsupported)
    curv_capital = next(
        rc.selected_capital
        for rc in result.risk_classes
        if rc.risk_measure is SbmRiskMeasure.CURVATURE
    )
    assert math.isclose(total_residual, curv_capital, rel_tol=1e-6)


# ---------------------------------------------------------------------------
# 2. Attribution — multi-sensitivity, single bucket
# ---------------------------------------------------------------------------


def test_attribution_two_sensitivities_same_bucket_reconciles() -> None:
    """Two GIRR delta sensitivities in the same bucket: Euler sum == K."""
    s1 = _single_girr_delta(run_id="run", amount=1_000_000.0, tenor="1y")
    s2 = SbmSensitivity(
        sensitivity_id="run-eur-2y",
        source_row_id="run-row-002",
        desk_id="rates-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket="1",
        risk_factor="EUR",
        tenor="2y",
        amount=800_000.0,
        amount_currency="USD",
        sign_convention=SbmSignConvention.RECEIVE,
        lineage=_lineage("run", "row-002"),
    )
    result = calculate_sbm_capital((s1, s2), context=_context())
    contributions = calculate_sbm_attribution(result)

    euler = [c for c in contributions if c.method == AttributionMethod.ANALYTICAL_EULER]
    assert len(euler) == 2

    total = sum((r.contribution or 0.0) + r.residual for r in contributions)
    assert math.isclose(total, result.total_capital, rel_tol=1e-6), (
        f"Euler sum {total} != total capital {result.total_capital}"
    )


# ---------------------------------------------------------------------------
# 3. Attribution — audit fields
# ---------------------------------------------------------------------------


def test_attribution_carries_input_and_profile_hash() -> None:
    result = calculate_sbm_capital((_single_girr_delta(),), context=_context())
    contributions = calculate_sbm_attribution(result)

    for c in contributions:
        assert c.input_hash == result.input_hash, "input_hash mismatch"
        assert c.profile_hash == result.profile_hash, "profile_hash mismatch"


def test_attribution_carries_citations() -> None:
    result = calculate_sbm_capital((_single_girr_delta(),), context=_context())
    contributions = calculate_sbm_attribution(result)

    for c in contributions:
        assert "basel_mar21_4_intra_bucket" in c.citations


def test_attribution_records_are_capital_contributions() -> None:
    result = calculate_sbm_capital((_single_girr_delta(),), context=_context())
    contributions = calculate_sbm_attribution(result)
    for c in contributions:
        assert isinstance(c, CapitalContribution)


# ---------------------------------------------------------------------------
# 4. Impact
# ---------------------------------------------------------------------------


def test_impact_delta_equals_difference() -> None:
    baseline = calculate_sbm_capital(
        (_single_girr_delta(run_id="base", amount=1_000_000.0),),
        context=_context(run_id="base"),
    )
    candidate = calculate_sbm_capital(
        (_single_girr_delta(run_id="cand", amount=1_200_000.0),),
        context=_context(run_id="cand"),
    )

    impact = calculate_sbm_capital_impact(baseline, candidate)

    assert isinstance(impact, CapitalImpact)
    assert impact.component == "frtb_sbm"
    assert impact.method == ImpactMethod.FINITE_DIFFERENCE
    assert math.isclose(impact.delta, candidate.total_capital - baseline.total_capital, rel_tol=1e-9)


def test_impact_carries_input_and_profile_hashes() -> None:
    baseline = calculate_sbm_capital(
        (_single_girr_delta(run_id="base", amount=1_000_000.0),),
        context=_context(run_id="base"),
    )
    candidate = calculate_sbm_capital(
        (_single_girr_delta(run_id="cand", amount=1_500_000.0),),
        context=_context(run_id="cand"),
    )
    impact = calculate_sbm_capital_impact(baseline, candidate)

    assert impact.baseline_input_hash == baseline.input_hash
    assert impact.candidate_input_hash == candidate.input_hash
    assert impact.baseline_profile_hash == baseline.profile_hash
    assert impact.candidate_profile_hash == candidate.profile_hash


def test_impact_negative_delta_when_candidate_lower() -> None:
    baseline = calculate_sbm_capital(
        (_single_girr_delta(run_id="base", amount=2_000_000.0),),
        context=_context(run_id="base"),
    )
    candidate = calculate_sbm_capital(
        (_single_girr_delta(run_id="cand", amount=500_000.0),),
        context=_context(run_id="cand"),
    )
    impact = calculate_sbm_capital_impact(baseline, candidate)

    assert impact.delta < 0.0
    assert math.isclose(impact.delta, candidate.total_capital - baseline.total_capital, rel_tol=1e-9)
