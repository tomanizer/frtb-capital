"""Tests for IMA organisation-scope metadata preservation."""

from datetime import date

import pytest
from frtb_common import CalculationScope, CalculationScopeLevel

from frtb_ima.audit import CapitalRunAuditLog, DeskAuditRecord
from frtb_ima.backtesting import BacktestLevelResult, TradingDeskBacktestResult
from frtb_ima.capital import models_based_capital
from frtb_ima.data_contracts import CapitalRunResult, Position, RFETEvidence
from frtb_ima.data_models import (
    DeskCapitalResult,
    LiquidityHorizon,
    ModellabilityStatus,
    RealPriceObservation,
    RiskClass,
    ScenarioPnL,
)
from frtb_ima.nmrf import NMRFStressArtifact, NMRFStressMethod, NMRFStressScenarioResult
from frtb_ima.nmrf_stress_spec import (
    NMRFDirectShockSpec,
    NMRFShockDirection,
    NMRFStressPeriodSpec,
    NMRFValuationSpec,
)
from frtb_ima.org_scope import scope_payload
from frtb_ima.pla import PlaPolicyAssessmentResult, PlaResult, PlaWindowDiagnostics
from frtb_ima.regimes import CalculationContext, RegulatoryRegime, get_policy
from frtb_ima.stress_periods import (
    HistoricalStressSeries,
    StressPeriodCandidate,
    StressSeverityMetric,
)

AS_OF = date(2026, 6, 30)
INPUTS_HASH = "1" * 64


def _scope() -> CalculationScope:
    return CalculationScope(
        level=CalculationScopeLevel.DESK,
        legal_entity_id="LE-US-BANK",
        desk_id="rates-desk",
        volcker_desk_id="volcker-rates",
        book_id="book-rates-01",
        trading_book_id="tb-rates-01",
        model_approval_scope_id="ima-approval-rates",
        metadata={"source": "synthetic-desk-fixture"},
    )


def test_desk_result_and_run_audit_preserve_scope_without_changing_capital() -> None:
    scope = _scope()
    capital = models_based_capital(
        imcc_t_minus_1=100.0,
        ses_t_minus_1=25.0,
        imcc_60d_avg=70.0,
        ses_60d_avg=15.0,
        multiplier=1.5,
    )
    unscoped = DeskCapitalResult(
        desk="rates-desk",
        imcc=100.0,
        ses=25.0,
        models_based_capital=capital.models_based_capital,
        pla_ks_statistic=0.04,
        backtesting_apl_exceptions=1,
        backtesting_hpl_exceptions=2,
    )
    scoped = DeskCapitalResult(
        desk="rates-desk",
        imcc=unscoped.imcc,
        ses=unscoped.ses,
        models_based_capital=unscoped.models_based_capital,
        pla_ks_statistic=unscoped.pla_ks_statistic,
        backtesting_apl_exceptions=unscoped.backtesting_apl_exceptions,
        backtesting_hpl_exceptions=unscoped.backtesting_hpl_exceptions,
        org_scope=scope,
    )

    assert unscoped.models_based_capital == pytest.approx(scoped.models_based_capital)
    assert "org_scope" not in unscoped.as_dict()
    scoped_payload = scoped.as_dict()
    assert scoped_payload["org_scope"]["desk_id"] == "rates-desk"  # type: ignore[index]
    assert scoped_payload["org_scope"]["model_approval_scope_id"] == "ima-approval-rates"  # type: ignore[index]

    run_result = CapitalRunResult(
        as_of_date=AS_OF,
        regime=RegulatoryRegime.FED_NPR_2_0,
        desk_results={"rates-desk": scoped},
        total_market_risk_capital=scoped.models_based_capital,
        calculation_scope=scope,
    )
    run_payload = run_result.as_dict()
    assert run_payload["calculation_scope"]["trading_book_id"] == "tb-rates-01"  # type: ignore[index]
    assert run_payload["desk_results"]["rates-desk"]["org_scope"]["book_id"] == "book-rates-01"  # type: ignore[index]

    audit_record = DeskAuditRecord(
        run_id="ima-run-1",
        desk_id="rates-desk",
        regime="FED_NPR_2_0",
        inputs_hash=INPUTS_HASH,
        imcc={"imcc": 100.0},
        ses={"total_ses": 25.0},
        pla={"zone": "GREEN"},
        backtesting={"model_eligible": True},
        capital=capital.as_dict(),
        elapsed_seconds=0.1,
        org_scope=scope,
    )
    audit_log = CapitalRunAuditLog(
        run_id="ima-run-1",
        regime="FED_NPR_2_0",
        desk_records=(audit_record,),
        calculation_scope=scope,
    )

    assert audit_record.as_dict()["org_scope"]["volcker_desk_id"] == "volcker-rates"  # type: ignore[index]
    assert audit_log.as_dict()["calculation_scope"]["legal_entity_id"] == "LE-US-BANK"  # type: ignore[index]


def test_ima_input_records_preserve_scope_metadata() -> None:
    scope = _scope()
    position = Position(
        position_id="pos-1",
        desk="rates-desk",
        instrument_id="swap-1",
        fair_value=10.0,
        currency="USD",
        risk_factor_names=("USD-SOFR",),
        org_scope=scope,
    )
    rfet = RFETEvidence(
        risk_factor_name="USD-SOFR",
        as_of_date=AS_OF,
        observations=(
            RealPriceObservation(
                risk_factor_name="USD-SOFR",
                observation_date=AS_OF,
                source="synthetic",
            ),
        ),
        qualitative_pass=True,
        org_scope=scope,
    )
    scenario_pnl = ScenarioPnL(desk="rates-desk", org_scope=scope).add_vector(
        RiskClass.GIRR,
        LiquidityHorizon.LH10,
        [1.0, 2.0, 3.0],
    )

    assert position.org_scope is scope
    assert rfet.org_scope is scope
    assert scenario_pnl.org_scope is scope


def test_pla_and_backtesting_evidence_preserve_scope_metadata() -> None:
    scope = _scope()
    backtesting = TradingDeskBacktestResult(
        levels=(
            BacktestLevelResult(
                confidence_level=0.99,
                apl_exceptions=1,
                hpl_exceptions=2,
                exception_limit=10,
                apl_passed=True,
                hpl_passed=True,
                level_passed=True,
                window_size=250,
            ),
        ),
        window_size=250,
        model_eligible=True,
        org_scope=scope,
    )
    pla = PlaPolicyAssessmentResult(
        pla=PlaResult(ks_statistic=0.04, zone="GREEN", n_hpl=250, n_rtpl=250, org_scope=scope),
        diagnostics=PlaWindowDiagnostics(
            available_observations=260,
            minimum_history=250,
            window_size=250,
            start_index=10,
            end_index_exclusive=260,
            org_scope=scope,
        ),
        org_scope=scope,
    )

    assert backtesting.as_dict()["org_scope"]["desk_id"] == "rates-desk"  # type: ignore[index]
    assert pla.as_dict()["org_scope"]["book_id"] == "book-rates-01"  # type: ignore[index]


def test_nmrf_evidence_preserves_scope_metadata() -> None:
    scope = _scope()
    stress_period = NMRFStressPeriodSpec(
        stress_period_id="stress-2008",
        calibration_source="synthetic",
        org_scope=scope,
    )
    valuation_spec = NMRFValuationSpec(
        risk_factor_name="USD-SOFR-NMRF",
        modellability_status=ModellabilityStatus.TYPE_A_NMRF,
        risk_class=RiskClass.GIRR,
        method=NMRFStressMethod.DIRECT,
        required_liquidity_horizon=LiquidityHorizon.LH20,
        stress_period=stress_period,
        direct_shock=NMRFDirectShockSpec(
            shock_size=0.01,
            shock_unit="rate",
            direction=NMRFShockDirection.UP,
            calibration_source="synthetic",
            confidence_level=0.975,
        ),
        source="synthetic",
        org_scope=scope,
    )
    stress_artifact = NMRFStressArtifact(
        risk_factor_name="USD-SOFR-NMRF",
        method=NMRFStressMethod.DIRECT,
        losses=[1.0, 1.5, 0.8],
        liquidity_horizon=LiquidityHorizon.LH20,
        stress_period="stress-2008",
        source="synthetic",
        org_scope=scope,
    )
    stress_result = NMRFStressScenarioResult(
        risk_factor_name="USD-SOFR-NMRF",
        method=NMRFStressMethod.DIRECT,
        ses=1.5,
        generated_by_prototype=False,
        source="synthetic",
        org_scope=scope,
    )

    assert valuation_spec.as_dict()["org_scope"]["model_approval_scope_id"] == "ima-approval-rates"  # type: ignore[index]
    assert stress_artifact.as_dict()["org_scope"]["trading_book_id"] == "tb-rates-01"  # type: ignore[index]
    assert stress_result.as_dict()["org_scope"]["desk_id"] == "rates-desk"  # type: ignore[index]


def test_stress_period_evidence_preserves_scope_metadata() -> None:
    scope = _scope()
    historical_series = HistoricalStressSeries(
        risk_class=RiskClass.GIRR,
        losses=[1.0, 2.0, 3.0],
        dates=(date(2007, 1, 1), date(2007, 1, 2), date(2007, 1, 3)),
        source="synthetic",
        org_scope=scope,
    )
    candidate = StressPeriodCandidate(
        risk_class=RiskClass.GIRR,
        period_id="stress-2008",
        start_date=date(2007, 1, 1),
        end_date=date(2007, 1, 3),
        start_index=0,
        end_index_exclusive=3,
        observation_count=3,
        severity_score=2.0,
        severity_metric=StressSeverityMetric.EXPECTED_SHORTFALL,
        confidence_level=0.975,
        es_estimator=get_policy().es_estimator,
        source="synthetic",
        start_scenario_id="s1",
        end_scenario_id="s3",
        org_scope=scope,
    )

    assert historical_series.as_dict()["org_scope"]["legal_entity_id"] == "LE-US-BANK"  # type: ignore[index]
    assert candidate.to_nmrf_stress_period_spec().org_scope is scope


def test_scope_fields_reject_non_scope_objects() -> None:
    with pytest.raises(TypeError, match=r"CalculationContext\.calculation_scope"):
        CalculationContext(
            policy=get_policy(RegulatoryRegime.FED_NPR_2_0),
            as_of_date=AS_OF,
            calculation_scope="desk",  # type: ignore[arg-type]
        )

    with pytest.raises(TypeError, match=r"DeskCapitalResult\.org_scope"):
        DeskCapitalResult(
            desk="rates-desk",
            imcc=1.0,
            ses=2.0,
            models_based_capital=3.0,
            pla_ks_statistic=0.0,
            backtesting_apl_exceptions=0,
            backtesting_hpl_exceptions=0,
            org_scope="desk",  # type: ignore[arg-type]
        )


def test_scope_payload_returns_fresh_payload_not_mutated_by_callers() -> None:
    scope = _scope()
    payload = scope_payload(scope)
    assert payload is not None
    payload["desk_id"] = "mutated"
    payload["metadata"]["source"] = "mutated"  # type: ignore[index]

    fresh_payload = scope_payload(scope)
    assert fresh_payload["desk_id"] == "rates-desk"  # type: ignore[index]
    assert fresh_payload["metadata"]["source"] == "synthetic-desk-fixture"  # type: ignore[index]
