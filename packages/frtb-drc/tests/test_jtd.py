"""
Tests for JTD netting and hedge benefit (Issue #26 baseline).

Uses synthetic positions that mirror simple Basel MAR22 examples.
"""

from __future__ import annotations

from frtb_drc.data_models import CreditQuality, NettedIssuerSeniority, Position, Seniority
from frtb_drc.jtd import (
    apply_hedging_benefit,
    compute_gross_jtd,
    net_positions_by_issuer_seniority,
)


def test_gross_jtd_from_explicit_fields() -> None:
    pos = Position(
        issuer_id="ISS1",
        bucket="CORPORATES",
        seniority=Seniority.SENIOR,
        credit_quality=CreditQuality.BBB,
        long_jtd=10_000_000.0,
        short_jtd=2_000_000.0,
    )
    assert compute_gross_jtd(pos) == 12_000_000.0


def test_netting_within_same_seniority() -> None:
    positions = [
        Position("ISS1", "CORPORATES", Seniority.SENIOR, CreditQuality.BBB, long_jtd=10e6, short_jtd=0),
        Position("ISS1", "CORPORATES", Seniority.SENIOR, CreditQuality.BBB, long_jtd=0, short_jtd=3e6),
    ]
    netted = net_positions_by_issuer_seniority(positions)
    assert len(netted) == 1
    n = netted[0]
    assert n.gross_long == 10e6
    assert n.gross_short == 3e6
    assert n.net_long == 7e6
    assert n.net_short == 0.0


def test_no_cross_seniority_netting() -> None:
    positions = [
        Position("ISS1", "CORPORATES", Seniority.SENIOR, CreditQuality.BBB, long_jtd=5e6),
        Position("ISS1", "CORPORATES", Seniority.NON_SENIOR, CreditQuality.BBB, long_jtd=2e6, short_jtd=1e6),
    ]
    netted = net_positions_by_issuer_seniority(positions)
    # Two separate records
    assert len(netted) == 2
    senior = next(x for x in netted if x.seniority == Seniority.SENIOR)
    non = next(x for x in netted if x.seniority == Seniority.NON_SENIOR)
    assert senior.net_long == 5e6
    assert non.net_long == 1e6
    assert non.net_short == 0.0


def test_hedge_benefit_50pct_on_smaller_leg() -> None:
    # Long 10, Short 4 -> effective long 10 - 2 = 8, benefit 2
    net = NettedIssuerSeniority(
        issuer_id="X", bucket="CORPORATES", seniority=Seniority.SENIOR,
        credit_quality=CreditQuality.BBB, net_long=10.0, net_short=4.0,
        risk_weight=0.06, lgd=0.25, gross_long=10.0, gross_short=4.0,
    )
    eff_l, eff_s, benefit = apply_hedging_benefit(net)
    assert eff_l == 8.0
    assert eff_s == 0.0
    assert benefit == 2.0
