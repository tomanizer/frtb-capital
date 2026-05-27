"""Tests for regulatory liquidity-horizon mapping helpers."""

import pytest

from frtb_ima.data_models import LiquidityHorizon, RiskClass
from frtb_ima.liquidity_horizon_mapping import (
    FED_NPR_SPECIFIED_FX_CURRENCY_CODES,
    LiquidityHorizonCategory,
    is_fed_npr_specified_fx_pair,
    liquidity_horizon_adjusted_for_maturity,
    liquidity_horizon_for_category,
    liquidity_horizon_for_fx_pair,
    liquidity_horizon_for_weighted_average,
    liquidity_horizon_mapping_entry,
    liquidity_horizon_mapping_table,
    risk_class_for_liquidity_horizon_category,
)


def test_liquidity_horizon_mapping_table_covers_all_risk_classes() -> None:
    table = liquidity_horizon_mapping_table()

    assert len(table) == 26
    assert {entry.risk_class for entry in table} == set(RiskClass)
    assert len({entry.category for entry in table}) == len(table)
    assert all(entry.source_section for entry in table)


@pytest.mark.parametrize(
    ("category", "expected_risk_class", "expected_horizon"),
    [
        (
            LiquidityHorizonCategory.INTEREST_RATE_SPECIFIED_CURRENCY,
            RiskClass.GIRR,
            LiquidityHorizon.LH10,
        ),
        (
            LiquidityHorizonCategory.CREDIT_SPREAD_SOVEREIGN_IG,
            RiskClass.CSR,
            LiquidityHorizon.LH20,
        ),
        (
            LiquidityHorizonCategory.CREDIT_SPREAD_CORPORATE_HY,
            RiskClass.CSR,
            LiquidityHorizon.LH60,
        ),
        (
            LiquidityHorizonCategory.EQUITY_PRICE_SMALL_CAP_VOLATILITY,
            RiskClass.EQUITY,
            LiquidityHorizon.LH60,
        ),
        (
            LiquidityHorizonCategory.FX_VOLATILITY,
            RiskClass.FX,
            LiquidityHorizon.LH40,
        ),
        (
            LiquidityHorizonCategory.COMMODITY_OTHER_VOLATILITY,
            RiskClass.COMMODITY,
            LiquidityHorizon.LH120,
        ),
    ],
)
def test_liquidity_horizon_for_category_uses_regulatory_table(
    category: LiquidityHorizonCategory,
    expected_risk_class: RiskClass,
    expected_horizon: LiquidityHorizon,
) -> None:
    assert liquidity_horizon_for_category(category) == expected_horizon
    assert risk_class_for_liquidity_horizon_category(category.value) == expected_risk_class
    assert liquidity_horizon_mapping_entry(category).as_dict()["category"] == category.value


@pytest.mark.parametrize(
    ("base_horizon", "maturity_days", "expected"),
    [
        (LiquidityHorizon.LH60, 5, LiquidityHorizon.LH10),
        (LiquidityHorizon.LH60, 10, LiquidityHorizon.LH10),
        (LiquidityHorizon.LH60, 20, LiquidityHorizon.LH20),
        (LiquidityHorizon.LH60, 30, LiquidityHorizon.LH40),
        (LiquidityHorizon.LH60, 59, LiquidityHorizon.LH60),
        (LiquidityHorizon.LH60, 60, LiquidityHorizon.LH60),
    ],
)
def test_liquidity_horizon_short_maturity_rule(
    base_horizon: LiquidityHorizon,
    maturity_days: int,
    expected: LiquidityHorizon,
) -> None:
    assert liquidity_horizon_adjusted_for_maturity(base_horizon, maturity_days) == expected


def test_liquidity_horizon_for_category_applies_short_maturity_rule() -> None:
    assert (
        liquidity_horizon_for_category(
            LiquidityHorizonCategory.CREDIT_SPREAD_CORPORATE_HY,
            maturity_days=30,
        )
        == LiquidityHorizon.LH40
    )


@pytest.mark.parametrize(
    ("underlying_horizons", "weights", "expected"),
    [
        ((LiquidityHorizon.LH20, LiquidityHorizon.LH20), None, LiquidityHorizon.LH20),
        ((LiquidityHorizon.LH10, LiquidityHorizon.LH40), (0.5, 0.5), LiquidityHorizon.LH40),
        ((LiquidityHorizon.LH10, LiquidityHorizon.LH20), (0.5, 0.5), LiquidityHorizon.LH20),
        ((LiquidityHorizon.LH60, LiquidityHorizon.LH120), (0.9, 0.1), LiquidityHorizon.LH120),
    ],
)
def test_liquidity_horizon_for_weighted_average(
    underlying_horizons: tuple[LiquidityHorizon, ...],
    weights: tuple[float, ...] | None,
    expected: LiquidityHorizon,
) -> None:
    assert liquidity_horizon_for_weighted_average(underlying_horizons, weights=weights) == expected


def test_liquidity_horizon_mapping_rejects_invalid_inputs() -> None:
    with pytest.raises(KeyError, match="unknown liquidity-horizon category"):
        liquidity_horizon_mapping_entry("UNKNOWN")
    with pytest.raises(ValueError, match="maturity_days must be positive"):
        liquidity_horizon_adjusted_for_maturity(LiquidityHorizon.LH60, 0)
    with pytest.raises(ValueError, match="same length"):
        liquidity_horizon_for_weighted_average((LiquidityHorizon.LH10,), weights=(1.0, 2.0))
    with pytest.raises(ValueError, match="positive total"):
        liquidity_horizon_for_weighted_average((LiquidityHorizon.LH10,), weights=(0.0,))


def test_fx_pair_helper_rejects_invalid_currency_codes() -> None:
    with pytest.raises(TypeError, match="currency code must be a string"):
        is_fed_npr_specified_fx_pair(123, "USD")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="three-letter"):
        is_fed_npr_specified_fx_pair("US", "EUR")


def test_fed_npr_specified_fx_pair_helper() -> None:
    assert "USD" in FED_NPR_SPECIFIED_FX_CURRENCY_CODES
    assert is_fed_npr_specified_fx_pair("usd", "eur")
    assert not is_fed_npr_specified_fx_pair("USD", "USD")
    assert not is_fed_npr_specified_fx_pair("USD", "ISK")
    assert is_fed_npr_specified_fx_pair("USD", "ISK", additional_currency_codes=("ISK",))
    assert liquidity_horizon_for_fx_pair("USD", "EUR") == LiquidityHorizon.LH10
    assert liquidity_horizon_for_fx_pair("USD", "ISK") == LiquidityHorizon.LH20
