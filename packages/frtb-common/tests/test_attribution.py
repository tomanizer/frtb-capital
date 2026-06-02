"""Tests for unified CapitalContribution primitives."""

import pytest
from frtb_common.attribution import AttributionMethod, CapitalContribution


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

    # Invalid method string
    with pytest.raises(
        ValueError, match="method must be one of: ANALYTICAL_EULER, RESIDUAL, UNSUPPORTED"
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
