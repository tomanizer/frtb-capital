"""Tests for vectorized stress-period calibration."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from frtb_ima.data_models import LiquidityHorizon, ModellabilityStatus, RiskClass
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

CONFIDENCE_LEVEL = 0.975


def _dates(count: int, *, start: date = date(2020, 1, 1)) -> tuple[date, ...]:
    return tuple(start + timedelta(days=idx) for idx in range(count))


def _series(
    losses: list[float] | np.ndarray,
    *,
    risk_class: RiskClass = RiskClass.CSR,
    source: str = "synthetic historical scenario loss series",
) -> HistoricalStressSeries:
    loss_arr = np.asarray(losses, dtype=float)
    return HistoricalStressSeries(
        risk_class=risk_class,
        losses=loss_arr,
        dates=_dates(int(loss_arr.size)),
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
    )
    selected = select_stress_period_from_history(
        _series(losses),
        window_observations=3,
        minimum_observations=3,
        severity_metric=StressSeverityMetric.CUMULATIVE_LOSS,
        confidence_level=CONFIDENCE_LEVEL,
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


def test_stress_period_specs_for_nmrf_bridge_uses_selected_windows() -> None:
    result = select_stress_periods_by_risk_class(
        [_series([1.0, 2.0, 10.0, 3.0])],
        as_of_date=date(2025, 6, 30),
        window_observations=3,
        minimum_observations=3,
        severity_metric=StressSeverityMetric.CUMULATIVE_LOSS,
        confidence_level=CONFIDENCE_LEVEL,
    )

    specs = stress_period_specs_for_nmrf(result)

    assert set(specs) == {RiskClass.CSR}
    assert specs[RiskClass.CSR].stress_period_id.startswith("csr-")
    assert specs[RiskClass.CSR].start_date == date(2020, 1, 2)
    assert specs[RiskClass.CSR].end_date == date(2020, 1, 4)


def test_historical_stress_series_rejects_invalid_inputs() -> None:
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


def test_selection_rejects_short_histories_and_duplicate_risk_classes() -> None:
    with pytest.raises(ValueError, match="at least 4 observations"):
        select_stress_period_from_history(
            _series([1.0, 2.0, 3.0]),
            window_observations=4,
            minimum_observations=4,
            severity_metric=StressSeverityMetric.MAX_LOSS,
            confidence_level=CONFIDENCE_LEVEL,
        )

    with pytest.raises(ValueError, match="duplicate history"):
        select_stress_periods_by_risk_class(
            [_series([1.0, 2.0, 3.0, 4.0]), _series([4.0, 3.0, 2.0, 1.0])],
            as_of_date=date(2025, 6, 30),
            window_observations=4,
            minimum_observations=4,
            severity_metric=StressSeverityMetric.MAX_LOSS,
            confidence_level=CONFIDENCE_LEVEL,
        )


def test_validate_selected_stress_periods_requires_all_risk_classes() -> None:
    result = select_stress_periods_by_risk_class(
        [_series([1.0, 2.0, 10.0, 3.0])],
        as_of_date=date(2025, 6, 30),
        window_observations=3,
        minimum_observations=3,
        severity_metric=StressSeverityMetric.CUMULATIVE_LOSS,
        confidence_level=CONFIDENCE_LEVEL,
    )

    validate_selected_stress_periods(result, [RiskClass.CSR])
    with pytest.raises(StressPeriodCalibrationError, match="EQUITY"):
        validate_selected_stress_periods(result, [RiskClass.CSR, RiskClass.EQUITY])


def test_same_risk_class_nmrfs_use_common_selected_stress_period() -> None:
    result = select_stress_periods_by_risk_class(
        [_series([1.0, 2.0, 10.0, 3.0, 1.0])],
        as_of_date=date(2025, 6, 30),
        window_observations=3,
        minimum_observations=3,
        severity_metric=StressSeverityMetric.CUMULATIVE_LOSS,
        confidence_level=CONFIDENCE_LEVEL,
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
