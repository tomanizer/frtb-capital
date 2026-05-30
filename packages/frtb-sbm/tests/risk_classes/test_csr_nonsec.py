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
from frtb_sbm.csr_nonsec_reference_data import (
    CSR_BOND_RISK_FACTOR,
    CSR_CDS_RISK_FACTOR,
    CSR_DIFFERENT_CURVE_CORRELATION,
    CSR_NAME_CORRELATION,
    CSR_OTHER_SECTOR_BUCKET,
    CSR_TENOR_CORRELATION,
    csr_nonsec_delta_intra_bucket_correlation,
    csr_nonsec_delta_risk_weight,
    csr_nonsec_inter_bucket_correlation,
)
from frtb_sbm.risk_classes.csr_nonsec import calculate_csr_nonsec_delta_risk_class_capital
from frtb_sbm.weighted_sensitivity import weight_csr_nonsec_delta_sensitivities

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "csr_nonsec_delta_v1"


def sample_lineage(row_id: str) -> SbmSourceLineage:
    return SbmSourceLineage(
        source_system="synthetic-risk",
        source_file="sbm.csv",
        source_row_id=row_id,
        source_column_map=(("amount", "amount"),),
    )


def sample_csr_sensitivity(
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
        desk_id="credit-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.CSR_NONSEC,
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
        run_id="sbm-csr-nonsec-run",
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )


def load_fixture_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "csr_nonsec_delta_v1_loader",
        FIXTURE_DIR / "loader.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_basel_profile_supports_csr_nonsec_delta() -> None:
    assert profile_supports_risk_class_measure(
        SbmRegulatoryProfile.BASEL_MAR21,
        SbmRiskClass.CSR_NONSEC,
        SbmRiskMeasure.DELTA,
    )


def test_csr_nonsec_delta_risk_weight_matches_bucket_table() -> None:
    weight, citations = csr_nonsec_delta_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket_id="4",
    )

    assert weight == pytest.approx(0.03)
    assert citations == ("basel_mar21_53",)


def test_csr_nonsec_intra_bucket_correlation_name_tenor_and_basis() -> None:
    correlation, citations = csr_nonsec_delta_intra_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket_id="4",
        risk_factor_a=CSR_BOND_RISK_FACTOR,
        risk_factor_b=CSR_CDS_RISK_FACTOR,
        issuer_a="ISS-A",
        issuer_b="ISS-B",
        tenor_a="1y",
        tenor_b="5y",
    )

    expected = CSR_NAME_CORRELATION * CSR_TENOR_CORRELATION * CSR_DIFFERENT_CURVE_CORRELATION
    assert correlation == pytest.approx(expected)
    assert citations == ("basel_mar21_54",)


def test_csr_nonsec_inter_bucket_correlation_uses_table_five() -> None:
    correlation, citations = csr_nonsec_inter_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket1="4",
        bucket2="5",
    )

    assert correlation == pytest.approx(0.20)
    assert citations == ("basel_mar21_57",)


def test_csr_nonsec_inter_bucket_correlation_other_sector_is_zero() -> None:
    correlation, citations = csr_nonsec_inter_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket1="4",
        bucket2=CSR_OTHER_SECTOR_BUCKET,
    )

    assert correlation == pytest.approx(0.00)
    assert citations == ("basel_mar21_57",)


def test_weight_csr_nonsec_delta_sensitivities_preserves_citations() -> None:
    weighted = weight_csr_nonsec_delta_sensitivities(
        (
            sample_csr_sensitivity(
                sensitivity_id="csr4-bond-a-1y",
                source_row_id="row-001",
                bucket="4",
                risk_factor=CSR_BOND_RISK_FACTOR,
                qualifier="ISS-A",
                tenor="1y",
                amount=1_000_000.0,
            ),
        ),
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )

    assert len(weighted) == 1
    assert weighted[0].risk_weight == pytest.approx(0.03)
    assert "basel_mar21_53" in weighted[0].citation_ids


def test_calculate_csr_nonsec_delta_risk_class_capital_reconciles() -> None:
    sensitivities = (
        sample_csr_sensitivity(
            sensitivity_id="csr4-bond-a-1y",
            source_row_id="row-001",
            bucket="4",
            risk_factor=CSR_BOND_RISK_FACTOR,
            qualifier="ISS-A",
            tenor="1y",
            amount=1_000_000.0,
        ),
        sample_csr_sensitivity(
            sensitivity_id="csr5-bond-c-3y",
            source_row_id="row-002",
            bucket="5",
            risk_factor=CSR_BOND_RISK_FACTOR,
            qualifier="ISS-C",
            tenor="3y",
            amount=2_000_000.0,
        ),
    )
    result = calculate_csr_nonsec_delta_risk_class_capital(
        sensitivities,
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )

    assert result.risk_class is SbmRiskClass.CSR_NONSEC
    assert result.risk_measure is SbmRiskMeasure.DELTA
    assert result.selected_capital == pytest.approx(max(result.scenario_totals.values()))
    assert len(result.buckets) == 2


def test_other_sector_bucket_uses_absolute_weight_aggregation() -> None:
    result = calculate_csr_nonsec_delta_risk_class_capital(
        (
            sample_csr_sensitivity(
                sensitivity_id="csr16-bond-x-1y",
                source_row_id="row-001",
                bucket=CSR_OTHER_SECTOR_BUCKET,
                risk_factor=CSR_BOND_RISK_FACTOR,
                qualifier="ISS-X",
                tenor="1y",
                amount=1_000_000.0,
            ),
            sample_csr_sensitivity(
                sensitivity_id="csr16-bond-y-1y",
                source_row_id="row-002",
                bucket=CSR_OTHER_SECTOR_BUCKET,
                risk_factor=CSR_BOND_RISK_FACTOR,
                qualifier="ISS-Y",
                tenor="1y",
                amount=-600_000.0,
            ),
        ),
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )

    bucket_16 = next(item for item in result.buckets if item.bucket_id == CSR_OTHER_SECTOR_BUCKET)
    assert bucket_16.kb == pytest.approx(192_000.0)


def test_calculate_sbm_capital_returns_csr_nonsec_delta_result() -> None:
    result = calculate_sbm_capital(
        (
            sample_csr_sensitivity(
                sensitivity_id="csr4-bond-a-1y",
                source_row_id="row-001",
                bucket="4",
                risk_factor=CSR_BOND_RISK_FACTOR,
                qualifier="ISS-A",
                tenor="1y",
                amount=1_000_000.0,
            ),
        ),
        context=sample_context(),
    )

    assert result.total_capital > 0.0
    assert len(result.risk_classes) == 1
    assert result.risk_classes[0].risk_class is SbmRiskClass.CSR_NONSEC


def test_csr_nonsec_vega_and_curvature_fail_closed() -> None:
    for measure in (SbmRiskMeasure.VEGA, SbmRiskMeasure.CURVATURE):
        sensitivity = SbmSensitivity(
            sensitivity_id=f"csr-{measure.value.lower()}",
            source_row_id="row-001",
            desk_id="credit-desk",
            legal_entity="LE-001",
            risk_class=SbmRiskClass.CSR_NONSEC,
            risk_measure=measure,
            bucket="4",
            risk_factor=CSR_BOND_RISK_FACTOR,
            qualifier="ISS-A",
            amount=1_000_000.0,
            amount_currency="USD",
            sign_convention=SbmSignConvention.LONG,
            lineage=sample_lineage("row-001"),
            option_tenor="1y" if measure is SbmRiskMeasure.VEGA else None,
            tenor="1y" if measure is SbmRiskMeasure.VEGA else None,
            up_shock_amount=100.0 if measure is SbmRiskMeasure.CURVATURE else None,
            down_shock_amount=-100.0 if measure is SbmRiskMeasure.CURVATURE else None,
        )
        with pytest.raises(UnsupportedRegulatoryFeatureError, match="does not support"):
            calculate_sbm_capital((sensitivity,), context=sample_context())


def test_csr_nonsec_delta_v1_fixture_matches_expected_outputs() -> None:
    loader = load_fixture_module()
    context = loader.load_fixture_context()
    sensitivities = loader.load_fixture_sensitivities()
    expected = loader.load_expected_outputs()
    result = calculate_sbm_capital(sensitivities, context=context)

    assert result.profile_id == expected["profile_id"]
    assert result.profile_hash == expected["profile_hash"]
    assert result.input_hash == expected["input_hash"]
    assert result.total_capital == pytest.approx(float(expected["total_capital"]))
    assert (
        result.risk_classes[0].selected_scenario.value
        == expected["risk_classes"][0]["selected_scenario"]
    )


@pytest.mark.parametrize(
    ("case_id", "expected_error_match", "sensitivities"),
    load_fixture_module().load_invalid_cases(),
)
def test_csr_nonsec_delta_v1_invalid_fixture_cases_fail(
    case_id: str,
    expected_error_match: str,
    sensitivities: tuple[SbmSensitivity, ...],
) -> None:
    del case_id
    loader = load_fixture_module()
    context = loader.load_fixture_context()
    with pytest.raises(
        (SbmInputError, UnsupportedRegulatoryFeatureError), match=expected_error_match
    ):
        calculate_sbm_capital(sensitivities, context=context)


def test_csr_nonsec_delta_v1_fixture_result_is_replay_stable() -> None:
    loader = load_fixture_module()
    context = loader.load_fixture_context()
    sensitivities = loader.load_fixture_sensitivities()
    first = calculate_sbm_capital(sensitivities, context=context)
    second = calculate_sbm_capital(sensitivities, context=context)

    assert first.as_dict() == second.as_dict()
    assert re.fullmatch(r"[0-9a-f]{64}", first.input_hash)
