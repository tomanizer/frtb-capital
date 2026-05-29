from __future__ import annotations

import math

import pytest
from frtb_drc import (
    DefaultDirection,
    DrcInputError,
    DrcRiskClass,
    GrossJtd,
    calculate_maturity_weight,
    scale_gross_jtd,
    scale_gross_jtds,
)


def test_maturity_below_three_months_uses_floor() -> None:
    scaled = scale_gross_jtd(_gross(), 0.10)

    assert scaled.maturity_weight == 0.25
    assert scaled.scaled_jtd == 25.0
    assert scaled.floor_applied is True
    assert scaled.branch_metadata[0].branch_type.value == "FLOOR"
    assert scaled.branch_metadata[0].source_id == "gross-pos-1"


def test_maturity_between_three_months_and_one_year_scales_linearly() -> None:
    scaled = scale_gross_jtd(_gross(), 0.50)

    assert scaled.maturity_weight == 0.50
    assert scaled.scaled_jtd == 50.0
    assert scaled.floor_applied is False
    assert scaled.branch_metadata == ()


def test_maturity_at_or_above_one_year_is_unscaled() -> None:
    scaled_at_one = scale_gross_jtd(_gross(), 1.0)
    scaled_above_one = scale_gross_jtd(_gross(), 2.0)

    assert scaled_at_one.maturity_weight == 1.0
    assert scaled_at_one.scaled_jtd == 100.0
    assert scaled_above_one.maturity_weight == 1.0
    assert scaled_above_one.scaled_jtd == 100.0


def test_invalid_maturity_fails_before_scaling() -> None:
    with pytest.raises(DrcInputError, match="maturity_years must be non-negative"):
        calculate_maturity_weight(-0.1)

    with pytest.raises(DrcInputError, match="maturity_years must be finite"):
        calculate_maturity_weight(math.inf)


def test_scale_gross_jtd_preserves_lineage_and_citation() -> None:
    scaled = scale_gross_jtd(_gross(position_id="pos-2", gross_jtd_id="gross-pos-2"), 0.75)

    assert scaled.scaled_jtd_id == "scaled-pos-2"
    assert scaled.gross_jtd_id == "gross-pos-2"
    assert scaled.position_id == "pos-2"
    assert scaled.citations == ("US_NPR_210_A_2_III",)


def test_scale_gross_jtds_preserves_input_order() -> None:
    records = scale_gross_jtds(
        (
            (_gross(position_id="pos-1", gross_jtd_id="gross-pos-1"), 1.0),
            (_gross(position_id="pos-2", gross_jtd_id="gross-pos-2"), 0.5),
        )
    )

    assert [record.position_id for record in records] == ["pos-1", "pos-2"]
    assert [record.scaled_jtd for record in records] == [100.0, 50.0]


def _gross(**overrides: object) -> GrossJtd:
    values: dict[str, object] = {
        "gross_jtd_id": "gross-pos-1",
        "position_id": "pos-1",
        "risk_class": DrcRiskClass.NON_SECURITISATION,
        "issuer_or_tranche_key": "issuer-a",
        "bucket_key": "CORPORATE",
        "default_direction": DefaultDirection.LONG,
        "lgd_rate": 0.75,
        "lgd_source": "profile",
        "notional": 100.0,
        "pnl_component": 0.0,
        "gross_jtd": 100.0,
        "citations": ("BASEL_MAR22_11", "US_NPR_210_B_1_IV"),
    }
    values.update(overrides)
    return GrossJtd(**values)  # type: ignore[arg-type]
