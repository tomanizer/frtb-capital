"""Tests for IMCC module."""

import pytest

from frtb_ima.data_models import LiquidityHorizon, RiskClass
from frtb_ima.imcc import (
    imcc,
    imcc_breakdown,
    imcc_breakdown_for_policy,
    imcc_constrained,
    imcc_constrained_breakdown,
    imcc_unconstrained,
    imcc_unconstrained_breakdown,
    scale_stress_es,
    scale_stress_es_breakdown,
)
from frtb_ima.regimes import get_policy


def _flat_vec(value: float, n: int = 100) -> list[float]:
    return [value] * n


# Flat vectors: ES = constant value, LHA_ES = sqrt(sum_w * val^2)
# For LH10-only: LHA_ES = sqrt(1 * val^2) = val

def test_imcc_unconstrained_lh10_only() -> None:
    vecs = {LiquidityHorizon.LH10: _flat_vec(100.0)}
    result = imcc_unconstrained(vecs)
    assert result == pytest.approx(100.0)


def test_imcc_unconstrained_breakdown_exposes_lha_components() -> None:
    vecs = {
        LiquidityHorizon.LH10: _flat_vec(100.0),
        LiquidityHorizon.LH20: _flat_vec(50.0),
    }

    result = imcc_unconstrained_breakdown(vecs)

    assert result.lha_es == pytest.approx((100.0**2 + 50.0**2) ** 0.5)
    assert result.component_by_horizon(
        LiquidityHorizon.LH20
    ).expected_shortfall == pytest.approx(50.0)


def test_imcc_constrained_single_class() -> None:
    per_class = {
        RiskClass.GIRR: {LiquidityHorizon.LH10: _flat_vec(100.0)}
    }
    result = imcc_constrained(per_class)
    assert result == pytest.approx(100.0)


def test_imcc_constrained_multiple_classes_no_diversification() -> None:
    # Two classes each contributing 100 -> constrained = 200 (no diversification)
    per_class = {
        RiskClass.GIRR:   {LiquidityHorizon.LH10: _flat_vec(100.0)},
        RiskClass.EQUITY: {LiquidityHorizon.LH10: _flat_vec(100.0)},
    }
    result = imcc_constrained(per_class)
    assert result == pytest.approx(200.0)


def test_imcc_constrained_breakdown_is_deterministic_by_risk_class() -> None:
    per_class = {
        RiskClass.EQUITY: {LiquidityHorizon.LH10: _flat_vec(100.0)},
        RiskClass.GIRR: {LiquidityHorizon.LH10: _flat_vec(50.0)},
    }

    result = imcc_constrained_breakdown(per_class)

    assert [component.risk_class for component in result] == [
        RiskClass.EQUITY,
        RiskClass.GIRR,
    ]
    assert [component.lha_es for component in result] == pytest.approx([100.0, 50.0])


def test_imcc_final_is_50_50_blend() -> None:
    all_class = {LiquidityHorizon.LH10: _flat_vec(200.0)}  # unconstrained = 200
    per_class = {
        RiskClass.GIRR:   {LiquidityHorizon.LH10: _flat_vec(100.0)},  # constrained = 200
        RiskClass.EQUITY: {LiquidityHorizon.LH10: _flat_vec(100.0)},
    }
    result = imcc(all_class, per_class, w=0.5)
    # 0.5 * 200 + 0.5 * 200 = 200
    assert result == pytest.approx(200.0)


def test_imcc_breakdown_reproduces_scalar_and_reports_components() -> None:
    all_class = {
        LiquidityHorizon.LH10: _flat_vec(200.0),
        LiquidityHorizon.LH20: _flat_vec(100.0),
    }
    per_class = {
        RiskClass.GIRR: {LiquidityHorizon.LH10: _flat_vec(100.0)},
        RiskClass.EQUITY: {LiquidityHorizon.LH10: _flat_vec(50.0)},
    }

    result = imcc_breakdown(all_class, per_class, w=0.5)

    unconstrained = (200.0**2 + 100.0**2) ** 0.5
    constrained = 150.0
    assert result.unconstrained_lha_es == pytest.approx(unconstrained)
    assert result.constrained_lha_es == pytest.approx(constrained)
    assert result.imcc == pytest.approx((unconstrained + constrained) * 0.5)
    assert result.imcc == pytest.approx(imcc(all_class, per_class, w=0.5))
    assert result.component_by_risk_class(RiskClass.GIRR).lha_es == pytest.approx(100.0)

    serialised = result.as_dict()
    assert serialised["unconstrained_weight"] == pytest.approx(0.5)
    assert serialised["constrained_weight"] == pytest.approx(0.5)
    assert "imcc=" in "\n".join(result.summary_lines())


def test_imcc_breakdown_for_policy_reproduces_policy_scalar() -> None:
    policy = get_policy()
    all_class = {LiquidityHorizon.LH10: _flat_vec(200.0)}
    per_class = {
        RiskClass.GIRR: {LiquidityHorizon.LH10: _flat_vec(100.0)},
        RiskClass.EQUITY: {LiquidityHorizon.LH10: _flat_vec(100.0)},
    }

    result = imcc_breakdown_for_policy(all_class, per_class, policy)

    assert result.alpha == policy.es_confidence_level
    assert result.unconstrained_weight == policy.imcc_unconstrained_weight
    assert result.imcc == pytest.approx(imcc(all_class, per_class))


def test_imcc_rejects_invalid_weight() -> None:
    all_class = {LiquidityHorizon.LH10: _flat_vec(200.0)}
    per_class = {RiskClass.GIRR: {LiquidityHorizon.LH10: _flat_vec(100.0)}}
    with pytest.raises(ValueError, match="w"):
        imcc(all_class, per_class, w=1.5)


def test_imcc_constrained_missing_lh10_raises() -> None:
    per_class = {
        RiskClass.GIRR: {LiquidityHorizon.LH20: _flat_vec(100.0)}
    }
    with pytest.raises(KeyError):
        imcc_constrained(per_class)


def test_imcc_breakdown_missing_constrained_lh10_raises() -> None:
    all_class = {LiquidityHorizon.LH10: _flat_vec(100.0)}
    per_class = {RiskClass.GIRR: {LiquidityHorizon.LH20: _flat_vec(100.0)}}
    with pytest.raises(KeyError, match="LH10"):
        imcc_breakdown(all_class, per_class)


def test_scale_stress_es_ratio_above_one() -> None:
    # current_full > current_reduced: ratio = 1.2, scaled = 100 * 1.2
    result = scale_stress_es(
        stress_reduced_es=100.0,
        current_full_es=120.0,
        current_reduced_es=100.0,
    )
    assert result == pytest.approx(120.0)


def test_scale_stress_es_breakdown_ratio_above_one() -> None:
    result = scale_stress_es_breakdown(
        stress_reduced_es=100.0,
        current_full_es=120.0,
        current_reduced_es=100.0,
    )

    assert result.raw_ratio == pytest.approx(1.2)
    assert result.applied_ratio == pytest.approx(1.2)
    assert result.floor_applied is False
    assert result.scaled_stress_es == pytest.approx(120.0)
    assert result.as_dict()["scaled_stress_es"] == pytest.approx(120.0)


def test_scale_stress_es_ratio_below_one_floors_at_one() -> None:
    # current_full < current_reduced: floor ratio at 1.0
    result = scale_stress_es(
        stress_reduced_es=100.0,
        current_full_es=80.0,
        current_reduced_es=100.0,
    )
    assert result == pytest.approx(100.0)


def test_scale_stress_es_breakdown_ratio_below_one_reports_floor() -> None:
    result = scale_stress_es_breakdown(
        stress_reduced_es=100.0,
        current_full_es=80.0,
        current_reduced_es=100.0,
    )

    assert result.raw_ratio == pytest.approx(0.8)
    assert result.applied_ratio == pytest.approx(1.0)
    assert result.floor_applied is True
    assert result.scaled_stress_es == pytest.approx(100.0)
    assert "floor_applied=True" in result.summary_lines()


def test_scale_stress_es_zero_reduced_raises() -> None:
    with pytest.raises(ValueError):
        scale_stress_es(100.0, current_full_es=100.0, current_reduced_es=0.0)


def test_scale_stress_es_rejects_negative_inputs() -> None:
    with pytest.raises(ValueError, match="stress_reduced_es"):
        scale_stress_es(-1.0, current_full_es=100.0, current_reduced_es=100.0)
