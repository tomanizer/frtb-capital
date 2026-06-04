"""
FRTB RRAO (Residual Risk Add-On) quick-start demo.

This is a thin executable front door that exercises the main
`calculate_rrao_capital` entrypoint using the existing high-quality
synthetic sample-book fixture.

It demonstrates:
- Loading canonical RraoPosition inputs (via the package's own examples.rrao_fixture).
- Running for supported profiles (US_NPR_2_0 primary + BASEL_MAR23 comparison).
- Printing key results: total capital, exclusion counts, per-risk-type lines.

All data is synthetic. Outputs are not final regulatory capital.

Run:
    uv run python packages/frtb-rrao/examples/run_demo.py

For deeper dives see the notebooks/ (classification, capital lines, allocation,
multi-profile) and the detailed fixture workflow tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make "from rrao_fixture import ..." work when the script is executed directly
# (e.g. `uv run python packages/frtb-rrao/examples/run_demo.py`).
# This mirrors the pattern used inside the package's own test fixture loaders.
sys.path.insert(0, str(Path(__file__).parent))

from frtb_rrao import (
    RraoCalculationContext,
    RraoRegulatoryProfile,
    calculate_rrao_capital,
)
from rrao_fixture import (
    load_context,
    load_expected_outputs,
    load_positions,
    PROFILE_BASEL,
    PROFILE_US_NPR,
)

def run_for_profile(profile: RraoRegulatoryProfile, label: str) -> None:
    print(f"\n=== RRAO demo — {label} ===")
    # The fixture loader gives a ready-to-use context for the profile
    # (we override the profile here to show both)
    base_ctx = load_context()
    ctx = RraoCalculationContext(
        run_id=f"rrao-demo-{label.lower().replace(' ', '-')}",
        calculation_date=base_ctx.calculation_date,
        base_currency=base_ctx.base_currency,
        profile=profile,
        desk_id=base_ctx.desk_id,
        legal_entity=base_ctx.legal_entity,
    )

    positions = load_positions()
    result = calculate_rrao_capital(positions, context=ctx)

    print(f"Total RRAO capital: {result.total_rrao:,.2f}")
    print(f"  Positions processed: {len(positions)}")
    print(f"  Excluded lines: {len(result.excluded_lines)}")
    print(f"  Capital lines: {len(result.lines)}")
    print(f"  Subtotals: {len(result.subtotals)}")

    # Show a couple of capital lines
    for line in list(result.lines)[:3]:
        print(f"    {line.classification.value} ({line.evidence_type.value}): "
              f"notional={line.gross_effective_notional:,.0f} rw={line.risk_weight} add_on={line.add_on:,.0f}")

    expected = load_expected_outputs()
    if label == "US NPR 2.0":
        exp_total = expected.get("total_rrao_capital")
        if exp_total is not None:
            print(f"  (Fixture expected total: {exp_total:,.2f})")


def main() -> None:
    print("FRTB RRAO Quick Demo (synthetic sample book)")
    print("Prototype only. Not for regulatory submission or capital reporting.\n")

    # Primary profile (US NPR) uses the full sample book including SUPERVISOR_DIRECTIVE etc.
    # Basel/EU profiles have narrower evidence rules; the multi-profile comparison and
    # exclusion behaviour for profile-specific types are covered in notebooks/04 and
    # test_eu_profile.py / test_fixture_workflow.py. Running the shared fixture under
    # BASEL here would raise on unsupported evidence_type for this book.
    run_for_profile(PROFILE_US_NPR, "US NPR 2.0")

    print("\nDemo complete.")
    print("See also:")
    print("  - examples/rrao_fixture.py (full loader + expected outputs)")
    print("  - notebooks/ (01_classification... 04_multi_profile_comparison)")
    print("  - tests/fixtures/rrao_v1/ and test_fixture_workflow.py + test_eu_profile.py")
    print("  - scripts/benchmark_rrao_target_scale.py for large-scale batch/Arrow")


if __name__ == "__main__":
    main()
