from __future__ import annotations

import importlib.util
import re
from datetime import date
from pathlib import Path
from types import ModuleType

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
    calculate_sbm_capital,
    profile_supports_risk_class_measure,
)
from frtb_sbm.commodity_reference_data import (
    COMMODITY_LOCATION_CORRELATION,
    COMMODITY_TENOR_CORRELATION,
    commodity_delta_intra_bucket_correlation,
    commodity_delta_risk_weight,
    commodity_inter_bucket_correlation,
)
from frtb_sbm.risk_classes.commodity import calculate_commodity_delta_risk_class_capital
from frtb_sbm.weighted_sensitivity import weight_commodity_delta_sensitivities

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "commodity_delta_v1"


def sample_lineage(row_id: str) -> SbmSourceLineage:
    return SbmSourceLineage(
        source_system="synthetic-risk",
        source_file="sbm.csv",
        source_row_id=row_id,
        source_column_map=(("amount", "amount"),),
    )


def sample_commodity_sensitivity(
    *,
    sensitivity_id: str,
    source_row_id: str,
    bucket: str,
    risk_factor: str,
    qualifier: str,
    tenor: str,
    amount: float,
) -> SbmSensitivity:
    return SbmSensitivity(
        sensitivity_id=sensitivity_id,
        source_row_id=source_row_id,
        desk_id="com-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.COMMODITY,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket=bucket,
        risk_factor=risk_factor,
        qualifier=qualifier,
        tenor=tenor,
        amount=amount,
        amount_currency="USD",
        sign_convention=SbmSignConvention.LONG,
        lineage=sample_lineage(source_row_id),
    )


def sample_context() -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id="sbm-commodity-run",
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )


def load_fixture_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "commodity_delta_v1_loader",
        FIXTURE_DIR / "loader.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_basel_profile_supports_commodity_delta() -> None:
    assert profile_supports_risk_class_measure(
        SbmRegulatoryProfile.BASEL_MAR21,
        SbmRiskClass.COMMODITY,
        SbmRiskMeasure.DELTA,
    )


def test_commodity_delta_risk_weight_matches_bucket_table() -> None:
    weight, citations = commodity_delta_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket_id="2",
    )

    assert weight == pytest.approx(0.35)
    assert citations == ("basel_mar21_82",)


def test_commodity_delta_intra_bucket_correlation_same_commodity_different_tenor() -> None:
    correlation, citations = commodity_delta_intra_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket_id="2",
        commodity_a="WTI",
        commodity_b="WTI",
        tenor_a="3m",
        tenor_b="6m",
        location_a="NYMEX",
        location_b="NYMEX",
    )

    assert correlation == pytest.approx(COMMODITY_TENOR_CORRELATION)
    assert citations == ("basel_mar21_83",)


def test_commodity_delta_intra_bucket_correlation_different_commodity_same_bucket() -> None:
    correlation, citations = commodity_delta_intra_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket_id="2",
        commodity_a="WTI",
        commodity_b="BRENT",
        tenor_a="3m",
        tenor_b="3m",
        location_a="NYMEX",
        location_b="ICE",
    )

    assert correlation == pytest.approx(0.95 * COMMODITY_LOCATION_CORRELATION)
    assert citations == ("basel_mar21_83",)


def test_commodity_inter_bucket_correlation_is_twenty_percent() -> None:
    correlation, citations = commodity_inter_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket1="2",
        bucket2="5",
    )

    assert correlation == pytest.approx(0.20)
    assert citations == ("basel_mar21_85",)


def test_weight_commodity_delta_sensitivities_preserves_citations() -> None:
    weighted = weight_commodity_delta_sensitivities(
        (
            sample_commodity_sensitivity(
                sensitivity_id="com2-wti-3m",
                source_row_id="row-001",
                bucket="2",
                risk_factor="WTI",
                qualifier="NYMEX",
                tenor="3m",
                amount=1_000_000.0,
            ),
        ),
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )

    assert len(weighted) == 1
    assert weighted[0].risk_weight == pytest.approx(0.35)
    assert "basel_mar21_82" in weighted[0].citation_ids


def test_calculate_commodity_delta_risk_class_capital_reconciles() -> None:
    sensitivities = (
        sample_commodity_sensitivity(
            sensitivity_id="com2-wti-3m",
            source_row_id="row-001",
            bucket="2",
            risk_factor="WTI",
            qualifier="NYMEX",
            tenor="3m",
            amount=3_000_000.0,
        ),
        sample_commodity_sensitivity(
            sensitivity_id="com5-alu-1y",
            source_row_id="row-002",
            bucket="5",
            risk_factor="ALU",
            qualifier="LME",
            tenor="1y",
            amount=1_500_000.0,
        ),
    )
    result = calculate_commodity_delta_risk_class_capital(
        sensitivities,
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )

    assert result.risk_class is SbmRiskClass.COMMODITY
    assert result.risk_measure is SbmRiskMeasure.DELTA
    assert result.selected_capital == pytest.approx(max(result.scenario_totals.values()))
    assert len(result.buckets) == 2


def test_calculate_sbm_capital_returns_commodity_delta_result() -> None:
    result = calculate_sbm_capital(
        (
            sample_commodity_sensitivity(
                sensitivity_id="com2-wti-3m",
                source_row_id="row-001",
                bucket="2",
                risk_factor="WTI",
                qualifier="NYMEX",
                tenor="3m",
                amount=1_000_000.0,
            ),
        ),
        context=sample_context(),
    )

    assert result.total_capital > 0.0
    assert len(result.risk_classes) == 1
    assert result.risk_classes[0].risk_class is SbmRiskClass.COMMODITY


def test_commodity_vega_and_curvature_fail_closed() -> None:
    for measure in (SbmRiskMeasure.VEGA, SbmRiskMeasure.CURVATURE):
        sensitivity = SbmSensitivity(
            sensitivity_id=f"com-{measure.value.lower()}",
            source_row_id="row-001",
            desk_id="com-desk",
            legal_entity="LE-001",
            risk_class=SbmRiskClass.COMMODITY,
            risk_measure=measure,
            bucket="2",
            risk_factor="WTI",
            qualifier="NYMEX",
            amount=1_000_000.0,
            amount_currency="USD",
            sign_convention=SbmSignConvention.LONG,
            lineage=sample_lineage("row-001"),
            option_tenor="1y" if measure is SbmRiskMeasure.VEGA else None,
            tenor="1y" if measure is SbmRiskMeasure.VEGA else None,
            up_shock_amount=100.0 if measure is SbmRiskMeasure.CURVATURE else None,
            down_shock_amount=-100.0 if measure is SbmRiskMeasure.CURVATURE else None,
        )
        error_match = (
            "curvature capital is unsupported"
            if measure is SbmRiskMeasure.CURVATURE
            else "phase-1 capital"
        )
        with pytest.raises(UnsupportedRegulatoryFeatureError, match=error_match):
            calculate_sbm_capital((sensitivity,), context=sample_context())


def test_commodity_delta_v1_fixture_matches_expected_outputs() -> None:
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
def test_commodity_delta_v1_invalid_fixture_cases_fail(
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
