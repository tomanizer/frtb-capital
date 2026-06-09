"""
FRTB SBM (Sensitivities-Based Method) end-to-end demo.

Demonstrates construction of synthetic SbmSensitivity inputs and calling
calculate_sbm_capital for supported paths under BASEL_MAR21 profile:
- GIRR delta and vega
- Equity, FX, Commodity delta
- CSR non-sec delta
- Curvature (GIRR example)
- Post-calculation analytical Euler attribution (delta/vega) and explicit
  unsupported records for curvature
- Baseline-vs-candidate capital impact (finite difference between two runs)

Uses the public API and produces SbmCapitalResult with breakdowns.

Not for regulatory use. All data fabricated for illustration.

Run:
    uv run python packages/frtb-sbm/examples/run_demo.py
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

from frtb_common.attribution import AttributionMethod
from frtb_sbm import (
    SbmCalculationContext,
    SbmCapitalResult,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    calculate_sbm_attribution,
    calculate_sbm_capital,
    calculate_sbm_capital_impact,
)

AS_OF = date(2026, 5, 30)
DESK = "rates-desk"
LE = "LE-001"


def _lineage(row_id: str) -> SbmSourceLineage:
    return SbmSourceLineage(
        source_system="synthetic-sbm-demo",
        source_file="run_demo.py",
        source_row_id=row_id,
        source_column_map=(("amount", "amount"),),
    )


def sample_context(
    profile: SbmRegulatoryProfile = SbmRegulatoryProfile.BASEL_MAR21,
) -> SbmCalculationContext:
    return SbmCalculationContext(
        run_id="sbm-demo-run",
        calculation_date=AS_OF,
        base_currency="USD",
        reporting_currency="USD",
        profile_id=profile.value,
        desk_id=DESK,
        legal_entity=LE,
    )


def make_girr_delta_sensitivities() -> list[SbmSensitivity]:
    """GIRR delta for EUR and USD in bucket 1 and 2."""
    return [
        SbmSensitivity(
            sensitivity_id="eur-1y",
            source_row_id="row-girr-001",
            desk_id=DESK,
            legal_entity=LE,
            risk_class=SbmRiskClass.GIRR,
            risk_measure=SbmRiskMeasure.DELTA,
            bucket="1",
            risk_factor="EUR",
            amount=1_000_000.0,
            amount_currency="USD",
            tenor="1y",
            sign_convention=SbmSignConvention.RECEIVE,
            lineage=_lineage("row-girr-001"),
        ),
        SbmSensitivity(
            sensitivity_id="eur-5y",
            source_row_id="row-girr-002",
            desk_id=DESK,
            legal_entity=LE,
            risk_class=SbmRiskClass.GIRR,
            risk_measure=SbmRiskMeasure.DELTA,
            bucket="1",
            risk_factor="EUR",
            amount=500_000.0,
            amount_currency="USD",
            tenor="5y",
            sign_convention=SbmSignConvention.RECEIVE,
            lineage=_lineage("row-girr-002"),
        ),
        SbmSensitivity(
            sensitivity_id="usd-5y",
            source_row_id="row-girr-003",
            desk_id=DESK,
            legal_entity=LE,
            risk_class=SbmRiskClass.GIRR,
            risk_measure=SbmRiskMeasure.DELTA,
            bucket="2",
            risk_factor="USD",
            amount=800_000.0,
            amount_currency="USD",
            tenor="5y",
            sign_convention=SbmSignConvention.RECEIVE,
            lineage=_lineage("row-girr-003"),
        ),
    ]


def make_equity_delta_sensitivities() -> list[SbmSensitivity]:
    return [
        SbmSensitivity(
            sensitivity_id="eq-spx",
            source_row_id="row-eq-001",
            desk_id=DESK,
            legal_entity=LE,
            risk_class=SbmRiskClass.EQUITY,
            risk_measure=SbmRiskMeasure.DELTA,
            bucket="5",
            risk_factor="SPOT",
            amount=2_000_000.0,
            amount_currency="USD",
            sign_convention=SbmSignConvention.RECEIVE,
            lineage=_lineage("row-eq-001"),
            qualifier="SPX",
        ),
    ]


def make_fx_delta_sensitivities() -> list[SbmSensitivity]:
    return [
        SbmSensitivity(
            sensitivity_id="fx-eurusd",
            source_row_id="row-fx-001",
            desk_id=DESK,
            legal_entity=LE,
            risk_class=SbmRiskClass.FX,
            risk_measure=SbmRiskMeasure.DELTA,
            bucket="EUR",
            risk_factor="EUR",
            amount=1_500_000.0,
            amount_currency="USD",
            sign_convention=SbmSignConvention.RECEIVE,
            lineage=_lineage("row-fx-001"),
        ),
    ]


def make_commodity_delta_sensitivities() -> list[SbmSensitivity]:
    return [
        SbmSensitivity(
            sensitivity_id="cmd-wti",
            source_row_id="row-cmd-001",
            desk_id=DESK,
            legal_entity=LE,
            risk_class=SbmRiskClass.COMMODITY,
            risk_measure=SbmRiskMeasure.DELTA,
            bucket="1",  # energy
            risk_factor="WTI",
            amount=500_000.0,
            amount_currency="USD",
            sign_convention=SbmSignConvention.RECEIVE,
            lineage=_lineage("row-cmd-001"),
            qualifier="CRUDE",
            tenor="3m",
        ),
    ]


def make_csr_nonsec_delta_sensitivities() -> list[SbmSensitivity]:
    return [
        SbmSensitivity(
            sensitivity_id="csr-bond",
            source_row_id="row-csr-001",
            desk_id=DESK,
            legal_entity=LE,
            risk_class=SbmRiskClass.CSR_NONSEC,
            risk_measure=SbmRiskMeasure.DELTA,
            bucket="4",
            risk_factor="BOND",
            amount=300_000.0,
            amount_currency="USD",
            tenor="5y",
            sign_convention=SbmSignConvention.RECEIVE,
            lineage=_lineage("row-csr-001"),
            qualifier="CORP",
        ),
    ]


def make_girr_vega_sensitivities() -> list[SbmSensitivity]:
    return [
        SbmSensitivity(
            sensitivity_id="girr-vega-eur-5y",
            source_row_id="row-vega-001",
            desk_id=DESK,
            legal_entity=LE,
            risk_class=SbmRiskClass.GIRR,
            risk_measure=SbmRiskMeasure.VEGA,
            bucket="1",
            risk_factor="EUR",
            amount=10_000.0,
            amount_currency="USD",
            tenor="5y",
            option_tenor="1y",
            sign_convention=SbmSignConvention.RECEIVE,
            lineage=_lineage("row-vega-001"),
        ),
    ]


def make_curvature_sensitivities() -> list[SbmSensitivity]:
    """GIRR curvature example with up/down shocks."""
    return [
        SbmSensitivity(
            sensitivity_id="girr-curv-eur",
            source_row_id="row-curv-001",
            desk_id=DESK,
            legal_entity=LE,
            risk_class=SbmRiskClass.GIRR,
            risk_measure=SbmRiskMeasure.CURVATURE,
            bucket="1",
            risk_factor="EUR",
            amount=0.0,  # not used directly for curv
            amount_currency="USD",
            tenor="5y",
            up_shock_amount=50_000.0,
            down_shock_amount=-40_000.0,
            sign_convention=SbmSignConvention.RECEIVE,
            lineage=_lineage("row-curv-001"),
        ),
    ]


def run_girr_delta_demo() -> SbmCapitalResult:
    print("\n=== GIRR Delta demo ===")
    context = sample_context()
    sens = make_girr_delta_sensitivities()
    result = calculate_sbm_capital(sens, context=context)
    print(f"Total SBM capital: {result.total_capital:,.2f}")
    for rc in result.risk_classes:
        if rc.risk_class == SbmRiskClass.GIRR:
            print(f"  GIRR delta capital: {rc.selected_capital:,.2f}")
            for b in rc.buckets:
                print(f"    Bucket {b.bucket_id}: Kb={b.kb:,.2f}")
    return result


def run_multi_class_delta_demo() -> SbmCapitalResult:
    print("\n=== Multi-class delta (GIRR + Equity + FX + Comm) demo ===")
    context = sample_context()
    sens = (
        make_girr_delta_sensitivities()
        + make_equity_delta_sensitivities()
        + make_fx_delta_sensitivities()
        + make_commodity_delta_sensitivities()
        + make_csr_nonsec_delta_sensitivities()
    )
    result = calculate_sbm_capital(sens, context=context)
    print(f"Total SBM capital: {result.total_capital:,.2f}")
    for rc in result.risk_classes:
        print(f"  {rc.risk_class.value} capital: {rc.selected_capital:,.2f}")
    return result


def run_vega_demo() -> SbmCapitalResult:
    print("\n=== GIRR Vega demo ===")
    context = sample_context()
    sens = make_girr_vega_sensitivities()
    result = calculate_sbm_capital(sens, context=context)
    print(f"Total SBM capital: {result.total_capital:,.2f}")
    return result


def run_curvature_demo() -> SbmCapitalResult:
    print("\n=== GIRR Curvature demo ===")
    context = sample_context()
    sens = make_curvature_sensitivities()
    result = calculate_sbm_capital(sens, context=context)
    print(f"Total SBM capital: {result.total_capital:,.2f}")
    for rc in result.risk_classes:
        if rc.risk_class == SbmRiskClass.GIRR:
            print(f"  GIRR curvature: {rc.selected_capital:,.2f}")
    return result


def print_attribution_summary(result: SbmCapitalResult, *, heading: str) -> None:
    """Print analytical Euler contributions and unsupported attribution branches."""
    contributions = calculate_sbm_attribution(result)
    print(f"\n--- {heading} ---")

    euler = [c for c in contributions if c.method == AttributionMethod.ANALYTICAL_EULER]
    unsupported = [c for c in contributions if c.method == AttributionMethod.UNSUPPORTED]
    residuals = [c for c in contributions if c.method == AttributionMethod.RESIDUAL]

    if euler:
        print(
            f"{'source_id':<18} {'category':<10} {'bucket':<8} "
            f"{'WS':>12} {'marginal':>10} {'contribution':>14}"
        )
        for c in sorted(euler, key=lambda row: (row.category, row.bucket_key or "", row.source_id)):
            print(
                f"{c.source_id:<18} {c.category:<10} {(c.bucket_key or '-'):<8} "
                f"{c.base_amount:>12,.2f} {c.marginal_multiplier:>10.6f} "
                f"{c.contribution:>14,.2f}"
            )

    for c in unsupported:
        print(f"  UNSUPPORTED ({c.category}): {c.reason}")
        if c.residual:
            print(f"    risk-class capital in residual: {c.residual:,.2f}")

    for c in residuals:
        print(f"  RESIDUAL ({c.category}): {c.residual:,.2f} — {c.reason}")

    attributed_total = sum((r.contribution or 0.0) + r.residual for r in contributions)
    print(f"  Attribution sum: {attributed_total:,.2f}  |  SBM total: {result.total_capital:,.2f}")


def run_attribution_demo(
    girr_delta_result: SbmCapitalResult,
    multi_class_result: SbmCapitalResult,
    curvature_result: SbmCapitalResult,
) -> None:
    print("\n=== Attribution (analytical Euler) demo ===")
    print(
        "Delta and vega paths decompose selected risk-class capital to sensitivity "
        "grain. Curvature returns explicit UNSUPPORTED records (MAR21.5 CVR floor)."
    )

    print_attribution_summary(
        girr_delta_result,
        heading="GIRR delta — per-sensitivity Euler contributions",
    )
    print_attribution_summary(
        multi_class_result,
        heading="Multi-class delta — portfolio-wide Euler contributions",
    )
    print_attribution_summary(
        curvature_result,
        heading="GIRR curvature — unsupported attribution branch",
    )


def run_impact_demo() -> None:
    """Compare two GIRR delta runs after bumping eur-1y notional (+20%)."""
    print("\n=== Capital impact (finite difference) demo ===")
    print(
        "Impact is the portfolio total delta between two reconciled capital runs. "
        "It is not per-sensitivity marginal attribution (see attribution section)."
    )

    baseline_context = replace(sample_context(), run_id="sbm-impact-baseline")
    candidate_context = replace(sample_context(), run_id="sbm-impact-candidate")

    baseline_sens = make_girr_delta_sensitivities()
    candidate_sens = [
        replace(s, amount=1_200_000.0) if s.sensitivity_id == "eur-1y" else s
        for s in baseline_sens
    ]

    baseline = calculate_sbm_capital(baseline_sens, context=baseline_context)
    candidate = calculate_sbm_capital(candidate_sens, context=candidate_context)
    impact = calculate_sbm_capital_impact(baseline, candidate)

    print("  Scenario: bump eur-1y notional 1,000,000 → 1,200,000 (+20%)")
    print(f"  Baseline total ({impact.baseline_run_id}): {impact.baseline_total:,.2f}")
    print(f"  Candidate total ({impact.candidate_run_id}): {impact.candidate_total:,.2f}")
    print(f"  Impact delta (candidate - baseline): {impact.delta:+,.2f}")
    print(f"  Method: {impact.method}")


def main() -> None:
    print("FRTB SBM End-to-End Demo (synthetic sensitivities)")
    print("Prototype / illustration only. Not final regulatory capital.\n")

    girr_delta_result = run_girr_delta_demo()
    multi_class_result = run_multi_class_delta_demo()
    run_vega_demo()
    curvature_result = run_curvature_demo()
    run_attribution_demo(girr_delta_result, multi_class_result, curvature_result)
    run_impact_demo()

    print("\nDemo complete.")
    print("See tests/fixtures/*/loader.py for more fixture-based examples.")
    print("See tests/test_sbm_public_api.py and batch/arrow tests for construction patterns.")
    print(
        "Supported under BASEL_MAR21 profile (GIRR/EQUITY/FX/COMMODITY/CSR delta/vega + curvature)."
    )
    print("See packages/frtb-sbm/ATTRIBUTION.md for attribution method and limitations.")


if __name__ == "__main__":
    main()
