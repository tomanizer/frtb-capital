"""Tests for NMRF SES module."""

import math

import pytest

from frtb_ima.nmrf import (
    NMRFStressMethod,
    aggregate_ses,
    aggregate_ses_breakdown,
    aggregate_ses_type_a,
    aggregate_ses_type_b,
    nmrf_stress_result_from_external_ses,
    nmrf_stress_result_from_linear_sensitivity,
    require_nmrf_stress_generation_supported,
    ses_for_nmrf_linear,
    ses_values_from_stress_results,
)
from frtb_ima.regimes import UnsupportedRegulatoryFeature, get_policy


def test_ses_linear_basic() -> None:
    assert ses_for_nmrf_linear(100.0, 0.05) == pytest.approx(5.0)


def test_ses_linear_negative_sensitivity() -> None:
    # Short position — abs(sensitivity) used
    assert ses_for_nmrf_linear(-200.0, 0.03) == pytest.approx(6.0)


def test_ses_linear_negative_shock() -> None:
    assert ses_for_nmrf_linear(100.0, -0.05) == pytest.approx(5.0)


def test_ses_linear_zero() -> None:
    assert ses_for_nmrf_linear(0.0, 0.10) == pytest.approx(0.0)


def test_nmrf_stress_result_from_linear_sensitivity_is_labelled_prototype() -> None:
    result = nmrf_stress_result_from_linear_sensitivity(
        "EXOTIC_RF",
        sensitivity=-200.0,
        shock=0.03,
        source="synthetic",
    )

    assert result.method == NMRFStressMethod.LINEAR_SENSITIVITY
    assert result.ses == pytest.approx(6.0)
    assert result.generated_by_prototype is True
    assert result.as_dict()["method"] == "LINEAR_SENSITIVITY"


def test_nmrf_stress_result_from_external_ses_records_upstream_method() -> None:
    result = nmrf_stress_result_from_external_ses(
        "EXOTIC_RF",
        ses=125.0,
        method=NMRFStressMethod.FULL_REVALUATION,
        source="upstream risk engine",
        notes="synthetic fixture",
    )

    assert result.method == NMRFStressMethod.FULL_REVALUATION
    assert result.ses == pytest.approx(125.0)
    assert result.generated_by_prototype is False
    assert result.source == "upstream risk engine"


def test_nmrf_stress_result_rejects_invalid_inputs() -> None:
    with pytest.raises(ValueError, match="risk_factor_name"):
        nmrf_stress_result_from_external_ses(
            "",
            ses=1.0,
            method=NMRFStressMethod.DIRECT,
            source="upstream",
        )
    with pytest.raises(ValueError, match="ses"):
        nmrf_stress_result_from_external_ses(
            "EXOTIC_RF",
            ses=-1.0,
            method=NMRFStressMethod.DIRECT,
            source="upstream",
        )


def test_nmrf_stress_generation_gates_unsupported_methods() -> None:
    policy = get_policy()

    require_nmrf_stress_generation_supported(
        NMRFStressMethod.LINEAR_SENSITIVITY,
        policy,
    )
    with pytest.raises(UnsupportedRegulatoryFeature, match="full_revaluation"):
        require_nmrf_stress_generation_supported(
            NMRFStressMethod.FULL_REVALUATION,
            policy,
        )


def test_ses_values_from_stress_results_extracts_vector_input() -> None:
    results = (
        nmrf_stress_result_from_linear_sensitivity("RF1", 100.0, 0.1),
        nmrf_stress_result_from_external_ses(
            "RF2",
            20.0,
            NMRFStressMethod.DIRECT,
            source="upstream",
        ),
    )

    assert ses_values_from_stress_results(results) == pytest.approx((10.0, 20.0))


def test_aggregate_ses_type_a_zero_correlation_root_sum_squares() -> None:
    values = [10.0, 20.0, 30.0]
    assert aggregate_ses_type_a(values) == pytest.approx(math.sqrt(10**2 + 20**2 + 30**2))


def test_aggregate_ses_type_a_empty() -> None:
    assert aggregate_ses_type_a([]) == pytest.approx(0.0)


def test_aggregate_ses_type_b_rho_zero() -> None:
    # rho=0: fully diversified -> sqrt(sum of squares)
    values = [3.0, 4.0]
    result = aggregate_ses_type_b(values, rho=0.0)
    assert result == pytest.approx(5.0)  # sqrt(9 + 16)


def test_aggregate_ses_type_b_rho_one() -> None:
    # rho=1: fully correlated -> linear sum
    values = [3.0, 4.0]
    result = aggregate_ses_type_b(values, rho=1.0)
    assert result == pytest.approx(7.0)


def test_aggregate_ses_type_b_default_rho() -> None:
    values = [10.0, 10.0]
    rho = 0.36
    expected = math.sqrt(rho * 20**2 + (1 - rho) * (10**2 + 10**2))
    result = aggregate_ses_type_b(values)
    assert result == pytest.approx(expected, rel=1e-9)


def test_aggregate_ses_type_b_invalid_rho() -> None:
    with pytest.raises(ValueError, match="rho"):
        aggregate_ses_type_b([1.0], rho=1.5)


def test_aggregate_ses_type_b_empty() -> None:
    assert aggregate_ses_type_b([]) == pytest.approx(0.0)


def test_aggregate_ses_combines_a_and_b() -> None:
    type_a = [10.0, 20.0]
    type_b = [5.0, 5.0]
    expected = math.sqrt(
        sum(v**2 for v in type_a) + aggregate_ses_type_b(type_b) ** 2
    )
    result = aggregate_ses(type_a, type_b)
    assert result == pytest.approx(expected, rel=1e-9)


def test_aggregate_ses_breakdown_is_vectorized_and_auditable() -> None:
    result = aggregate_ses_breakdown([3.0, 4.0], [10.0, 10.0])
    assert result.type_a_count == 2
    assert result.type_b_count == 2
    assert result.type_a_sum_of_squares == pytest.approx(25.0)
    assert result.type_b_linear_sum == pytest.approx(20.0)
    assert result.total_ses == pytest.approx(aggregate_ses([3.0, 4.0], [10.0, 10.0]))
