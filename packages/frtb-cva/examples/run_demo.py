"""
FRTB CVA prototype demo.

Demonstrates end-to-end CVA capital calculation using synthetic data
for the supported paths:
- BA-CVA Reduced
- SA-CVA (GIRR delta shown)
- Mixed carve-out (BA + SA)

Not for regulatory use. All data is fabricated for illustration.

Run with:
    uv run python packages/frtb-cva/examples/run_demo.py
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from frtb_cva import (
    BaCvaHedgeType,
    CreditQuality,
    CvaCalculationContext,
    CvaCapitalResult,
    CvaCounterparty,
    CvaHedge,
    CvaMethod,
    CvaNettingSet,
    CvaRegulatoryProfile,
    CvaSector,
    CvaSourceLineage,
    HedgeEligibility,
    HedgeReferenceRelation,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
    calculate_cva_capital,
)

AS_OF = date(2026, 5, 31)
DESK = "cva-desk"
LE = "LE-001"


def _lineage(source_row_id: str) -> CvaSourceLineage:
    return CvaSourceLineage(
        source_system="synthetic-cva-demo",
        source_file="run_demo.py",
        source_row_id=source_row_id,
    )


def make_synthetic_counterparties(n: int = 5) -> tuple[CvaCounterparty, ...]:
    sectors = [
        CvaSector.SOVEREIGN,
        CvaSector.FINANCIALS,
        CvaSector.BASIC_MATERIALS_ENERGY_INDUSTRIALS,
    ]
    qualities = [CreditQuality.INVESTMENT_GRADE, CreditQuality.HIGH_YIELD]
    regions = ["EMEA", "AMER", "APAC"]
    return tuple(
        CvaCounterparty(
            counterparty_id=f"ctp-{i}",
            desk_id=DESK,
            legal_entity=LE,
            sector=sectors[i % len(sectors)],
            credit_quality=qualities[i % len(qualities)],
            region=regions[i % len(regions)],
            source_row_id=f"row-ctp-{i}",
            lineage=_lineage(f"row-ctp-{i}"),
        )
        for i in range(n)
    )


def make_synthetic_netting_sets(
    counterparties: tuple[CvaCounterparty, ...], n_per: int = 2
) -> tuple[CvaNettingSet, ...]:
    ns: list[CvaNettingSet] = []
    for i, ctp in enumerate(counterparties):
        for j in range(n_per):
            ns.append(
                CvaNettingSet(
                    netting_set_id=f"ns-{i}-{j}",
                    counterparty_id=ctp.counterparty_id,
                    ead=1_000_000.0 + i * 100_000 + j * 50_000,
                    effective_maturity=1.0 + (i % 5) * 0.5,
                    discount_factor=0.95,
                    currency="USD",
                    sign_convention="non_negative",
                    uses_imm_ead=False,
                    source_row_id=f"row-ns-{i}-{j}",
                    lineage=_lineage(f"row-ns-{i}-{j}"),
                )
            )
    return tuple(ns)


def make_synthetic_hedges(counterparties: tuple[CvaCounterparty, ...]) -> tuple[CvaHedge, ...]:
    # Minimal eligible single-name hedges for full BA demo
    return tuple(
        CvaHedge(
            hedge_id=f"hedge-{i}",
            source_row_id=f"row-hedge-{i}",
            counterparty_id=ctp.counterparty_id,
            hedge_type=BaCvaHedgeType.SINGLE_NAME_CDS,
            notional=500_000.0,
            remaining_maturity=3.0,
            discount_factor=0.92,
            reference_sector=ctp.sector,
            reference_credit_quality=ctp.credit_quality,
            reference_region=ctp.region,
            reference_relation=HedgeReferenceRelation.DIRECT,
            eligibility=HedgeEligibility.ELIGIBLE,
            is_internal=False,
            eligibility_evidence_id="ev-1",
            lineage=_lineage(f"row-hedge-{i}"),
        )
        for i, ctp in enumerate(counterparties[:2])
    )


def make_synthetic_sa_sensitivities() -> tuple[SaCvaSensitivity, ...]:
    # Minimal GIRR delta sensitivities for SA-CVA demo (portfolio aggregate style)
    tenors = ["1y", "5y", "10y"]
    return tuple(
        SaCvaSensitivity(
            sensitivity_id=f"sa-sens-{i}",
            risk_class=SaCvaRiskClass.GIRR,
            risk_measure=SaCvaRiskMeasure.DELTA,
            sensitivity_tag=SensitivityTag.CVA,
            bucket_id="USD",
            risk_factor_key=f"USD-ois-{tenors[i % 3]}",
            amount=100.0 + i * 5,
            amount_currency="USD",
            sign_convention="positive_loss",
            source_row_id=f"row-sa-sens-{i}",
            tenor=tenors[i % 3],
            lineage=_lineage(f"row-sa-sens-{i}"),
        )
        for i in range(6)
    )


def run_ba_reduced_demo() -> CvaCapitalResult:
    print("\n=== BA-CVA Reduced demo ===")
    context = CvaCalculationContext(
        run_id="demo-ba-reduced",
        calculation_date=AS_OF,
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.BA_CVA_REDUCED,
    )
    ctps = make_synthetic_counterparties(4)
    nss = make_synthetic_netting_sets(ctps, n_per=1)
    result = calculate_cva_capital(context, ctps, nss)
    print(f"Total CVA capital (reduced): {result.total_cva_capital:,.2f}")
    if result.ba_cva_reduced:
        print(f"  K_reduced: {result.ba_cva_reduced.k_reduced:,.2f}")
    return result


def run_sa_cva_demo() -> CvaCapitalResult:
    print("\n=== SA-CVA (GIRR delta) demo ===")
    context = CvaCalculationContext(
        run_id="demo-sa-cva",
        calculation_date=AS_OF,
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.SA_CVA,
        sa_cva_approved=True,
    )
    # For pure SA, counterparties/netting_sets can be minimal or empty if only using sensitivities
    # but API requires them; use dummies or from BA style
    # For pure SA-CVA, counterparties/netting_sets are not used (per validation)
    sens = make_synthetic_sa_sensitivities()
    result = calculate_cva_capital(context, [], [], sensitivities=sens)
    print(f"Total CVA capital (SA): {result.total_cva_capital:,.2f}")
    for rc in result.sa_cva_risk_class_capitals:
        print(f"  {rc.risk_class}: {rc.post_multiplier_capital:,.2f}")
    return result


def run_mixed_demo() -> CvaCapitalResult:
    print("\n=== Mixed carve-out demo (BA reduced + SA) ===")
    context = CvaCalculationContext(
        run_id="demo-mixed",
        calculation_date=AS_OF,
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.MIXED_CARVE_OUT,
        sa_cva_approved=True,
        carve_out_netting_set_ids=("ns-0-0",),
        sa_cva_sensitivity_scope_evidence_id="demo-sa-slice-non-carved",
    )
    ctps = make_synthetic_counterparties(3)
    nss = make_synthetic_netting_sets(ctps, n_per=2)
    # Mark the carved-out one (use enumerate to avoid hardcoding index 0)
    nss = list(nss)
    for idx, ns in enumerate(nss):
        if ns.netting_set_id == "ns-0-0":
            # recreate with flag (dataclass frozen, so new)
            nss[idx] = replace(ns, carved_out_to_ba_cva=True)
            break
    nss = tuple(nss)
    sens = make_synthetic_sa_sensitivities()
    result = calculate_cva_capital(context, ctps, nss, sensitivities=sens)
    print(f"Total CVA capital (mixed): {result.total_cva_capital:,.2f}")
    print(f"  Method components: {[(m.method, m.total_capital) for m in result.method_components]}")
    return result


def run_with_hedges_demo() -> CvaCapitalResult:
    print("\n=== BA-CVA Full (with hedges) demo ===")
    context = CvaCalculationContext(
        run_id="demo-ba-full",
        calculation_date=AS_OF,
        base_currency="USD",
        profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
        method=CvaMethod.BA_CVA_FULL,
    )
    ctps = make_synthetic_counterparties(3)
    nss = make_synthetic_netting_sets(ctps, n_per=1)
    hedges = make_synthetic_hedges(ctps)
    result = calculate_cva_capital(context, ctps, nss, hedges=hedges)
    print(f"Total CVA capital (full with hedges): {result.total_cva_capital:,.2f}")
    if result.ba_cva_full:
        print(f"  K_full: {result.ba_cva_full.k_full:,.2f}")
    return result


def main() -> None:
    print("FRTB CVA End-to-End Demo (synthetic data)")
    print("Prototype / illustration only. Not regulatory capital.\n")

    run_ba_reduced_demo()
    run_with_hedges_demo()
    run_sa_cva_demo()
    run_mixed_demo()

    print("\nDemo complete. See also:")
    print("  - tests/fixtures/*/loader.py for fixture-style inputs")
    print("  - scripts/benchmark_cva_target_scale.py for large-scale synthetic")
    print("  - test_*_fixture_workflow.py for workflow tests")


if __name__ == "__main__":
    main()
