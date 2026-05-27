"""
Risk-factor category to liquidity-horizon mapping helpers.

This module does not infer risk-factor categories from trade, vendor, CRIF, or
instrument data. Callers must supply the regulatory category they have assigned
through their own documented classification process.

Regulatory traceability:
    Basel MAR33.12 Table 2, U.S. NPR 2.0 proposed section __.215(b)(11), and
    EU CRR Article 325bd liquidity-horizon mapping concepts. See
    docs/REGULATORY_TRACEABILITY.md.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from frtb_ima.data_models import LiquidityHorizon, RiskClass

SOURCE_SECTION = "Basel MAR33.12 Table 2 / proposed Sec. __.215(b)(11)"


class LiquidityHorizonCategory(StrEnum):
    """Regulatory risk-factor categories for liquidity-horizon assignment."""

    INTEREST_RATE_SPECIFIED_CURRENCY = "INTEREST_RATE_SPECIFIED_CURRENCY"
    INTEREST_RATE_UNSPECIFIED_CURRENCY = "INTEREST_RATE_UNSPECIFIED_CURRENCY"
    INTEREST_RATE_VOLATILITY = "INTEREST_RATE_VOLATILITY"
    INTEREST_RATE_OTHER = "INTEREST_RATE_OTHER"
    CREDIT_SPREAD_SOVEREIGN_IG = "CREDIT_SPREAD_SOVEREIGN_IG"
    CREDIT_SPREAD_SOVEREIGN_HY = "CREDIT_SPREAD_SOVEREIGN_HY"
    CREDIT_SPREAD_CORPORATE_IG = "CREDIT_SPREAD_CORPORATE_IG"
    CREDIT_SPREAD_CORPORATE_HY = "CREDIT_SPREAD_CORPORATE_HY"
    CREDIT_SPREAD_VOLATILITY = "CREDIT_SPREAD_VOLATILITY"
    CREDIT_SPREAD_OTHER = "CREDIT_SPREAD_OTHER"
    EQUITY_PRICE_LARGE_CAP = "EQUITY_PRICE_LARGE_CAP"
    EQUITY_PRICE_SMALL_CAP = "EQUITY_PRICE_SMALL_CAP"
    EQUITY_PRICE_LARGE_CAP_VOLATILITY = "EQUITY_PRICE_LARGE_CAP_VOLATILITY"
    EQUITY_PRICE_SMALL_CAP_VOLATILITY = "EQUITY_PRICE_SMALL_CAP_VOLATILITY"
    EQUITY_OTHER = "EQUITY_OTHER"
    FX_RATE_SPECIFIED_CURRENCY_PAIR = "FX_RATE_SPECIFIED_CURRENCY_PAIR"
    FX_RATE_OTHER_CURRENCY_PAIR = "FX_RATE_OTHER_CURRENCY_PAIR"
    FX_VOLATILITY = "FX_VOLATILITY"
    FX_OTHER = "FX_OTHER"
    COMMODITY_ENERGY_OR_CARBON_PRICE = "COMMODITY_ENERGY_OR_CARBON_PRICE"
    COMMODITY_PRECIOUS_OR_NONFERROUS_METALS_PRICE = "COMMODITY_PRECIOUS_OR_NONFERROUS_METALS_PRICE"
    COMMODITY_OTHER_PRICE = "COMMODITY_OTHER_PRICE"
    COMMODITY_ENERGY_OR_CARBON_VOLATILITY = "COMMODITY_ENERGY_OR_CARBON_VOLATILITY"
    COMMODITY_PRECIOUS_OR_NONFERROUS_METALS_VOLATILITY = (
        "COMMODITY_PRECIOUS_OR_NONFERROUS_METALS_VOLATILITY"
    )
    COMMODITY_OTHER_VOLATILITY = "COMMODITY_OTHER_VOLATILITY"
    COMMODITY_OTHER = "COMMODITY_OTHER"


@dataclass(frozen=True)
class LiquidityHorizonMappingEntry:
    """One row in the regulatory liquidity-horizon mapping table."""

    category: LiquidityHorizonCategory
    risk_class: RiskClass
    liquidity_horizon: LiquidityHorizon
    description: str
    source_section: str = SOURCE_SECTION

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable dictionary for traceability reports."""
        return {
            "category": self.category.value,
            "risk_class": self.risk_class.value,
            "liquidity_horizon": self.liquidity_horizon.value,
            "description": self.description,
            "source_section": self.source_section,
        }


FED_NPR_SPECIFIED_FX_CURRENCY_CODES: tuple[str, ...] = (
    "USD",
    "AUD",
    "BRL",
    "CAD",
    "CNY",
    "EUR",
    "HKD",
    "INR",
    "JPY",
    "MXN",
    "NZD",
    "NOK",
    "SGD",
    "ZAR",
    "KRW",
    "SEK",
    "CHF",
    "TRY",
    "GBP",
)

_SPECIFIED_CURRENCY_SET = frozenset(FED_NPR_SPECIFIED_FX_CURRENCY_CODES)


_MAPPING_TABLE: tuple[LiquidityHorizonMappingEntry, ...] = (
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.INTEREST_RATE_SPECIFIED_CURRENCY,
        RiskClass.GIRR,
        LiquidityHorizon.LH10,
        "Interest-rate risk for specified currencies.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.INTEREST_RATE_UNSPECIFIED_CURRENCY,
        RiskClass.GIRR,
        LiquidityHorizon.LH20,
        "Interest-rate risk for currencies outside the specified-currency set.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.INTEREST_RATE_VOLATILITY,
        RiskClass.GIRR,
        LiquidityHorizon.LH60,
        "Interest-rate volatility risk factors.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.INTEREST_RATE_OTHER,
        RiskClass.GIRR,
        LiquidityHorizon.LH60,
        "Other interest-rate risk factors.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.CREDIT_SPREAD_SOVEREIGN_IG,
        RiskClass.CSR,
        LiquidityHorizon.LH20,
        "Investment-grade sovereign credit spread risk factors.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.CREDIT_SPREAD_SOVEREIGN_HY,
        RiskClass.CSR,
        LiquidityHorizon.LH40,
        "High-yield sovereign credit spread risk factors.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.CREDIT_SPREAD_CORPORATE_IG,
        RiskClass.CSR,
        LiquidityHorizon.LH40,
        "Investment-grade corporate credit spread risk factors.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.CREDIT_SPREAD_CORPORATE_HY,
        RiskClass.CSR,
        LiquidityHorizon.LH60,
        "High-yield corporate credit spread risk factors.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.CREDIT_SPREAD_VOLATILITY,
        RiskClass.CSR,
        LiquidityHorizon.LH120,
        "Credit spread volatility risk factors.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.CREDIT_SPREAD_OTHER,
        RiskClass.CSR,
        LiquidityHorizon.LH120,
        "Other credit spread risk factors.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.EQUITY_PRICE_LARGE_CAP,
        RiskClass.EQUITY,
        LiquidityHorizon.LH10,
        "Large-cap equity price risk factors.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.EQUITY_PRICE_SMALL_CAP,
        RiskClass.EQUITY,
        LiquidityHorizon.LH20,
        "Small-cap equity price risk factors.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.EQUITY_PRICE_LARGE_CAP_VOLATILITY,
        RiskClass.EQUITY,
        LiquidityHorizon.LH20,
        "Large-cap equity volatility risk factors.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.EQUITY_PRICE_SMALL_CAP_VOLATILITY,
        RiskClass.EQUITY,
        LiquidityHorizon.LH60,
        "Small-cap equity volatility risk factors.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.EQUITY_OTHER,
        RiskClass.EQUITY,
        LiquidityHorizon.LH60,
        "Other equity risk factors.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.FX_RATE_SPECIFIED_CURRENCY_PAIR,
        RiskClass.FX,
        LiquidityHorizon.LH10,
        "Foreign-exchange rate risk factors for specified currency pairs.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.FX_RATE_OTHER_CURRENCY_PAIR,
        RiskClass.FX,
        LiquidityHorizon.LH20,
        "Foreign-exchange rate risk factors for other currency pairs.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.FX_VOLATILITY,
        RiskClass.FX,
        LiquidityHorizon.LH40,
        "Foreign-exchange volatility risk factors.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.FX_OTHER,
        RiskClass.FX,
        LiquidityHorizon.LH40,
        "Other foreign-exchange risk factors.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.COMMODITY_ENERGY_OR_CARBON_PRICE,
        RiskClass.COMMODITY,
        LiquidityHorizon.LH20,
        "Energy and carbon-emissions trading price risk factors.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.COMMODITY_PRECIOUS_OR_NONFERROUS_METALS_PRICE,
        RiskClass.COMMODITY,
        LiquidityHorizon.LH20,
        "Precious-metals and non-ferrous-metals price risk factors.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.COMMODITY_OTHER_PRICE,
        RiskClass.COMMODITY,
        LiquidityHorizon.LH60,
        "Other commodity price risk factors.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.COMMODITY_ENERGY_OR_CARBON_VOLATILITY,
        RiskClass.COMMODITY,
        LiquidityHorizon.LH60,
        "Energy and carbon-emissions trading volatility risk factors.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.COMMODITY_PRECIOUS_OR_NONFERROUS_METALS_VOLATILITY,
        RiskClass.COMMODITY,
        LiquidityHorizon.LH60,
        "Precious-metals and non-ferrous-metals volatility risk factors.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.COMMODITY_OTHER_VOLATILITY,
        RiskClass.COMMODITY,
        LiquidityHorizon.LH120,
        "Other commodity volatility risk factors.",
    ),
    LiquidityHorizonMappingEntry(
        LiquidityHorizonCategory.COMMODITY_OTHER,
        RiskClass.COMMODITY,
        LiquidityHorizon.LH120,
        "Other commodity risk factors.",
    ),
)

_ENTRY_BY_CATEGORY = {entry.category: entry for entry in _MAPPING_TABLE}
_ORDERED_HORIZONS = tuple(sorted(LiquidityHorizon, key=lambda item: item.value))


def liquidity_horizon_mapping_table() -> tuple[LiquidityHorizonMappingEntry, ...]:
    """Return the Fed NPR 2.0 / Basel liquidity-horizon mapping table."""
    return _MAPPING_TABLE


def liquidity_horizon_mapping_entry(
    category: LiquidityHorizonCategory | str,
) -> LiquidityHorizonMappingEntry:
    """Return the mapping entry for a caller-supplied regulatory category."""
    return _ENTRY_BY_CATEGORY[_as_category(category)]


def risk_class_for_liquidity_horizon_category(
    category: LiquidityHorizonCategory | str,
) -> RiskClass:
    """Return the broad risk class for a regulatory LH mapping category."""
    return liquidity_horizon_mapping_entry(category).risk_class


def liquidity_horizon_for_category(
    category: LiquidityHorizonCategory | str,
    *,
    maturity_days: int | None = None,
) -> LiquidityHorizon:
    """
    Return the minimum liquidity horizon for a regulatory category.

    If ``maturity_days`` is supplied and shorter than the category floor, the
    U.S. NPR working assumption is applied: use the next longer standard
    liquidity horizon from the position maturity.
    """
    base_horizon = liquidity_horizon_mapping_entry(category).liquidity_horizon
    if maturity_days is None:
        return base_horizon
    return liquidity_horizon_adjusted_for_maturity(base_horizon, maturity_days)


def liquidity_horizon_adjusted_for_maturity(
    liquidity_horizon: LiquidityHorizon | int,
    maturity_days: int,
) -> LiquidityHorizon:
    """
    Apply the short-maturity liquidity-horizon rule to an assigned category LH.

    When maturity is shorter than the category floor, the returned horizon is
    the next standard 10/20/40/60/120-day horizon equal to or longer than maturity.
    """
    base_horizon = _as_liquidity_horizon(liquidity_horizon)
    if maturity_days <= 0:
        raise ValueError("maturity_days must be positive")
    if maturity_days >= base_horizon.value:
        return base_horizon
    return _shortest_horizon_at_least(float(maturity_days))


def liquidity_horizon_for_weighted_average(
    underlying_horizons: Sequence[LiquidityHorizon | int],
    *,
    weights: Sequence[float] | None = None,
) -> LiquidityHorizon:
    """
    Return the minimum LH for credit/equity indices or similar instruments.

    The returned value is the shortest standard liquidity horizon equal to or
    longer than the weighted average of the underlying liquidity horizons.
    """
    horizons = tuple(_as_liquidity_horizon(item) for item in underlying_horizons)
    if not horizons:
        raise ValueError("underlying_horizons must be non-empty")

    if weights is None:
        normalized_weights = (1.0,) * len(horizons)
    else:
        normalized_weights = tuple(float(item) for item in weights)
        if len(normalized_weights) != len(horizons):
            raise ValueError("weights must have the same length as underlying_horizons")

    if any(not isfinite(weight) or weight < 0.0 for weight in normalized_weights):
        raise ValueError("weights must be finite and non-negative")
    total_weight = sum(normalized_weights)
    if total_weight <= 0.0:
        raise ValueError("weights must have positive total weight")

    weighted_average = (
        sum(horizon.value * weight for horizon, weight in zip(horizons, normalized_weights))
        / total_weight
    )
    return _shortest_horizon_at_least(weighted_average)


def is_fed_npr_specified_fx_pair(
    base_currency: str,
    quote_currency: str,
    *,
    additional_currency_codes: Sequence[str] = (),
) -> bool:
    """Return True when an FX pair is in the Fed NPR specified-currency set."""
    base = _normalise_currency_code(base_currency)
    quote = _normalise_currency_code(quote_currency)
    if base == quote:
        return False
    if not additional_currency_codes:
        return base in _SPECIFIED_CURRENCY_SET and quote in _SPECIFIED_CURRENCY_SET
    specified = set(_SPECIFIED_CURRENCY_SET)
    specified.update(_normalise_currency_code(item) for item in additional_currency_codes)
    return base in specified and quote in specified


def liquidity_horizon_for_fx_pair(
    base_currency: str,
    quote_currency: str,
    *,
    additional_currency_codes: Sequence[str] = (),
) -> LiquidityHorizon:
    """Return the FX rate liquidity horizon for a Fed NPR specified/other pair."""
    if is_fed_npr_specified_fx_pair(
        base_currency,
        quote_currency,
        additional_currency_codes=additional_currency_codes,
    ):
        return LiquidityHorizon.LH10
    return LiquidityHorizon.LH20


def _as_category(category: LiquidityHorizonCategory | str) -> LiquidityHorizonCategory:
    try:
        return (
            category
            if isinstance(category, LiquidityHorizonCategory)
            else LiquidityHorizonCategory(category)
        )
    except ValueError as exc:
        raise KeyError(f"unknown liquidity-horizon category: {category!r}") from exc


def _as_liquidity_horizon(liquidity_horizon: LiquidityHorizon | int) -> LiquidityHorizon:
    try:
        return (
            liquidity_horizon
            if isinstance(liquidity_horizon, LiquidityHorizon)
            else LiquidityHorizon(int(liquidity_horizon))
        )
    except ValueError as exc:
        raise ValueError(f"invalid liquidity horizon: {liquidity_horizon!r}") from exc


def _shortest_horizon_at_least(days: float) -> LiquidityHorizon:
    for horizon in _ORDERED_HORIZONS:
        if horizon.value >= days:
            return horizon
    return LiquidityHorizon.LH120


def _normalise_currency_code(currency: str) -> str:
    if not isinstance(currency, str):
        raise TypeError("currency code must be a string")
    code = currency.strip().upper()
    if len(code) != 3:
        raise ValueError("currency codes must be three-letter ISO-style codes")
    return code
