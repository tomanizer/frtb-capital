"""Tests for PLA KS statistic."""

from datetime import date, timedelta

import pytest

from frtb_ima.pla import (
    PlaPolicyAssessmentResult,
    PlaResult,
    PlaWindowDiagnostics,
    SpearmanPlaResult,
    ks_statistic,
    pla_assessment,
    pla_assessment_for_policy,
    pla_assessment_for_policy_with_diagnostics,
    spearman_correlation,
    spearman_pla_assessment,
)
from frtb_ima.regimes import PLAMetricsRequired, RegulatoryPolicy, RegulatoryRegime, get_policy


def _diagnostics() -> PlaWindowDiagnostics:
    return PlaWindowDiagnostics(
        available_observations=250,
        minimum_history=250,
        window_size=250,
        start_index=0,
        end_index_exclusive=250,
    )


def _worse_test_zone(zone1: str, zone2: str) -> str:
    severity = {"GREEN": 0, "AMBER": 1, "RED": 2}
    return zone1 if severity[zone1] >= severity[zone2] else zone2


def test_ks_identical_distributions() -> None:
    # Same vector: KS = 0
    vec = [float(i) for i in range(1, 101)]
    assert ks_statistic(vec, vec) == pytest.approx(0.0)


def test_ks_completely_separated() -> None:
    # Two non-overlapping distributions: KS should be 1.0
    hpl = [1.0, 2.0, 3.0]
    rtpl = [10.0, 20.0, 30.0]
    result = ks_statistic(hpl, rtpl)
    assert result == pytest.approx(1.0)


def test_ks_partial_overlap() -> None:
    hpl = [1.0, 2.0, 3.0, 4.0]
    rtpl = [2.0, 3.0, 4.0, 5.0]
    result = ks_statistic(hpl, rtpl)
    assert 0.0 < result < 1.0


def test_ks_empty_hpl_raises() -> None:
    with pytest.raises(ValueError, match="hpl"):
        ks_statistic([], [1.0, 2.0])


def test_ks_empty_rtpl_raises() -> None:
    with pytest.raises(ValueError, match="rtpl"):
        ks_statistic([1.0, 2.0], [])


def test_ks_accepts_numpy_arrays() -> None:
    import numpy as np

    vec = np.array([1.0, 2.0, 3.0])
    assert ks_statistic(vec, vec) == pytest.approx(0.0)


def test_ks_rejects_non_finite_values() -> None:
    with pytest.raises(ValueError, match="finite"):
        ks_statistic([1.0, float("nan")], [1.0, 2.0])


def test_spearman_correlation_identical_vectors_returns_one() -> None:
    vec = [float(i) for i in range(1, 101)]

    assert spearman_correlation(vec, vec) == pytest.approx(1.0)


def test_spearman_correlation_reversed_returns_minus_one() -> None:
    assert spearman_correlation(
        [1.0, 2.0, 3.0, 4.0, 5.0], [5.0, 4.0, 3.0, 2.0, 1.0]
    ) == pytest.approx(-1.0)


def test_spearman_correlation_shifted_is_approximately_one() -> None:
    hpl = [float(i) for i in range(1, 101)]
    rtpl = [float(i) for i in range(2, 102)]

    assert spearman_correlation(hpl, rtpl) == pytest.approx(1.0)


def test_spearman_correlation_requires_equal_length() -> None:
    with pytest.raises(ValueError, match="equal length"):
        spearman_correlation([1.0, 2.0], [1.0])


def test_spearman_correlation_requires_at_least_two_observations() -> None:
    with pytest.raises(ValueError, match="at least two"):
        spearman_correlation([1.0], [1.0])


def test_spearman_correlation_raises_for_all_constant_hpl() -> None:
    with pytest.raises(ValueError, match="undefined"):
        spearman_correlation([1.0] * 10, [float(i) for i in range(1, 11)])


def test_spearman_correlation_rejects_non_finite() -> None:
    with pytest.raises(ValueError, match="finite"):
        spearman_correlation([1.0, float("nan")], [1.0, 2.0])


def test_spearman_correlation_rejects_string_input() -> None:
    with pytest.raises(ValueError, match="sequence or numpy array"):
        spearman_correlation("not-a-vector", [1.0, 2.0])  # type: ignore[arg-type]


def test_pla_assessment_green_zone() -> None:
    vec = [float(i) for i in range(200)]
    result = pla_assessment(vec, vec)
    assert result.zone == "GREEN"
    assert result.ks_statistic == pytest.approx(0.0)


def test_pla_assessment_red_zone() -> None:
    hpl = [float(i) for i in range(1, 101)]
    rtpl = [float(i + 200) for i in range(1, 101)]
    result = pla_assessment(hpl, rtpl)
    assert result.zone == "RED"
    assert result.ks_statistic > 0.12


def test_pla_result_lengths() -> None:
    hpl = [1.0, 2.0, 3.0]
    rtpl = [1.0, 2.0, 3.0, 4.0]
    result = pla_assessment(hpl, rtpl)
    assert result.n_hpl == 3
    assert result.n_rtpl == 4


def test_pla_assessment_rejects_invalid_thresholds() -> None:
    with pytest.raises(ValueError, match="thresholds"):
        pla_assessment([1.0, 2.0], [1.0, 2.0], green_threshold=0.2, amber_threshold=0.1)


def test_spearman_pla_assessment_green_zone() -> None:
    vec = [float(i) for i in range(1, 101)]

    result = spearman_pla_assessment(
        vec,
        vec,
        green_threshold=0.80,
        amber_threshold=0.70,
    )

    assert result.zone == "GREEN"
    assert result.spearman_correlation == pytest.approx(1.0)


def test_spearman_pla_assessment_red_zone_anticorrelated() -> None:
    result = spearman_pla_assessment(
        [1.0, 2.0, 3.0, 4.0, 5.0],
        [5.0, 4.0, 3.0, 2.0, 1.0],
        green_threshold=0.80,
        amber_threshold=0.70,
    )

    assert result.zone == "RED"
    assert result.spearman_correlation == pytest.approx(-1.0)


def test_spearman_pla_assessment_rejects_invalid_thresholds() -> None:
    with pytest.raises(ValueError, match="thresholds"):
        spearman_pla_assessment(
            [1.0, 2.0],
            [1.0, 2.0],
            green_threshold=0.5,
            amber_threshold=0.8,
        )


def test_spearman_pla_assessment_rejects_non_numeric_threshold() -> None:
    with pytest.raises(ValueError, match="green_threshold"):
        spearman_pla_assessment(
            [1.0, 2.0],
            [1.0, 2.0],
            green_threshold="0.8",  # type: ignore[arg-type]
            amber_threshold=0.7,
        )


def test_spearman_pla_assessment_rejects_invalid_zone_labels() -> None:
    with pytest.raises(ValueError, match="zone_labels"):
        spearman_pla_assessment(
            [1.0, 2.0],
            [1.0, 2.0],
            green_threshold=0.8,
            amber_threshold=0.7,
            zone_labels=("GREEN", "GREEN", "RED"),
        )


def test_pla_joint_zone_ks_green_spearman_amber_gives_amber() -> None:
    result = PlaPolicyAssessmentResult(
        pla=PlaResult(ks_statistic=0.0, zone="GREEN", n_hpl=250, n_rtpl=250),
        spearman=SpearmanPlaResult(
            spearman_correlation=0.75,
            zone="AMBER",
            n_hpl=250,
            n_rtpl=250,
        ),
        diagnostics=_diagnostics(),
    )

    assert result.zone == "AMBER"


def test_pla_joint_zone_ks_red_spearman_green_gives_red() -> None:
    result = PlaPolicyAssessmentResult(
        pla=PlaResult(ks_statistic=0.2, zone="RED", n_hpl=250, n_rtpl=250),
        spearman=SpearmanPlaResult(
            spearman_correlation=1.0,
            zone="GREEN",
            n_hpl=250,
            n_rtpl=250,
        ),
        diagnostics=_diagnostics(),
    )

    assert result.zone == "RED"


def test_pla_joint_zone_when_spearman_none_delegates_to_ks() -> None:
    result = PlaPolicyAssessmentResult(
        pla=PlaResult(ks_statistic=0.1, zone="AMBER", n_hpl=250, n_rtpl=250),
        diagnostics=_diagnostics(),
    )

    assert result.zone == "AMBER"


def test_pla_assessment_for_policy_with_diagnostics_reports_window() -> None:
    policy = get_policy()
    n = 300
    start = date(2025, 1, 1)
    dates = tuple(start + timedelta(days=idx) for idx in range(n))
    hpl = [float(idx) for idx in range(n)]
    rtpl = [float(idx) for idx in range(n)]

    result = pla_assessment_for_policy_with_diagnostics(
        hpl,
        rtpl,
        policy,
        observation_dates=dates,
    )

    assert result.pla == pla_assessment_for_policy(hpl, rtpl, policy)
    assert result.zone == "GREEN"
    assert result.diagnostics.available_observations == n
    assert result.diagnostics.window_size == policy.pla_window_days
    assert result.diagnostics.start_index == n - policy.pla_window_days
    assert result.diagnostics.start_date == dates[n - policy.pla_window_days]
    assert result.diagnostics.end_date == dates[-1]
    assert result.as_dict()["diagnostics"]["window_size"] == policy.pla_window_days


def test_pla_ecb_policy_no_longer_raises_unsupported_feature() -> None:
    policy = get_policy(RegulatoryRegime.ECB_CRR3)
    hpl = [float(idx) for idx in range(250)]
    rtpl = [float(idx) for idx in range(250)]

    result = pla_assessment_for_policy_with_diagnostics(hpl, rtpl, policy)

    assert result.zone == "GREEN"


def test_pla_ecb_policy_returns_spearman_result() -> None:
    policy = get_policy(RegulatoryRegime.ECB_CRR3)
    hpl = [float(idx) for idx in range(250)]
    rtpl = [float(idx + 1) for idx in range(250)]

    result = pla_assessment_for_policy_with_diagnostics(hpl, rtpl, policy)

    assert result.spearman is not None
    assert result.spearman.spearman_correlation == pytest.approx(1.0)


def test_pla_ecb_policy_joint_zone_propagates() -> None:
    policy = get_policy(RegulatoryRegime.ECB_CRR3)
    hpl = [float(idx) for idx in range(250)]
    rtpl = [float(idx + 1) for idx in range(250)]

    result = pla_assessment_for_policy_with_diagnostics(hpl, rtpl, policy)

    assert result.spearman is not None
    assert result.zone == _worse_test_zone(result.pla.zone, result.spearman.zone)


def test_pla_policy_joint_zone_uses_custom_zone_labels() -> None:
    policy = RegulatoryPolicy(
        regime=RegulatoryRegime.ECB_CRR3,
        pla_metrics_required=PLAMetricsRequired.KS_AND_SPEARMAN,
        pla_zone_labels=("PASS", "WATCH", "FAIL"),
    )
    hpl = [float(idx) for idx in range(250)]
    rtpl = [float(idx) for idx in range(249, -1, -1)]

    result = pla_assessment_for_policy_with_diagnostics(hpl, rtpl, policy)

    assert result.pla.zone == "PASS"
    assert result.spearman is not None
    assert result.spearman.zone == "FAIL"
    assert result.zone == "FAIL"


def test_pla_assessment_for_policy_returns_authoritative_joint_zone() -> None:
    policy = get_policy(RegulatoryRegime.ECB_CRR3)
    hpl = [float(idx) for idx in range(250)]
    rtpl = [float(idx) for idx in range(249, -1, -1)]

    result = pla_assessment_for_policy(hpl, rtpl, policy)

    assert result.ks_statistic == pytest.approx(0.0)
    assert result.zone == "RED"


def test_pla_fed_policy_spearman_is_none() -> None:
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    hpl = [float(idx) for idx in range(250)]
    rtpl = [float(idx) for idx in range(250)]

    result = pla_assessment_for_policy_with_diagnostics(hpl, rtpl, policy)

    assert result.spearman is None


def test_pla_assessment_result_as_dict_includes_spearman_when_present() -> None:
    policy = get_policy(RegulatoryRegime.ECB_CRR3)
    hpl = [float(idx) for idx in range(250)]
    rtpl = [float(idx + 1) for idx in range(250)]

    result = pla_assessment_for_policy_with_diagnostics(hpl, rtpl, policy)

    payload = result.as_dict()
    assert payload["spearman"] is not None
    assert "spearman_correlation" in payload["spearman"]


def test_pla_assessment_result_as_dict_spearman_is_none_for_fed_policy() -> None:
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    hpl = [float(idx) for idx in range(250)]
    rtpl = [float(idx) for idx in range(250)]

    result = pla_assessment_for_policy_with_diagnostics(hpl, rtpl, policy)

    assert result.as_dict()["spearman"] is None


def test_pla_policy_assessment_requires_aligned_hpl_rtpl_lengths() -> None:
    policy = get_policy()
    with pytest.raises(ValueError, match="equal length"):
        pla_assessment_for_policy_with_diagnostics(
            [1.0] * policy.pla_minimum_history_days,
            [1.0] * (policy.pla_minimum_history_days + 1),
            policy,
        )


def test_pla_policy_assessment_rejects_misaligned_dates() -> None:
    policy = get_policy()
    hpl = [1.0] * policy.pla_minimum_history_days
    rtpl = [1.0] * policy.pla_minimum_history_days
    with pytest.raises(ValueError, match="observation_dates"):
        pla_assessment_for_policy_with_diagnostics(
            hpl,
            rtpl,
            policy,
            observation_dates=[date(2025, 1, 1)],
        )
