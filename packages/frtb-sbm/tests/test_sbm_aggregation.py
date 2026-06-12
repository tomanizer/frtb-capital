"""Tests for intra-bucket SBM aggregation (SBM-REQ-005)."""

from __future__ import annotations

import math

import numpy as np
import pytest
from frtb_sbm import SbmRiskClass, SbmRiskMeasure
from frtb_sbm.aggregation import aggregate_intra_bucket, group_weighted_sensitivities_by_bucket
from frtb_sbm.validation import SbmInputError

from tests.sbm_fixture_helpers import sample_sbm_weighted_sensitivity as _weighted


def test_single_sensitivity_intra_bucket_matches_absolute_amount() -> None:
    """MAR21.4(4): one factor yields Kb = |WS| and Sb = WS."""
    weighted = _weighted(sensitivity_id="ws-1", scaled_amount=16_000.0)
    result = aggregate_intra_bucket(
        "USD",
        (weighted,),
        np.array([[1.0]], dtype=np.float64),
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
    )

    assert result.bucket_capital.kb == pytest.approx(16_000.0)
    assert result.bucket_capital.sb == pytest.approx(16_000.0)
    assert result.variance_before_floor == pytest.approx(16_000.0**2)
    assert result.zero_variance_floor_applied is False
    assert len(result.pairwise_correlations) == 1


def test_two_factor_intra_bucket_uses_correlation_matrix() -> None:
    """MAR21.4(4): Kb^2 = WS1^2 + WS2^2 + 2 * rho * WS1 * WS2."""
    ws1 = _weighted(sensitivity_id="ws-1", scaled_amount=100.0)
    ws2 = _weighted(sensitivity_id="ws-2", scaled_amount=50.0)
    rho = 0.5
    matrix = np.array([[1.0, rho], [rho, 1.0]], dtype=np.float64)
    expected_variance = 100.0**2 + 50.0**2 + 2.0 * rho * 100.0 * 50.0

    result = aggregate_intra_bucket(
        "USD",
        (ws1, ws2),
        matrix,
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
    )

    assert result.bucket_capital.sb == pytest.approx(150.0)
    assert result.variance_before_floor == pytest.approx(expected_variance)
    assert result.bucket_capital.kb == pytest.approx(math.sqrt(expected_variance))
    assert result.pairwise_correlations[1].correlation == pytest.approx(rho)


def test_intra_bucket_zero_variance_floor_applies_for_perfect_offset() -> None:
    """MAR21.4(4): the quantity inside the square root is floored at zero."""
    ws1 = _weighted(sensitivity_id="ws-long", scaled_amount=100.0)
    ws2 = _weighted(sensitivity_id="ws-short", scaled_amount=-100.0)
    matrix = np.array([[1.0, 1.0], [1.0, 1.0]], dtype=np.float64)

    result = aggregate_intra_bucket(
        "USD",
        (ws1, ws2),
        matrix,
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
    )

    assert result.variance_before_floor == pytest.approx(0.0)
    assert result.zero_variance_floor_applied is False
    assert result.bucket_capital.kb == pytest.approx(0.0)
    assert result.bucket_capital.floor_applied is False


def test_intra_bucket_sb_correlation_floor_can_bind() -> None:
    ws1 = _weighted(sensitivity_id="ws-1", scaled_amount=10.0)
    ws2 = _weighted(sensitivity_id="ws-2", scaled_amount=5.0)
    matrix = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float64)

    result = aggregate_intra_bucket(
        "USD",
        (ws1, ws2),
        matrix,
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
        sb_correlation_floor=1.0,
    )

    assert result.bucket_capital.sb == pytest.approx(15.0)
    assert result.sb_correlation_floor_applied is True
    assert result.bucket_capital.kb == pytest.approx(15.0)


def test_intra_bucket_zero_floor_handles_non_psd_correlation_matrix() -> None:
    """MAR21.4(4): max(0, variance) guards inconsistent correlation inputs."""
    ws1 = _weighted(sensitivity_id="ws-1", scaled_amount=100.0)
    ws2 = _weighted(sensitivity_id="ws-2", scaled_amount=-100.0)
    matrix = np.array([[1.0, 1.05], [1.05, 1.0]], dtype=np.float64)

    result = aggregate_intra_bucket(
        "USD",
        (ws1, ws2),
        matrix,
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
    )

    assert result.variance_before_floor < 0.0
    assert result.zero_variance_floor_applied is True
    assert result.bucket_capital.kb == pytest.approx(0.0)
    assert result.bucket_capital.floor_applied is True


def test_group_weighted_sensitivities_by_bucket_is_deterministic() -> None:
    usd_a = _weighted(sensitivity_id="a", scaled_amount=1.0, bucket="USD")
    usd_b = _weighted(sensitivity_id="b", scaled_amount=2.0, bucket="USD")
    eur = _weighted(sensitivity_id="c", scaled_amount=3.0, bucket="EUR")

    grouped = group_weighted_sensitivities_by_bucket((eur, usd_b, usd_a))

    assert grouped[(SbmRiskClass.GIRR, SbmRiskMeasure.DELTA, "EUR")] == (eur,)
    assert grouped[(SbmRiskClass.GIRR, SbmRiskMeasure.DELTA, "USD")] == (usd_a, usd_b)


def test_intra_bucket_rejects_mismatched_correlation_shape() -> None:
    weighted = _weighted(sensitivity_id="ws-1", scaled_amount=1.0)
    with pytest.raises(SbmInputError, match="correlation_matrix shape"):
        aggregate_intra_bucket(
            "USD",
            (weighted,),
            np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float64),
            risk_class=SbmRiskClass.GIRR,
            risk_measure=SbmRiskMeasure.DELTA,
        )


def test_intra_bucket_rejects_empty_weighted_sensitivities() -> None:
    with pytest.raises(SbmInputError, match="must not be empty"):
        aggregate_intra_bucket(
            "USD",
            (),
            np.zeros((0, 0), dtype=np.float64),
            risk_class=SbmRiskClass.GIRR,
            risk_measure=SbmRiskMeasure.DELTA,
        )
