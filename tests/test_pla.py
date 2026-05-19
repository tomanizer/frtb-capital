"""Tests for PLA KS statistic."""

import pytest

from frtb_ima.pla import PlaResult, ks_statistic, pla_assessment


def test_ks_identical_distributions() -> None:
    # Same vector: KS = 0
    vec = [float(i) for i in range(1, 101)]
    assert ks_statistic(vec, vec) == pytest.approx(0.0)


def test_ks_completely_separated() -> None:
    # Two non-overlapping distributions: KS should be 1.0
    hpl  = [1.0, 2.0, 3.0]
    rtpl = [10.0, 20.0, 30.0]
    result = ks_statistic(hpl, rtpl)
    assert result == pytest.approx(1.0)


def test_ks_partial_overlap() -> None:
    hpl  = [1.0, 2.0, 3.0, 4.0]
    rtpl = [2.0, 3.0, 4.0, 5.0]
    result = ks_statistic(hpl, rtpl)
    assert 0.0 < result < 1.0


def test_ks_empty_hpl_raises() -> None:
    with pytest.raises(ValueError, match="hpl"):
        ks_statistic([], [1.0, 2.0])


def test_ks_empty_rtpl_raises() -> None:
    with pytest.raises(ValueError, match="rtpl"):
        ks_statistic([1.0, 2.0], [])


def test_pla_assessment_green_zone() -> None:
    vec = [float(i) for i in range(200)]
    result = pla_assessment(vec, vec)
    assert result.zone == "GREEN"
    assert result.ks_statistic == pytest.approx(0.0)


def test_pla_assessment_red_zone() -> None:
    hpl  = [float(i) for i in range(1, 101)]
    rtpl = [float(i + 200) for i in range(1, 101)]
    result = pla_assessment(hpl, rtpl)
    assert result.zone == "RED"
    assert result.ks_statistic > 0.12


def test_pla_result_lengths() -> None:
    hpl  = [1.0, 2.0, 3.0]
    rtpl = [1.0, 2.0, 3.0, 4.0]
    result = pla_assessment(hpl, rtpl)
    assert result.n_hpl == 3
    assert result.n_rtpl == 4
