"""
FRTB IMA prototype demo.

Demonstrates the full capital calculation pipeline using synthetic data.
Not for regulatory use. All data is fabricated.
"""

from __future__ import annotations

from datetime import date

from frtb_ima.backtesting import trading_desk_backtest_for_policy
from frtb_ima.capital import models_based_capital, supervisory_multiplier_for_policy
from frtb_ima.data_models import ModellabilityStatus
from frtb_ima.demo_data import (
    DEMO_RISK_FACTORS,
    aggregate_lh_vectors,
    make_observations,
    make_pnl_series,
    make_scenario_pnl,
)
from frtb_ima.imcc import imcc_for_policy
from frtb_ima.liquidity_horizon import lha_es_from_vectors
from frtb_ima.nmrf import aggregate_ses_for_policy, ses_for_nmrf_linear
from frtb_ima.pla import pla_assessment_for_policy
from frtb_ima.regimes import CalculationContext, RegulatoryRegime, get_policy
from frtb_ima.rfet import classify_risk_factor_for_policy

AS_OF = date(2025, 6, 30)
DESK = "Rates & Credit"

SEP = "-" * 60


def section(title: str) -> None:
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


def main() -> None:
    context = CalculationContext(
        policy=get_policy(RegulatoryRegime.FED_NPR_2_0),
        as_of_date=AS_OF,
        desk=DESK,
        run_id="synthetic-demo",
    )

    print("\nFRTB IMA Prototype — NPR 2.0-style capital demo")
    print("Prototype only. Not for regulatory reporting.\n")
    print(f"Regulatory profile: {context.policy.regime.value}\n")

    # ------------------------------------------------------------------
    # 1. Risk factor classifications
    # ------------------------------------------------------------------
    section("Risk factor classifications")

    well_observed = [rf.name for rf in DEMO_RISK_FACTORS if rf.name != "EXOTIC_RF"]
    poorly_observed = ["EXOTIC_RF"]

    observations = make_observations(context.as_of_date, well_observed, poorly_observed)

    # Qualitative pass for all except the exotic factor
    qualitative_decisions = {rf.name: rf.name != "EXOTIC_RF" for rf in DEMO_RISK_FACTORS}

    classifications: dict[str, ModellabilityStatus] = {}
    for rf in DEMO_RISK_FACTORS:
        status = classify_risk_factor_for_policy(
            rf,
            observations,
            qualitative_pass=qualitative_decisions[rf.name],
            as_of_date=context.as_of_date,
            policy=context.policy,
        )
        classifications[rf.name] = status
        print(f"  {rf.name:<20} LH={rf.liquidity_horizon.value:>3}d  {status.value}")

    modellable    = [n for n, s in classifications.items() if s == ModellabilityStatus.MODELLABLE]
    type_a_nmrfs  = [n for n, s in classifications.items() if s == ModellabilityStatus.TYPE_A_NMRF]
    type_b_nmrfs  = [n for n, s in classifications.items() if s == ModellabilityStatus.TYPE_B_NMRF]

    print(
        f"\n  Modellable: {len(modellable)}  |  "
        f"Type A NMRF: {len(type_a_nmrfs)}  |  "
        f"Type B NMRF: {len(type_b_nmrfs)}"
    )

    # ------------------------------------------------------------------
    # 2. Scenario P&L + Liquidity horizon adjusted ES
    # ------------------------------------------------------------------
    section("Liquidity horizon adjusted ES")

    spnl = make_scenario_pnl(DESK)
    all_class_vectors, per_class_vectors = aggregate_lh_vectors(spnl)

    lha_es = lha_es_from_vectors(
        all_class_vectors,
        alpha=context.policy.es_confidence_level,
        lha_weights=context.policy.lha_weights,
    )
    print(f"  LHA ES (all classes):  {lha_es:>12,.2f}")

    print("\n  Per risk-class LHA ES:")
    for rc, lh_vecs in per_class_vectors.items():
        rc_lha = lha_es_from_vectors(
            lh_vecs,
            alpha=context.policy.es_confidence_level,
            lha_weights=context.policy.lha_weights,
        )
        print(f"    {rc.value:<12} {rc_lha:>12,.2f}")

    # ------------------------------------------------------------------
    # 3. IMCC
    # ------------------------------------------------------------------
    section("IMCC")

    imcc_value = imcc_for_policy(all_class_vectors, per_class_vectors, context.policy)
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

    ses_total = aggregate_ses_for_policy(type_a_ses_values, type_b_ses_values, context.policy)
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
    pla = pla_assessment_for_policy(hpl=hpl, rtpl=apl, policy=context.policy)
    print(f"  KS statistic:   {pla.ks_statistic:.4f}")
    print(f"  Zone:           {pla.zone}")
    print(f"  HPL length:     {pla.n_hpl}")
    print(f"  RTPL length:    {pla.n_rtpl}")

    # ------------------------------------------------------------------
    # 7. Backtesting exception counts
    # ------------------------------------------------------------------
    section("Backtesting exception counts")

    var_by_confidence = {
        0.975: [v * 0.85 for v in var_estimates],
        0.99: var_estimates,
    }
    bt = trading_desk_backtest_for_policy(
        apl,
        hpl,
        var_by_confidence,
        policy=context.policy,
    )
    bt99 = bt.level(0.99)
    bt975 = bt.level(0.975)
    mult = supervisory_multiplier_for_policy(bt99.apl_exceptions, context.policy)
    print(f"  Window:             {bt.window_size} business days")
    print(
        f"  APL exceptions 99%: {bt99.apl_exceptions:>4}  "
        f"(limit: {bt99.exception_limit:.0f})"
    )
    print(
        f"  HPL exceptions 99%: {bt99.hpl_exceptions:>4}  "
        f"(limit: {bt99.exception_limit:.0f})"
    )
    print(
        f"  APL exceptions 97.5%: {bt975.apl_exceptions:>2}  "
        f"(limit: {bt975.exception_limit:.0f})"
    )
    print(
        f"  HPL exceptions 97.5%: {bt975.hpl_exceptions:>2}  "
        f"(limit: {bt975.exception_limit:.0f})"
    )
    print(f"  Backtesting pass:   {bt.model_eligible}")
    print(f"  Supervisory mult:   {mult:.2f}")

    print(f"\n{SEP}")
    print("  Demo complete.")
    print(SEP)


if __name__ == "__main__":
    main()
