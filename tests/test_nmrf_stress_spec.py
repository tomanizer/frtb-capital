"""Tests for NMRF valuation-run specifications."""

from datetime import date

import numpy as np
import pytest

from frtb_ima.data_models import LiquidityHorizon, ModellabilityStatus, RiskClass
from frtb_ima.nmrf import NMRFStressMethod
from frtb_ima.nmrf_method_selection import NMRFMethodReason, NMRFValuationInstruction
from frtb_ima.nmrf_stress_spec import (
    NMRFDirectShockSpec,
    NMRFFullRevaluationSpec,
    NMRFMaxLossFallbackSpec,
    NMRFShockDirection,
    NMRFStepwiseShockGrid,
    NMRFStressPeriodSpec,
    NMRFStressSpecError,
    build_nmrf_valuation_spec,
    build_nmrf_valuation_specs,
    required_liquidity_horizons_from_valuation_specs,
    required_methods_from_valuation_specs,
)
from frtb_ima.regimes import RegulatoryRegime, UnsupportedRegulatoryFeature, get_policy


def _instruction(
    *,
    risk_factor_name: str = "HY_CREDIT_SPD",
    method: NMRFStressMethod = NMRFStressMethod.DIRECT,
    status: ModellabilityStatus = ModellabilityStatus.TYPE_A_NMRF,
    risk_factor_lh: LiquidityHorizon = LiquidityHorizon.LH20,
    required_lh: LiquidityHorizon = LiquidityHorizon.LH20,
) -> NMRFValuationInstruction:
    return NMRFValuationInstruction(
        risk_factor_name=risk_factor_name,
        modellability_status=status,
        method=method,
        risk_factor_liquidity_horizon=risk_factor_lh,
        required_liquidity_horizon=required_lh,
        reason=NMRFMethodReason.DIRECT_STABLE_AND_WELL_DEFINED,
        source="synthetic selector",
    )


def _stress_period(stress_period_id: str = "csr-2008") -> NMRFStressPeriodSpec:
    return NMRFStressPeriodSpec(
        stress_period_id=stress_period_id,
        calibration_source="synthetic stress-window selector",
        start_date=date(2008, 9, 1),
        end_date=date(2009, 8, 31),
    )


def test_direct_valuation_spec_requires_calibrated_direct_shock() -> None:
    spec = build_nmrf_valuation_spec(
        _instruction(),
        RiskClass.CSR,
        _stress_period(),
        get_policy(),
        direct_shock=NMRFDirectShockSpec(
            shock_size=350.0,
            shock_unit="spread_bps",
            direction=NMRFShockDirection.UP,
            calibration_source="synthetic 12-month stress window",
        ),
    )

    assert spec.risk_factor_name == "HY_CREDIT_SPD"
    assert spec.method == NMRFStressMethod.DIRECT
    assert spec.direct_shock is not None
    assert spec.direct_shock.shock_size == pytest.approx(350.0)
    assert spec.stepwise_grid is None


def test_direct_valuation_spec_fails_without_direct_payload() -> None:
    with pytest.raises(ValueError, match="DIRECT requires"):
        build_nmrf_valuation_spec(
            _instruction(),
            RiskClass.CSR,
            _stress_period(),
            get_policy(),
        )


def test_stepwise_grid_is_vectorized_validated_and_order_preserving() -> None:
    grid = NMRFStepwiseShockGrid(
        shock_points=np.array([-200.0, -100.0, 0.0, 100.0, 200.0]),
        shock_unit="spread_bps",
        calibration_source="synthetic grid calibration",
    )

    spec = build_nmrf_valuation_spec(
        _instruction(method=NMRFStressMethod.STEPWISE),
        RiskClass.CSR,
        _stress_period(),
        get_policy(),
        stepwise_grid=grid,
    )

    assert spec.stepwise_grid is not None
    assert spec.stepwise_grid.shock_count == 5
    assert spec.stepwise_grid.shock_points == (-200.0, -100.0, 0.0, 100.0, 200.0)


def test_stepwise_grid_rejects_duplicate_or_short_grids() -> None:
    with pytest.raises(ValueError, match="at least two"):
        NMRFStepwiseShockGrid(
            shock_points=[0.0],
            shock_unit="spread_bps",
            calibration_source="synthetic",
        )

    with pytest.raises(ValueError, match="duplicates"):
        NMRFStepwiseShockGrid(
            shock_points=[0.0, 100.0, 100.0],
            shock_unit="spread_bps",
            calibration_source="synthetic",
        )


def test_full_revaluation_spec_requires_unique_market_states() -> None:
    spec = build_nmrf_valuation_spec(
        _instruction(
            risk_factor_name="EXOTIC_RF",
            method=NMRFStressMethod.FULL_REVALUATION,
            status=ModellabilityStatus.TYPE_B_NMRF,
            risk_factor_lh=LiquidityHorizon.LH120,
            required_lh=LiquidityHorizon.LH120,
        ),
        RiskClass.EQUITY,
        _stress_period("equity-2020"),
        get_policy(),
        full_revaluation=NMRFFullRevaluationSpec(
            scenario_set_id="synthetic-full-reval",
            market_state_ids=("ms-1", "ms-2"),
            calibration_source="synthetic market-state replay",
        ),
    )

    assert spec.full_revaluation is not None
    assert spec.full_revaluation.market_state_ids == ("ms-1", "ms-2")
    assert spec.full_revaluation.require_full_trade_repricing is True

    with pytest.raises(ValueError, match="duplicates"):
        NMRFFullRevaluationSpec(
            scenario_set_id="synthetic-full-reval",
            market_state_ids=("ms-1", "ms-1"),
            calibration_source="synthetic market-state replay",
        )

    with pytest.raises(TypeError, match="only strings"):
        NMRFFullRevaluationSpec(
            scenario_set_id="synthetic-full-reval",
            market_state_ids=("ms-1", 1),  # type: ignore[arg-type]
            calibration_source="synthetic market-state replay",
        )


def test_max_loss_fallback_spec_requires_candidate_scenarios() -> None:
    spec = build_nmrf_valuation_spec(
        _instruction(method=NMRFStressMethod.MAX_LOSS_FALLBACK),
        RiskClass.CSR,
        _stress_period(),
        get_policy(),
        max_loss_fallback=NMRFMaxLossFallbackSpec(
            candidate_scenario_ids=("candidate-1", "candidate-2"),
            loss_source="upstream valuation candidate losses",
        ),
    )

    assert spec.max_loss_fallback is not None
    assert spec.max_loss_fallback.SELECTION_RULE == "MAXIMUM_LOSS"


def test_bulk_spec_builder_uses_risk_class_period_and_factor_override() -> None:
    instructions = (
        _instruction(risk_factor_name="HY_CREDIT_SPD", method=NMRFStressMethod.DIRECT),
        _instruction(
            risk_factor_name="EXOTIC_RF",
            method=NMRFStressMethod.FULL_REVALUATION,
            status=ModellabilityStatus.TYPE_B_NMRF,
            risk_factor_lh=LiquidityHorizon.LH120,
            required_lh=LiquidityHorizon.LH120,
        ),
    )
    risk_classes = {
        "HY_CREDIT_SPD": RiskClass.CSR,
        "EXOTIC_RF": RiskClass.EQUITY,
    }
    specs = build_nmrf_valuation_specs(
        instructions,
        risk_classes,
        {
            RiskClass.CSR: _stress_period("csr-2008"),
            RiskClass.EQUITY: _stress_period("equity-default"),
        },
        get_policy(),
        stress_periods_by_risk_factor={
            "EXOTIC_RF": _stress_period("equity-idiosyncratic-2020"),
        },
        direct_shocks={
            "HY_CREDIT_SPD": NMRFDirectShockSpec(
                shock_size=350.0,
                shock_unit="spread_bps",
                direction=NMRFShockDirection.UP,
                calibration_source="synthetic",
            ),
        },
        full_revaluations={
            "EXOTIC_RF": NMRFFullRevaluationSpec(
                scenario_set_id="synthetic-full-reval",
                market_state_ids=("ms-1", "ms-2"),
                calibration_source="synthetic",
            ),
        },
    )

    assert [spec.risk_factor_name for spec in specs] == ["HY_CREDIT_SPD", "EXOTIC_RF"]
    assert specs[0].stress_period.stress_period_id == "csr-2008"
    assert specs[1].stress_period.stress_period_id == "equity-idiosyncratic-2020"
    assert required_methods_from_valuation_specs(specs) == {
        "HY_CREDIT_SPD": NMRFStressMethod.DIRECT,
        "EXOTIC_RF": NMRFStressMethod.FULL_REVALUATION,
    }
    assert required_liquidity_horizons_from_valuation_specs(specs) == {
        "HY_CREDIT_SPD": LiquidityHorizon.LH20,
        "EXOTIC_RF": LiquidityHorizon.LH120,
    }


def test_bulk_spec_builder_reports_missing_risk_class() -> None:
    with pytest.raises(NMRFStressSpecError, match="missing risk class"):
        build_nmrf_valuation_specs(
            (_instruction(),),
            {},
            {RiskClass.CSR: _stress_period()},
            get_policy(),
        )


def test_bulk_spec_builder_rejects_duplicate_instructions() -> None:
    direct_shock = NMRFDirectShockSpec(
        shock_size=350.0,
        shock_unit="spread_bps",
        direction=NMRFShockDirection.UP,
        calibration_source="synthetic",
    )

    with pytest.raises(NMRFStressSpecError, match="duplicate instruction"):
        build_nmrf_valuation_specs(
            (
                _instruction(risk_factor_name="HY_CREDIT_SPD"),
                _instruction(risk_factor_name="HY_CREDIT_SPD"),
            ),
            {"HY_CREDIT_SPD": RiskClass.CSR},
            {RiskClass.CSR: _stress_period()},
            get_policy(),
            direct_shocks={"HY_CREDIT_SPD": direct_shock},
        )


def test_spec_builder_rejects_unsupported_ecb_type_a_type_b_policy() -> None:
    with pytest.raises(UnsupportedRegulatoryFeature, match="type_a_type_b"):
        build_nmrf_valuation_spec(
            _instruction(),
            RiskClass.CSR,
            _stress_period(),
            get_policy(RegulatoryRegime.ECB_CRR3),
            direct_shock=NMRFDirectShockSpec(
                shock_size=350.0,
                shock_unit="spread_bps",
                direction=NMRFShockDirection.UP,
                calibration_source="synthetic",
            ),
        )


def test_linear_sensitivity_is_not_a_valuation_run_spec() -> None:
    with pytest.raises(ValueError, match="LINEAR_SENSITIVITY"):
        build_nmrf_valuation_spec(
            _instruction(method=NMRFStressMethod.LINEAR_SENSITIVITY),
            RiskClass.CSR,
            _stress_period(),
            get_policy(),
        )
