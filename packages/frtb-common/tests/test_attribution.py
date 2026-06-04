"""Tests for unified CapitalContribution primitives."""

import pytest
from frtb_common.attribution import AttributionMethod, CapitalContribution, ReconciliationStatus


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
        ValueError, match="marginal_multiplier must not be None when method is ANALYTICAL_EULER"
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
        ValueError, match="contribution must not be None when method is ANALYTICAL_EULER"
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
