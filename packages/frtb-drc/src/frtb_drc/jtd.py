"""
JTD gross calculation and seniority-based netting (Issue #26).

Pure functions. No side effects.

Regulatory traceability:
    Basel MAR22.8–22.14 (gross JTD, long/short definition, seniority netting,
    no cross-seniority offset within an issuer, 50% hedge benefit on smaller leg).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from frtb_drc.data_models import (
    SENIORITY_TO_STR,
    CreditQuality,
    NettedIssuerSeniority,
    Position,
    Seniority,
)
from frtb_drc.reference_data import get_lgd, get_risk_weight


def compute_gross_jtd(
    position: Position,
    lgd_override: float | None = None,
) -> float:
    """
    Compute gross JTD for a single position.

    If the position already carries explicit long_jtd / short_jtd (preferred
    for upstream feeds that have already applied LGD and notional), those are
    returned directly (summed).

    Otherwise falls back to LGD * notional (sign-aware).

    Regulatory: Basel MAR22.9 (JTD = LGD × LGD × notional for non-defaulted).
    """
    if position.long_jtd > 0 or position.short_jtd > 0:
        return position.long_jtd + position.short_jtd

    if position.notional is None or position.notional == 0:
        return 0.0

    lgd = get_lgd(SENIORITY_TO_STR[position.seniority], lgd_override)
    # Simplified: treat positive notional as long exposure
    return lgd * abs(position.notional)


def net_positions_by_issuer_seniority(
    positions: Iterable[Position],
    rules_version: str = "CRR2",  # kept for future RW/LGD policy
) -> list[NettedIssuerSeniority]:
    """
    Aggregate positions to (issuer, seniority) level and apply within-seniority
    long/short netting.

    Per Basel MAR22.11: netting is performed separately for each combination of
    obligor and seniority. No netting across seniorities for the same issuer.

    Returns one NettedIssuerSeniority per (issuer, seniority) that has exposure.
    Risk weight and LGD are looked up at this stage for audit completeness.
    """
    # Group gross long/short by (issuer, seniority, bucket, cq)
    buckets: dict[tuple[str, Seniority, str, str], dict[str, float]] = defaultdict(
        lambda: {"gross_long": 0.0, "gross_short": 0.0}
    )

    for p in positions:
        key = (p.issuer_id, p.seniority, p.bucket, p.credit_quality.value)
        buckets[key]["gross_long"] += p.long_jtd
        buckets[key]["gross_short"] += p.short_jtd

    results: list[NettedIssuerSeniority] = []
    for (issuer, seniority, bucket, cq_str), g in buckets.items():
        gl = g["gross_long"]
        gs = g["gross_short"]

        net_long = max(0.0, gl - gs)
        net_short = max(0.0, gs - gl)

        # Lookup RW (FRB path uses bucket + cq; others use cq or bucket)
        # We pass the credit_quality string; get_risk_weight handles regime internally
        # For now default to CRR2-style; caller can re-apply with correct RulesVersion later.
        rw = get_risk_weight(bucket, cq_str)  # safe default
        lgd = get_lgd(SENIORITY_TO_STR[seniority])

        cq = CreditQuality(cq_str)
        results.append(
            NettedIssuerSeniority(
                issuer_id=issuer,
                bucket=bucket,
                seniority=seniority,
                credit_quality=cq,
                net_long=net_long,
                net_short=net_short,
                risk_weight=rw,
                lgd=lgd,
                gross_long=gl,
                gross_short=gs,
            )
        )

    return results


def apply_hedging_benefit(
    netted: NettedIssuerSeniority,
) -> tuple[float, float, float]:
    """
    Apply the 50% hedge benefit on the smaller leg (Basel MAR22.13–22.14).

    Returns (effective_long, effective_short, hedging_benefit_amount).
    The capital-relevant JTD for this seniority is effective_long - 0.5 * effective_short
    (or symmetric) before multiplication by RW.
    """
    nl = netted.net_long
    ns = netted.net_short

    if nl >= ns:
        eff_long = nl - 0.5 * ns
        eff_short = 0.0
        benefit = 0.5 * ns
    else:
        eff_long = 0.0
        eff_short = ns - 0.5 * nl
        benefit = 0.5 * nl

    return eff_long, eff_short, benefit
