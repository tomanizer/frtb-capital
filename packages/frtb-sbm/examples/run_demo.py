"""
FRTB SBM (Sensitivities-Based Method) end-to-end demo.

Demonstrates construction of synthetic SbmSensitivity inputs and calling
calculate_sbm_capital for supported paths under BASEL_MAR21 profile:
- GIRR delta and vega
- Equity, FX, Commodity delta
- CSR non-sec delta
- Curvature (GIRR example)

Uses the public API and produces SbmCapitalResult with breakdowns.

Not for regulatory use. All data fabricated for illustration.

Run:
    uv run python packages/frtb-sbm/examples/run_demo.py
"""

from __future__ import annotations

from datetime import date

from frtb_sbm import (
    SbmCalculationContext,
    SbmCapitalResult,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    calculate_sbm_capital,
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


def main() -> None:
    print("FRTB SBM End-to-End Demo (synthetic sensitivities)")
    print("Prototype / illustration only. Not final regulatory capital.\n")

    run_girr_delta_demo()
    run_multi_class_delta_demo()
    run_vega_demo()
    run_curvature_demo()

    print("\nDemo complete.")
    print("See tests/fixtures/*/loader.py for more fixture-based examples.")
    print("See tests/test_sbm_public_api.py and batch/arrow tests for construction patterns.")
    print(
        "Supported under BASEL_MAR21 profile "
        "(GIRR/EQUITY/FX/COMMODITY/CSR delta/vega + curvature)."
    )


if __name__ == "__main__":
    main()
