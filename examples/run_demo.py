"""
FRTB IMA prototype demo.

Demonstrates the full capital calculation pipeline using synthetic data.
Not for regulatory use. All data is fabricated.
"""

from __future__ import annotations

from datetime import date

from frtb_ima.backtesting import backtest
from frtb_ima.capital import models_based_capital, supervisory_multiplier
from frtb_ima.data_models import ModellabilityStatus
from frtb_ima.demo_data import (
    DEMO_RISK_FACTORS,
    aggregate_lh_vectors,
    make_observations,
    make_pnl_series,
    make_scenario_pnl,
)
from frtb_ima.imcc import imcc
from frtb_ima.liquidity_horizon import lha_es_from_vectors
from frtb_ima.nmrf import aggregate_ses, ses_for_nmrf_linear
from frtb_ima.pla import pla_assessment
from frtb_ima.rfet import classify_risk_factor

AS_OF = date(2025, 6, 30)
DESK = "Rates & Credit"

SEP = "-" * 60


def section(title: str) -> None:
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


def main() -> None:
    print("\nFRTB IMA Prototype — NPR 2.0-style capital demo")
    print("Prototype only. Not for regulatory reporting.\n")

    # ------------------------------------------------------------------
    # 1. Risk factor classifications
    # ------------------------------------------------------------------
    section("Risk factor classifications")

    well_observed = [rf.name for rf in DEMO_RISK_FACTORS if rf.name != "EXOTIC_RF"]
    poorly_observed = ["EXOTIC_RF"]

    observations = make_observations(AS_OF, well_observed, poorly_observed)

    # Qualitative pass for all except the exotic factor
    qualitative_decisions = {rf.name: rf.name != "EXOTIC_RF" for rf in DEMO_RISK_FACTORS}

    classifications: dict[str, ModellabilityStatus] = {}
    for rf in DEMO_RISK_FACTORS:
        status = classify_risk_factor(
            rf,
            observations,
            qualitative_pass=qualitative_decisions[rf.name],
            as_of_date=AS_OF,
        )
        classifications[rf.name] = status
        print(f"  {rf.name:<20} LH={rf.liquidity_horizon.value:>3}d  {status.value}")

    modellable    = [n for n, s in classifications.items() if s == ModellabilityStatus.MODELLABLE]
    type_a_nmrfs  = [n for n, s in classifications.items() if s == ModellabilityStatus.TYPE_A_NMRF]
    type_b_nmrfs  = [n for n, s in classifications.items() if s == ModellabilityStatus.TYPE_B_NMRF]

    print(f"\n  Modellable: {len(modellable)}  |  Type A NMRF: {len(type_a_nmrfs)}  |  Type B NMRF: {len(type_b_nmrfs)}")

    # ------------------------------------------------------------------
    # 2. Scenario P&L + Liquidity horizon adjusted ES
    # ------------------------------------------------------------------
    section("Liquidity horizon adjusted ES")

    spnl = make_scenario_pnl(DESK)
    all_class_vectors, per_class_vectors = aggregate_lh_vectors(spnl)

    lha_es = lha_es_from_vectors(all_class_vectors)
    print(f"  LHA ES (all classes):  {lha_es:>12,.2f}")

    print("\n  Per risk-class LHA ES:")
    for rc, lh_vecs in per_class_vectors.items():
        rc_lha = lha_es_from_vectors(lh_vecs)
        print(f"    {rc.value:<12} {rc_lha:>12,.2f}")

    # ------------------------------------------------------------------
    # 3. IMCC
    # ------------------------------------------------------------------
    section("IMCC")

    imcc_value = imcc(all_class_vectors, per_class_vectors)
    print(f"  IMCC:  {imcc_value:>12,.2f}")

    # For the 60d average demo, just use today's value repeated (simplification)
    imcc_60d_avg = imcc_value

    # ------------------------------------------------------------------
    # 4. SES (NMRF stressed ES)
    # ------------------------------------------------------------------
    section("SES")

    # Synthetic sensitivities and shocks for NMRF factors
    nmrf_shocks: dict[str, tuple[float, float]] = {
        # name -> (sensitivity, shock)
        "EM_CREDIT_SPD": (50_000.0, 0.02),   # hypothetical Type A NMRF
        "EXOTIC_RF":     (30_000.0, 0.05),    # Type B
    }

    # Inject hypothetical Type A factor not in the RFET classification above
    classifications["EM_CREDIT_SPD"] = ModellabilityStatus.TYPE_A_NMRF

    type_a_ses_values: list[float] = []
    type_b_ses_values: list[float] = []

    for name, (sens, shock) in nmrf_shocks.items():
        ses_i = ses_for_nmrf_linear(sens, shock)
        status = classifications.get(name, ModellabilityStatus.TYPE_B_NMRF)
        if status == ModellabilityStatus.TYPE_A_NMRF:
            type_a_ses_values.append(ses_i)
            tag = "Type A"
        else:
            type_b_ses_values.append(ses_i)
            tag = "Type B"
        print(f"  {name:<20} SES_i = {ses_i:>10,.2f}  ({tag})")

    ses_total = aggregate_ses(type_a_ses_values, type_b_ses_values)
    print(f"\n  Total SES:  {ses_total:>12,.2f}")

    ses_60d_avg = ses_total

    # ------------------------------------------------------------------
    # 5. Models-based capital
    # ------------------------------------------------------------------
    section("Models-based capital")

    # Use backtesting to determine multiplier (computed below — no exceptions yet)
    multiplier = 1.5
    capital_result = models_based_capital(
        imcc_t_minus_1=imcc_value,
        ses_t_minus_1=ses_total,
        imcc_60d_avg=imcc_60d_avg,
        ses_60d_avg=ses_60d_avg,
        multiplier=multiplier,
    )
    print(f"  IMCC (t-1):         {capital_result.imcc_t_minus_1:>12,.2f}")
    print(f"  SES (t-1):          {capital_result.ses_t_minus_1:>12,.2f}")
    print(f"  IMCC 60d avg:       {capital_result.imcc_60d_avg:>12,.2f}")
    print(f"  SES 60d avg:        {capital_result.ses_60d_avg:>12,.2f}")
    print(f"  Multiplier:         {capital_result.multiplier:>12.2f}")
    print(f"  Binding term:       {capital_result.binding_term:>12}")
    print(f"  Models-based MRC:   {capital_result.models_based_capital:>12,.2f}")

    # ------------------------------------------------------------------
    # 6. PLA KS statistic
    # ------------------------------------------------------------------
    section("PLA KS statistic")

    apl, hpl, var_estimates = make_pnl_series(n=260)
    pla = pla_assessment(hpl=hpl, rtpl=apl)  # using APL as RTPL proxy in demo
    print(f"  KS statistic:   {pla.ks_statistic:.4f}")
    print(f"  Zone:           {pla.zone}")
    print(f"  HPL length:     {pla.n_hpl}")
    print(f"  RTPL length:    {pla.n_rtpl}")

    # ------------------------------------------------------------------
    # 7. Backtesting exception counts
    # ------------------------------------------------------------------
    section("Backtesting exception counts")

    bt = backtest(apl, hpl, var_estimates, window=250)
    mult = supervisory_multiplier(bt.apl_exceptions)
    print(f"  Window:             {bt.window_size} business days")
    print(f"  APL exceptions:     {bt.apl_exceptions:>4}  (zone: {bt.apl_zone})")
    print(f"  HPL exceptions:     {bt.hpl_exceptions:>4}  (zone: {bt.hpl_zone})")
    print(f"  Supervisory mult:   {mult:.2f}")

    print(f"\n{SEP}")
    print("  Demo complete.")
    print(SEP)


if __name__ == "__main__":
    main()
