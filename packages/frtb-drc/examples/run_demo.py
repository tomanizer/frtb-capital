"""
FRTB DRC (Default Risk Charge) quick-start demo.

Demonstrates:
- Loading the canonical synthetic non-securitisation portfolio (40 positions)
  via the package's committed v2 fixture (exercises gross JTD, maturity
  scaling, same-seniority netting, HBR, bucket/category capital, P&L
  flooring, defaulted overrides, rejected offsets).
- Calling the public calculate_drc_capital entrypoint.
- Printing total, category, and sample bucket breakdowns plus rejected
  offsets (for attribution readiness).
- A minimal inline raw DrcPosition construction example (shows the exact
  input fields an upstream risk system must supply).

Uses the public API and DrcCapitalResult (frozen, with BranchMetadata,
citations, input_hash, profile_hash for audit/reconciliation).

Not for regulatory use. All data is fabricated for illustration only.

Run:
    uv run python packages/frtb-drc/examples/run_demo.py

See also the detailed step-by-step notebooks/ (00-05) for math walkthroughs
per regulatory mechanic, tests/fixtures/drc_nonsec_v2/ for the golden
manifest + expected outputs, and docs/ for regulatory traceability.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

# Support direct execution: uv run python packages/frtb-drc/examples/run_demo.py
# (makes "from drc_nonsec_fixture import ..." resolve the local shim).
sys.path.insert(0, str(Path(__file__).parent))

from drc_nonsec_fixture import (
    load_drc_nonsec_v2_fixture,
    run_fixture_workflow,
)
from frtb_drc import (
    CreditQuality,
    DefaultDirection,
    DrcCalculationContext,
    DrcCapitalResult,
    DrcInstrumentType,
    DrcPosition,
    DrcRiskClass,
    DrcSeniority,
    DrcSourceLineage,
    calculate_drc_capital,
)

AS_OF = date(2026, 5, 29)
DESK = "credit-desk"
LE = "bank-na"


def _lineage(row_id: str) -> DrcSourceLineage:
    return DrcSourceLineage(
        source_system="synthetic-drc-demo",
        source_file="run_demo.py",
        source_row_id=row_id,
        source_column_map={"notional": "notional"},
    )


def make_minimal_drc_position() -> DrcPosition:
    """Minimal raw DrcPosition construction (illustrates exact upstream fields)."""
    return DrcPosition(
        position_id="demo-minimal-001",
        source_row_id="row-demo-001",
        desk_id=DESK,
        legal_entity=LE,
        risk_class=DrcRiskClass.NON_SECURITISATION,
        instrument_type=DrcInstrumentType.BOND,
        default_direction=DefaultDirection.LONG,
        issuer_id="acme-corp",
        tranche_id=None,
        index_series_id=None,
        bucket_key="CORPORATE",
        seniority=DrcSeniority.SENIOR_DEBT,
        credit_quality=CreditQuality.INVESTMENT_GRADE,
        notional=1_000_000.0,
        market_value=None,
        cumulative_pnl=0.0,
        maturity_years=2.5,
        currency="USD",
        lineage=_lineage("row-demo-001"),
        citation_ids=("US_NPR_210_SCOPE",),
        is_defaulted=False,
    )


def run_fixture_demo() -> DrcCapitalResult:
    print("\n=== DRC non-securitisation v2 fixture demo (40 positions) ===")
    fixture = load_drc_nonsec_v2_fixture()
    print(f"  Positions: {len(fixture.positions)}")
    print(f"  Profile:   {fixture.context.profile_id}")
    print(f"  As-of:     {fixture.context.calculation_date}")

    result: DrcCapitalResult = calculate_drc_capital(
        fixture.positions, context=fixture.context
    )
    print(f"\n  Total DRC capital: {result.total_drc:,.2f}")
    print(f"  Input hash: {result.input_hash[:16]}...")
    print(f"  Profile hash: {result.profile_hash[:16]}...")

    # Category level (for non-sec there is one main category result)
    for cat in result.categories:
        print(f"  Category {cat.category_id} capital: {cat.capital:,.2f}")

    # Show a couple buckets with HBR / weighted
    print("\n  Sample bucket results:")
    shown = 0
    for cat in result.categories:
        for b in cat.bucket_results:
            if shown >= 3:
                break
            print(
                f"    {b.bucket_key:<18} capital={b.capital:>10,.2f} "
                f"HBR={b.hbr.ratio:.3f} wl={b.weighted_long:>10,.0f} "
                f"ws={b.weighted_short:>10,.0f} floor={b.floor_applied}"
            )
            shown += 1

    # Rejected offsets live inside NetJtd.rejected_offsets (per netting group) for
    # attribution. Count any non-empty here for the demo summary.
    rejected_count = sum(len(nj.rejected_offsets) for nj in result.net_jtds)
    if rejected_count:
        print(
            f"\n  Rejected offsets (across nets): {rejected_count} "
            "(see NetJtd.rejected_offsets + BranchMetadata)"
        )
        for nj in result.net_jtds:
            if nj.rejected_offsets:
                for ro in nj.rejected_offsets[:1]:
                    print(f"    net={nj.net_jtd_id} reason={ro.reason_code}")
                break

    # Also exercise the fixture workflow helper (used by tests/notebooks)
    summary = run_fixture_workflow(fixture)
    print(f"\n  Workflow summary total_drc: {summary['total_drc']:,.2f}")
    return result


def run_raw_construction_demo() -> DrcCapitalResult:
    print("\n=== Minimal raw DrcPosition construction demo ===")
    pos = make_minimal_drc_position()
    print(
        f"  Built position: {pos.position_id} issuer={pos.issuer_id} "
        f"notional={pos.notional:,.0f}"
    )

    ctx = DrcCalculationContext(
        run_id="drc-demo-raw",
        calculation_date=AS_OF,
        base_currency="USD",
        profile_id="US_NPR_2_0",
        desk_id=DESK,
        legal_entity=LE,
    )
    result = calculate_drc_capital([pos], context=ctx)
    print(f"  Total DRC (single pos): {result.total_drc:,.2f}")
    print(f"  Gross JTDs computed: {len(result.gross_jtds)}")
    return result


def main() -> None:
    print("FRTB DRC End-to-End Demo (synthetic non-securitisation book)")
    print("Prototype / illustration only. Not final regulatory capital.\n")
    print("See packages/frtb-drc/docs/ and REGULATORY_TRACEABILITY.md for citations.")
    print(
        "Securitisation and CTP paths explicitly fail closed "
        "(UnsupportedRegulatoryFeatureError)."
    )

    run_fixture_demo()
    run_raw_construction_demo()

    print("\nDemo complete.")
    print("See also:")
    print("  - notebooks/ (00_validation_map.ipynb through 05_category_capital.ipynb)")
    print("  - tests/fixtures/drc_nonsec_v2/ (positions.json + manifest + expected_outputs)")
    print("  - tests/test_nonsec_v2_fixture.py and test_drc_capital.py")
    print("  - src/frtb_drc/demo_data.py (the generator for the 40-pos book)")
    print("  - frtb_drc.calculate_drc_capital public contract + DrcCapitalResult")


if __name__ == "__main__":
    main()
