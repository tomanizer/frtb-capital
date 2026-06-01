from __future__ import annotations

from datetime import date

import pytest
from frtb_sbm import (
    SbmCalculationContext,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    calculate_sbm_capital,
    input_hash_for_sensitivities,
)
from frtb_sbm.factor_grid import net_girr_delta_weighted_sensitivities
from frtb_sbm.weighted_sensitivity import weight_girr_delta_sensitivities


def _context() -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id="run-girr-factor-grid",
        calculation_date=date(2026, 6, 1),
        base_currency="USD",
        reporting_currency="USD",
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
    )


def _sensitivity(
    index: int,
    *,
    amount: float,
    risk_factor: str,
    tenor: str,
    bucket: str = "2",
) -> SbmSensitivity:
    row_id = f"row-{index:04d}"
    return SbmSensitivity(
        sensitivity_id=f"sens-{index:04d}",
        source_row_id=row_id,
        desk_id="rates",
        legal_entity="LE-001",
        risk_class=SbmRiskClass.GIRR,
        risk_measure=SbmRiskMeasure.DELTA,
        bucket=bucket,
        risk_factor=risk_factor,
        amount=amount,
        amount_currency="USD",
        sign_convention=SbmSignConvention.RECEIVE,
        tenor=tenor,
        lineage=SbmSourceLineage(
            source_system="unit-test",
            source_file="girr-factor-grid.csv",
            source_row_id=row_id,
        ),
    )


def test_girr_delta_factor_grid_nets_duplicate_curve_tenor_rows() -> None:
    sensitivities = (
        _sensitivity(1, amount=100.0, risk_factor="USD-OIS", tenor="5y"),
        _sensitivity(2, amount=200.0, risk_factor="USD-OIS", tenor="5y"),
        _sensitivity(3, amount=-25.0, risk_factor="USD-OIS", tenor="5y"),
        _sensitivity(4, amount=50.0, risk_factor="USD-LIBOR", tenor="5y"),
    )
    weighted = weight_girr_delta_sensitivities(
        sensitivities,
        profile_id=SbmRegulatoryProfile.BASEL_MAR21.value,
        reporting_currency="USD",
    )

    grid = net_girr_delta_weighted_sensitivities(sensitivities, weighted)

    assert grid.raw_row_count == 4
    assert grid.factor_count == 2
    netted = next(item for item in grid.weighted_sensitivities if item.factor_key)
    assert netted.factor_key == ("2", "USD-OIS", "5y")
    assert netted.raw_amount == pytest.approx(275.0)
    assert netted.scaled_amount == pytest.approx(
        sum(
            item.scaled_amount
            for item in weighted
            if item.sensitivity_id in {"sens-0001", "sens-0002", "sens-0003"}
        )
    )
    assert netted.contributing_sensitivity_ids == ("sens-0001", "sens-0002", "sens-0003")
    assert netted.contributing_source_row_ids == ("row-0001", "row-0002", "row-0003")
    assert grid.tenor_by_id[netted.sensitivity_id] == "5y"
    assert grid.risk_factor_by_id[netted.sensitivity_id] == "USD-OIS"


def test_girr_delta_capital_uses_netted_factor_count_not_raw_row_count() -> None:
    duplicate_rows = tuple(
        _sensitivity(index, amount=100.0 + index, risk_factor="USD-OIS", tenor="5y")
        for index in range(1, 7)
    ) + tuple(
        _sensitivity(index, amount=50.0 + index, risk_factor="USD-LIBOR", tenor="5y")
        for index in range(7, 11)
    )
    equivalent_factors = (
        _sensitivity(
            101,
            amount=sum(item.amount for item in duplicate_rows[:6]),
            risk_factor="USD-OIS",
            tenor="5y",
        ),
        _sensitivity(
            102,
            amount=sum(item.amount for item in duplicate_rows[6:]),
            risk_factor="USD-LIBOR",
            tenor="5y",
        ),
    )

    duplicate_result = calculate_sbm_capital(duplicate_rows, context=_context())
    equivalent_result = calculate_sbm_capital(equivalent_factors, context=_context())

    assert duplicate_result.total_capital == pytest.approx(equivalent_result.total_capital)
    assert duplicate_result.input_hash == input_hash_for_sensitivities(duplicate_rows)
    assert duplicate_result.input_hash != equivalent_result.input_hash

    risk_class = duplicate_result.risk_classes[0]
    assert len(risk_class.buckets) == 1
    assert len(risk_class.buckets[0].weighted_sensitivities) == 2
    for detail in risk_class.scenario_details:
        assert len(detail.intra_buckets) == 1
        # Two netted factors produce the upper-triangular audit set:
        # (factor 1, factor 1), (factor 1, factor 2), (factor 2, factor 2).
        assert len(detail.intra_buckets[0].pairwise_correlations) == 3
