"""Tests for PLA KS statistic."""

import logging
from dataclasses import replace
from datetime import date, timedelta

import pytest

from frtb_ima.calendar import BusinessCalendar, ObservationWindowBasis
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
from tests.ima_helpers import business_dates

PLA_GREEN_THRESHOLD = 0.09
PLA_AMBER_THRESHOLD = 0.12


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
    with pytest.raises(ValueError, match="hpl vector is empty"):
        ks_statistic([], [1.0, 2.0])


def test_ks_empty_rtpl_raises() -> None:
    with pytest.raises(ValueError, match="rtpl vector is empty"):
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


def test_spearman_correlation_uses_average_ranks_for_ties() -> None:
    assert spearman_correlation(
        [1.0, 1.0, 2.0, 3.0],
        [4.0, 4.0, 5.0, 6.0],
    ) == pytest.approx(1.0)
    assert spearman_correlation(
        [1.0, 1.0, 2.0, 3.0],
        [6.0, 6.0, 5.0, 4.0],
    ) == pytest.approx(-1.0)


def test_spearman_correlation_uses_average_ranks_for_asymmetric_ties() -> None:
    assert spearman_correlation(
        [1.0, 1.0, 2.0, 3.0],
        [1.0, 2.0, 2.0, 3.0],
    ) == pytest.approx(5.0 / 6.0)


def test_spearman_correlation_requires_equal_length() -> None:
    with pytest.raises(ValueError, match="equal length"):
        spearman_correlation([1.0, 2.0], [1.0])


def test_spearman_correlation_requires_at_least_two_observations() -> None:
    with pytest.raises(ValueError, match="at least two"):
        spearman_correlation([1.0], [1.0])


def test_spearman_correlation_raises_for_all_constant_hpl() -> None:
    with pytest.raises(ValueError) as exc_info:
        spearman_correlation([1.0] * 10, [float(i) for i in range(1, 11)])
    assert (
        str(exc_info.value)
        == "Spearman correlation is undefined: all HPL or RTPL values are identical"
    )


def test_spearman_correlation_rejects_non_finite() -> None:
    with pytest.raises(ValueError, match="finite"):
        spearman_correlation([1.0, float("nan")], [1.0, 2.0])


def test_spearman_correlation_rejects_string_input() -> None:
    with pytest.raises(ValueError, match="sequence or numpy array"):
        spearman_correlation("not-a-vector", [1.0, 2.0])  # type: ignore[arg-type]


def test_pla_assessment_green_zone() -> None:
    vec = [float(i) for i in range(200)]
    result = pla_assessment(
        vec,
        vec,
        green_threshold=PLA_GREEN_THRESHOLD,
        amber_threshold=PLA_AMBER_THRESHOLD,
    )
    assert result.zone == "GREEN"
    assert result.ks_statistic == pytest.approx(0.0)


def test_pla_assessment_classifies_exact_threshold_boundaries() -> None:
    hpl = [0.0, 1.0]
    rtpl = [0.0, 2.0]

    green = pla_assessment(
        hpl,
        rtpl,
        green_threshold=0.5,
        amber_threshold=0.75,
        zone_labels=("PASS", "WATCH", "FAIL"),
    )
    amber = pla_assessment(
        hpl,
        rtpl,
        green_threshold=0.25,
        amber_threshold=0.5,
        zone_labels=("PASS", "WATCH", "FAIL"),
    )

    assert green.ks_statistic == pytest.approx(0.5)
    assert green.zone == "PASS"
    assert green.as_dict() == {
        "ks_statistic": pytest.approx(0.5),
        "zone": "PASS",
        "n_hpl": 2,
        "n_rtpl": 2,
    }
    assert amber.zone == "WATCH"


def test_pla_assessment_accepts_zero_green_threshold_boundary() -> None:
    result = pla_assessment(
        [0.0, 1.0],
        [0.0, 2.0],
        green_threshold=0.0,
        amber_threshold=0.5,
    )

    assert result.ks_statistic == pytest.approx(0.5)
    assert result.zone == "AMBER"


def test_pla_assessment_red_zone() -> None:
    hpl = [float(i) for i in range(1, 101)]
    rtpl = [float(i + 200) for i in range(1, 101)]
    result = pla_assessment(
        hpl,
        rtpl,
        green_threshold=PLA_GREEN_THRESHOLD,
        amber_threshold=PLA_AMBER_THRESHOLD,
    )
    assert result.zone == "RED"
    assert result.ks_statistic > 0.12


def test_pla_result_lengths() -> None:
    hpl = [1.0, 2.0, 3.0]
    rtpl = [1.0, 2.0, 3.0, 4.0]
    result = pla_assessment(
        hpl,
        rtpl,
        green_threshold=PLA_GREEN_THRESHOLD,
        amber_threshold=PLA_AMBER_THRESHOLD,
    )
    assert result.n_hpl == 3
    assert result.n_rtpl == 4


def test_pla_assessment_rejects_invalid_thresholds() -> None:
    with pytest.raises(ValueError, match="thresholds"):
        pla_assessment([1.0, 2.0], [1.0, 2.0], green_threshold=0.2, amber_threshold=0.1)

    with pytest.raises(ValueError, match="green_threshold"):
        pla_assessment(
            [1.0, 2.0],
            [1.0, 2.0],
            green_threshold=True,  # type: ignore[arg-type]
            amber_threshold=0.2,
        )

    with pytest.raises(ValueError, match="amber_threshold"):
        pla_assessment(
            [1.0, 2.0],
            [1.0, 2.0],
            green_threshold=0.1,
            amber_threshold=float("inf"),
        )


def test_pla_assessment_rejects_invalid_zone_labels() -> None:
    invalid_labels = (
        "BAD",
        "GREEN",
        ("GREEN", "AMBER"),
        ("GREEN", "", "RED"),
        ("GREEN", "GREEN", "RED"),
    )
    for labels in invalid_labels:
        with pytest.raises(ValueError, match="zone_labels"):
            pla_assessment(
                [1.0, 2.0],
                [1.0, 2.0],
                green_threshold=0.1,
                amber_threshold=0.2,
                zone_labels=labels,  # type: ignore[arg-type]
            )


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
    assert result.as_dict() == {
        "spearman_correlation": pytest.approx(-1.0),
        "zone": "RED",
        "n_hpl": 5,
        "n_rtpl": 5,
    }


def test_spearman_pla_assessment_classifies_exact_threshold_boundaries() -> None:
    hpl = [1.0, 1.0, 2.0, 3.0]
    rtpl = [1.0, 2.0, 2.0, 3.0]

    green = spearman_pla_assessment(
        hpl,
        rtpl,
        green_threshold=5.0 / 6.0,
        amber_threshold=0.70,
        zone_labels=("PASS", "WATCH", "FAIL"),
    )
    amber = spearman_pla_assessment(
        hpl,
        rtpl,
        green_threshold=0.90,
        amber_threshold=5.0 / 6.0,
        zone_labels=("PASS", "WATCH", "FAIL"),
    )

    assert green.spearman_correlation == pytest.approx(5.0 / 6.0)
    assert green.zone == "PASS"
    assert amber.zone == "WATCH"


def test_spearman_pla_assessment_accepts_zero_amber_threshold_boundary() -> None:
    result = spearman_pla_assessment(
        [1.0, 2.0, 3.0],
        [3.0, 2.0, 1.0],
        green_threshold=1.0,
        amber_threshold=0.0,
    )

    assert result.spearman_correlation == pytest.approx(-1.0)
    assert result.zone == "RED"


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
        hpl_time_series_id="ts-hpl",
        rtpl_time_series_id="ts-rtpl",
        upl_time_series_id="ts-upl",
    )

    assert result.zone == "AMBER"
    assert result.as_dict()["zone"] == "AMBER"
    assert result.as_dict()["time_series"] == {
        "hpl": "ts-hpl",
        "rtpl": "ts-rtpl",
        "upl": "ts-upl",
    }


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

    with pytest.warns(DeprecationWarning, match="calendar=None uses an observation count"):
        result = pla_assessment_for_policy_with_diagnostics(
            hpl,
            rtpl,
            policy,
            observation_dates=dates,
        )
    with pytest.warns(DeprecationWarning, match="calendar=None uses an observation count"):
        compatibility_result = pla_assessment_for_policy(hpl, rtpl, policy)

    assert result.pla == compatibility_result
    assert result.zone == "GREEN"
    assert result.diagnostics.available_observations == n
    assert result.diagnostics.window_size == policy.pla_window_days
    assert result.diagnostics.start_index == n - policy.pla_window_days
    assert result.diagnostics.start_date == dates[n - policy.pla_window_days]
    assert result.diagnostics.end_date == dates[-1]
    assert result.diagnostics.end_index_exclusive == n
    assert result.diagnostics.minimum_history == policy.pla_minimum_history_days
    assert result.as_dict()["diagnostics"] == {
        "available_observations": n,
        "minimum_history": policy.pla_minimum_history_days,
        "window_size": policy.pla_window_days,
        "start_index": n - policy.pla_window_days,
        "end_index_exclusive": n,
        "start_date": dates[n - policy.pla_window_days].isoformat(),
        "end_date": dates[-1].isoformat(),
        "calendar_source": "",
        "calendar_version": "",
        "calendar_basis": ObservationWindowBasis.OBSERVATION_COUNT_PROXY.value,
        "official_holiday_count": 0,
        "missing_business_dates": [],
    }


def test_pla_assessment_for_policy_with_diagnostics_logs_audit_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    policy = get_policy(RegulatoryRegime.ECB_CRR3)
    hpl = [float(idx) for idx in range(250)]
    rtpl = [float(idx + 1) for idx in range(250)]
    caplog.set_level(logging.INFO, logger="frtb_ima.pla")

    with pytest.warns(DeprecationWarning, match="calendar=None uses an observation count"):
        result = pla_assessment_for_policy_with_diagnostics(
            hpl,
            rtpl,
            policy,
            run_id="run-pla",
            desk_id="desk-pla",
        )

    record = caplog.records[-1]
    assert record.getMessage() == "pla_complete"
    assert record.run_id == "run-pla"
    assert record.desk_id == "desk-pla"
    assert record.regime == policy.regime.value
    assert record.ks_statistic == pytest.approx(result.ks_statistic)
    assert record.zone == result.zone
    assert record.window_size == policy.pla_window_days
    assert record.available_observations == 250
    assert record.spearman_correlation == pytest.approx(result.spearman.spearman_correlation)
    assert record.joint_zone == result.zone


def test_pla_policy_without_calendar_warns_observation_count_is_unverified() -> None:
    policy = get_policy()
    hpl = [float(idx) for idx in range(policy.pla_minimum_history_days)]
    rtpl = [float(idx) for idx in range(policy.pla_minimum_history_days)]

    with pytest.warns(DeprecationWarning, match="calendar=None uses an observation count"):
        result = pla_assessment_for_policy_with_diagnostics(hpl, rtpl, policy)

    assert result.diagnostics.calendar_basis == ObservationWindowBasis.OBSERVATION_COUNT_PROXY


def test_pla_policy_compatibility_wrapper_warns_without_calendar() -> None:
    policy = get_policy()
    hpl = [float(idx) for idx in range(policy.pla_minimum_history_days)]
    rtpl = [float(idx) for idx in range(policy.pla_minimum_history_days)]

    with pytest.warns(DeprecationWarning, match="calendar=None uses an observation count"):
        result = pla_assessment_for_policy(hpl, rtpl, policy)

    assert result.zone == "GREEN"


def test_pla_policy_calendar_validates_business_window_and_reports_holidays() -> None:
    policy = get_policy()
    holiday = date(2025, 12, 25)
    dates = business_dates(300, start=date(2025, 1, 1), holidays={holiday})
    calendar = BusinessCalendar(
        business_dates=dates,
        official_holidays=(holiday,),
        source="FED",
        version="2026.1",
    )
    hpl = [float(idx) for idx in range(300)]
    rtpl = [float(idx) for idx in range(300)]

    result = pla_assessment_for_policy_with_diagnostics(
        hpl,
        rtpl,
        policy,
        observation_dates=dates,
        calendar=calendar,
    )

    assert result.diagnostics.calendar_basis == ObservationWindowBasis.MOST_RECENT_BUSINESS_DAYS
    assert result.diagnostics.calendar_source == "FED"
    assert result.diagnostics.official_holiday_count == 1
    assert result.as_dict()["diagnostics"]["official_holiday_count"] == 1


def test_pla_policy_calendar_uses_actual_short_window_size() -> None:
    policy = replace(get_policy(), pla_window_days=10, pla_minimum_history_days=5)
    dates = business_dates(6, start=date(2025, 1, 1))
    calendar = BusinessCalendar(
        business_dates=dates,
        source="FED",
        version="2026.1",
    )
    hpl = [float(idx) for idx in range(6)]
    rtpl = [float(idx) for idx in range(6)]

    result = pla_assessment_for_policy_with_diagnostics(
        hpl,
        rtpl,
        policy,
        observation_dates=dates,
        calendar=calendar,
    )

    assert result.diagnostics.window_size == 6
    assert result.diagnostics.calendar_basis == ObservationWindowBasis.MOST_RECENT_BUSINESS_DAYS


def test_pla_ecb_policy_no_longer_raises_unsupported_feature() -> None:
    policy = get_policy(RegulatoryRegime.ECB_CRR3)
    hpl = [float(idx) for idx in range(250)]
    rtpl = [float(idx) for idx in range(250)]

    with pytest.warns(DeprecationWarning, match="calendar=None uses an observation count"):
        result = pla_assessment_for_policy_with_diagnostics(hpl, rtpl, policy)

    assert result.zone == "GREEN"


def test_pla_ecb_policy_returns_spearman_result() -> None:
    policy = get_policy(RegulatoryRegime.ECB_CRR3)
    hpl = [float(idx) for idx in range(250)]
    rtpl = [float(idx + 1) for idx in range(250)]

    with pytest.warns(DeprecationWarning, match="calendar=None uses an observation count"):
        result = pla_assessment_for_policy_with_diagnostics(hpl, rtpl, policy)

    assert result.spearman is not None
    assert result.spearman.spearman_correlation == pytest.approx(1.0)


def test_pla_ecb_policy_joint_zone_propagates() -> None:
    policy = get_policy(RegulatoryRegime.ECB_CRR3)
    hpl = [float(idx) for idx in range(250)]
    rtpl = [float(idx + 1) for idx in range(250)]

    with pytest.warns(DeprecationWarning, match="calendar=None uses an observation count"):
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

    with pytest.warns(DeprecationWarning, match="calendar=None uses an observation count"):
        result = pla_assessment_for_policy_with_diagnostics(hpl, rtpl, policy)

    assert result.pla.zone == "PASS"
    assert result.spearman is not None
    assert result.spearman.zone == "FAIL"
    assert result.zone == "FAIL"


def test_pla_assessment_for_policy_returns_authoritative_joint_zone() -> None:
    policy = get_policy(RegulatoryRegime.ECB_CRR3)
    hpl = [float(idx) for idx in range(250)]
    rtpl = [float(idx) for idx in range(249, -1, -1)]

    with pytest.warns(DeprecationWarning, match="calendar=None uses an observation count"):
        result = pla_assessment_for_policy(hpl, rtpl, policy)

    assert result.ks_statistic == pytest.approx(0.0)
    assert result.zone == "RED"


def test_pla_assessment_for_policy_forwards_observation_dates() -> None:
    policy = get_policy()
    hpl = [1.0] * policy.pla_minimum_history_days
    rtpl = [1.0] * policy.pla_minimum_history_days

    with pytest.raises(ValueError, match="observation_dates length"):
        pla_assessment_for_policy(
            hpl,
            rtpl,
            policy,
            observation_dates=[date(2025, 1, 1)],
        )


def test_pla_assessment_for_policy_forwards_calendar() -> None:
    policy = replace(get_policy(), pla_window_days=3, pla_minimum_history_days=3)
    dates = business_dates(3, start=date(2025, 1, 1))
    calendar = BusinessCalendar(
        business_dates=dates,
        source="FED",
        version="2026.1",
    )

    result = pla_assessment_for_policy(
        [1.0, 2.0, 3.0],
        [1.0, 2.0, 3.0],
        policy,
        observation_dates=dates,
        calendar=calendar,
    )

    assert result.zone == "GREEN"


def test_pla_fed_policy_spearman_is_none() -> None:
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    hpl = [float(idx) for idx in range(250)]
    rtpl = [float(idx) for idx in range(250)]

    with pytest.warns(DeprecationWarning, match="calendar=None uses an observation count"):
        result = pla_assessment_for_policy_with_diagnostics(hpl, rtpl, policy)

    assert result.spearman is None


def test_pla_assessment_result_as_dict_includes_spearman_when_present() -> None:
    policy = get_policy(RegulatoryRegime.ECB_CRR3)
    hpl = [float(idx) for idx in range(250)]
    rtpl = [float(idx + 1) for idx in range(250)]

    with pytest.warns(DeprecationWarning, match="calendar=None uses an observation count"):
        result = pla_assessment_for_policy_with_diagnostics(hpl, rtpl, policy)

    payload = result.as_dict()
    assert payload["zone"] == _worse_test_zone(result.pla.zone, result.spearman.zone)
    assert payload["spearman"] is not None
    assert "spearman_correlation" in payload["spearman"]


def test_pla_assessment_result_as_dict_spearman_is_none_for_fed_policy() -> None:
    policy = get_policy(RegulatoryRegime.FED_NPR_2_0)
    hpl = [float(idx) for idx in range(250)]
    rtpl = [float(idx) for idx in range(250)]

    with pytest.warns(DeprecationWarning, match="calendar=None uses an observation count"):
        result = pla_assessment_for_policy_with_diagnostics(hpl, rtpl, policy)

    payload = result.as_dict()
    assert payload["zone"] == payload["pla"]["zone"]
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


def test_pla_policy_assessment_reports_policy_window_field_names() -> None:
    policy = replace(get_policy(), pla_window_days=0, pla_minimum_history_days=1)

    with pytest.raises(ValueError, match="pla_window_days must be positive"):
        pla_assessment_for_policy_with_diagnostics([1.0], [1.0], policy)


def test_pla_policy_assessment_reports_minimum_history_field_name() -> None:
    policy = replace(get_policy(), pla_window_days=1, pla_minimum_history_days=0)

    with pytest.raises(ValueError, match="pla_minimum_history_days must be positive"):
        pla_assessment_for_policy_with_diagnostics([1.0], [1.0], policy)


def test_pla_policy_assessment_reports_calendar_validation_label() -> None:
    policy = replace(get_policy(), pla_window_days=2, pla_minimum_history_days=2)
    dates = (date(2025, 1, 1), date(2025, 1, 3))
    calendar = BusinessCalendar(
        business_dates=(date(2025, 1, 2), date(2025, 1, 3)),
        source="FED",
        version="2026.1",
    )

    with pytest.raises(ValueError, match="PLA window dates"):
        pla_assessment_for_policy_with_diagnostics(
            [1.0, 2.0],
            [1.0, 2.0],
            policy,
            observation_dates=dates,
            calendar=calendar,
        )


def test_pla_policy_assessment_rejects_insufficient_history() -> None:
    policy = get_policy()

    with pytest.warns(DeprecationWarning, match="calendar=None uses an observation count"):
        with pytest.raises(ValueError, match="at least"):
            pla_assessment_for_policy_with_diagnostics(
                [1.0] * (policy.pla_minimum_history_days - 1),
                [1.0] * (policy.pla_minimum_history_days - 1),
                policy,
            )
