"""
FRTB Orchestration suite-level demo (scaffold / handoff recognition).

Demonstrates the *only* cross-component boundary in the suite:

- Constructing (or loading) real public result objects from component packages
  (frtb-rrao, frtb-drc, and a minimal SBM-shaped handoff).
- Using the public recognise_* functions (structural, no component imports
  required at orchestration runtime) to produce ComponentResultHandoffs.
- Calling compose_standardised_approach_capital (and calculate_suite_capital)
  which currently fail closed with NotImplementedCapitalComponentError or
  OrchestrationInputError (jurisdiction family mismatch etc.).
- The jurisdiction-family check (ADR 0022): SBM/DRC/RRAO results must share
  the same family (BASEL, US_NPR, EU_CRR3) or composition is rejected even
  before arithmetic.

This package is allowed to depend on the capital components; the components
must never import each other or orchestration.

When full SA arithmetic lands, the same handoff shapes will be used to produce
the SA total (SBM + DRC + RRAO) and top-of-house aggregates with IMA/CVA.

Not for regulatory use. All data fabricated. Composition arithmetic is not
yet implemented.

Run:
    uv run python packages/frtb-orchestration/examples/run_demo.py
"""

from __future__ import annotations

from datetime import date

from frtb_common import NotImplementedCapitalComponentError

from frtb_drc import (
    CreditQuality,
    DefaultDirection,
    DrcCalculationContext,
    DrcInstrumentType,
    DrcPosition,
    DrcRiskClass,
    DrcSeniority,
    DrcSourceLineage,
    calculate_drc_capital,
)
from frtb_orchestration import (
    OrchestrationInputError,
    StandardisedComponent,
    calculate_suite_capital,
    compose_standardised_approach_capital,
    recognise_drc_result,
    recognise_rrao_result,
    recognise_sbm_result,
)
from frtb_rrao import (
    RraoCalculationContext,
    RraoEvidenceType,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
    calculate_rrao_capital,
)
from frtb_sbm import (
    SbmCalculationContext,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmRiskMeasure,
    SbmSensitivity,
    SbmSignConvention,
    SbmSourceLineage,
    calculate_sbm_capital,
)

# Local stand-in for the *planned* flat SBM result shape that recognise_sbm_result
# and compose expect (see test_orchestration_scaffold.py MinimalResult and
# recognise_sbm_result docstring). Real current SbmCapitalResult uses nested
# run_context + total_capital + risk_classes; the planned shape will be flat
# for handoff simplicity.
class _PlannedSbmResult:
    def __init__(self, **fields: object) -> None:
        self.__dict__.update(fields)

AS_OF = date(2026, 5, 30)
DESK = "suite-demo"
LE = "LE-001"


def _drc_lineage(row: str) -> DrcSourceLineage:
    return DrcSourceLineage(
        source_system="orch-demo",
        source_file="run_demo.py",
        source_row_id=row,
    )


def _rrao_lineage(row: str) -> RraoSourceLineage:
    return RraoSourceLineage(
        source_system="orch-demo",
        source_file="run_demo.py",
        source_row_id=row,
    )


def _sbm_lineage(row: str) -> SbmSourceLineage:
    return SbmSourceLineage(
        source_system="orch-demo",
        source_file="run_demo.py",
        source_row_id=row,
        source_column_map=(("amount", "amount"),),
    )


def make_minimal_drc_result() -> object:
    """Real DrcCapitalResult via 1-position book (US_NPR profile)."""
    pos = DrcPosition(
        position_id="orch-drc-001",
        source_row_id="row-drc-001",
        desk_id=DESK,
        legal_entity=LE,
        risk_class=DrcRiskClass.NON_SECURITISATION,
        instrument_type=DrcInstrumentType.BOND,
        default_direction=DefaultDirection.LONG,
        issuer_id="demo-issuer",
        tranche_id=None,
        index_series_id=None,
        bucket_key="CORPORATE",
        seniority=DrcSeniority.SENIOR_DEBT,
        credit_quality=CreditQuality.INVESTMENT_GRADE,
        notional=500_000.0,
        market_value=None,
        cumulative_pnl=0.0,
        maturity_years=1.5,
        currency="USD",
        lineage=_drc_lineage("row-drc-001"),
        citation_ids=("US_NPR_210_SCOPE",),
    )
    ctx = DrcCalculationContext(
        run_id="orch-drc-run",
        calculation_date=AS_OF,
        base_currency="USD",
        profile_id="US_NPR_2_0",
        desk_id=DESK,
        legal_entity=LE,
    )
    return calculate_drc_capital([pos], context=ctx)


def make_minimal_rrao_result() -> object:
    """Real RraoCapitalResult via 1-position book (US_NPR profile)."""
    pos = RraoPosition(
        position_id="orch-rrao-001",
        source_row_id="row-rrao-001",
        desk_id=DESK,
        legal_entity=LE,
        gross_effective_notional=2_000_000.0,
        currency="USD",
        evidence_type=RraoEvidenceType.EXOTIC_UNDERLYING,
        evidence_label="demo exotic",
        lineage=_rrao_lineage("row-rrao-001"),
        classification_hint=None,
    )
    ctx = RraoCalculationContext(
        run_id="orch-rrao-run",
        calculation_date=AS_OF,
        base_currency="USD",
        profile=RraoRegulatoryProfile.US_NPR_2_0,
        desk_id=DESK,
        legal_entity=LE,
    )
    return calculate_rrao_capital([pos], context=ctx)


def make_minimal_sbm_result() -> object:
    """Planned flat SBM result shape for recognise/compose demo (see docstring above).

    Uses US_NPR_2_0 profile id so it can be mixed with real DRC/RRAO US_NPR results
    for the jurisdiction-consistent compose path.
    """
    return _PlannedSbmResult(
        package_name="frtb-sbm",
        run_id="orch-sbm-run",
        calculation_date=AS_OF,
        base_currency="USD",
        profile_id="US_NPR_2_0",
        total_sbm=42.0,
        profile_hash="profile-hash-orch",
        input_hash="input-hash-orch",
        sensitivity_count=1,
        unsupported_count=0,
        sensitivities=(object(),),
        unsupported_features=(),
        risk_class_results=(object(),),
        citations=("MAR21.4",),
        warnings=(),
    )


def run_recognise_demo() -> None:
    print("\n=== recognise_* on real component results ===")
    drc_res = make_minimal_drc_result()
    rrao_res = make_minimal_rrao_result()
    sbm_res = make_minimal_sbm_result()

    h_drc = recognise_drc_result(drc_res)
    h_rrao = recognise_rrao_result(rrao_res)
    h_sbm = recognise_sbm_result(sbm_res)

    print(f"  DRC  handoff: component={h_drc.component} profile={h_drc.profile_id} total={h_drc.total_capital:,.2f}")
    print(f"  RRAO handoff: component={h_rrao.component} profile={h_rrao.profile_id} total={h_rrao.total_capital:,.2f}")
    print(f"  SBM  handoff: component={h_sbm.component} profile={h_sbm.profile_id} total={h_sbm.total_capital:,.2f}")

    print("\n  All three recognised successfully (structural shapes).")


def run_compose_demo_same_family() -> None:
    print("\n=== compose SA (same jurisdiction family) ===")
    drc_res = make_minimal_drc_result()
    rrao_res = make_minimal_rrao_result()
    sbm_res = make_minimal_sbm_result()

    try:
        compose_standardised_approach_capital(
            sbm_result=sbm_res,
            drc_result=drc_res,
            rrao_result=rrao_res,
        )
    except NotImplementedCapitalComponentError as e:
        print(f"  As designed (arithmetic not implemented): {e}")
    except Exception as e:
        print(f"  Unexpected: {type(e).__name__}: {e}")


def run_jurisdiction_mismatch_demo() -> None:
    print("\n=== jurisdiction family mismatch is rejected ===")
    # BASEL profile for SBM + US_NPR for DRC -> different families (see _SA_JURISDICTION_FAMILY)
    # Supply only these two (rrao=None); assert runs on provided handoffs before missing check.
    sbm_basel = _PlannedSbmResult(
        package_name="frtb-sbm",
        run_id="orch-sbm-basel",
        calculation_date=AS_OF,
        base_currency="USD",
        profile_id="BASEL_MAR21",
        total_sbm=42.0,
        profile_hash="profile-hash-basel",
        input_hash="input-hash-basel",
        sensitivity_count=1,
        unsupported_count=0,
        sensitivities=(object(),),
        unsupported_features=(),
        risk_class_results=(object(),),
        citations=("MAR21.4",),
        warnings=(),
    )
    drc_us = make_minimal_drc_result()
    try:
        compose_standardised_approach_capital(sbm_result=sbm_basel, drc_result=drc_us, rrao_result=None)
    except OrchestrationInputError as e:
        print(f"  Caught expected OrchestrationInputError: {e}")
    except Exception as e:
        print(f"  Unexpected: {type(e).__name__}: {e}")


def run_suite_demo() -> None:
    print("\n=== calculate_suite_capital (top-of-house) ===")
    try:
        calculate_suite_capital()
    except NotImplementedCapitalComponentError as e:
        print(f"  As designed: {e}")


def main() -> None:
    print("FRTB Orchestration Demo (handoff recognition + SA composition scaffold)")
    print("Prototype only. Composition arithmetic not yet implemented.\n")

    run_recognise_demo()
    run_compose_demo_same_family()
    run_jurisdiction_mismatch_demo()
    run_suite_demo()

    print("\nDemo complete.")
    print("See also:")
    print("  - tests/test_orchestration_scaffold.py (sample result builders + full tests)")
    print("  - src/frtb_orchestration/standardised.py (recognise + compose + ADR 0022 notes)")
    print("  - docs/AGENTS.md and CLAUDE.md (package boundary rules)")
    print("  - Once SBM/DRC/RRAO arithmetic complete, this will produce the SA total.")


if __name__ == "__main__":
    main()
