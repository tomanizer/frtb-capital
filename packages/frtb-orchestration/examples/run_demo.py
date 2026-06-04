"""
FRTB Orchestration suite-level demo (current manifest / summary API).

Demonstrates the cross-component boundary:

- Constructing ComponentCapitalSummary (the stable handoff from owning
  packages) for SBM / DRC / RRAO.
- Calling compose_standardised_approach_capital (validates jurisdiction
  family per ADR 0022, produces StandardisedApproachCapitalResult).
- Calling calculate_suite_capital (fails closed as designed).
- Using standardised_jurisdiction_family helper.
- (Optional) manifest validation entrypoints are also exported.

This package is allowed to depend on / re-export contracts from components;
components must never import orchestration.

Not for regulatory use. All data fabricated.

Run:
    uv run python packages/frtb-orchestration/examples/run_demo.py
"""

from __future__ import annotations

from datetime import date

from frtb_common import ComponentCapitalSummary
from frtb_orchestration import (
    OrchestrationInputError,
    StandardisedComponent,
    calculate_suite_capital,
    compose_standardised_approach_capital,
    standardised_jurisdiction_family,
)

AS_OF = date(2026, 5, 30)
DESK = "suite-demo"
LE = "LE-001"


def make_summary(
    component: StandardisedComponent, profile_id: str, total: float
) -> ComponentCapitalSummary:
    """Minimal synthetic ComponentCapitalSummary for demo."""
    return ComponentCapitalSummary(
        component=component,
        package_name=f"frtb-{component.value.lower()}",
        run_id=f"orch-{component.value.lower()}-demo",
        calculation_date=AS_OF,
        base_currency="USD",
        profile_id=profile_id,
        total_capital=total,
        profile_hash=f"ph-{profile_id}",
        input_hash=f"ih-{component.value}",
        line_count=5,
        excluded_line_count=0,
        subtotal_count=2,
        citations=("demo-cite",),
        warnings=(),
    )


def run_compose_demo() -> None:
    print("\n=== compose SA from ComponentCapitalSummary (US_NPR family) ===")
    sbm = make_summary(StandardisedComponent.SBM, "US_NPR_2_0", 42.0)
    drc = make_summary(StandardisedComponent.DRC, "US_NPR_2_0", 7875.0)
    rrao = make_summary(StandardisedComponent.RRAO, "US_NPR_2_0", 20000.0)
    result = compose_standardised_approach_capital(
        sbm_summary=sbm,
        drc_summary=drc,
        rrao_summary=rrao,
        run_id="orch-sa-demo",
    )
    print(f"  SA total: {result.total_capital:,.2f}")
    print(f"  Jurisdiction: {result.jurisdiction_family}")
    print(f"  Components: {[s.component.value for s in result.component_subtotals]}")
    print(f"  Fallback routes: {len(result.fallback_routes)}")


def run_jurisdiction_demo() -> None:
    print("\n=== jurisdiction family mismatch rejected (ADR 0022) ===")
    sbm = make_summary(StandardisedComponent.SBM, "BASEL_MAR21", 42.0)
    drc = make_summary(StandardisedComponent.DRC, "US_NPR_2_0", 7875.0)
    try:
        compose_standardised_approach_capital(sbm_summary=sbm, drc_summary=drc, rrao_summary=None)
    except OrchestrationInputError as e:
        print(f"  Caught expected: {e}")
    # Also show helper
    print(
        f"  standardised_jurisdiction_family('US_NPR_2_0') = "
        f"{standardised_jurisdiction_family('US_NPR_2_0')}"
    )


def run_suite_demo() -> None:
    print("\n=== calculate_suite_capital (top-of-house) ===")
    try:
        calculate_suite_capital()
    except Exception as e:  # NotImplementedCapitalComponentError or similar
        print(f"  As designed (fails closed): {type(e).__name__}: {e}")


def main() -> None:
    print("FRTB Orchestration Demo (ComponentCapitalSummary + SA compose)")
    print("Prototype only. All numbers fabricated.\n")

    run_compose_demo()
    run_jurisdiction_demo()
    run_suite_demo()

    print("\nDemo complete.")
    print("See tests/test_orchestration_scaffold.py and src/ for full contracts.")
    print(
        "Manifest-based SA routing is also available via run_standardised_approach_from_manifest."
    )


if __name__ == "__main__":
    main()
