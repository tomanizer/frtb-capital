"""
Synthetic demo data for FRTB IMA examples.

All data is fabricated. No real market data, no real positions.

Regulatory traceability:
    Demo data is not regulatory evidence. See docs/REGULATORY_TRACEABILITY.md
    for the calculation modules that consume these synthetic inputs.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from frtb_ima.data_models import (
    LiquidityHorizon,
    RealPriceObservation,
    RiskClass,
    RiskFactor,
    ScenarioPnL,
)

RNG = np.random.default_rng(seed=42)


# ---------------------------------------------------------------------------
# Risk factors
# ---------------------------------------------------------------------------

DEMO_RISK_FACTORS: list[RiskFactor] = [
    RiskFactor("USD_LIBOR_3M", RiskClass.GIRR, LiquidityHorizon.LH10),
    RiskFactor("EUR_SWAP_10Y", RiskClass.GIRR, LiquidityHorizon.LH20),
    RiskFactor("IG_CREDIT_SPD", RiskClass.CSR, LiquidityHorizon.LH40),
    RiskFactor("HY_CREDIT_SPD", RiskClass.CSR, LiquidityHorizon.LH60),
    RiskFactor("SPX_EQUITY", RiskClass.EQUITY, LiquidityHorizon.LH20),
    RiskFactor("EM_EQUITY", RiskClass.EQUITY, LiquidityHorizon.LH60),
    RiskFactor("EURUSD_FX", RiskClass.FX, LiquidityHorizon.LH10),
    RiskFactor("WTI_CRUDE", RiskClass.COMMODITY, LiquidityHorizon.LH20),
    RiskFactor("EXOTIC_RF", RiskClass.EQUITY, LiquidityHorizon.LH120),  # NMRF
]


def make_observations(
    as_of_date: date,
    well_observed_names: list[str],
    poorly_observed_names: list[str],
) -> list[RealPriceObservation]:
    """
    Generate synthetic real-price observations.

    well_observed: >= 24 observations in past 12 months  -> quantitative pass
    poorly_observed: only 10 observations                -> quantitative fail
    """
    obs: list[RealPriceObservation] = []

    for name in well_observed_names:
        n = 28  # comfortably above both thresholds
        step = 365 // n
        for i in range(n):
            d = as_of_date - timedelta(days=i * step)
            obs.append(RealPriceObservation(name, d, source="VENDOR_A"))

    for name in poorly_observed_names:
        n = 10  # below both thresholds
        step = 20
        for i in range(n):
            d = as_of_date - timedelta(days=i * step)
            obs.append(RealPriceObservation(name, d, source="VENDOR_B"))

    return obs


def make_scenario_pnl(desk: str, n_scenarios: int = 500) -> ScenarioPnL:
    """
    Generate a ScenarioPnL with plausible nested LH vectors.

    Strategy: simulate a base factor shock common to all scenarios, then
    add progressively larger shocks for risk factors with longer LH.
    Positive = loss convention.
    """
    spnl = ScenarioPnL(desk=desk)

    # LH10: all risk factors — base volatility
    base = RNG.normal(loc=0.0, scale=1_000.0, size=n_scenarios)

    # LH20+: only factors with LH >= 20 — slightly larger shocks
    lh20 = RNG.normal(loc=0.0, scale=800.0, size=n_scenarios)

    # LH40+: factors with LH >= 40
    lh40 = RNG.normal(loc=0.0, scale=600.0, size=n_scenarios)

    # LH60+: factors with LH >= 60
    lh60 = RNG.normal(loc=0.0, scale=400.0, size=n_scenarios)

    # LH120+: exotic/illiquid factors only
    lh120 = RNG.normal(loc=0.0, scale=200.0, size=n_scenarios)

    # Build per-risk-class vectors (simplified: pro-rata split across classes)
    # In practice these would come from the risk engine per risk class.
    for rc in [RiskClass.GIRR, RiskClass.FX]:
        spnl.add_vector(rc, LiquidityHorizon.LH10, (base * 0.3).tolist())
        spnl.add_vector(rc, LiquidityHorizon.LH20, (lh20 * 0.3).tolist())

    for rc in [RiskClass.CSR]:
        spnl.add_vector(rc, LiquidityHorizon.LH10, (base * 0.2).tolist())
        spnl.add_vector(rc, LiquidityHorizon.LH40, (lh40 * 0.2).tolist())
        spnl.add_vector(rc, LiquidityHorizon.LH60, (lh60 * 0.2).tolist())

    for rc in [RiskClass.EQUITY]:
        spnl.add_vector(rc, LiquidityHorizon.LH10, (base * 0.3).tolist())
        spnl.add_vector(rc, LiquidityHorizon.LH20, (lh20 * 0.3).tolist())
        spnl.add_vector(rc, LiquidityHorizon.LH60, (lh60 * 0.3).tolist())
        spnl.add_vector(rc, LiquidityHorizon.LH120, (lh120 * 0.3).tolist())

    for rc in [RiskClass.COMMODITY]:
        spnl.add_vector(rc, LiquidityHorizon.LH10, (base * 0.2).tolist())
        spnl.add_vector(rc, LiquidityHorizon.LH20, (lh20 * 0.2).tolist())

    return spnl


def aggregate_lh_vectors(
    spnl: ScenarioPnL,
) -> tuple[
    dict[LiquidityHorizon, list[float]],  # all-class aggregated
    dict[RiskClass, dict[LiquidityHorizon, list[float]]],  # per-class
]:
    """
    Aggregate scenario vectors for IMCC inputs.

    Returns:
        all_class:  LH -> summed vector across all risk classes
        per_class:  RiskClass -> LH -> vector
    """
    import collections

    # Gather per-class LH -> vector
    per_class: dict[RiskClass, dict[LiquidityHorizon, list[float]]] = {}
    for rc, lh_map in spnl.vectors.items():
        per_class[rc] = {}
        for lh, vec in lh_map.items():
            per_class[rc][lh] = vec

    # Per-class: fill missing LH10 from lowest available horizon
    # (LH10 must always exist for lha_es_from_vectors)
    for rc in per_class:
        if LiquidityHorizon.LH10 not in per_class[rc]:
            # Use the smallest available as the full-factor proxy
            smallest = min(per_class[rc].keys(), key=lambda lh: lh.value)
            per_class[rc][LiquidityHorizon.LH10] = per_class[rc][smallest]

    # Aggregate across all classes per LH by summing
    all_lh: dict[LiquidityHorizon, list[float]] = collections.defaultdict(list)
    n_scenarios: dict[LiquidityHorizon, int] = {}

    for rc, lh_map in per_class.items():
        for lh, vec in lh_map.items():
            if lh not in n_scenarios:
                n_scenarios[lh] = len(vec)
                all_lh[lh] = [0.0] * len(vec)
            for i, v in enumerate(vec):
                all_lh[lh][i] += v

    # Ensure LH10 exists in all_class
    if LiquidityHorizon.LH10 not in all_lh:
        raise RuntimeError("Could not build LH10 all-class vector — check scenario data")

    return dict(all_lh), per_class


def make_pnl_series(n: int = 260) -> tuple[list[float], list[float], list[float]]:
    """
    Generate synthetic APL, HPL, and VaR series for backtesting / PLA.

    Returns:
        (apl, hpl, var_estimates) — each of length n.
        P&L convention: positive = profit.
        VaR convention: positive magnitude.
    """
    # APL: actual — slightly fatter tails than HPL
    apl = RNG.normal(loc=50.0, scale=1_200.0, size=n).tolist()
    # HPL: hypothetical — same centre, tighter
    hpl = RNG.normal(loc=50.0, scale=1_050.0, size=n).tolist()
    # VaR: constant approximation for demo
    var_estimates = [2_500.0] * n
    return apl, hpl, var_estimates
