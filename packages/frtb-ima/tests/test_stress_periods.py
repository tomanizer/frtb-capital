"""Tests for vectorized stress-period calibration."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from frtb_ima.calendar import BusinessCalendar, ObservationWindowBasis
from frtb_ima.data_models import LiquidityHorizon, ModellabilityStatus, RiskClass
from frtb_ima.expected_shortfall import ESEstimator
from frtb_ima.nmrf import NMRFStressMethod
from frtb_ima.nmrf_method_selection import NMRFMethodReason, NMRFValuationInstruction
from frtb_ima.nmrf_stress_spec import (
    NMRFDirectShockSpec,
    NMRFShockDirection,
    build_nmrf_valuation_specs,
)
from frtb_ima.regimes import get_policy
from frtb_ima.stress_periods import (
    HistoricalStressSeries,
    StressPeriodCalibrationError,
    StressPeriodCandidate,
    StressPeriodSelectionResult,
    StressPeriodTieBreak,
    StressSeverityMetric,
    rolling_window_severity_scores,
    select_stress_period_from_history,
    select_stress_periods_by_risk_class,
    select_stress_periods_for_policy,
    stress_period_candidates_from_history,
    stress_period_specs_for_nmrf,
    validate_selected_stress_periods,
)
from tests.ima_helpers import business_dates

CONFIDENCE_LEVEL = 0.975
ES_ESTIMATOR = ESEstimator.DISCRETE_CEIL


def _dates(count: int, *, start: date = date(2020, 1, 1)) -> tuple[date, ...]:
    return tuple(start + timedelta(days=idx) for idx in range(count))


def _series(
    losses: list[float] | np.ndarray,
    *,
    risk_class: RiskClass = RiskClass.CSR,
    source: str = "synthetic historical scenario loss series",
    dates: tuple[date, ...] | None = None,
) -> HistoricalStressSeries:
    loss_arr = np.asarray(losses, dtype=float)
    series_dates = _dates(int(loss_arr.size)) if dates is None else dates
    return HistoricalStressSeries(
        risk_class=risk_class,
        losses=loss_arr,
        dates=series_dates,
        source=source,
        scenario_ids=tuple(f"{risk_class.value.lower()}-{idx:03d}" for idx in range(loss_arr.size)),
    )


def test_expected_shortfall_scores_match_naive_tail_mean() -> None:
    losses = np.array([1.0, 2.0, 100.0, 3.0, 4.0, 5.0])
    scores = rolling_window_severity_scores(
        losses,
        window_observations=4,
        minimum_observations=4,
        severity_metric=StressSeverityMetric.EXPECTED_SHORTFALL,
        confidence_level=0.50,
        es_estimator=ES_ESTIMATOR,
    )
    naive = []
    for start in range(0, 3):
        window = np.sort(losses[start : start + 4])
        naive.append(float(np.mean(window[-2:])))

    np.testing.assert_allclose(scores, naive)


def test_cumulative_loss_uses_window_sum_and_selects_severe_cluster() -> None:
    losses = np.zeros(12)
    losses[5:8] = [30.0, 40.0, 50.0]
    scores = rolling_window_severity_scores(
        losses,
        window_observations=3,
        minimum_observations=3,
        severity_metric=StressSeverityMetric.CUMULATIVE_LOSS,
        confidence_level=CONFIDENCE_LEVEL,
        es_estimator=ES_ESTIMATOR,
    )
    selected = select_stress_period_from_history(
        _series(losses),
        window_observations=3,
        minimum_observations=3,
        severity_metric=StressSeverityMetric.CUMULATIVE_LOSS,
        confidence_level=CONFIDENCE_LEVEL,
        es_estimator=ES_ESTIMATOR,
    )

    assert scores[5] == pytest.approx(120.0)
    assert selected.start_index == 5
    assert selected.end_index_exclusive == 8
    assert selected.severity_score == pytest.approx(120.0)


def test_latest_start_date_tie_break_is_deterministic() -> None:
    losses = np.array([1.0, 5.0, 1.0, 5.0, 1.0])
    selected = select_stress_period_from_history(
        _series(losses),
        window_observations=2,
        minimum_observations=2,
        severity_metric=StressSeverityMetric.MAX_LOSS,
        confidence_level=CONFIDENCE_LEVEL,
        es_estimator=ES_ESTIMATOR,
        tie_break=StressPeriodTieBreak.LATEST_START_DATE,
    )

    assert selected.start_index == 3
    assert selected.end_index_exclusive == 5


def test_earliest_start_date_tie_break_is_deterministic() -> None:
    losses = np.array([1.0, 5.0, 1.0, 5.0, 1.0])
    selected = select_stress_period_from_history(
        _series(losses),
        window_observations=2,
        minimum_observations=2,
        severity_metric=StressSeverityMetric.MAX_LOSS,
        confidence_level=CONFIDENCE_LEVEL,
        es_estimator=ES_ESTIMATOR,
        tie_break=StressPeriodTieBreak.EARLIEST_START_DATE,
    )

    assert selected.start_index == 0
    assert selected.end_index_exclusive == 2


def test_candidates_from_history_materialises_audit_windows_without_losses() -> None:
    candidates = stress_period_candidates_from_history(
        _series([1.0, 3.0, 2.0, 5.0, 4.0]),
        window_observations=3,
        minimum_observations=3,
        severity_metric=StressSeverityMetric.MAX_LOSS,
        confidence_level=CONFIDENCE_LEVEL,
        es_estimator=ES_ESTIMATOR,
    )

    assert len(candidates) == 3
    assert candidates[0].start_scenario_id == "csr-000"
    assert candidates[-1].end_scenario_id == "csr-004"
    assert "losses" not in candidates[0].as_dict()


def test_historical_stress_series_defensively_freezes_loss_vector() -> None:
    original_losses = np.array([1.0, 2.0, 3.0, 4.0])
    series = _series(original_losses)

    original_losses[0] = 100.0

    assert series.losses[0] == pytest.approx(1.0)
    assert series.losses.flags.writeable is False
    with pytest.raises(ValueError, match="read-only"):
        series.losses[0] = 200.0


def test_select_stress_periods_by_risk_class_selects_independently() -> None:
    csr_losses = np.zeros(10)
    csr_losses[2:5] = [10.0, 20.0, 30.0]
    equity_losses = np.zeros(10)
    equity_losses[6:9] = [40.0, 50.0, 60.0]
    result = select_stress_periods_by_risk_class(
        [
            _series(csr_losses, risk_class=RiskClass.CSR),
            _series(equity_losses, risk_class=RiskClass.EQUITY),
        ],
        as_of_date=date(2025, 6, 30),
        window_observations=3,
        minimum_observations=3,
        severity_metric=StressSeverityMetric.CUMULATIVE_LOSS,
        confidence_level=CONFIDENCE_LEVEL,
        es_estimator=ES_ESTIMATOR,
    )

    assert isinstance(result, StressPeriodSelectionResult)
    assert result.selected_by_risk_class[RiskClass.CSR].start_index == 2
    assert result.selected_by_risk_class[RiskClass.EQUITY].start_index == 6
    assert result.candidate_counts[RiskClass.CSR] == 8
    assert result.as_dict()["risk_class_count"] == 2


def test_policy_wrapper_uses_policy_regime_and_confidence_level() -> None:
    policy = get_policy()
    policy_length_losses = np.linspace(1.0, 260.0, 260)
    defaulted = select_stress_periods_for_policy(
        [_series(policy_length_losses)],
        policy,
        as_of_date=date(2025, 6, 30),
    )

    assert defaulted.regime == policy.regime.value
    assert defaulted.confidence_level == pytest.approx(policy.es_confidence_level)
    assert defaulted.window_observations == policy.stress_period_window_observations
    assert defaulted.minimum_observations == policy.stress_period_minimum_observations


def test_stress_period_selection_records_exact_calendar_window_basis() -> None:
    policy = get_policy()
    as_of_date = date(2025, 2, 28)
    holiday = date(2024, 12, 25)
    calendar_dates = business_dates(270, start=date(2024, 2, 29), holidays={holiday})
    calendar = BusinessCalendar(
        business_dates=calendar_dates,
        official_holidays=(holiday,),
        source="FED",
        version="2026.1",
    )
    losses = np.linspace(1.0, float(len(calendar_dates)), len(calendar_dates))

    result = select_stress_periods_for_policy(
        [_series(losses, dates=calendar_dates)],
        policy,
        as_of_date=as_of_date,
        calendar=calendar,
        use_exact_twelve_month_window=True,
    )

    assert result.window_basis == ObservationWindowBasis.EXACT_TWELVE_MONTH_BUSINESS_CALENDAR
    assert (
        result.window_observations
        == calendar.exact_twelve_month_window(as_of_date).business_day_count
    )
    assert result.official_holiday_count == 1
    assert result.as_dict()["selection_parameters"]["calendar_source"] == "FED"


def test_stress_period_specs_for_nmrf_bridge_uses_selected_windows() -> None:
    result = select_stress_periods_by_risk_class(
        [_series([1.0, 2.0, 10.0, 3.0])],
        as_of_date=date(2025, 6, 30),
        window_observations=3,
        minimum_observations=3,
        severity_metric=StressSeverityMetric.CUMULATIVE_LOSS,
        confidence_level=CONFIDENCE_LEVEL,
        es_estimator=ES_ESTIMATOR,
    )

    specs = stress_period_specs_for_nmrf(result)

    assert set(specs) == {RiskClass.CSR}
    assert specs[RiskClass.CSR].stress_period_id.startswith("csr-")
    assert specs[RiskClass.CSR].start_date == date(2020, 1, 2)
    assert specs[RiskClass.CSR].end_date == date(2020, 1, 4)


def test_historical_stress_series_rejects_invalid_inputs() -> None:
    with pytest.raises(TypeError, match="RiskClass"):
        HistoricalStressSeries(
            risk_class="CSR",  # type: ignore[arg-type]
            losses=[1.0],
            dates=_dates(1),
            source="synthetic",
        )

    with pytest.raises(ValueError, match="non-empty"):
        HistoricalStressSeries(
            risk_class=RiskClass.CSR,
            losses=[],
            dates=(),
            source="synthetic",
        )

    with pytest.raises(ValueError, match="dates must be non-empty"):
        HistoricalStressSeries(
            risk_class=RiskClass.CSR,
            losses=[1.0],
            dates=(),
            source="synthetic",
        )

    with pytest.raises(ValueError, match="finite"):
        HistoricalStressSeries(
            risk_class=RiskClass.CSR,
            losses=[1.0, float("nan")],
            dates=_dates(2),
            source="synthetic",
        )

    with pytest.raises(ValueError, match="strictly increasing"):
        HistoricalStressSeries(
            risk_class=RiskClass.CSR,
            losses=[1.0, 2.0],
            dates=(date(2020, 1, 2), date(2020, 1, 1)),
            source="synthetic",
        )

    with pytest.raises(ValueError, match="length"):
        HistoricalStressSeries(
            risk_class=RiskClass.CSR,
            losses=[1.0, 2.0],
            dates=_dates(1),
            source="synthetic",
        )

    with pytest.raises(ValueError, match="source"):
        HistoricalStressSeries(
            risk_class=RiskClass.CSR,
            losses=[1.0],
            dates=_dates(1),
            source="",
        )

    with pytest.raises(TypeError, match=r"datetime\.date"):
        HistoricalStressSeries(
            risk_class=RiskClass.CSR,
            losses=[1.0],
            dates=("2020-01-01",),  # type: ignore[arg-type]
            source="synthetic",
        )

    with pytest.raises(ValueError, match="one-dimensional"):
        HistoricalStressSeries(
            risk_class=RiskClass.CSR,
            losses=[[1.0]],  # type: ignore[list-item]
            dates=_dates(1),
            source="synthetic",
        )


def test_historical_stress_series_defaults_and_validates_scenario_ids() -> None:
    series = HistoricalStressSeries(
        risk_class=RiskClass.CSR,
        losses=[1.0, 2.0],
        dates=_dates(2),
        source="synthetic",
    )

    assert series.scenario_ids == ("csr-2020-01-01", "csr-2020-01-02")
    assert series.as_dict()["start_date"] == "2020-01-01"

    with pytest.raises(ValueError, match="scenario_ids length"):
        HistoricalStressSeries(
            risk_class=RiskClass.CSR,
            losses=[1.0, 2.0],
            dates=_dates(2),
            source="synthetic",
            scenario_ids=("one",),
        )
    with pytest.raises(TypeError, match="scenario_ids"):
        HistoricalStressSeries(
            risk_class=RiskClass.CSR,
            losses=[1.0, 2.0],
            dates=_dates(2),
            source="synthetic",
            scenario_ids=("one", 2),  # type: ignore[list-item]
        )
    with pytest.raises(ValueError, match="empty"):
        HistoricalStressSeries(
            risk_class=RiskClass.CSR,
            losses=[1.0, 2.0],
            dates=_dates(2),
            source="synthetic",
            scenario_ids=("one", ""),
        )
    with pytest.raises(ValueError, match="duplicates"):
        HistoricalStressSeries(
            risk_class=RiskClass.CSR,
            losses=[1.0, 2.0],
            dates=_dates(2),
            source="synthetic",
            scenario_ids=("one", "one"),
        )


def test_stress_period_candidate_validates_inputs_and_serializes_spec() -> None:
    candidate = StressPeriodCandidate(
        risk_class=RiskClass.CSR,
        period_id="csr-20200101-20200102",
        start_date=date(2020, 1, 1),
        end_date=date(2020, 1, 2),
        start_index=0,
        end_index_exclusive=2,
        observation_count=2,
        severity_score=10.0,
        severity_metric=StressSeverityMetric.MAX_LOSS,
        confidence_level=CONFIDENCE_LEVEL,
        es_estimator=ES_ESTIMATOR.value,
        source="synthetic",
        start_scenario_id="s1",
        end_scenario_id="s2",
    )

    assert candidate.es_estimator == ES_ESTIMATOR
    assert candidate.to_nmrf_stress_period_spec().stress_period_id == candidate.period_id
    assert candidate.as_dict()["severity_metric"] == "MAX_LOSS"

    invalid_cases = (
        {"risk_class": "CSR", "match": "RiskClass"},
        {"period_id": "", "match": "period_id"},
        {"start_date": date(2020, 1, 3), "match": "start_date"},
        {"start_index": -1, "match": "start_index"},
        {"end_index_exclusive": 0, "match": "end_index_exclusive"},
        {"observation_count": 0, "match": "observation_count"},
        {"observation_count": 3, "match": "index span"},
        {"severity_score": float("nan"), "match": "severity_score"},
        {"severity_metric": "MAX_LOSS", "match": "StressSeverityMetric"},
        {"confidence_level": 1.0, "match": "confidence_level"},
        {"source": "", "match": "source"},
        {"start_scenario_id": "", "match": "scenario_id"},
    )
    base = {
        "risk_class": RiskClass.CSR,
        "period_id": "csr-20200101-20200102",
        "start_date": date(2020, 1, 1),
        "end_date": date(2020, 1, 2),
        "start_index": 0,
        "end_index_exclusive": 2,
        "observation_count": 2,
        "severity_score": 10.0,
        "severity_metric": StressSeverityMetric.MAX_LOSS,
        "confidence_level": CONFIDENCE_LEVEL,
        "es_estimator": ES_ESTIMATOR,
        "source": "synthetic",
        "start_scenario_id": "s1",
        "end_scenario_id": "s2",
    }
    for case in invalid_cases:
        kwargs = {**base, **{key: value for key, value in case.items() if key != "match"}}
        with pytest.raises((TypeError, ValueError), match=str(case["match"])):
            StressPeriodCandidate(**kwargs)  # type: ignore[arg-type]


def test_selection_rejects_short_histories_and_duplicate_risk_classes() -> None:
    with pytest.raises(ValueError, match="at least 4 observations"):
        select_stress_period_from_history(
            _series([1.0, 2.0, 3.0]),
            window_observations=4,
            minimum_observations=4,
            severity_metric=StressSeverityMetric.MAX_LOSS,
            confidence_level=CONFIDENCE_LEVEL,
            es_estimator=ES_ESTIMATOR,
        )

    with pytest.raises(ValueError, match="duplicate history"):
        select_stress_periods_by_risk_class(
            [_series([1.0, 2.0, 3.0, 4.0]), _series([4.0, 3.0, 2.0, 1.0])],
            as_of_date=date(2025, 6, 30),
            window_observations=4,
            minimum_observations=4,
            severity_metric=StressSeverityMetric.MAX_LOSS,
            confidence_level=CONFIDENCE_LEVEL,
            es_estimator=ES_ESTIMATOR,
        )

    with pytest.raises(ValueError, match="histories"):
        select_stress_periods_by_risk_class(
            (),
            as_of_date=date(2025, 6, 30),
            confidence_level=CONFIDENCE_LEVEL,
            es_estimator=ES_ESTIMATOR,
        )

    with pytest.raises(TypeError, match="as_of_date"):
        select_stress_periods_by_risk_class(
            [_series([1.0, 2.0, 3.0, 4.0])],
            as_of_date="2025-06-30",  # type: ignore[arg-type]
            window_observations=4,
            minimum_observations=4,
            severity_metric=StressSeverityMetric.MAX_LOSS,
            confidence_level=CONFIDENCE_LEVEL,
            es_estimator=ES_ESTIMATOR,
        )

    with pytest.raises(TypeError, match="HistoricalStressSeries"):
        select_stress_periods_by_risk_class(
            [object()],  # type: ignore[list-item]
            as_of_date=date(2025, 6, 30),
            confidence_level=CONFIDENCE_LEVEL,
            es_estimator=ES_ESTIMATOR,
        )


def test_stress_period_selection_parameter_validation() -> None:
    series = _series([1.0, 2.0, 3.0, 4.0])

    invalid_calls = (
        {"window_observations": 0, "match": "window_observations"},
        {"minimum_observations": 0, "match": "minimum_observations"},
        {"minimum_observations": 2, "window_observations": 3, "match": "minimum_observations"},
        {"severity_metric": "MAX_LOSS", "match": "StressSeverityMetric"},
        {"confidence_level": 1.0, "match": "confidence_level"},
        {"tie_break": object(), "match": "Unsupported tie-break"},
    )
    for case in invalid_calls:
        kwargs = {
            "window_observations": case.get("window_observations", 2),
            "minimum_observations": case.get("minimum_observations", 2),
            "severity_metric": case.get("severity_metric", StressSeverityMetric.MAX_LOSS),
            "confidence_level": case.get("confidence_level", CONFIDENCE_LEVEL),
            "es_estimator": ES_ESTIMATOR,
            "tie_break": case.get("tie_break", StressPeriodTieBreak.LATEST_START_DATE),
        }
        with pytest.raises((TypeError, ValueError), match=str(case["match"])):
            select_stress_period_from_history(series, **kwargs)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="window_observations"):
        rolling_window_severity_scores(
            [1.0],
            window_observations=2,
            minimum_observations=1,
            severity_metric=StressSeverityMetric.MAX_LOSS,
            confidence_level=CONFIDENCE_LEVEL,
            es_estimator=ES_ESTIMATOR,
        )

    tie_break_test_candidate = select_stress_period_from_history(
        series,
        window_observations=2,
        minimum_observations=2,
        severity_metric=StressSeverityMetric.MAX_LOSS,
        confidence_level=CONFIDENCE_LEVEL,
        es_estimator=ES_ESTIMATOR,
    )
    with pytest.raises(TypeError, match="tie_break must be a StressPeriodTieBreak"):
        StressPeriodSelectionResult(
            as_of_date=date(2025, 6, 30),
            regime="FED_NPR_2_0",
            window_observations=2,
            minimum_observations=2,
            severity_metric=StressSeverityMetric.MAX_LOSS,
            confidence_level=CONFIDENCE_LEVEL,
            es_estimator=ES_ESTIMATOR,
            tie_break=object(),  # type: ignore[arg-type]
            selected_by_risk_class={RiskClass.CSR: tie_break_test_candidate},
            candidate_counts={RiskClass.CSR: 3},
        )


def test_validate_selected_stress_periods_requires_all_risk_classes() -> None:
    result = select_stress_periods_by_risk_class(
        [_series([1.0, 2.0, 10.0, 3.0])],
        as_of_date=date(2025, 6, 30),
        window_observations=3,
        minimum_observations=3,
        severity_metric=StressSeverityMetric.CUMULATIVE_LOSS,
        confidence_level=CONFIDENCE_LEVEL,
        es_estimator=ES_ESTIMATOR,
    )

    validate_selected_stress_periods(result, [RiskClass.CSR])
    with pytest.raises(ValueError, match="required_risk_classes"):
        validate_selected_stress_periods(result, [])
    with pytest.raises(TypeError, match="RiskClass"):
        validate_selected_stress_periods(result, ["CSR"])  # type: ignore[list-item]
    with pytest.raises(StressPeriodCalibrationError, match="EQUITY"):
        validate_selected_stress_periods(result, [RiskClass.CSR, RiskClass.EQUITY])


def test_selection_result_validates_candidate_mapping() -> None:
    candidate = select_stress_period_from_history(
        _series([1.0, 2.0, 3.0, 4.0]),
        window_observations=2,
        minimum_observations=2,
        severity_metric=StressSeverityMetric.MAX_LOSS,
        confidence_level=CONFIDENCE_LEVEL,
        es_estimator=ES_ESTIMATOR,
    )

    with pytest.raises(TypeError, match="as_of_date"):
        StressPeriodSelectionResult(
            as_of_date="2025-06-30",  # type: ignore[arg-type]
            regime="FED_NPR_2_0",
            window_observations=2,
            minimum_observations=2,
            severity_metric=StressSeverityMetric.MAX_LOSS,
            confidence_level=CONFIDENCE_LEVEL,
            es_estimator=ES_ESTIMATOR,
            tie_break=StressPeriodTieBreak.LATEST_START_DATE,
            selected_by_risk_class={RiskClass.CSR: candidate},
            candidate_counts={RiskClass.CSR: 3},
        )
    with pytest.raises(ValueError, match="regime"):
        StressPeriodSelectionResult(
            as_of_date=date(2025, 6, 30),
            regime="",
            window_observations=2,
            minimum_observations=2,
            severity_metric=StressSeverityMetric.MAX_LOSS,
            confidence_level=CONFIDENCE_LEVEL,
            es_estimator=ES_ESTIMATOR,
            tie_break=StressPeriodTieBreak.LATEST_START_DATE,
            selected_by_risk_class={RiskClass.CSR: candidate},
            candidate_counts={RiskClass.CSR: 3},
        )
    with pytest.raises(ValueError, match="non-empty"):
        StressPeriodSelectionResult(
            as_of_date=date(2025, 6, 30),
            regime="FED_NPR_2_0",
            window_observations=2,
            minimum_observations=2,
            severity_metric=StressSeverityMetric.MAX_LOSS,
            confidence_level=CONFIDENCE_LEVEL,
            es_estimator=ES_ESTIMATOR,
            tie_break=StressPeriodTieBreak.LATEST_START_DATE,
            selected_by_risk_class={},
            candidate_counts={},
        )
    with pytest.raises(ValueError, match="keys"):
        StressPeriodSelectionResult(
            as_of_date=date(2025, 6, 30),
            regime="FED_NPR_2_0",
            window_observations=2,
            minimum_observations=2,
            severity_metric=StressSeverityMetric.MAX_LOSS,
            confidence_level=CONFIDENCE_LEVEL,
            es_estimator=ES_ESTIMATOR,
            tie_break=StressPeriodTieBreak.LATEST_START_DATE,
            selected_by_risk_class={RiskClass.CSR: candidate},
            candidate_counts={RiskClass.EQUITY: 1},
        )
    with pytest.raises(TypeError, match="RiskClass"):
        StressPeriodSelectionResult(
            as_of_date=date(2025, 6, 30),
            regime="FED_NPR_2_0",
            window_observations=2,
            minimum_observations=2,
            severity_metric=StressSeverityMetric.MAX_LOSS,
            confidence_level=CONFIDENCE_LEVEL,
            es_estimator=ES_ESTIMATOR,
            tie_break=StressPeriodTieBreak.LATEST_START_DATE,
            selected_by_risk_class={"CSR": candidate},  # type: ignore[dict-item]
            candidate_counts={"CSR": 1},  # type: ignore[dict-item]
        )
    with pytest.raises(ValueError, match="risk_class"):
        StressPeriodSelectionResult(
            as_of_date=date(2025, 6, 30),
            regime="FED_NPR_2_0",
            window_observations=2,
            minimum_observations=2,
            severity_metric=StressSeverityMetric.MAX_LOSS,
            confidence_level=CONFIDENCE_LEVEL,
            es_estimator=ES_ESTIMATOR,
            tie_break=StressPeriodTieBreak.LATEST_START_DATE,
            selected_by_risk_class={
                RiskClass.CSR: StressPeriodCandidate(
                    risk_class=RiskClass.EQUITY,
                    period_id="equity-20200101-20200102",
                    start_date=date(2020, 1, 1),
                    end_date=date(2020, 1, 2),
                    start_index=0,
                    end_index_exclusive=2,
                    observation_count=2,
                    severity_score=10.0,
                    severity_metric=StressSeverityMetric.MAX_LOSS,
                    confidence_level=CONFIDENCE_LEVEL,
                    es_estimator=ES_ESTIMATOR,
                    source="synthetic",
                    start_scenario_id="s1",
                    end_scenario_id="s2",
                )
            },
            candidate_counts={RiskClass.CSR: 1},
        )
    with pytest.raises(ValueError, match="positive"):
        StressPeriodSelectionResult(
            as_of_date=date(2025, 6, 30),
            regime="FED_NPR_2_0",
            window_observations=2,
            minimum_observations=2,
            severity_metric=StressSeverityMetric.MAX_LOSS,
            confidence_level=CONFIDENCE_LEVEL,
            es_estimator=ES_ESTIMATOR,
            tie_break=StressPeriodTieBreak.LATEST_START_DATE,
            selected_by_risk_class={RiskClass.CSR: candidate},
            candidate_counts={RiskClass.CSR: 0},
        )


def test_public_input_guards_raise_for_wrong_types() -> None:
    with pytest.raises(TypeError, match="HistoricalStressSeries"):
        stress_period_candidates_from_history(  # type: ignore[arg-type]
            object(),
            window_observations=2,
            minimum_observations=2,
            severity_metric=StressSeverityMetric.MAX_LOSS,
            confidence_level=CONFIDENCE_LEVEL,
            es_estimator=ES_ESTIMATOR,
        )
    with pytest.raises(TypeError, match="HistoricalStressSeries"):
        select_stress_period_from_history(  # type: ignore[arg-type]
            object(),
            window_observations=2,
            minimum_observations=2,
            severity_metric=StressSeverityMetric.MAX_LOSS,
            confidence_level=CONFIDENCE_LEVEL,
            es_estimator=ES_ESTIMATOR,
        )
    with pytest.raises(ValueError, match="calendar is required"):
        select_stress_periods_by_risk_class(
            [_series([1.0, 2.0, 3.0, 4.0])],
            as_of_date=date(2025, 6, 30),
            confidence_level=CONFIDENCE_LEVEL,
            es_estimator=ES_ESTIMATOR,
            use_exact_twelve_month_window=True,
        )
    with pytest.raises(TypeError, match="RegulatoryPolicy"):
        select_stress_periods_for_policy(  # type: ignore[arg-type]
            [_series([1.0, 2.0, 3.0, 4.0])],
            object(),
            as_of_date=date(2025, 6, 30),
        )
    with pytest.raises(TypeError, match="StressPeriodSelectionResult"):
        stress_period_specs_for_nmrf(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="StressPeriodSelectionResult"):
        validate_selected_stress_periods(object(), [RiskClass.CSR])  # type: ignore[arg-type]


def test_rolling_window_raises_on_insufficient_data_and_invalid_metric(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Exercise terminal rolling-window guards that are unreachable via public validation.

    If selection-parameter validation semantics change, this test should be revisited.
    """
    import frtb_ima.stress_period_windows as stress_period_windows

    # Disabling parameter validation is intentional: otherwise minimum/window and
    # metric-type checks fail earlier and these final guards cannot be executed.
    monkeypatch.setattr(stress_period_windows, "_validate_selection_parameters", lambda **_: None)

    with pytest.raises(ValueError, match="window_observations"):
        rolling_window_severity_scores(
            [1.0, 2.0],
            window_observations=3,
            minimum_observations=1,
            severity_metric=StressSeverityMetric.MAX_LOSS,
            confidence_level=CONFIDENCE_LEVEL,
            es_estimator=ES_ESTIMATOR,
        )
    with pytest.raises(ValueError, match="Unsupported severity metric"):
        rolling_window_severity_scores(
            [1.0, 2.0, 3.0],
            window_observations=2,
            minimum_observations=1,
            severity_metric="UNKNOWN_METRIC",  # type: ignore[arg-type]
            confidence_level=CONFIDENCE_LEVEL,
            es_estimator=ES_ESTIMATOR,
        )


def test_stress_period_compatibility_imports_match_physical_modules() -> None:
    import frtb_ima.stress_period_results as stress_period_results
    import frtb_ima.stress_period_selection as stress_period_selection
    import frtb_ima.stress_period_types as stress_period_types
    import frtb_ima.stress_period_windows as stress_period_windows
    import frtb_ima.stress_periods as stress_periods_module

    compatibility_symbols = (
        stress_periods_module.HistoricalStressSeries,
        stress_periods_module.StressPeriodCandidate,
        stress_periods_module.StressPeriodSelectionResult,
        stress_periods_module.rolling_window_severity_scores,
        stress_periods_module.select_stress_periods_by_risk_class,
    )
    physical_symbols = (
        stress_period_types.HistoricalStressSeries,
        stress_period_types.StressPeriodCandidate,
        stress_period_results.StressPeriodSelectionResult,
        stress_period_windows.rolling_window_severity_scores,
        stress_period_selection.select_stress_periods_by_risk_class,
    )
    assert compatibility_symbols == physical_symbols


def test_same_risk_class_nmrfs_use_common_selected_stress_period() -> None:
    result = select_stress_periods_by_risk_class(
        [_series([1.0, 2.0, 10.0, 3.0, 1.0])],
        as_of_date=date(2025, 6, 30),
        window_observations=3,
        minimum_observations=3,
        severity_metric=StressSeverityMetric.CUMULATIVE_LOSS,
        confidence_level=CONFIDENCE_LEVEL,
        es_estimator=ES_ESTIMATOR,
    )
    stress_periods = stress_period_specs_for_nmrf(result)
    instructions = (
        NMRFValuationInstruction(
            risk_factor_name="HY_CREDIT_SPD",
            modellability_status=ModellabilityStatus.TYPE_A_NMRF,
            method=NMRFStressMethod.DIRECT,
            risk_factor_liquidity_horizon=LiquidityHorizon.LH60,
            required_liquidity_horizon=LiquidityHorizon.LH60,
            reason=NMRFMethodReason.DIRECT_STABLE_AND_WELL_DEFINED,
            source="synthetic selector",
        ),
        NMRFValuationInstruction(
            risk_factor_name="DISTRESSED_CREDIT_SPD",
            modellability_status=ModellabilityStatus.TYPE_A_NMRF,
            method=NMRFStressMethod.DIRECT,
            risk_factor_liquidity_horizon=LiquidityHorizon.LH60,
            required_liquidity_horizon=LiquidityHorizon.LH60,
            reason=NMRFMethodReason.DIRECT_STABLE_AND_WELL_DEFINED,
            source="synthetic selector",
        ),
    )

    specs = build_nmrf_valuation_specs(
        instructions,
        {
            "HY_CREDIT_SPD": RiskClass.CSR,
            "DISTRESSED_CREDIT_SPD": RiskClass.CSR,
        },
        stress_periods,
        get_policy(),
        direct_shocks={
            "HY_CREDIT_SPD": NMRFDirectShockSpec(
                shock_size=350.0,
                shock_unit="spread_bps",
                direction=NMRFShockDirection.UP,
                calibration_source="synthetic stress calibration",
                confidence_level=CONFIDENCE_LEVEL,
            ),
            "DISTRESSED_CREDIT_SPD": NMRFDirectShockSpec(
                shock_size=500.0,
                shock_unit="spread_bps",
                direction=NMRFShockDirection.UP,
                calibration_source="synthetic stress calibration",
                confidence_level=CONFIDENCE_LEVEL,
            ),
        },
    )

    assert specs[0].stress_period == specs[1].stress_period
