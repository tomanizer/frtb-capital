"""
Minimal DRC demo (Issues #25–#26 baseline).

Synthesises a tiny credit book, runs JTD netting + hedge benefit,
and prints risk-weighted exposures.

Run:
    uv run python packages/frtb-drc/examples/run_demo.py
"""

from __future__ import annotations

from frtb_drc import (
    CreditQuality,
    Position,
    RulesVersion,
    Seniority,
    apply_hedging_benefit,
    get_risk_weight,
    net_positions_by_issuer_seniority,
)


def main() -> None:
    print("FRTB-DRC demo (core data models + JTD netting)")
    print("=" * 52)

    # Synthetic book: one corporate issuer, mixed seniorities
    positions = [
        Position("CORP_ABC", "CORPORATES", Seniority.SENIOR, CreditQuality.BBB, long_jtd=50_000_000),
        Position("CORP_ABC", "CORPORATES", Seniority.SENIOR, CreditQuality.BBB, short_jtd=15_000_000),
        Position("CORP_ABC", "CORPORATES", Seniority.NON_SENIOR, CreditQuality.BB, long_jtd=8_000_000),
        # FRB-style sovereign exposure
        Position("GOV_X", "NON_US_SOVEREIGNS", Seniority.SENIOR, CreditQuality.IG, long_jtd=100_000_000),
    ]

    print("\nInput positions:")
    for p in positions:
        print(f"  {p.issuer_id:10} {p.bucket:18} {p.seniority.name:12} {p.credit_quality.value:8} L={p.long_jtd:>12,.0f} S={p.short_jtd:>12,.0f}")

    netted = net_positions_by_issuer_seniority(positions)
    # Note: current netting helper uses default regime; real call site will pass RulesVersion.BCBS for letter ratings.
    print("\nNetted by (issuer, seniority):")
    for n in netted:
        eff_l, eff_s, benefit = apply_hedging_benefit(n)
        rw = get_risk_weight(n.bucket, n.credit_quality.value, RulesVersion.CRR2)
        capital_contrib = (eff_l - eff_s) * rw * n.lgd   # simplified pre-bucket view
        print(
            f"  {n.issuer_id:10} {n.bucket:18} {n.seniority.name:12} "
            f"netL={n.net_long:>12,.0f} netS={n.net_short:>12,.0f} "
            f"RW={rw:.3f} effL={eff_l:>10,.0f} benefit={benefit:>10,.0f} contrib≈{capital_contrib:>10,.0f}"
        )

    print("\nFRB risk weight sanity check (NON_US_SOVEREIGNS IG):")
    print(f"  {get_risk_weight('NON_US_SOVEREIGNS', 'IG', RulesVersion.FRB):.3%}")

    print("\nDemo complete (JTD + seniority netting + hedge benefit).")
    print("Full bucket aggregation + capital in subsequent issues.")


if __name__ == "__main__":
    main()
