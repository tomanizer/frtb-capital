"""Tests for IMCC module."""

import pytest

from frtb_ima.data_models import LiquidityHorizon, RiskClass
from frtb_ima.imcc import (
    imcc,
    imcc_constrained,
    imcc_unconstrained,
    scale_stress_es,
)


def _flat_vec(value: float, n: int = 100) -> list[float]:
    return [value] * n


# Flat vectors: ES = constant value, LHA_ES = sqrt(sum_w * val^2)
# For LH10-only: LHA_ES = sqrt(1 * val^2) = val

def test_imcc_unconstrained_lh10_only() -> None:
    vecs = {LiquidityHorizon.LH10: _flat_vec(100.0)}
    result = imcc_unconstrained(vecs)
    assert result == pytest.approx(100.0)


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


def test_imcc_final_is_50_50_blend() -> None:
    all_class = {LiquidityHorizon.LH10: _flat_vec(200.0)}  # unconstrained = 200
    per_class = {
        RiskClass.GIRR:   {LiquidityHorizon.LH10: _flat_vec(100.0)},  # constrained = 200
        RiskClass.EQUITY: {LiquidityHorizon.LH10: _flat_vec(100.0)},
    }
    result = imcc(all_class, per_class, w=0.5)
    # 0.5 * 200 + 0.5 * 200 = 200
    assert result == pytest.approx(200.0)


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


def test_scale_stress_es_ratio_above_one() -> None:
    # current_full > current_reduced: ratio = 1.2, scaled = 100 * 1.2
    result = scale_stress_es(
        stress_reduced_es=100.0,
        current_full_es=120.0,
        current_reduced_es=100.0,
    )
    assert result == pytest.approx(120.0)


def test_scale_stress_es_ratio_below_one_floors_at_one() -> None:
    # current_full < current_reduced: floor ratio at 1.0
    result = scale_stress_es(
        stress_reduced_es=100.0,
        current_full_es=80.0,
        current_reduced_es=100.0,
    )
    assert result == pytest.approx(100.0)


def test_scale_stress_es_zero_reduced_raises() -> None:
    with pytest.raises(ValueError):
        scale_stress_es(100.0, current_full_es=100.0, current_reduced_es=0.0)


def test_scale_stress_es_rejects_negative_inputs() -> None:
    with pytest.raises(ValueError, match="stress_reduced_es"):
        scale_stress_es(-1.0, current_full_es=100.0, current_reduced_es=100.0)
