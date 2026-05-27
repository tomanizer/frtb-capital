"""
FRTB IMA prototype demo.

Demonstrates the full capital calculation pipeline using synthetic data.
Not for regulatory use. All data is fabricated.
"""

from __future__ import annotations

from datetime import date

import numpy as np

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
from frtb_ima.nmrf import (
    NMRFStressArtifact,
    calculate_nmrf_capital_for_policy,
)
from frtb_ima.nmrf_method_selection import (
    NMRFMethodSelectionInput,
    select_nmrf_methods,
)
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

    well_observed = [
        rf.name for rf in DEMO_RISK_FACTORS if rf.name not in {"HY_CREDIT_SPD", "EXOTIC_RF"}
    ]
    poorly_observed = ["HY_CREDIT_SPD", "EXOTIC_RF"]

    observations = make_observations(
        context.as_of_date,
        well_observed,
        poorly_observed,
    )

    # Qualitative pass for all except the exotic factor. HY_CREDIT_SPD therefore
    # becomes a synthetic Type A NMRF; EXOTIC_RF becomes a synthetic Type B NMRF.
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
    # 2. NMRF method selection
    # ------------------------------------------------------------------
    section("NMRF method selection")

    selection_inputs: list[NMRFMethodSelectionInput] = []
    risk_factor_by_name = {rf.name: rf for rf in DEMO_RISK_FACTORS}
    for name in [*type_a_nmrfs, *type_b_nmrfs]:
        rf = risk_factor_by_name[name]
        if name == "HY_CREDIT_SPD":
            selection_inputs.append(
                NMRFMethodSelectionInput(
                    risk_factor_name=name,
                    modellability_status=classifications[name],
                    liquidity_horizon=rf.liquidity_horizon,
                    direct_method_available=True,
                    direct_shock_well_defined=True,
                    direct_robust=True,
                    source="synthetic governance rule",
                )
            )
        else:
            selection_inputs.append(
                NMRFMethodSelectionInput(
                    risk_factor_name=name,
                    modellability_status=classifications[name],
                    liquidity_horizon=rf.liquidity_horizon,
                    nonlinear=True,
                    full_revaluation_available=True,
                    source="synthetic governance rule",
                )
            )

    method_decisions = select_nmrf_methods(selection_inputs, context.policy)
    valuation_instructions = tuple(
        decision.to_valuation_instruction() for decision in method_decisions
    )
    for instruction in valuation_instructions:
        print(
            f"  {instruction.risk_factor_name:<20} "
            f"{instruction.method.value:<18} "
            f"required LH={instruction.required_liquidity_horizon.value:>3}d  "
            f"{instruction.reason.value}"
        )

    # ------------------------------------------------------------------
    # 3. Scenario P&L + Liquidity horizon adjusted ES
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
    # 4. IMCC
    # ------------------------------------------------------------------
    section("IMCC")

    imcc_value = imcc_for_policy(all_class_vectors, per_class_vectors, context.policy)
    print(f"  IMCC:  {imcc_value:>12,.2f}")

    # For the 60d average demo, just use today's value repeated (simplification)
    imcc_60d_avg = imcc_value

    # ------------------------------------------------------------------
    # 5. SES (NMRF stressed ES)
    # ------------------------------------------------------------------
    section("SES")

    artifact_losses = {
        "HY_CREDIT_SPD": np.linspace(-500.0, 2_500.0, 500),
        "EXOTIC_RF": np.linspace(-1_000.0, 4_000.0, 500),
    }
    artifacts = tuple(
        NMRFStressArtifact(
            risk_factor_name=instruction.risk_factor_name,
            method=instruction.method,
            losses=artifact_losses[instruction.risk_factor_name],
            liquidity_horizon=instruction.required_liquidity_horizon,
            stress_period="synthetic 12-month stress window",
            source="synthetic valuation run artifact",
            generated_by_prototype=True,
            notes="Demo artifact; not a production pricing output.",
        )
        for instruction in valuation_instructions
    )

    nmrf_capital = calculate_nmrf_capital_for_policy(
        classifications,
        artifacts,
        context.policy,
        required_methods={
            instruction.risk_factor_name: instruction.method
            for instruction in valuation_instructions
        },
        required_liquidity_horizons={
            instruction.risk_factor_name: instruction.required_liquidity_horizon
            for instruction in valuation_instructions
        },
    )
    for result in [*nmrf_capital.type_a_results, *nmrf_capital.type_b_results]:
        status = classifications[result.risk_factor_name]
        print(
            f"  {result.risk_factor_name:<20} SES_i = {result.ses:>10,.2f}  "
            f"({status.value}, {result.method.value})"
        )

    print(
        "\n  IMCC RFs: "
        f"{len(nmrf_capital.routing.imcc_risk_factors)}  |  "
        f"SES RFs: {len(nmrf_capital.routing.ses_risk_factors)}"
    )

    ses_total = nmrf_capital.total_ses
    print(f"\n  Total SES:  {ses_total:>12,.2f}")

    ses_60d_avg = ses_total

    # ------------------------------------------------------------------
    # 6. Models-based capital
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
    # 7. PLA KS statistic
    # ------------------------------------------------------------------
    section("PLA KS statistic")

    apl, hpl, var_estimates = make_pnl_series(n=260)
    pla = pla_assessment_for_policy(hpl=hpl, rtpl=apl, policy=context.policy)
    print(f"  KS statistic:   {pla.ks_statistic:.4f}")
    print(f"  Zone:           {pla.zone}")
    print(f"  HPL length:     {pla.n_hpl}")
    print(f"  RTPL length:    {pla.n_rtpl}")

    # ------------------------------------------------------------------
    # 8. Backtesting exception counts
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
