from __future__ import annotations

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_sbm import (
    SbmInputError,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    ensure_sbm_capital_paths_supported,
    ensure_sbm_profile_known,
    ensure_sbm_risk_class_measure_supported,
    ensure_sbm_run_supported,
)
from frtb_sbm.capital import _portfolio_scenario_citations

from tests.sbm_fixture_helpers import (
    sample_sbm_context as sample_context,
)
from tests.sbm_fixture_helpers import (
    sample_sbm_sensitivity as sample_sensitivity,
)


@pytest.mark.parametrize(
    "profile",
    [
        SbmRegulatoryProfile.EU_CRR3,
        SbmRegulatoryProfile.PRA_UK_CRR,
    ],
)
def test_known_profiles_are_recognised(profile: SbmRegulatoryProfile) -> None:
    assert ensure_sbm_profile_known(profile.value) is profile


def test_unknown_profile_fails_closed() -> None:
    with pytest.raises(SbmInputError, match="profile_id must be one of"):
        ensure_sbm_profile_known("UNKNOWN_PROFILE")


def test_us_npr_fx_delta_path_is_supported() -> None:
    ensure_sbm_risk_class_measure_supported(
        SbmRegulatoryProfile.US_NPR_2_0.value,
        SbmRiskClass.FX,
        SbmRiskMeasure.DELTA,
    )


def test_ensure_sbm_run_supported_rejects_scope_mismatch() -> None:
    context = sample_context(desk_id="rates-desk", legal_entity="LE-001")
    sensitivity = sample_sensitivity(desk_id="fx-desk")

    with pytest.raises(SbmInputError, match="desk_id"):
        ensure_sbm_run_supported(context, (sensitivity,))


def test_ensure_sbm_capital_paths_supported_accepts_supported_npr_fx_delta() -> None:
    sensitivity = sample_sensitivity(
        risk_class=SbmRiskClass.FX,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket="EUR",
        risk_factor="EUR",
        tenor=None,
    )
    ensure_sbm_capital_paths_supported(
        SbmRegulatoryProfile.US_NPR_2_0.value,
        (sensitivity,),
    )


def test_portfolio_scenario_citations_do_not_fall_back_to_basel() -> None:
    assert _portfolio_scenario_citations(SbmRegulatoryProfile.BASEL_MAR21.value) == (
        "basel_mar21_7_scenario_selection",
    )
    assert _portfolio_scenario_citations(SbmRegulatoryProfile.US_NPR_2_0.value) == (
        "us_npr_91_fr_14952_va7a_correlation_scenarios",
    )
    assert _portfolio_scenario_citations(SbmRegulatoryProfile.EU_CRR3.value) == (
        "eu_crr3_art_325u_correlation_scenarios",
    )
    assert _portfolio_scenario_citations(SbmRegulatoryProfile.PRA_UK_CRR.value) == (
        "pra_uk_crr_art_325u_correlation_scenarios",
    )


def test_basel_fx_curvature_measure_is_supported() -> None:
    curvature = sample_sensitivity(
        risk_class=SbmRiskClass.FX,
        risk_measure=SbmRiskMeasure.CURVATURE,
        up_shock_amount=-100.0,
        down_shock_amount=-200.0,
        tenor="1y",
    )
    ensure_sbm_capital_paths_supported(
        SbmRegulatoryProfile.BASEL_MAR21.value,
        (curvature,),
    )


def test_ensure_sbm_run_supported_skips_sensitivity_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    def _track_validate(_: object) -> tuple[SbmSensitivity, ...]:
        calls.append(True)
        return ()

    monkeypatch.setattr(
        "frtb_sbm.validation.validate_sbm_sensitivities",
        _track_validate,
    )
    context = sample_context(profile_id=SbmRegulatoryProfile.BASEL_MAR21.value)
    ensure_sbm_run_supported(context, (sample_sensitivity(),))
    assert calls == []
