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
    NMRFValuationSpec,
    build_nmrf_valuation_spec,
    build_nmrf_valuation_specs,
    required_liquidity_horizons_from_valuation_specs,
    required_methods_from_valuation_specs,
)
from frtb_ima.regimes import RegulatoryRegime, get_policy

CONFIDENCE_LEVEL = 0.975


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
            confidence_level=CONFIDENCE_LEVEL,
        ),
    )

    assert spec.risk_factor_name == "HY_CREDIT_SPD"
    assert spec.method == NMRFStressMethod.DIRECT
    assert spec.direct_shock is not None
    assert spec.direct_shock.shock_size == pytest.approx(350.0)
    assert spec.stepwise_grid is None
    assert spec.as_dict()["direct_shock"] == spec.direct_shock.as_dict()


def test_stress_period_and_direct_shock_specs_validate_fields() -> None:
    stress_period = NMRFStressPeriodSpec(
        stress_period_id="csr-2008",
        calibration_source="synthetic",
        notes="unit test",
    )
    direct = NMRFDirectShockSpec(
        shock_size=350.0,
        shock_unit="spread_bps",
        direction=NMRFShockDirection.TWO_SIDED,
        calibration_source="synthetic",
        confidence_level=CONFIDENCE_LEVEL,
        notes="unit test",
    )

    assert stress_period.as_dict()["start_date"] is None
    assert direct.as_dict()["direction"] == "TWO_SIDED"

    invalid_stress_periods = (
        {"stress_period_id": "", "calibration_source": "synthetic", "match": "stress_period_id"},
        {"stress_period_id": "csr", "calibration_source": "", "match": "calibration_source"},
        {
            "stress_period_id": "csr",
            "calibration_source": "synthetic",
            "start_date": "2020-01-01",
            "match": "start_date",
        },
        {
            "stress_period_id": "csr",
            "calibration_source": "synthetic",
            "end_date": "2020-01-01",
            "match": "end_date",
        },
        {
            "stress_period_id": "csr",
            "calibration_source": "synthetic",
            "start_date": date(2020, 1, 2),
            "end_date": date(2020, 1, 1),
            "match": "start_date",
        },
    )
    for case in invalid_stress_periods:
        kwargs = {key: value for key, value in case.items() if key != "match"}
        with pytest.raises((TypeError, ValueError), match=str(case["match"])):
            NMRFStressPeriodSpec(**kwargs)  # type: ignore[arg-type]

    invalid_direct_shocks = (
        {"shock_size": 0.0, "match": "shock_size"},
        {"shock_unit": "", "match": "shock_unit"},
        {"direction": "UP", "match": "NMRFShockDirection"},
        {"calibration_source": "", "match": "calibration_source"},
        {"confidence_level": 1.0, "match": "confidence_level"},
    )
    base = {
        "shock_size": 350.0,
        "shock_unit": "spread_bps",
        "direction": NMRFShockDirection.UP,
        "calibration_source": "synthetic",
        "confidence_level": CONFIDENCE_LEVEL,
    }
    for case in invalid_direct_shocks:
        kwargs = {**base, **{key: value for key, value in case.items() if key != "match"}}
        with pytest.raises((TypeError, ValueError), match=str(case["match"])):
            NMRFDirectShockSpec(**kwargs)  # type: ignore[arg-type]


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
    grid = NMRFStepwiseShockGrid(
        shock_points=[-1.0, 0.0, 1.0],
        shock_unit="spread_bps",
        calibration_source="synthetic",
        path_dependent=True,
        require_monotonic_loss_check=False,
        notes="unit test",
    )

    assert grid.as_dict()["shock_count"] == 3
    assert grid.as_dict()["path_dependent"] is True

    with pytest.raises(ValueError, match="one-dimensional"):
        NMRFStepwiseShockGrid(
            shock_points=np.array([[0.0, 1.0]]),
            shock_unit="spread_bps",
            calibration_source="synthetic",
        )
    with pytest.raises(ValueError, match="finite"):
        NMRFStepwiseShockGrid(
            shock_points=[0.0, float("nan")],
            shock_unit="spread_bps",
            calibration_source="synthetic",
        )
    with pytest.raises(ValueError, match="non-empty"):
        NMRFStepwiseShockGrid(
            shock_points=[],
            shock_unit="spread_bps",
            calibration_source="synthetic",
        )
    with pytest.raises(ValueError, match="at least two"):
        NMRFStepwiseShockGrid(
            shock_points=[0.0],
            shock_unit="spread_bps",
            calibration_source="synthetic",
        )
    with pytest.raises(ValueError, match="strictly monotonic"):
        NMRFStepwiseShockGrid(
            shock_points=[-100.0, 100.0, 0.0],
            shock_unit="spread_bps",
            calibration_source="synthetic",
        )

    with pytest.raises(ValueError, match="duplicates"):
        NMRFStepwiseShockGrid(
            shock_points=[0.0, 100.0, 100.0],
            shock_unit="spread_bps",
            calibration_source="synthetic",
        )
    with pytest.raises(ValueError, match="shock_unit"):
        NMRFStepwiseShockGrid(
            shock_points=[0.0, 100.0],
            shock_unit="",
            calibration_source="synthetic",
        )
    with pytest.raises(ValueError, match="calibration_source"):
        NMRFStepwiseShockGrid(
            shock_points=[0.0, 100.0],
            shock_unit="spread_bps",
            calibration_source="",
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
    assert spec.full_revaluation.as_dict()["market_state_count"] == 2

    with pytest.raises(ValueError, match="scenario_set_id"):
        NMRFFullRevaluationSpec(
            scenario_set_id="",
            market_state_ids=("ms-1",),
            calibration_source="synthetic market-state replay",
        )
    with pytest.raises(ValueError, match="market_state_ids must be non-empty"):
        NMRFFullRevaluationSpec(
            scenario_set_id="synthetic-full-reval",
            market_state_ids=(),
            calibration_source="synthetic market-state replay",
        )
    with pytest.raises(ValueError, match="empty values"):
        NMRFFullRevaluationSpec(
            scenario_set_id="synthetic-full-reval",
            market_state_ids=("ms-1", ""),
            calibration_source="synthetic market-state replay",
        )
    with pytest.raises(ValueError, match="duplicates"):
        NMRFFullRevaluationSpec(
            scenario_set_id="synthetic-full-reval",
            market_state_ids=("ms-1", "ms-1"),
            calibration_source="synthetic market-state replay",
        )
    with pytest.raises(ValueError, match="calibration_source"):
        NMRFFullRevaluationSpec(
            scenario_set_id="synthetic-full-reval",
            market_state_ids=("ms-1",),
            calibration_source="",
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
    assert spec.max_loss_fallback.as_dict()["candidate_scenario_count"] == 2

    with pytest.raises(ValueError, match="candidate_scenario_ids"):
        NMRFMaxLossFallbackSpec(candidate_scenario_ids=(), loss_source="synthetic")
    with pytest.raises(ValueError, match="loss_source"):
        NMRFMaxLossFallbackSpec(candidate_scenario_ids=("candidate-1",), loss_source="")


def test_bulk_builder_emits_fallback_spec_for_fallback_instruction() -> None:
    fallback_spec = NMRFMaxLossFallbackSpec(
        candidate_scenario_ids=("candidate-1", "candidate-2"),
        loss_source="synthetic candidate-loss inventory",
    )
    specs = build_nmrf_valuation_specs(
        (_instruction(method=NMRFStressMethod.MAX_LOSS_FALLBACK),),
        {"HY_CREDIT_SPD": RiskClass.CSR},
        {RiskClass.CSR: _stress_period()},
        get_policy(),
        max_loss_fallbacks={"HY_CREDIT_SPD": fallback_spec},
    )

    assert len(specs) == 1
    assert specs[0].max_loss_fallback == fallback_spec
    assert specs[0].direct_shock is None


def test_valuation_spec_validates_identity_and_payload_consistency() -> None:
    direct = NMRFDirectShockSpec(
        shock_size=350.0,
        shock_unit="spread_bps",
        direction=NMRFShockDirection.UP,
        calibration_source="synthetic",
        confidence_level=CONFIDENCE_LEVEL,
    )
    stepwise = NMRFStepwiseShockGrid(
        shock_points=[0.0, 100.0],
        shock_unit="spread_bps",
        calibration_source="synthetic",
    )

    base = {
        "risk_factor_name": "HY_CREDIT_SPD",
        "modellability_status": ModellabilityStatus.TYPE_A_NMRF,
        "risk_class": RiskClass.CSR,
        "method": NMRFStressMethod.DIRECT,
        "required_liquidity_horizon": LiquidityHorizon.LH20,
        "stress_period": _stress_period(),
        "direct_shock": direct,
        "source": "synthetic",
    }

    invalid_cases = (
        {"risk_factor_name": "", "match": "risk_factor_name"},
        {"modellability_status": ModellabilityStatus.MODELLABLE, "match": "only valid for NMRFs"},
        {"risk_class": "CSR", "match": "RiskClass"},
        {"method": "DIRECT", "match": "NMRFStressMethod"},
        {"required_liquidity_horizon": 20, "match": "LiquidityHorizon"},
        {"required_liquidity_horizon": LiquidityHorizon.LH10, "match": "at least 20"},
        {"stress_period": object(), "match": "stress_period"},
        {"source": "", "match": "source"},
        {"stepwise_grid": stepwise, "match": "unexpected payloads"},
    )
    for case in invalid_cases:
        kwargs = {**base, **{key: value for key, value in case.items() if key != "match"}}
        with pytest.raises((TypeError, ValueError), match=str(case["match"])):
            NMRFValuationSpec(**kwargs)  # type: ignore[arg-type]


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
                confidence_level=CONFIDENCE_LEVEL,
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


def test_bulk_spec_builder_rejects_empty_instruction_sequence() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        build_nmrf_valuation_specs(
            (),
            {"HY_CREDIT_SPD": RiskClass.CSR},
            {RiskClass.CSR: _stress_period()},
            get_policy(),
        )


def test_bulk_spec_builder_reports_missing_stress_period_and_wrapped_payload_errors() -> None:
    with pytest.raises(NMRFStressSpecError, match="missing stress period"):
        build_nmrf_valuation_specs(
            (_instruction(),),
            {"HY_CREDIT_SPD": RiskClass.CSR},
            {},
            get_policy(),
        )

    with pytest.raises(NMRFStressSpecError, match="invalid valuation spec"):
        build_nmrf_valuation_specs(
            (_instruction(),),
            {"HY_CREDIT_SPD": RiskClass.CSR},
            {RiskClass.CSR: _stress_period()},
            get_policy(),
        )


def test_bulk_spec_builder_rejects_duplicate_instructions() -> None:
    direct_shock = NMRFDirectShockSpec(
        shock_size=350.0,
        shock_unit="spread_bps",
        direction=NMRFShockDirection.UP,
        calibration_source="synthetic",
        confidence_level=CONFIDENCE_LEVEL,
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


def test_spec_builder_supports_ecb_profile_without_type_a_type_b_taxonomy_gate() -> None:
    spec = build_nmrf_valuation_spec(
        _instruction(),
        RiskClass.CSR,
        _stress_period(),
        get_policy(RegulatoryRegime.ECB_CRR3),
        direct_shock=NMRFDirectShockSpec(
            shock_size=350.0,
            shock_unit="spread_bps",
            direction=NMRFShockDirection.UP,
            calibration_source="synthetic",
            confidence_level=CONFIDENCE_LEVEL,
        ),
    )
    assert spec.risk_factor_name == "HY_CREDIT_SPD"


def test_linear_sensitivity_is_not_a_valuation_run_spec() -> None:
    with pytest.raises(ValueError, match="LINEAR_SENSITIVITY"):
        build_nmrf_valuation_spec(
            _instruction(method=NMRFStressMethod.LINEAR_SENSITIVITY),
            RiskClass.CSR,
            _stress_period(),
            get_policy(),
        )


def test_spec_builder_rejects_invalid_instruction_type() -> None:
    with pytest.raises(TypeError, match="NMRFValuationInstruction"):
        build_nmrf_valuation_spec(  # type: ignore[arg-type]
            "invalid-instruction",
            RiskClass.CSR,
            _stress_period(),
            get_policy(),
        )


def test_required_mapping_helpers_reject_empty_specs() -> None:
    with pytest.raises(ValueError, match="specs"):
        required_methods_from_valuation_specs(())
    with pytest.raises(ValueError, match="specs"):
        required_liquidity_horizons_from_valuation_specs(())


def test_required_mapping_helpers_support_single_spec() -> None:
    spec = build_nmrf_valuation_spec(
        _instruction(),
        RiskClass.CSR,
        _stress_period(),
        get_policy(),
        direct_shock=NMRFDirectShockSpec(
            shock_size=350.0,
            shock_unit="spread_bps",
            direction=NMRFShockDirection.UP,
            calibration_source="synthetic",
            confidence_level=CONFIDENCE_LEVEL,
        ),
    )
    assert required_methods_from_valuation_specs((spec,)) == {
        "HY_CREDIT_SPD": NMRFStressMethod.DIRECT
    }
    assert required_liquidity_horizons_from_valuation_specs((spec,)) == {
        "HY_CREDIT_SPD": LiquidityHorizon.LH20
    }
