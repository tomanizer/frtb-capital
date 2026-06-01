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
from frtb_sbm.equity_reference_data import (
    EQUITY_OTHER_SECTOR_BUCKET,
    EQUITY_REPO_RISK_FACTOR,
    EQUITY_SAME_ISSUER_SPOT_REPO_CORRELATION,
    EQUITY_SPOT_RISK_FACTOR,
    equity_delta_intra_bucket_correlation,
    equity_delta_risk_weight,
    equity_inter_bucket_correlation,
)
from frtb_sbm.risk_classes.equity import (
    aggregate_equity_delta_measure_capital,
    calculate_equity_delta_risk_class_capital,
)
from frtb_sbm.weighted_sensitivity import weight_equity_delta_sensitivities

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "equity_delta_v1"


def sample_lineage(row_id: str) -> SbmSourceLineage:
    return SbmSourceLineage(
        source_system="synthetic-risk",
        source_file="sbm.csv",
        source_row_id=row_id,
        source_column_map=(("amount", "amount"),),
    )


def sample_equity_sensitivity(
    *,
    sensitivity_id: str,
    source_row_id: str,
    bucket: str,
    risk_factor: str,
    qualifier: str,
    amount: float,
) -> SbmSensitivity:
    return SbmSensitivity(
        sensitivity_id=sensitivity_id,
        source_row_id=source_row_id,
        desk_id="eq-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.EQUITY,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket=bucket,
        risk_factor=risk_factor,
        qualifier=qualifier,
        amount=amount,
        amount_currency="USD",
        sign_convention=SbmSignConvention.LONG,
        lineage=sample_lineage(source_row_id),
    )


def sample_context() -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id="sbm-equity-run",
        calculation_date=date(2026, 5, 30),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )


def load_fixture_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "equity_delta_v1_loader", FIXTURE_DIR / "loader.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_basel_profile_supports_equity_delta() -> None:
    assert profile_supports_risk_class_measure(
        SbmRegulatoryProfile.BASEL_MAR21,
        SbmRiskClass.EQUITY,
        SbmRiskMeasure.DELTA,
    )


def test_equity_delta_risk_weight_applies_spot_and_repo_weights() -> None:
    spot_weight, spot_citations = equity_delta_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket_id="5",
        risk_factor=EQUITY_SPOT_RISK_FACTOR,
    )
    repo_weight, repo_citations = equity_delta_risk_weight(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket_id="5",
        risk_factor=EQUITY_REPO_RISK_FACTOR,
    )

    assert spot_weight == pytest.approx(0.30)
    assert repo_weight == pytest.approx(0.0030)
    assert spot_citations == ("basel_mar21_77",)
    assert repo_citations == ("basel_mar21_77",)


def test_equity_delta_intra_bucket_correlation_same_issuer_spot_repo() -> None:
    correlation, citations = equity_delta_intra_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket_id="5",
        risk_factor_a=EQUITY_SPOT_RISK_FACTOR,
        risk_factor_b=EQUITY_REPO_RISK_FACTOR,
        issuer_a="ISS-A",
        issuer_b="ISS-A",
    )

    assert correlation == pytest.approx(EQUITY_SAME_ISSUER_SPOT_REPO_CORRELATION)
    assert citations == ("basel_mar21_78",)


def test_equity_delta_intra_bucket_correlation_same_issuer_same_factor_is_one() -> None:
    correlation, citations = equity_delta_intra_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket_id="5",
        risk_factor_a=EQUITY_SPOT_RISK_FACTOR,
        risk_factor_b=EQUITY_SPOT_RISK_FACTOR,
        issuer_a="ISS-A",
        issuer_b="ISS-A",
    )

    assert correlation == pytest.approx(1.0)
    assert citations == ("basel_mar21_78",)


def test_equity_delta_intra_bucket_correlation_cross_issuer_spot() -> None:
    correlation, citations = equity_delta_intra_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket_id="5",
        risk_factor_a=EQUITY_SPOT_RISK_FACTOR,
        risk_factor_b=EQUITY_SPOT_RISK_FACTOR,
        issuer_a="ISS-A",
        issuer_b="ISS-B",
    )

    assert correlation == pytest.approx(0.25)
    assert citations == ("basel_mar21_78",)


def test_equity_inter_bucket_correlation_other_sector_is_zero() -> None:
    correlation, citations = equity_inter_bucket_correlation(
        SbmRegulatoryProfile.BASEL_MAR21,
        bucket1="5",
        bucket2=EQUITY_OTHER_SECTOR_BUCKET,
    )

    assert correlation == pytest.approx(0.0)
    assert citations == ("basel_mar21_80",)


def test_weight_equity_delta_sensitivities_preserves_citations() -> None:
    weighted = weight_equity_delta_sensitivities(
        (
            sample_equity_sensitivity(
                sensitivity_id="eq5-spot-a",
                source_row_id="row-001",
                bucket="5",
                risk_factor=EQUITY_SPOT_RISK_FACTOR,
                qualifier="ISS-A",
                amount=1_000_000.0,
            ),
        ),
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )

    assert len(weighted) == 1
    assert weighted[0].risk_weight == pytest.approx(0.30)
    assert "basel_mar21_77" in weighted[0].citation_ids


def test_aggregate_equity_delta_measure_capital_bucket_11_uses_absolute_weights() -> None:
    weighted = weight_equity_delta_sensitivities(
        (
            sample_equity_sensitivity(
                sensitivity_id="eq11-long",
                source_row_id="row-001",
                bucket=EQUITY_OTHER_SECTOR_BUCKET,
                risk_factor=EQUITY_SPOT_RISK_FACTOR,
                qualifier="ISS-X",
                amount=1_000_000.0,
            ),
            sample_equity_sensitivity(
                sensitivity_id="eq11-short",
                source_row_id="row-002",
                bucket=EQUITY_OTHER_SECTOR_BUCKET,
                risk_factor=EQUITY_SPOT_RISK_FACTOR,
                qualifier="ISS-Y",
                amount=-800_000.0,
            ),
        ),
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )
    result = aggregate_equity_delta_measure_capital(
        weighted,
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        issuer_by_id={
            "eq11-long": "ISS-X",
            "eq11-short": "ISS-Y",
        },
        risk_factor_by_id={
            "eq11-long": EQUITY_SPOT_RISK_FACTOR,
            "eq11-short": EQUITY_SPOT_RISK_FACTOR,
        },
    )
    bucket_11 = next(
        bucket for bucket in result.buckets if bucket.bucket_id == EQUITY_OTHER_SECTOR_BUCKET
    )

    assert bucket_11.kb == pytest.approx(1_260_000.0)
    assert bucket_11.sb == pytest.approx(140_000.0)
    assert "basel_mar21_79" in bucket_11.citation_ids


def test_calculate_equity_delta_risk_class_capital_reconciles() -> None:
    sensitivities = (
        sample_equity_sensitivity(
            sensitivity_id="eq5-spot-a",
            source_row_id="row-001",
            bucket="5",
            risk_factor=EQUITY_SPOT_RISK_FACTOR,
            qualifier="ISS-A",
            amount=2_000_000.0,
        ),
        sample_equity_sensitivity(
            sensitivity_id="eq6-spot-c",
            source_row_id="row-002",
            bucket="6",
            risk_factor=EQUITY_SPOT_RISK_FACTOR,
            qualifier="ISS-C",
            amount=1_500_000.0,
        ),
    )
    result = calculate_equity_delta_risk_class_capital(
        sensitivities,
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )

    assert result.risk_class is SbmRiskClass.EQUITY
    assert result.risk_measure is SbmRiskMeasure.DELTA
    assert result.selected_capital == pytest.approx(max(result.scenario_totals.values()))
    assert len(result.buckets) == 2


def test_calculate_sbm_capital_returns_equity_delta_result() -> None:
    result = calculate_sbm_capital(
        (
            sample_equity_sensitivity(
                sensitivity_id="eq5-spot-a",
                source_row_id="row-001",
                bucket="5",
                risk_factor=EQUITY_SPOT_RISK_FACTOR,
                qualifier="ISS-A",
                amount=1_000_000.0,
            ),
        ),
        context=sample_context(),
    )

    assert result.total_capital > 0.0
    assert len(result.risk_classes) == 1
    assert result.risk_classes[0].risk_class is SbmRiskClass.EQUITY


def test_equity_vega_fails_closed() -> None:
    sensitivity = SbmSensitivity(
        sensitivity_id="eq-vega",
        source_row_id="row-001",
        desk_id="eq-desk",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.EQUITY,
        risk_measure=SbmRiskMeasure.VEGA,
        bucket="5",
        risk_factor=EQUITY_SPOT_RISK_FACTOR,
        qualifier="ISS-A",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention=SbmSignConvention.LONG,
        lineage=sample_lineage("row-001"),
        option_tenor="1y",
        tenor="1y",
    )
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="phase-1 capital"):
        calculate_sbm_capital((sensitivity,), context=sample_context())


def test_equity_delta_v1_fixture_matches_expected_outputs() -> None:
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
def test_equity_delta_v1_invalid_fixture_cases_fail(
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
