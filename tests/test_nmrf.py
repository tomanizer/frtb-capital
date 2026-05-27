"""Tests for NMRF SES module."""

import math

import numpy as np
import pytest

from frtb_ima.data_models import LiquidityHorizon, ModellabilityStatus
from frtb_ima.nmrf import (
    NMRFStressArtifact,
    NMRFStressMethod,
    aggregate_ses,
    aggregate_ses_breakdown,
    aggregate_ses_breakdown_for_policy,
    aggregate_ses_type_a,
    aggregate_ses_type_b,
    calculate_nmrf_capital_for_policy,
    calculate_nmrf_ses_from_revaluation,
    nmrf_effective_liquidity_horizon,
    nmrf_stress_result_from_external_ses,
    nmrf_stress_result_from_linear_sensitivity,
    require_nmrf_stress_generation_supported,
    route_nmrf_classifications_for_capital,
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


def test_nmrf_stress_generation_gates_max_loss_fallback() -> None:
    with pytest.raises(UnsupportedRegulatoryFeature, match="max_loss"):
        require_nmrf_stress_generation_supported(
            NMRFStressMethod.MAX_LOSS_FALLBACK,
            get_policy(),
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


def test_nmrf_effective_liquidity_horizon_applies_20_day_floor() -> None:
    assert nmrf_effective_liquidity_horizon(LiquidityHorizon.LH10) == (
        LiquidityHorizon.LH20
    )
    assert nmrf_effective_liquidity_horizon(LiquidityHorizon.LH60) == (
        LiquidityHorizon.LH60
    )


def test_stress_artifact_extracts_ses_from_vectorized_revaluation_losses() -> None:
    artifact = NMRFStressArtifact(
        risk_factor_name="EXOTIC_RF",
        method=NMRFStressMethod.FULL_REVALUATION,
        losses=[1.0, 2.0, 100.0, 50.0],
        liquidity_horizon=LiquidityHorizon.LH120,
        stress_period="synthetic-2008",
        source="upstream risk engine",
    )

    result = calculate_nmrf_ses_from_revaluation(artifact, get_policy())

    # Four observations at 97.5% confidence uses the single worst loss.
    assert result.ses == pytest.approx(100.0)
    assert result.method == NMRFStressMethod.FULL_REVALUATION
    assert result.generated_by_prototype is False


def test_stress_artifact_defensively_freezes_loss_vector() -> None:
    original_losses = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    artifact = NMRFStressArtifact(
        risk_factor_name="EXOTIC_RF",
        method=NMRFStressMethod.FULL_REVALUATION,
        losses=original_losses,
        liquidity_horizon=LiquidityHorizon.LH120,
        stress_period="synthetic-stress",
        source="upstream risk engine",
    )

    original_losses[0] = 99.0

    assert artifact.losses.tolist() == pytest.approx([1.0, 2.0, 3.0])
    assert artifact.losses.flags.writeable is False
    with pytest.raises(ValueError, match="read-only"):
        artifact.losses[0] = 10.0


def test_stress_artifact_ses_is_floored_at_zero_for_all_gain_vectors() -> None:
    artifact = NMRFStressArtifact(
        risk_factor_name="EXOTIC_RF",
        method=NMRFStressMethod.DIRECT,
        losses=[-10.0, -5.0, -1.0],
        liquidity_horizon=LiquidityHorizon.LH20,
        stress_period="synthetic-stress",
        source="upstream risk engine",
    )

    result = calculate_nmrf_ses_from_revaluation(artifact, get_policy())

    assert result.ses == pytest.approx(0.0)


def test_max_loss_fallback_artifact_uses_maximum_loss_not_tail_average() -> None:
    artifact = NMRFStressArtifact(
        risk_factor_name="EXOTIC_RF",
        method=NMRFStressMethod.MAX_LOSS_FALLBACK,
        losses=[100.0, 80.0, 60.0, *([0.0] * 97)],
        liquidity_horizon=LiquidityHorizon.LH20,
        stress_period="synthetic-stress",
        source="upstream risk engine",
    )

    result = calculate_nmrf_ses_from_revaluation(artifact, get_policy())

    assert result.ses == pytest.approx(100.0)


def test_stress_artifact_rejects_short_nmrf_liquidity_horizon() -> None:
    with pytest.raises(ValueError, match="at least 20"):
        NMRFStressArtifact(
            risk_factor_name="EXOTIC_RF",
            method=NMRFStressMethod.DIRECT,
            losses=[1.0],
            liquidity_horizon=LiquidityHorizon.LH10,
            stress_period="synthetic-stress",
            source="upstream risk engine",
        )


def test_linear_artifact_requires_explicit_approximation_opt_in() -> None:
    artifact = NMRFStressArtifact(
        risk_factor_name="EXOTIC_RF",
        method=NMRFStressMethod.LINEAR_SENSITIVITY,
        losses=[25.0],
        liquidity_horizon=LiquidityHorizon.LH20,
        stress_period="synthetic-stress",
        source="prototype",
        generated_by_prototype=True,
    )

    with pytest.raises(ValueError, match="approximation-only"):
        calculate_nmrf_ses_from_revaluation(artifact, get_policy())

    result = calculate_nmrf_ses_from_revaluation(
        artifact,
        get_policy(),
        allow_linear_approximation=True,
    )
    assert result.ses == pytest.approx(25.0)


def test_route_nmrf_classifications_for_capital_keeps_type_a_in_imcc_and_ses() -> None:
    routing = route_nmrf_classifications_for_capital(
        {
            "RF_MODELLABLE": ModellabilityStatus.MODELLABLE,
            "RF_TYPE_A": ModellabilityStatus.TYPE_A_NMRF,
            "RF_TYPE_B": ModellabilityStatus.TYPE_B_NMRF,
        },
        get_policy(),
    )

    assert routing.imcc_risk_factors == ("RF_MODELLABLE", "RF_TYPE_A")
    assert routing.ses_risk_factors == ("RF_TYPE_A", "RF_TYPE_B")


def test_route_nmrf_classifications_for_capital_is_deterministically_sorted() -> None:
    routing = route_nmrf_classifications_for_capital(
        {
            "Z_TYPE_B": ModellabilityStatus.TYPE_B_NMRF,
            "M_TYPE_A": ModellabilityStatus.TYPE_A_NMRF,
            "A_MODELLABLE": ModellabilityStatus.MODELLABLE,
            "A_TYPE_B": ModellabilityStatus.TYPE_B_NMRF,
        },
        get_policy(),
    )

    assert routing.modellable_risk_factors == ("A_MODELLABLE",)
    assert routing.type_a_nmrf_risk_factors == ("M_TYPE_A",)
    assert routing.type_b_nmrf_risk_factors == ("A_TYPE_B", "Z_TYPE_B")
    assert routing.imcc_risk_factors == ("A_MODELLABLE", "M_TYPE_A")
    assert routing.ses_risk_factors == ("M_TYPE_A", "A_TYPE_B", "Z_TYPE_B")


def test_calculate_nmrf_capital_requires_artifacts_for_all_nmrfs() -> None:
    classifications = {
        "RF_TYPE_A": ModellabilityStatus.TYPE_A_NMRF,
        "RF_TYPE_B": ModellabilityStatus.TYPE_B_NMRF,
    }
    artifacts = (
        NMRFStressArtifact(
            risk_factor_name="RF_TYPE_A",
            method=NMRFStressMethod.DIRECT,
            losses=[10.0],
            liquidity_horizon=LiquidityHorizon.LH20,
            stress_period="synthetic-stress",
            source="upstream risk engine",
        ),
    )

    with pytest.raises(ValueError, match="Missing NMRF stress artifacts"):
        calculate_nmrf_capital_for_policy(classifications, artifacts, get_policy())


def test_calculate_nmrf_capital_validates_methods_and_liquidity_horizons() -> None:
    classifications = {"RF_TYPE_A": ModellabilityStatus.TYPE_A_NMRF}
    artifacts = (
        NMRFStressArtifact(
            risk_factor_name="RF_TYPE_A",
            method=NMRFStressMethod.STEPWISE,
            losses=[10.0],
            liquidity_horizon=LiquidityHorizon.LH20,
            stress_period="synthetic-stress",
            source="upstream risk engine",
        ),
    )

    with pytest.raises(ValueError, match="method mismatch"):
        calculate_nmrf_capital_for_policy(
            classifications,
            artifacts,
            get_policy(),
            required_methods={"RF_TYPE_A": NMRFStressMethod.DIRECT},
        )

    with pytest.raises(ValueError, match="liquidity horizon too short"):
        calculate_nmrf_capital_for_policy(
            classifications,
            artifacts,
            get_policy(),
            required_liquidity_horizons={"RF_TYPE_A": LiquidityHorizon.LH40},
        )


def test_calculate_nmrf_capital_allows_partial_required_constraint_mappings() -> None:
    classifications = {
        "RF_TYPE_A": ModellabilityStatus.TYPE_A_NMRF,
        "RF_TYPE_B": ModellabilityStatus.TYPE_B_NMRF,
    }
    artifacts = (
        NMRFStressArtifact(
            risk_factor_name="RF_TYPE_A",
            method=NMRFStressMethod.DIRECT,
            losses=[10.0],
            liquidity_horizon=LiquidityHorizon.LH20,
            stress_period="synthetic-stress",
            source="upstream risk engine",
        ),
        NMRFStressArtifact(
            risk_factor_name="RF_TYPE_B",
            method=NMRFStressMethod.STEPWISE,
            losses=[20.0],
            liquidity_horizon=LiquidityHorizon.LH40,
            stress_period="synthetic-stress",
            source="upstream risk engine",
        ),
    )

    result = calculate_nmrf_capital_for_policy(
        classifications,
        artifacts,
        get_policy(),
        required_methods={"RF_TYPE_A": NMRFStressMethod.DIRECT},
        required_liquidity_horizons={"RF_TYPE_B": LiquidityHorizon.LH20},
    )

    assert result.type_a_results[0].ses == pytest.approx(10.0)
    assert result.type_b_results[0].ses == pytest.approx(20.0)


def test_calculate_nmrf_capital_aggregates_type_a_and_type_b_artifacts() -> None:
    classifications = {
        "RF_MODELLABLE": ModellabilityStatus.MODELLABLE,
        "RF_TYPE_A": ModellabilityStatus.TYPE_A_NMRF,
        "RF_TYPE_B": ModellabilityStatus.TYPE_B_NMRF,
    }
    artifacts = (
        NMRFStressArtifact(
            risk_factor_name="RF_TYPE_A",
            method=NMRFStressMethod.DIRECT,
            losses=[10.0, 20.0],
            liquidity_horizon=LiquidityHorizon.LH20,
            stress_period="synthetic-stress",
            source="upstream risk engine",
        ),
        NMRFStressArtifact(
            risk_factor_name="RF_TYPE_B",
            method=NMRFStressMethod.FULL_REVALUATION,
            losses=[5.0, 15.0],
            liquidity_horizon=LiquidityHorizon.LH120,
            stress_period="synthetic-stress",
            source="upstream risk engine",
        ),
    )

    result = calculate_nmrf_capital_for_policy(classifications, artifacts, get_policy())
    expected = aggregate_ses_breakdown_for_policy([20.0], [15.0], get_policy())

    assert result.type_a_results[0].ses == pytest.approx(20.0)
    assert result.type_b_results[0].ses == pytest.approx(15.0)
    assert result.total_ses == pytest.approx(expected.total_ses)
    assert result.as_dict()["total_ses"] == pytest.approx(expected.total_ses)
    assert result.aggregation.as_dict()["type_b_rho"] == pytest.approx(0.36)


def test_calculate_nmrf_capital_rejects_modellable_artifacts() -> None:
    classifications = {"RF_MODELLABLE": ModellabilityStatus.MODELLABLE}
    artifacts = (
        NMRFStressArtifact(
            risk_factor_name="RF_MODELLABLE",
            method=NMRFStressMethod.DIRECT,
            losses=[10.0],
            liquidity_horizon=LiquidityHorizon.LH20,
            stress_period="synthetic-stress",
            source="upstream risk engine",
        ),
    )

    with pytest.raises(ValueError, match="modellable risk factors"):
        calculate_nmrf_capital_for_policy(classifications, artifacts, get_policy())
