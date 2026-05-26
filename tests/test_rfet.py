"""Tests for RFET / modellability classification."""

from datetime import date, timedelta

from frtb_ima.data_models import (
    LiquidityHorizon,
    ModellabilityStatus,
    RealPriceObservation,
    RiskClass,
    RiskFactor,
)
from frtb_ima.rfet import (
    classify_risk_factor,
    count_eligible_observations,
    passes_quantitative_test,
)

AS_OF = date(2025, 6, 30)


def _make_obs(name: str, n: int, spacing_days: int = 10) -> list[RealPriceObservation]:
    """n observations spaced `spacing_days` apart, all within 12 months of AS_OF."""
    return [
        RealPriceObservation(name, AS_OF - timedelta(days=i * spacing_days))
        for i in range(n)
    ]


RF_LH10 = RiskFactor("RF_A", RiskClass.GIRR, LiquidityHorizon.LH10)
RF_LH20 = RiskFactor("RF_B", RiskClass.FX, LiquidityHorizon.LH20)
RF_LH40 = RiskFactor("RF_C", RiskClass.CSR, LiquidityHorizon.LH40)
RF_LH120 = RiskFactor("RF_D", RiskClass.EQUITY, LiquidityHorizon.LH120)


def test_count_eligible_observations_within_window() -> None:
    obs = _make_obs("RF_A", n=20, spacing_days=10)
    count = count_eligible_observations(obs, "RF_A", AS_OF)
    assert count == 20


def test_count_eligible_observations_excludes_old() -> None:
    # 5 recent + 5 outside 365-day window
    recent = _make_obs("RF_A", n=5, spacing_days=10)
    old = [
        RealPriceObservation("RF_A", AS_OF - timedelta(days=400 + i * 10))
        for i in range(5)
    ]
    count = count_eligible_observations(recent + old, "RF_A", AS_OF)
    assert count == 5


def test_count_eligible_observations_deduplicates_dates() -> None:
    # Two obs on same date — should count as 1
    d = AS_OF - timedelta(days=5)
    obs = [
        RealPriceObservation("RF_A", d, source="VENDOR_A"),
        RealPriceObservation("RF_A", d, source="VENDOR_B"),
    ]
    count = count_eligible_observations(obs, "RF_A", AS_OF)
    assert count == 1


def test_passes_quantitative_lh10_exactly_24() -> None:
    obs = _make_obs("RF_A", n=24, spacing_days=14)
    assert passes_quantitative_test(obs, RF_LH10, AS_OF) is True


def test_fails_quantitative_lh10_below_24() -> None:
    obs = _make_obs("RF_A", n=23, spacing_days=14)
    assert passes_quantitative_test(obs, RF_LH10, AS_OF) is False


def test_passes_quantitative_lh40_exactly_16() -> None:
    obs = _make_obs("RF_C", n=16, spacing_days=20)
    assert passes_quantitative_test(obs, RF_LH40, AS_OF) is True


def test_fails_quantitative_lh40_below_16() -> None:
    obs = _make_obs("RF_C", n=15, spacing_days=20)
    assert passes_quantitative_test(obs, RF_LH40, AS_OF) is False


def test_classify_modellable() -> None:
    obs = _make_obs("RF_A", n=30, spacing_days=10)
    result = classify_risk_factor(RF_LH10, obs, qualitative_pass=True, as_of_date=AS_OF)
    assert result == ModellabilityStatus.MODELLABLE


def test_classify_type_a_nmrf() -> None:
    # Qualitative pass, quantitative fail
    obs = _make_obs("RF_A", n=10, spacing_days=10)
    result = classify_risk_factor(RF_LH10, obs, qualitative_pass=True, as_of_date=AS_OF)
    assert result == ModellabilityStatus.TYPE_A_NMRF


def test_classify_type_b_nmrf_qual_fail() -> None:
    # Qualitative fail -> Type B regardless of quantitative
    obs = _make_obs("RF_A", n=30, spacing_days=10)
    result = classify_risk_factor(RF_LH10, obs, qualitative_pass=False, as_of_date=AS_OF)
    assert result == ModellabilityStatus.TYPE_B_NMRF


def test_classify_type_b_nmrf_no_obs() -> None:
    result = classify_risk_factor(RF_LH10, [], qualitative_pass=False, as_of_date=AS_OF)
    assert result == ModellabilityStatus.TYPE_B_NMRF
