from __future__ import annotations

import numpy as np
import pytest
from frtb_sbm import (
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmScenarioLabel,
    WeightedSensitivity,
)
from frtb_sbm.aggregation import adjust_correlation_matrix_for_scenario
from frtb_sbm.reference_data import apply_correlation_scenario, girr_delta_intra_bucket_correlation
from frtb_sbm.risk_classes.girr_delta_correlations import (
    _build_girr_delta_intra_bucket_correlation_matrix,
)
from frtb_sbm.validation import SbmInputError


def _weighted(sensitivity_id: str) -> WeightedSensitivity:
    return WeightedSensitivity(
        sensitivity_id=sensitivity_id,
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket="1",
        raw_amount=1.0,
        risk_weight=1.0,
        scaled_amount=1.0,
        citation_ids=("basel_mar21_45_49",),
    )


def test_vectorized_girr_delta_matrix_matches_scalar_reference() -> None:
    ordered = tuple(
        _weighted(sensitivity_id)
        for sensitivity_id in (
            "usd-ois-1y",
            "usd-ois-5y",
            "usd-libor-1y",
            "eur-ois-10y",
            "usd-infl-a",
            "usd-infl-b",
            "usd-xccy-a",
            "usd-xccy-b",
        )
    )
    tenor_by_id = {
        "usd-ois-1y": "1y",
        "usd-ois-5y": "5y",
        "usd-libor-1y": "1y",
        "eur-ois-10y": "10y",
        "usd-infl-a": "INFL",
        "usd-infl-b": "INFL",
        "usd-xccy-a": "XCCY",
        "usd-xccy-b": "XCCY",
    }
    risk_factor_by_id = {
        "usd-ois-1y": "USD-OIS",
        "usd-ois-5y": "USD-OIS",
        "usd-libor-1y": "USD-LIBOR",
        "eur-ois-10y": "EUR-OIS",
        "usd-infl-a": "USD-INFL",
        "usd-infl-b": "USD-INFL-ALT",
        "usd-xccy-a": "USD-XCCY",
        "usd-xccy-b": "USD-XCCY-ALT",
    }

    vectorized = _build_girr_delta_intra_bucket_correlation_matrix(
        ordered,
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        tenor_by_id=tenor_by_id,
        risk_factor_by_id=risk_factor_by_id,
    )
    scalar = _scalar_girr_delta_matrix(ordered, tenor_by_id, risk_factor_by_id)

    assert np.allclose(vectorized, scalar)
    assert vectorized[0, 1] == pytest.approx(scalar[0, 1])
    assert vectorized[0, 2] == pytest.approx(0.999)
    assert vectorized[4, 5] == pytest.approx(1.0)
    assert vectorized[0, 4] == pytest.approx(0.40)
    assert vectorized[0, 6] == pytest.approx(0.0)
    assert vectorized[6, 7] == pytest.approx(1.0)


@pytest.mark.parametrize(
    "scenario",
    (SbmScenarioLabel.LOW, SbmScenarioLabel.MEDIUM, SbmScenarioLabel.HIGH),
)
def test_vectorized_scenario_matrix_adjustment_matches_scalar_reference(
    scenario: SbmScenarioLabel,
) -> None:
    base = np.array(
        [
            [1.0, 0.30, 0.80, 0.95],
            [0.30, 1.0, 0.40, 1.00],
            [0.80, 0.40, 1.0, 0.999],
            [0.95, 1.00, 0.999, 1.0],
        ],
        dtype=np.float64,
    )

    vectorized = adjust_correlation_matrix_for_scenario(base, scenario)
    scalar = _scalar_scenario_adjustment(base, scenario)

    assert np.allclose(vectorized, scalar)
    assert np.diag(vectorized).tolist() == pytest.approx(np.diag(base).tolist())


def test_vectorized_scenario_matrix_adjustment_rejects_non_finite_diagonal() -> None:
    base = np.array([[float("nan"), 0.50], [0.50, 1.0]], dtype=np.float64)

    with pytest.raises(SbmInputError, match="base_matrix must contain only finite values"):
        adjust_correlation_matrix_for_scenario(base, SbmScenarioLabel.MEDIUM)


def _scalar_girr_delta_matrix(
    ordered: tuple[WeightedSensitivity, ...],
    tenor_by_id: dict[str, str],
    risk_factor_by_id: dict[str, str],
) -> np.ndarray:
    size = len(ordered)
    matrix = np.eye(size, dtype=np.float64)
    for row_index, sensitivity_a in enumerate(ordered):
        for col_index in range(row_index, size):
            sensitivity_b = ordered[col_index]
            same_curve = (
                risk_factor_by_id[sensitivity_a.sensitivity_id]
                == risk_factor_by_id[sensitivity_b.sensitivity_id]
            )
            correlation, _ = girr_delta_intra_bucket_correlation(
                SbmRegulatoryProfile.BASEL_MAR21,
                tenor1=tenor_by_id[sensitivity_a.sensitivity_id],
                tenor2=tenor_by_id[sensitivity_b.sensitivity_id],
                same_curve=same_curve,
            )
            matrix[row_index, col_index] = correlation
            matrix[col_index, row_index] = correlation
    return matrix


def _scalar_scenario_adjustment(
    base: np.ndarray,
    scenario: SbmScenarioLabel,
) -> np.ndarray:
    adjusted = np.array(base, dtype=np.float64, copy=True)
    for row_index in range(adjusted.shape[0]):
        for col_index in range(row_index + 1, adjusted.shape[1]):
            correlation, _ = apply_correlation_scenario(
                SbmRegulatoryProfile.BASEL_MAR21,
                base_correlation=float(base[row_index, col_index]),
                scenario=scenario,
            )
            adjusted[row_index, col_index] = correlation
            adjusted[col_index, row_index] = correlation
    return adjusted
