from __future__ import annotations

import re
from dataclasses import FrozenInstanceError, replace
from datetime import date

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_sbm import (
    SbmCalculationContext,
    SbmCapitalResult,
    SbmInputError,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmScenarioLabel,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    calculate_sbm_capital,
)


def sample_lineage(row_id: str) -> SbmSourceLineage:
    return SbmSourceLineage(
        source_system="synthetic-risk",
        source_file="sbm.csv",
        source_row_id=row_id,
        source_column_map=(("DeltaUSD", "amount"),),
    )


def sample_sensitivity(
    *,
    sensitivity_id: str,
    source_row_id: str,
    bucket: str,
    risk_factor: str,
    tenor: str,
    amount: float,
    desk_id: str = "rates-desk",
    legal_entity: str = "LE-001",
) -> SbmSensitivity:
    return SbmSensitivity(
        sensitivity_id=sensitivity_id,
        source_row_id=source_row_id,
        desk_id=desk_id,
        legal_entity=legal_entity,
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket=bucket,
        risk_factor=risk_factor,
        amount=amount,
        amount_currency="USD",
        tenor=tenor,
        sign_convention=SbmSignConvention.RECEIVE,
        lineage=sample_lineage(source_row_id),
    )


def sample_context(
    profile: SbmRegulatoryProfile = SbmRegulatoryProfile.BASEL_MAR21,
) -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id="sbm-run-001",
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=profile.value,
    )


def test_calculate_sbm_capital_returns_public_result_for_supported_inputs() -> None:
    result = calculate_sbm_capital(
        (
            sample_sensitivity(
                sensitivity_id="eur-1y",
                source_row_id="row-001",
                bucket="1",
                risk_factor="EUR",
                tenor="1y",
                amount=1_000_000.0,
            ),
            sample_sensitivity(
                sensitivity_id="eur-5y",
                source_row_id="row-002",
                bucket="1",
                risk_factor="EUR",
                tenor="5y",
                amount=500_000.0,
            ),
            sample_sensitivity(
                sensitivity_id="usd-5y",
                source_row_id="row-003",
                bucket="2",
                risk_factor="USD",
                tenor="5y",
                amount=800_000.0,
            ),
        ),
        context=sample_context(),
    )

    assert isinstance(result, SbmCapitalResult)
    assert result.profile_id == "BASEL_MAR21"
    assert re.fullmatch(r"[0-9a-f]{64}", result.profile_hash)
    assert re.fullmatch(r"[0-9a-f]{64}", result.input_hash)
    assert len(result.risk_classes) == 1
    girr = result.risk_classes[0]
    assert girr.risk_class is SbmRiskClass.GIRR
    assert girr.risk_measure is SbmRiskMeasure.DELTA
    assert girr.selected_scenario is not None
    assert girr.scenario_totals is not None
    assert len(girr.buckets) == 2
    assert result.total_capital == girr.selected_capital
    assert result.total_capital == pytest.approx(max(girr.scenario_totals.values()))
    assert result.reconciliation is not None
    assert result.reconciliation.input_count == 3
    assert "SBM-AUDIT-001" in result.reconciliation.requirement_ids

    payload = result.as_dict()
    assert payload["total_capital"] == result.total_capital
    assert payload["profile_id"] == "BASEL_MAR21"
    with pytest.raises(FrozenInstanceError):
        setattr(result, "total_capital", 0.0)


def test_calculate_sbm_capital_requires_context() -> None:
    with pytest.raises(SbmInputError, match="calculation context is required"):
        calculate_sbm_capital(())


def test_calculate_sbm_capital_requires_sensitivities() -> None:
    with pytest.raises(SbmInputError, match="sensitivities are required"):
        calculate_sbm_capital(context=sample_context())


def test_calculate_sbm_capital_validates_context_shape() -> None:
    sensitivity = sample_sensitivity(
        sensitivity_id="eur-1y",
        source_row_id="row-001",
        bucket="1",
        risk_factor="EUR",
        tenor="1y",
        amount=1_000_000.0,
    )

    with pytest.raises(SbmInputError, match="calculation context must be SbmCalculationContext"):
        calculate_sbm_capital((sensitivity,), context=object())  # type: ignore[arg-type]


def test_calculate_sbm_capital_fails_closed_for_unsupported_profile_cells() -> None:
    unsupported = replace(
        sample_sensitivity(
            sensitivity_id="csr-nonsec-delta",
            source_row_id="row-001",
            bucket="4",
            risk_factor="BOND",
            tenor="5y",
            amount=1_000_000.0,
        ),
        risk_class=SbmRiskClass.CSR_NONSEC,
        qualifier="ISS-001",
    )
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="unsupported"):
        calculate_sbm_capital(
            (unsupported,),
            context=sample_context(SbmRegulatoryProfile.PRA_UK_CRR),
        )


def test_calculate_sbm_capital_returns_fx_delta_result() -> None:
    sensitivity = SbmSensitivity(
        sensitivity_id="fx-eur",
        source_row_id="row-fx",
        desk_id="rates-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.FX,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket="EUR",
        risk_factor="EUR",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention=SbmSignConvention.RECEIVE,
        lineage=sample_lineage("row-fx"),
    )

    result = calculate_sbm_capital((sensitivity,), context=sample_context())
    assert result.total_capital > 0.0
    assert result.risk_classes[0].risk_class is SbmRiskClass.FX


def sample_vega_sensitivity(
    *,
    sensitivity_id: str,
    source_row_id: str,
    bucket: str,
    risk_factor: str,
    tenor: str,
    option_tenor: str,
    amount: float,
) -> SbmSensitivity:
    return SbmSensitivity(
        sensitivity_id=sensitivity_id,
        source_row_id=source_row_id,
        desk_id="rates-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.VEGA,
        bucket=bucket,
        risk_factor=risk_factor,
        amount=amount,
        amount_currency="USD",
        tenor=tenor,
        option_tenor=option_tenor,
        sign_convention=SbmSignConvention.RECEIVE,
        lineage=sample_lineage(source_row_id),
    )


def test_calculate_sbm_capital_supports_girr_vega_inputs() -> None:
    result = calculate_sbm_capital(
        (
            sample_vega_sensitivity(
                sensitivity_id="eur-vega",
                source_row_id="row-101",
                bucket="1",
                risk_factor="EUR",
                tenor="1y",
                option_tenor="1y",
                amount=250_000.0,
            ),
        ),
        context=sample_context(),
    )

    assert len(result.risk_classes) == 1
    assert result.risk_classes[0].risk_measure is SbmRiskMeasure.VEGA
    assert result.total_capital == result.risk_classes[0].selected_capital


def test_calculate_sbm_capital_sums_delta_and_vega_measures() -> None:
    result = calculate_sbm_capital(
        (
            sample_sensitivity(
                sensitivity_id="eur-1y",
                source_row_id="row-001",
                bucket="1",
                risk_factor="EUR",
                tenor="1y",
                amount=1_000_000.0,
            ),
            sample_vega_sensitivity(
                sensitivity_id="eur-vega",
                source_row_id="row-101",
                bucket="1",
                risk_factor="EUR",
                tenor="1y",
                option_tenor="1y",
                amount=250_000.0,
            ),
        ),
        context=sample_context(),
    )

    assert len(result.risk_classes) == 2
    measures = {item.risk_measure for item in result.risk_classes}
    assert measures == {SbmRiskMeasure.DELTA, SbmRiskMeasure.VEGA}
    assert result.selected_portfolio_scenario is not None
    assert result.portfolio_scenario_totals is not None
    assert result.total_capital == pytest.approx(
        result.portfolio_scenario_totals[result.selected_portfolio_scenario]
    )
    assert result.total_capital == pytest.approx(
        sum(item.selected_capital for item in result.risk_classes)
    )
    assert all(
        item.selected_scenario is result.selected_portfolio_scenario for item in result.risk_classes
    )


def test_calculate_sbm_capital_selects_max_correlation_scenario() -> None:
    result = calculate_sbm_capital(
        (
            sample_sensitivity(
                sensitivity_id="eur-1y",
                source_row_id="row-001",
                bucket="1",
                risk_factor="EUR",
                tenor="1y",
                amount=1_000_000.0,
            ),
            sample_sensitivity(
                sensitivity_id="usd-5y",
                source_row_id="row-002",
                bucket="2",
                risk_factor="USD",
                tenor="5y",
                amount=800_000.0,
            ),
        ),
        context=sample_context(),
    )
    girr = result.risk_classes[0]
    assert girr.selected_scenario is not None
    assert girr.scenario_totals is not None
    assert girr.selected_scenario == max(
        girr.scenario_totals,
        key=lambda label: girr.scenario_totals[label],
    )
    assert girr.selected_scenario in {
        SbmScenarioLabel.LOW,
        SbmScenarioLabel.MEDIUM,
        SbmScenarioLabel.HIGH,
    }


def test_calculate_sbm_capital_applies_mar21_7_portfolio_scenario_selection() -> None:
    """MAR21.7: sum risk classes by scenario before selecting portfolio total."""
    import importlib.util
    from pathlib import Path

    def _load_fixture(name: str, loader_path: Path):
        spec = importlib.util.spec_from_file_location(name, loader_path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module

    fixture_root = Path(__file__).parent / "fixtures"
    girr_delta = _load_fixture(
        "girr_delta_v1_loader",
        fixture_root / "girr_delta_v1" / "loader.py",
    )
    girr_vega = _load_fixture(
        "girr_vega_v1_loader",
        fixture_root / "girr_vega_v1" / "loader.py",
    )
    fx_delta = _load_fixture(
        "fx_delta_v1_loader",
        fixture_root / "fx_delta_v1" / "loader.py",
    )

    sensitivities = (
        girr_delta.load_fixture_sensitivities()
        + girr_vega.load_fixture_sensitivities()
        + fx_delta.load_fixture_sensitivities()
    )
    result = calculate_sbm_capital(
        sensitivities,
        context=girr_delta.load_fixture_context(),
    )

    assert result.selected_portfolio_scenario is SbmScenarioLabel.HIGH
    assert result.total_capital == pytest.approx(744_280.5750048613)
    assert result.portfolio_scenario_totals is not None
    assert result.portfolio_scenario_totals[SbmScenarioLabel.LOW] == pytest.approx(
        738_059.0463905977
    )
    assert result.portfolio_scenario_totals[SbmScenarioLabel.MEDIUM] == pytest.approx(
        743_026.7984056943
    )
    assert result.portfolio_scenario_totals[SbmScenarioLabel.HIGH] == pytest.approx(
        744_280.5750048613
    )
    assert all(item.selected_scenario is SbmScenarioLabel.HIGH for item in result.risk_classes)
    assert result.portfolio_scenario_selection is not None
    assert result.portfolio_scenario_selection.branch_id == "portfolio_scenario_selection"
