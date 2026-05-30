"""Integration tests for MAR21.7 multi-class portfolio scenario selection."""

from __future__ import annotations

import importlib.util
from functools import cache
from pathlib import Path
from types import ModuleType

import pytest
from frtb_sbm import (
    SbmRiskClass,
    SbmRiskMeasure,
    SbmScenarioLabel,
    calculate_sbm_capital,
    validate_sbm_result_reconciliation,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures"


@cache
def _load_fixture_module(relative_path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"{relative_path.parent.name}_loader",
        relative_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_sensitivities(*fixture_names: str) -> tuple[object, ...]:
    sensitivities: list[object] = []
    for fixture_name in fixture_names:
        loader = _load_fixture_module(FIXTURE_ROOT / fixture_name / "loader.py")
        sensitivities.extend(loader.load_fixture_sensitivities())
    return tuple(sensitivities)


def _load_context(fixture_name: str = "girr_delta_v1") -> object:
    loader = _load_fixture_module(FIXTURE_ROOT / fixture_name / "loader.py")
    return loader.load_fixture_context()


def test_multi_class_girr_and_fx_portfolio_realigns_girr_scenario() -> None:
    """MAR21.7: portfolio LOW wins even though solo GIRR delta would select HIGH."""

    solo_girr = calculate_sbm_capital(
        _load_sensitivities("girr_delta_v1"),
        context=_load_context(),
    )
    solo_fx = calculate_sbm_capital(
        _load_sensitivities("fx_delta_v1"),
        context=_load_context("fx_delta_v1"),
    )
    portfolio = calculate_sbm_capital(
        _load_sensitivities("girr_delta_v1", "fx_delta_v1"),
        context=_load_context(),
    )

    girr_solo = solo_girr.risk_classes[0]
    fx_solo = solo_fx.risk_classes[0]
    assert girr_solo.risk_class is SbmRiskClass.GIRR
    assert fx_solo.risk_class is SbmRiskClass.FX
    assert girr_solo.selected_scenario is SbmScenarioLabel.HIGH
    assert fx_solo.selected_scenario is SbmScenarioLabel.LOW

    assert len(portfolio.risk_classes) == 2
    assert portfolio.selected_portfolio_scenario is SbmScenarioLabel.LOW
    assert portfolio.portfolio_scenario_totals is not None
    assert portfolio.portfolio_scenario_totals[SbmScenarioLabel.LOW] == pytest.approx(
        239_593.95036280624
    )
    assert portfolio.portfolio_scenario_totals[SbmScenarioLabel.HIGH] == pytest.approx(
        196_558.01749969524
    )
    assert portfolio.total_capital == pytest.approx(
        portfolio.portfolio_scenario_totals[SbmScenarioLabel.LOW]
    )

    aligned = {item.risk_class: item for item in portfolio.risk_classes}
    assert aligned[SbmRiskClass.GIRR].selected_scenario is SbmScenarioLabel.LOW
    assert aligned[SbmRiskClass.FX].selected_scenario is SbmScenarioLabel.LOW
    assert aligned[SbmRiskClass.GIRR].selected_capital == pytest.approx(
        girr_solo.scenario_totals[SbmScenarioLabel.LOW]
    )
    assert aligned[SbmRiskClass.GIRR].selected_capital < girr_solo.selected_capital
    assert aligned[SbmRiskClass.FX].selected_capital == pytest.approx(fx_solo.selected_capital)
    assert portfolio.portfolio_scenario_selection is not None
    assert portfolio.portfolio_scenario_selection.branch_id == "portfolio_scenario_selection"
    validate_sbm_result_reconciliation(portfolio)


def test_multi_class_five_delta_risk_classes_share_portfolio_scenario() -> None:
    """Exercise GIRR, FX, equity, commodity, and CSR non-sec in one capital call."""

    sensitivities = _load_sensitivities(
        "girr_delta_v1",
        "fx_delta_v1",
        "equity_delta_v1",
        "commodity_delta_v1",
        "csr_nonsec_delta_v1",
    )
    result = calculate_sbm_capital(sensitivities, context=_load_context())

    risk_classes = {item.risk_class for item in result.risk_classes}
    assert risk_classes == {
        SbmRiskClass.GIRR,
        SbmRiskClass.FX,
        SbmRiskClass.EQUITY,
        SbmRiskClass.COMMODITY,
        SbmRiskClass.CSR_NONSEC,
    }
    assert all(item.risk_measure is SbmRiskMeasure.DELTA for item in result.risk_classes)
    assert result.selected_portfolio_scenario is SbmScenarioLabel.LOW
    assert result.portfolio_scenario_totals is not None
    assert result.portfolio_scenario_totals[SbmScenarioLabel.LOW] == pytest.approx(
        3_042_815.614423092
    )
    assert result.portfolio_scenario_totals[SbmScenarioLabel.MEDIUM] == pytest.approx(
        2_994_202.227386948
    )
    assert result.portfolio_scenario_totals[SbmScenarioLabel.HIGH] == pytest.approx(
        2_942_374.5861144587
    )
    assert result.total_capital == pytest.approx(
        result.portfolio_scenario_totals[result.selected_portfolio_scenario]
    )
    assert all(
        item.selected_scenario is result.selected_portfolio_scenario for item in result.risk_classes
    )
    validate_sbm_result_reconciliation(result)
