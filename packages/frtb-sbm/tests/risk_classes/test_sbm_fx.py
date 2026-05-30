from __future__ import annotations

import importlib.util
import re
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_sbm import (
    FX_DELTA_RISK_WEIGHT,
    FX_INTER_BUCKET_CORRELATION,
    SbmCalculationContext,
    SbmInputError,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    calculate_sbm_capital,
    fx_delta_risk_weight,
    fx_inter_bucket_correlation,
    profile_supports_risk_class_measure,
    weight_fx_delta_sensitivities,
)
from frtb_sbm.risk_classes.fx import calculate_fx_delta_risk_class_capital

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "fx_delta_v1"
_SQRT2_REDUCED_WEIGHT = FX_DELTA_RISK_WEIGHT / (2**0.5)


def sample_lineage(row_id: str) -> SbmSourceLineage:
    return SbmSourceLineage(
        source_system="synthetic-risk",
        source_file="sbm.csv",
        source_row_id=row_id,
        source_column_map=(("amount", "amount"),),
    )


def sample_fx_sensitivity(
    *,
    sensitivity_id: str,
    source_row_id: str,
    currency: str,
    amount: float,
) -> SbmSensitivity:
    return SbmSensitivity(
        sensitivity_id=sensitivity_id,
        source_row_id=source_row_id,
        desk_id="fx-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.FX,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket=currency,
        risk_factor=currency,
        amount=amount,
        amount_currency="USD",
        sign_convention=SbmSignConvention.LONG,
        lineage=sample_lineage(source_row_id),
    )


def sample_context() -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id="sbm-fx-run",
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )


def load_fixture_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("fx_delta_v1_loader", FIXTURE_DIR / "loader.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_basel_profile_supports_fx_delta() -> None:
    assert profile_supports_risk_class_measure(
        SbmRegulatoryProfile.BASEL_MAR21,
        SbmRiskClass.FX,
        SbmRiskMeasure.DELTA,
    )


def test_fx_delta_risk_weight_applies_sqrt2_for_specified_pairs() -> None:
    reduced, citations = fx_delta_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21,
        currency="EUR",
        reporting_currency="USD",
    )
    full, full_citations = fx_delta_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21,
        currency="MYR",
        reporting_currency="USD",
    )

    assert reduced == pytest.approx(_SQRT2_REDUCED_WEIGHT)
    assert full == pytest.approx(FX_DELTA_RISK_WEIGHT)
    assert "basel_mar21_88" in citations
    assert "basel_mar21_88" not in full_citations


def test_fx_inter_bucket_correlation_is_sixty_percent() -> None:
    correlation, citations = fx_inter_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket1="EUR",
        bucket2="GBP",
    )

    assert correlation == pytest.approx(FX_INTER_BUCKET_CORRELATION)
    assert citations == ("basel_mar21_89",)


def test_weight_fx_delta_sensitivities_preserves_citations() -> None:
    weighted = weight_fx_delta_sensitivities(
        (
            sample_fx_sensitivity(
                sensitivity_id="eur-usd",
                source_row_id="row-001",
                currency="EUR",
                amount=1_000_000.0,
            ),
        ),
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        reporting_currency="USD",
    )

    assert len(weighted) == 1
    assert weighted[0].risk_weight == pytest.approx(_SQRT2_REDUCED_WEIGHT)
    assert "basel_mar21_87" in weighted[0].citation_ids


def test_calculate_fx_delta_risk_class_capital_reconciles() -> None:
    sensitivities = (
        sample_fx_sensitivity(
            sensitivity_id="eur-usd",
            source_row_id="row-001",
            currency="EUR",
            amount=2_000_000.0,
        ),
        sample_fx_sensitivity(
            sensitivity_id="gbp-usd",
            source_row_id="row-002",
            currency="GBP",
            amount=-1_500_000.0,
        ),
    )
    result = calculate_fx_delta_risk_class_capital(
        sensitivities,
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        reporting_currency="USD",
    )

    assert result.risk_class is SbmRiskClass.FX
    assert result.risk_measure is SbmRiskMeasure.DELTA
    assert result.selected_capital == pytest.approx(max(result.scenario_totals.values()))
    assert len(result.buckets) == 2


def test_calculate_sbm_capital_returns_fx_delta_result() -> None:
    result = calculate_sbm_capital(
        (
            sample_fx_sensitivity(
                sensitivity_id="eur-usd",
                source_row_id="row-001",
                currency="EUR",
                amount=1_000_000.0,
            ),
        ),
        context=sample_context(),
    )

    assert result.total_capital > 0.0
    assert len(result.risk_classes) == 1
    assert result.risk_classes[0].risk_class is SbmRiskClass.FX


def test_fx_vega_and_curvature_fail_closed() -> None:
    for measure in (SbmRiskMeasure.VEGA, SbmRiskMeasure.CURVATURE):
        sensitivity = SbmSensitivity(
            sensitivity_id=f"fx-{measure.value.lower()}",
            source_row_id="row-001",
            desk_id="fx-desk",
            legal_entity="LE-001",
            risk_class=SbmRiskClass.FX,
            risk_measure=measure,
            bucket="EUR",
            risk_factor="EUR",
            amount=1_000_000.0,
            amount_currency="USD",
            sign_convention=SbmSignConvention.LONG,
            lineage=sample_lineage("row-001"),
            option_tenor="1y" if measure is SbmRiskMeasure.VEGA else None,
            tenor="1y" if measure is SbmRiskMeasure.VEGA else None,
            up_shock_amount=100.0 if measure is SbmRiskMeasure.CURVATURE else None,
            down_shock_amount=-100.0 if measure is SbmRiskMeasure.CURVATURE else None,
        )
        with pytest.raises(UnsupportedRegulatoryFeatureError, match="phase-1 capital"):
            calculate_sbm_capital((sensitivity,), context=sample_context())


def test_fx_delta_v1_fixture_matches_expected_outputs() -> None:
    """Replay fx_delta_v1 and assert bit-identical hashes and capital totals.

    Uses raw numeric equality on serialized payloads; no BLAS-dependent paths
    are exercised beyond the existing numpy aggregation kernels.
    """
    loader = load_fixture_module()
    context = loader.load_fixture_context()
    sensitivities = loader.load_fixture_sensitivities()
    expected = loader.load_expected_outputs()

    result = calculate_sbm_capital(sensitivities, context=context)
    payload = result.as_dict()

    assert payload["profile_id"] == expected["profile_id"]
    assert payload["profile_hash"] == expected["profile_hash"]
    assert payload["input_hash"] == expected["input_hash"]
    assert payload["total_capital"] == expected["total_capital"]
    assert payload["warnings"] == expected["warnings"]
    assert re.fullmatch(r"[0-9a-f]{64}", payload["profile_hash"])


@pytest.mark.parametrize(
    ("case_id", "expected_error_match", "sensitivities"),
    load_fixture_module().load_invalid_cases(),
    ids=lambda item: item if isinstance(item, str) else None,
)
def test_fx_delta_v1_invalid_fixture_cases_fail(
    case_id: str,
    expected_error_match: str,
    sensitivities: tuple[object, ...],
) -> None:
    loader = load_fixture_module()
    context = loader.load_fixture_context()

    with pytest.raises(
        (SbmInputError, UnsupportedRegulatoryFeatureError),
        match=expected_error_match,
    ):
        calculate_sbm_capital(sensitivities, context=context)
    assert case_id
