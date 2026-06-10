"""Tests for unified CapitalContribution primitives."""

import math

import pytest
from frtb_common.attribution import (
    AttributionMethod,
    CapitalContribution,
    ContributionReconciliation,
    ReconciliationStatus,
    reconcile_contribution_set,
    validate_contribution_reconciliation,
)


def test_capital_contribution_creation() -> None:
    contrib = CapitalContribution(
        contribution_id="contrib-1",
        source_id="pos-1",
        source_level="position",
        bucket_key="bucket-A",
        category="GIRR",
        base_amount=100.0,
        marginal_multiplier=1.5,
        contribution=150.0,
        method=AttributionMethod.ANALYTICAL_EULER,
        reason="analytical Euler",
    )
    assert contrib.contribution_id == "contrib-1"
    assert contrib.source_id == "pos-1"
    assert contrib.source_level == "position"
    assert contrib.bucket_key == "bucket-A"
    assert contrib.category == "GIRR"
    assert contrib.base_amount == 100.0
    assert contrib.marginal_multiplier == 1.5
    assert contrib.contribution == 150.0
    assert contrib.method == AttributionMethod.ANALYTICAL_EULER
    assert contrib.residual == 0.0
    assert contrib.reason == "analytical Euler"
    # new audit fields default to empty / UNKNOWN
    assert contrib.citations == ()
    assert contrib.input_hash == ""
    assert contrib.profile_hash == ""
    assert contrib.reconciliation_status == ReconciliationStatus.UNKNOWN

    d = contrib.as_dict()
    assert d["contribution_id"] == "contrib-1"
    assert d["source_id"] == "pos-1"
    assert d["source_level"] == "position"
    assert d["bucket_key"] == "bucket-A"
    assert d["category"] == "GIRR"
    assert d["base_amount"] == 100.0
    assert d["marginal_multiplier"] == 1.5
    assert d["contribution"] == 150.0
    assert d["method"] == "ANALYTICAL_EULER"
    assert d["residual"] == 0.0
    assert d["reason"] == "analytical Euler"
    assert d["citations"] == []
    assert d["input_hash"] == ""
    assert d["profile_hash"] == ""
    assert d["reconciliation_status"] == "UNKNOWN"


def test_capital_contribution_method_coercion() -> None:
    # Coercion from string
    contrib = CapitalContribution(
        contribution_id="contrib-1",
        source_id="pos-1",
        source_level="position",
        bucket_key=None,
        category="GIRR",
        base_amount=100.0,
        marginal_multiplier=None,
        contribution=None,
        method="RESIDUAL",
        residual=100.0,
        reason="residual allocation",
    )
    assert contrib.method == AttributionMethod.RESIDUAL

    standalone = CapitalContribution(
        contribution_id="contrib-standalone",
        source_id="line-1",
        source_level="line",
        bucket_key=None,
        category="RRAO",
        base_amount=100.0,
        marginal_multiplier=None,
        contribution=1.0,
        method="STANDALONE",
        reason="standalone line add-on",
    )
    assert standalone.method == AttributionMethod.STANDALONE
    assert standalone.contribution == 1.0

    # Invalid method string
    with pytest.raises(
        ValueError,
        match="method must be one of: ANALYTICAL_EULER, STANDALONE, RESIDUAL, UNSUPPORTED",
    ):
        CapitalContribution(
            contribution_id="contrib-1",
            source_id="pos-1",
            source_level="position",
            bucket_key=None,
            category="GIRR",
            base_amount=100.0,
            marginal_multiplier=None,
            contribution=None,
            method="INVALID_METHOD",
        )


def test_capital_contribution_analytical_euler_validation() -> None:
    # Requires marginal_multiplier
    with pytest.raises(
        ValueError,
        match="marginal_multiplier must not be None when method is ANALYTICAL_EULER",
    ):
        CapitalContribution(
            contribution_id="contrib-1",
            source_id="pos-1",
            source_level="position",
            bucket_key=None,
            category="GIRR",
            base_amount=100.0,
            marginal_multiplier=None,
            contribution=150.0,
            method=AttributionMethod.ANALYTICAL_EULER,
        )

    # Requires contribution
    with pytest.raises(
        ValueError,
        match="contribution must not be None when method is ANALYTICAL_EULER",
    ):
        CapitalContribution(
            contribution_id="contrib-1",
            source_id="pos-1",
            source_level="position",
            bucket_key=None,
            category="GIRR",
            base_amount=100.0,
            marginal_multiplier=1.5,
            contribution=None,
            method=AttributionMethod.ANALYTICAL_EULER,
        )


def test_capital_contribution_audit_fields() -> None:
    contrib = CapitalContribution(
        contribution_id="contrib-1",
        source_id="pos-1",
        source_level="position",
        bucket_key=None,
        category="GIRR",
        base_amount=100.0,
        marginal_multiplier=1.0,
        contribution=100.0,
        method=AttributionMethod.ANALYTICAL_EULER,
        citations=("CRE52.4", "CRE52.5"),
        input_hash="abc123",
        profile_hash="def456",
        reconciliation_status=ReconciliationStatus.RECONCILED,
    )
    assert contrib.citations == ("CRE52.4", "CRE52.5")
    assert contrib.input_hash == "abc123"
    assert contrib.profile_hash == "def456"
    assert contrib.reconciliation_status == ReconciliationStatus.RECONCILED

    d = contrib.as_dict()
    assert d["citations"] == ["CRE52.4", "CRE52.5"]
    assert d["input_hash"] == "abc123"
    assert d["profile_hash"] == "def456"
    assert d["reconciliation_status"] == "RECONCILED"


def test_reconcile_contribution_set_reports_reconciled_status() -> None:
    contribution = CapitalContribution(
        contribution_id="contrib-1",
        source_id="pos-1",
        source_level="position",
        bucket_key="bucket-A",
        category="GIRR",
        base_amount=100.0,
        marginal_multiplier=1.0,
        contribution=100.0,
        method=AttributionMethod.ANALYTICAL_EULER,
    )

    reconciliation = reconcile_contribution_set((contribution,), capital_total=100.0)

    assert isinstance(reconciliation, ContributionReconciliation)
    assert reconciliation.record_count == 1
    assert reconciliation.contribution_sum == pytest.approx(100.0)
    assert reconciliation.residual_sum == pytest.approx(0.0)
    assert reconciliation.explained_total == pytest.approx(100.0)
    assert reconciliation.difference == pytest.approx(0.0)
    assert reconciliation.status == ReconciliationStatus.RECONCILED
    assert reconciliation.is_reconciled
    assert reconciliation.as_dict()["status"] == "RECONCILED"


def test_reconcile_contribution_set_reports_partial_residual_status() -> None:
    contribution = CapitalContribution(
        contribution_id="contrib-1",
        source_id="pos-1",
        source_level="position",
        bucket_key="bucket-A",
        category="GIRR",
        base_amount=90.0,
        marginal_multiplier=None,
        contribution=90.0,
        method=AttributionMethod.STANDALONE,
    )
    residual = CapitalContribution(
        contribution_id="residual-1",
        source_id="bucket-A",
        source_level="bucket",
        bucket_key="bucket-A",
        category="GIRR",
        base_amount=0.0,
        marginal_multiplier=None,
        contribution=None,
        method=AttributionMethod.RESIDUAL,
        residual=10.0,
    )

    reconciliation = reconcile_contribution_set(
        (contribution, residual), capital_total=100.0
    )

    assert reconciliation.contribution_sum == pytest.approx(90.0)
    assert reconciliation.residual_sum == pytest.approx(10.0)
    assert reconciliation.status == ReconciliationStatus.PARTIAL_RESIDUAL
    assert reconciliation.is_reconciled


def test_reconcile_contribution_set_marks_small_residual_partial() -> None:
    contribution = CapitalContribution(
        contribution_id="contrib-1",
        source_id="pos-1",
        source_level="position",
        bucket_key="bucket-A",
        category="GIRR",
        base_amount=98.5,
        marginal_multiplier=None,
        contribution=98.5,
        method=AttributionMethod.STANDALONE,
    )
    residual = CapitalContribution(
        contribution_id="residual-1",
        source_id="bucket-A",
        source_level="bucket",
        bucket_key="bucket-A",
        category="GIRR",
        base_amount=0.0,
        marginal_multiplier=None,
        contribution=None,
        method=AttributionMethod.RESIDUAL,
        residual=0.9,
    )

    reconciliation = reconcile_contribution_set(
        (contribution, residual), capital_total=100.0, relative_tolerance=1e-2
    )

    assert reconciliation.difference == pytest.approx(-0.6)
    assert reconciliation.tolerance == pytest.approx(1.0)
    assert reconciliation.status == ReconciliationStatus.PARTIAL_RESIDUAL
    assert reconciliation.is_reconciled


def test_validate_contribution_reconciliation_raises_for_unreconciled_set() -> None:
    contribution = CapitalContribution(
        contribution_id="contrib-1",
        source_id="pos-1",
        source_level="position",
        bucket_key="bucket-A",
        category="GIRR",
        base_amount=90.0,
        marginal_multiplier=None,
        contribution=90.0,
        method=AttributionMethod.STANDALONE,
    )

    reconciliation = reconcile_contribution_set((contribution,), capital_total=100.0)
    assert reconciliation.status == ReconciliationStatus.UNRECONCILED
    assert not reconciliation.is_reconciled

    with pytest.raises(ValueError, match="does not match capital_total"):
        validate_contribution_reconciliation((contribution,), capital_total=100.0)


def test_reconcile_contribution_set_scales_zero_capital_tolerance() -> None:
    contribution = CapitalContribution(
        contribution_id="contrib-1",
        source_id="pos-1",
        source_level="position",
        bucket_key="bucket-A",
        category="GIRR",
        base_amount=0.0,
        marginal_multiplier=None,
        contribution=5e-7,
        method=AttributionMethod.STANDALONE,
    )

    reconciliation = reconcile_contribution_set((contribution,), capital_total=0.0)

    assert reconciliation.tolerance == pytest.approx(1e-6)
    assert reconciliation.status == ReconciliationStatus.RECONCILED


def test_reconcile_contribution_set_rejects_non_finite_values() -> None:
    contribution = CapitalContribution(
        contribution_id="contrib-1",
        source_id="pos-1",
        source_level="position",
        bucket_key="bucket-A",
        category="GIRR",
        base_amount=100.0,
        marginal_multiplier=None,
        contribution=math.inf,
        method=AttributionMethod.STANDALONE,
    )

    with pytest.raises(ValueError, match="contribution contrib-1 must be finite"):
        reconcile_contribution_set((contribution,), capital_total=100.0)
    with pytest.raises(ValueError, match="capital_total must be finite"):
        reconcile_contribution_set((), capital_total=math.inf)
    with pytest.raises(ValueError, match="relative_tolerance must be non-negative"):
        reconcile_contribution_set((), capital_total=100.0, relative_tolerance=-1e-6)
