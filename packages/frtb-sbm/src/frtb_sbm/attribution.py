"""
Analytical Euler capital contribution attribution for SBM delta and vega.

Regulatory traceability:
    Basel MAR21.4(4)-(5) — intra- and inter-bucket aggregation (Euler basis).
    Basel MAR21.5       — curvature: CVR max(⋅,0) floor → UNSUPPORTED.
    ADR 0038            — suite-wide attribution and impact contract.
    ADR 0037            — analytical Euler decomposition framework.
"""

from __future__ import annotations

from frtb_common.attribution import (
    AttributionMethod,
    CapitalContribution,
    ReconciliationStatus,
)

from frtb_sbm.data_models import (
    BucketCapital,
    IntraBucketScenarioRecord,
    PairwiseCorrelationRecord,
    RiskClassCapital,
    RiskClassScenarioDetail,
    SbmCapitalResult,
    SbmRiskMeasure,
    WeightedSensitivity,
)

_RECONCILIATION_TOLERANCE = 1e-6

# Citation IDs carried on every SBM attribution record.
_ATTRIBUTION_CITATIONS = (
    "basel_mar21_4_intra_bucket",
    "basel_mar21_4_inter_bucket",
    "adr_0037",
    "adr_0038",
)


def calculate_sbm_attribution(
    result: SbmCapitalResult,
) -> tuple[CapitalContribution, ...]:
    """Return analytical Euler contributions for all delta and vega risk classes.

    Curvature risk classes are returned as ``UNSUPPORTED`` records because the
    CVR max(⋅,0) floor prevents exact Euler decomposition (MAR21.5).

    Attribution records are at sensitivity granularity for analytical Euler
    paths and at risk-class granularity for unsupported paths.  The sum of
    ``(contribution or 0) + residual`` across all returned records equals
    ``result.total_capital`` when all risk classes use the analytical path.
    """
    records: list[CapitalContribution] = []
    for rc in result.risk_classes:
        records.extend(_risk_class_contributions(rc, result.input_hash, result.profile_hash))
    return tuple(records)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _risk_class_contributions(
    rc: RiskClassCapital,
    input_hash: str,
    profile_hash: str,
) -> list[CapitalContribution]:
    source_id = f"{rc.risk_class}:{rc.risk_measure}"
    citations = _ATTRIBUTION_CITATIONS + tuple(rc.citation_ids)

    # Curvature: CVR max(⋅,0) prevents analytical Euler decomposition.
    if rc.risk_measure is SbmRiskMeasure.CURVATURE:
        return [
            _unsupported_rc(
                source_id=source_id,
                rc=rc,
                citations=citations,
                input_hash=input_hash,
                profile_hash=profile_hash,
                reason=(
                    "Curvature capital: CVR max(⋅,0) floor prevents exact Euler "
                    "decomposition (MAR21.5). See ADR 0038."
                ),
            )
        ]

    capital = rc.selected_capital
    if capital == 0.0:
        return []

    # Find the selected scenario detail (needed for pairwise correlations and S_b).
    selected_scenario = rc.selected_scenario
    if selected_scenario is None or not rc.scenario_details:
        return [
            _unsupported_rc(
                source_id=source_id,
                rc=rc,
                citations=citations,
                input_hash=input_hash,
                profile_hash=profile_hash,
                reason="No scenario detail retained; cannot reconstruct correlation matrices.",
            )
        ]

    selected_detail: RiskClassScenarioDetail | None = next(
        (d for d in rc.scenario_details if d.scenario == selected_scenario), None
    )
    if selected_detail is None:
        return [
            _unsupported_rc(
                source_id=source_id,
                rc=rc,
                citations=citations,
                input_hash=input_hash,
                profile_hash=profile_hash,
                reason=f"Scenario detail not found for selected scenario {selected_scenario}.",
            )
        ]

    # Alternative S_b (MAR21.4(5)(b)): adjusted values are not retained in the result.
    if selected_detail.alternative_sb_used:
        return [
            _unsupported_rc(
                source_id=source_id,
                rc=rc,
                citations=citations,
                input_hash=input_hash,
                profile_hash=profile_hash,
                reason=(
                    "Alternative S_b specification (MAR21.4(5)(b)) was used; "
                    "adjusted S_b values are not retained for Euler decomposition."
                ),
            )
        ]

    intra_by_bucket: dict[str, IntraBucketScenarioRecord] = {
        rec.bucket_id: rec for rec in selected_detail.intra_buckets
    }

    # Partial pairwise materialisation: correlation matrix cannot be reconstructed.
    for intra_check in intra_by_bucket.values():
        summary = intra_check.pairwise_correlation_summary
        if summary is not None and summary.omitted_count > 0:
            return [
                _unsupported_rc(
                    source_id=source_id,
                    rc=rc,
                    citations=citations,
                    input_hash=input_hash,
                    profile_hash=profile_hash,
                    reason=(
                        f"Pairwise correlations not fully materialised for bucket "
                        f"'{intra_check.bucket_id}' "
                        f"({summary.omitted_count} of {summary.total_count} pairs omitted). "
                        "Increase pairwise_evidence_limit to enable full attribution."
                    ),
                )
            ]

    # Any active floor: Euler derivative is undefined at the floor boundary.
    for bucket in rc.buckets:
        if bucket.floor_applied:
            return [
                _unsupported_rc(
                    source_id=source_id,
                    rc=rc,
                    citations=citations,
                    input_hash=input_hash,
                    profile_hash=profile_hash,
                    reason=(
                        f"Floor active in bucket '{bucket.bucket_id}'; "
                        "Euler derivative undefined at floor boundary."
                    ),
                )
            ]

    # All preconditions met → compute analytical Euler contributions.
    s_by_bucket: dict[str, float] = {rec.bucket_id: rec.sb for rec in selected_detail.intra_buckets}
    gamma_s = _compute_gamma_s(selected_detail.inter_bucket_correlations, s_by_bucket)

    records: list[CapitalContribution] = []
    for bucket in rc.buckets:
        intra: IntraBucketScenarioRecord | None = intra_by_bucket.get(bucket.bucket_id)
        if intra is None:
            records.append(
                _unsupported_rc(
                    source_id=f"{source_id}:{bucket.bucket_id}",
                    rc=rc,
                    citations=citations,
                    input_hash=input_hash,
                    profile_hash=profile_hash,
                    reason=f"Intra-bucket detail missing for bucket '{bucket.bucket_id}'.",
                )
            )
            continue
        gamma_s_a = gamma_s.get(bucket.bucket_id, 0.0)
        records.extend(
            _bucket_euler_contributions(
                bucket=bucket,
                intra=intra,
                capital=capital,
                gamma_s_a=gamma_s_a,
                citations=citations,
                input_hash=input_hash,
                profile_hash=profile_hash,
            )
        )

    # Add a reconciliation residual for floating-point drift (should be negligible).
    total = sum((r.contribution or 0.0) + r.residual for r in records)
    tol = _RECONCILIATION_TOLERANCE * max(abs(capital), 1.0)
    if abs(total - capital) > tol:
        records.append(
            CapitalContribution(
                contribution_id=f"sbm-{source_id}-residual",
                source_id=source_id,
                source_level="risk_class",
                bucket_key=None,
                category=str(rc.risk_class),
                base_amount=0.0,
                marginal_multiplier=None,
                contribution=None,
                method=AttributionMethod.RESIDUAL,
                residual=capital - total,
                reason="Euler decomposition rounding residual.",
                citations=citations,
                input_hash=input_hash,
                profile_hash=profile_hash,
                reconciliation_status=ReconciliationStatus.PARTIAL_RESIDUAL,
            )
        )

    return records


def _bucket_euler_contributions(
    *,
    bucket: BucketCapital,
    intra: IntraBucketScenarioRecord,
    capital: float,
    gamma_s_a: float,
    citations: tuple[str, ...],
    input_hash: str,
    profile_hash: str,
) -> list[CapitalContribution]:
    """Euler contributions for every weighted sensitivity in one bucket.

    For sensitivity i in bucket a with capital K:

        marginal_i = [(rho_a @ ws_a)[i] + (gamma @ S)_a] / K
        contribution_i = WS_i * marginal_i

    Euler's theorem guarantees sum(contribution_i) == K when summed over all
    buckets (no floors, complete pairwise materialisation).
    """
    ws_list: tuple[WeightedSensitivity, ...] = bucket.weighted_sensitivities
    if not ws_list:
        return []

    rho_ws = _compute_rho_times_ws(ws_list, intra.pairwise_correlations)

    records: list[CapitalContribution] = []
    for i, ws in enumerate(ws_list):
        numerator_i = rho_ws[i] + gamma_s_a
        marginal = numerator_i / capital
        contribution = ws.scaled_amount * marginal

        sensitivity_citations = citations + tuple(ws.citation_ids)
        records.append(
            CapitalContribution(
                contribution_id=f"sbm-{ws.sensitivity_id}",
                source_id=ws.sensitivity_id,
                source_level="sensitivity",
                bucket_key=bucket.bucket_id,
                category=str(bucket.risk_class),
                base_amount=ws.scaled_amount,
                marginal_multiplier=marginal,
                contribution=contribution,
                method=AttributionMethod.ANALYTICAL_EULER,
                residual=0.0,
                reason="",
                citations=sensitivity_citations,
                input_hash=input_hash,
                profile_hash=profile_hash,
                reconciliation_status=ReconciliationStatus.RECONCILED,
            )
        )
    return records


def _compute_rho_times_ws(
    ws_list: tuple[WeightedSensitivity, ...],
    pairwise: tuple[PairwiseCorrelationRecord, ...],
) -> list[float]:
    """Return the vector (rho @ ws) computed from upper-triangle pairwise records.

    Pairwise records store the upper triangle including the diagonal.  Off-diagonal
    entries are applied symmetrically.
    """
    id_to_index = {ws.sensitivity_id: idx for idx, ws in enumerate(ws_list)}
    ws_values = [ws.scaled_amount for ws in ws_list]
    result = [0.0] * len(ws_list)

    for rec in pairwise:
        i = id_to_index.get(rec.sensitivity_a)
        j = id_to_index.get(rec.sensitivity_b)
        if i is None or j is None:
            continue
        if i == j:
            result[i] += ws_values[i]  # diagonal rho_ii = 1
        else:
            result[i] += rec.correlation * ws_values[j]
            result[j] += rec.correlation * ws_values[i]

    return result


def _compute_gamma_s(
    inter_bucket_correlations: tuple[tuple[str, str, float], ...],
    s_by_bucket: dict[str, float],
) -> dict[str, float]:
    """Compute (gamma @ S) for each bucket from stored upper-triangle gamma records.

    The stored records have one direction per pair (a < b in sorted order).
    Each entry contributes symmetrically to both buckets.
    """
    gamma_s: dict[str, float] = {bid: 0.0 for bid in s_by_bucket}

    for bucket_a, bucket_b, gamma_ab in inter_bucket_correlations:
        if bucket_a == bucket_b:
            continue
        s_a = s_by_bucket.get(bucket_a, 0.0)
        s_b = s_by_bucket.get(bucket_b, 0.0)
        if bucket_a in gamma_s:
            gamma_s[bucket_a] += gamma_ab * s_b
        if bucket_b in gamma_s:
            gamma_s[bucket_b] += gamma_ab * s_a

    return gamma_s


def _unsupported_rc(
    *,
    source_id: str,
    rc: RiskClassCapital,
    citations: tuple[str, ...],
    input_hash: str,
    profile_hash: str,
    reason: str,
) -> CapitalContribution:
    return CapitalContribution(
        contribution_id=f"sbm-{source_id}-unsupported",
        source_id=source_id,
        source_level="risk_class",
        bucket_key=None,
        category=str(rc.risk_class),
        base_amount=0.0,
        marginal_multiplier=None,
        contribution=None,
        method=AttributionMethod.UNSUPPORTED,
        residual=rc.selected_capital,
        reason=reason,
        citations=citations,
        input_hash=input_hash,
        profile_hash=profile_hash,
        reconciliation_status=ReconciliationStatus.PARTIAL_RESIDUAL,
    )


__all__ = ["calculate_sbm_attribution"]
