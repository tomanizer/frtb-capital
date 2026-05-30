from __future__ import annotations

from datetime import date

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_sbm import (
    SbmCalculationContext,
    SbmInputError,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    ensure_sbm_capital_paths_supported,
    ensure_sbm_profile_known,
    ensure_sbm_risk_class_measure_supported,
    ensure_sbm_run_supported,
)


def sample_lineage() -> SbmSourceLineage:
    return SbmSourceLineage(
        source_system="synthetic-risk",
        source_file="sbm.csv",
        source_row_id="row-001",
    )


def sample_sensitivity(**overrides: object) -> SbmSensitivity:
    fields = {
        "sensitivity_id": "sens-001",
        "source_row_id": "row-001",
        "desk_id": "rates-desk",
        "legal_entity": "LE-001",
        "risk_class": SbmRiskClass.GIRR,
        "risk_measure": SbmRiskMeasure.DELTA,
        "bucket": "1",
        "risk_factor": "USD",
        "amount": 1_000_000.0,
        "amount_currency": "USD",
        "tenor": "5y",
        "sign_convention": SbmSignConvention.RECEIVE,
        "lineage": sample_lineage(),
    }
    fields.update(overrides)
    return SbmSensitivity(**fields)  # type: ignore[arg-type]


def sample_context(**overrides: object) -> SbmCalculationContext:
    fields = {
        "run_id": "run-001",
        "calculation_date": date(2026, 5, 30),
        "base_currency": "USD",
        "reporting_currency": "USD",
        "profile_id": SbmRegulatoryProfile.US_NPR_2_0.value,
    }
    fields.update(overrides)
    return SbmCalculationContext(**fields)  # type: ignore[arg-type]


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


@pytest.mark.parametrize(
    ("risk_class", "risk_measure"),
    [
        (SbmRiskClass.GIRR, SbmRiskMeasure.DELTA),
        (SbmRiskClass.GIRR, SbmRiskMeasure.VEGA),
        (SbmRiskClass.GIRR, SbmRiskMeasure.CURVATURE),
        (SbmRiskClass.FX, SbmRiskMeasure.DELTA),
        (SbmRiskClass.CSR_NONSEC, SbmRiskMeasure.DELTA),
    ],
)
def test_unsupported_risk_class_measure_paths_fail_closed(
    risk_class: SbmRiskClass,
    risk_measure: SbmRiskMeasure,
) -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="phase-1 capital"):
        ensure_sbm_risk_class_measure_supported(
            SbmRegulatoryProfile.US_NPR_2_0.value,
            risk_class,
            risk_measure,
        )


def test_ensure_sbm_run_supported_rejects_scope_mismatch() -> None:
    context = sample_context(desk_id="rates-desk", legal_entity="LE-001")
    sensitivity = sample_sensitivity(desk_id="fx-desk")

    with pytest.raises(SbmInputError, match="desk_id"):
        ensure_sbm_run_supported(context, (sensitivity,))


def test_ensure_sbm_capital_paths_supported_rejects_non_basel_profile() -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="phase-1 capital is unsupported"):
        ensure_sbm_capital_paths_supported(
            SbmRegulatoryProfile.US_NPR_2_0.value,
            (sample_sensitivity(),),
        )


def test_basel_curvature_measure_reports_curvature_specific_error() -> None:
    curvature = sample_sensitivity(
        risk_measure=SbmRiskMeasure.CURVATURE,
        up_shock_amount=-100.0,
        down_shock_amount=-200.0,
    )
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="curvature capital is unsupported"):
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
