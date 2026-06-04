"""
CVA capital attribution projection helpers (ADR 0012, ADR 0038).

The :func:`project_cva_attribution` helper projects a
:class:`CvaAttributionResult` to a tuple of
:class:`~frtb_common.attribution.CapitalContribution` records, including
explicit unsupported-branch and residual records when CVA nonlinear aggregation
cannot be represented as exact analytical Euler decomposition.
"""

from __future__ import annotations

from dataclasses import dataclass

from frtb_common.attribution import AttributionMethod, CapitalContribution, ReconciliationStatus

from frtb_cva.data_models import CvaCapitalResult, CvaMethod
from frtb_cva.numeric import is_reconciled


@dataclass(frozen=True)
class CvaAttributionContribution:
    """One attribution contribution with reconciliation metadata."""

    contribution_id: str
    amount: float
    method: str
    branch: str
    residual: float
    citations: tuple[str, ...]


@dataclass(frozen=True)
class CvaAttributionResult:
    """Attribution output that does not alter capital totals."""

    total_capital: float
    contributions: tuple[CvaAttributionContribution, ...]
    sum_contributions: float
    residual: float
    reconciled: bool
    unsupported_branches: tuple[str, ...] = ()


def attribute_cva_capital(result: CvaCapitalResult) -> CvaAttributionResult:
    """Return standalone explain amounts and explicit unsupported CVA branches.

    Parameters
    ----------
    result : CvaCapitalResult
        Assembled CVA capital result whose method components are explained.

    Returns
    -------
    CvaAttributionResult
        Standalone contribution rows, residual, and unsupported-branch flags.
    """

    contributions: list[CvaAttributionContribution] = []
    unsupported: list[str] = []

    ba_methods = {CvaMethod.BA_CVA_REDUCED, CvaMethod.BA_CVA_FULL, CvaMethod.MIXED_CARVE_OUT}
    if result.method in ba_methods:
        if result.ba_cva_netting_set_lines:
            for line in result.ba_cva_netting_set_lines:
                contributions.append(
                    CvaAttributionContribution(
                        contribution_id=line.netting_set_id,
                        amount=line.standalone_capital,
                        method="standalone",
                        branch="ba_cva_standalone_linear",
                        residual=0.0,
                        citations=line.citations,
                    )
                )
        if result.ba_cva_reduced is not None:
            unsupported.append("ba_cva_reduced_portfolio_sqrt")
        if result.method is CvaMethod.BA_CVA_FULL and result.ba_cva_full is not None:
            unsupported.extend(("ba_cva_hedged_sqrt", "ba_cva_beta_floor"))

    if result.sa_cva_risk_class_capitals:
        for risk_class_capital in result.sa_cva_risk_class_capitals:
            for bucket in risk_class_capital.bucket_capitals:
                for sensitivity_id in bucket.sensitivity_ids:
                    contributions.append(
                        CvaAttributionContribution(
                            contribution_id=sensitivity_id,
                            amount=bucket.k_b / max(len(bucket.sensitivity_ids), 1),
                            method="standalone_allocated",
                            branch="sa_cva_bucket_allocated",
                            residual=0.0,
                            citations=bucket.citations,
                        )
                    )
            unsupported.append(f"sa_cva_risk_class_sqrt:{risk_class_capital.risk_class.value}")

    total = result.total_cva_capital
    sum_contributions = sum(item.amount for item in contributions)
    residual = total - sum_contributions
    reconciled = is_reconciled(total, sum_contributions) if not unsupported else False

    return CvaAttributionResult(
        total_capital=total,
        contributions=tuple(contributions),
        sum_contributions=sum_contributions,
        residual=residual,
        reconciled=reconciled,
        unsupported_branches=tuple(unsupported),
    )


def project_cva_attribution(
    result: CvaAttributionResult,
    capital_result: CvaCapitalResult,
) -> tuple[CapitalContribution, ...]:
    """Project a :class:`CvaAttributionResult` to suite-wide attribution records.

    Standalone explain rows are projected as
    :attr:`AttributionMethod.STANDALONE`. Unsupported nonlinear branches are
    projected as :attr:`AttributionMethod.UNSUPPORTED`, and any gap between the
    explain rows and :attr:`CvaAttributionResult.total_capital` is projected as
    a single :attr:`AttributionMethod.RESIDUAL` row. The projected set therefore
    reconciles through ``sum(contribution) + sum(residual)`` even when exact
    Euler decomposition is not valid for a CVA branch.

        Parameters
        ----------
        result : CvaAttributionResult
            CVA attribution totals and branch flags from :func:`attribute_cva_capital`.
        capital_result : CvaCapitalResult
            Source capital result supplying input and profile hashes for contributions.

        Returns
        -------
        tuple[CapitalContribution, ...]
            Suite-wide contribution records including residual and unsupported rows.
    """
    input_hash = capital_result.input_hash
    profile_hash = capital_result.profile_hash
    has_residual = not is_reconciled(result.residual, 0.0)
    has_unsupported = bool(result.unsupported_branches)
    reconciliation_status = (
        ReconciliationStatus.PARTIAL_RESIDUAL
        if has_residual or has_unsupported
        else ReconciliationStatus.RECONCILED
    )

    projected: list[CapitalContribution] = []
    for contrib in result.contributions:
        projected.append(
            CapitalContribution(
                contribution_id=contrib.contribution_id,
                source_id=capital_result.run_id,
                source_level="frtb_cva",
                bucket_key=contrib.branch,
                category=contrib.method,
                base_amount=contrib.amount,
                marginal_multiplier=None,
                contribution=contrib.amount,
                method=AttributionMethod.STANDALONE,
                residual=contrib.residual,
                reason=_standalone_reason(contrib.branch),
                citations=contrib.citations,
                input_hash=input_hash,
                profile_hash=profile_hash,
                reconciliation_status=reconciliation_status,
            )
        )

    for branch in result.unsupported_branches:
        projected.append(
            CapitalContribution(
                contribution_id=f"cva-unsupported-{_stable_record_id(branch)}",
                source_id=capital_result.run_id,
                source_level="unsupported_branch",
                bucket_key=branch,
                category="cva_unsupported_branch",
                base_amount=0.0,
                marginal_multiplier=None,
                contribution=None,
                method=AttributionMethod.UNSUPPORTED,
                residual=0.0,
                reason=_unsupported_branch_reason(branch),
                citations=_branch_citations(branch, capital_result),
                input_hash=input_hash,
                profile_hash=profile_hash,
                reconciliation_status=reconciliation_status,
            )
        )

    if has_residual:
        projected.append(
            CapitalContribution(
                contribution_id=f"cva-residual-{capital_result.run_id}",
                source_id=capital_result.run_id,
                source_level="frtb_cva",
                bucket_key="cva_residual",
                category="cva_attribution_residual",
                base_amount=0.0,
                marginal_multiplier=None,
                contribution=None,
                method=AttributionMethod.RESIDUAL,
                residual=result.residual,
                reason=_residual_reason(result.unsupported_branches),
                citations=capital_result.citations,
                input_hash=input_hash,
                profile_hash=profile_hash,
                reconciliation_status=reconciliation_status,
            )
        )

    return tuple(projected)


def _standalone_reason(branch: str) -> str:
    if branch == "sa_cva_bucket_allocated":
        return (
            "SA-CVA bucket K_b allocated across retained sensitivity ids; "
            "not exact Euler through risk-class aggregation."
        )
    return "BA-CVA standalone explain amount; not exact Euler through portfolio aggregation."


def _unsupported_branch_reason(branch: str) -> str:
    if branch == "ba_cva_reduced_portfolio_sqrt":
        return "Reduced BA-CVA portfolio square-root aggregation is not projected as exact Euler."
    if branch == "ba_cva_hedged_sqrt":
        return "Full BA-CVA hedged square-root aggregation is not projected as exact Euler."
    if branch == "ba_cva_beta_floor":
        return "Full BA-CVA beta floor branch is not projected as exact Euler."
    if branch.startswith("sa_cva_risk_class_sqrt:"):
        risk_class = branch.split(":", maxsplit=1)[1]
        return (
            f"SA-CVA {risk_class} risk-class square-root aggregation is not projected "
            "as exact Euler."
        )
    return f"CVA branch {branch} is not projected as exact Euler."


def _residual_reason(unsupported_branches: tuple[str, ...]) -> str:
    if unsupported_branches:
        return (
            "Residual between CVA capital and standalone/allocated explain rows from "
            f"unsupported nonlinear branches: {', '.join(unsupported_branches)}."
        )
    return "Residual between CVA capital and standalone/allocated explain rows."


def _branch_citations(branch: str, capital_result: CvaCapitalResult) -> tuple[str, ...]:
    if branch == "ba_cva_reduced_portfolio_sqrt" and capital_result.ba_cva_reduced is not None:
        return capital_result.ba_cva_reduced.citations
    if branch in {"ba_cva_hedged_sqrt", "ba_cva_beta_floor"} and capital_result.ba_cva_full:
        return capital_result.ba_cva_full.citations
    if branch.startswith("sa_cva_risk_class_sqrt:") and capital_result.sa_cva_risk_class_capitals:
        risk_class = branch.split(":", maxsplit=1)[1]
        for risk_class_capital in capital_result.sa_cva_risk_class_capitals:
            if risk_class_capital.risk_class.value == risk_class:
                return risk_class_capital.citations
    return capital_result.citations


def _stable_record_id(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")


__all__ = [
    "CvaAttributionContribution",
    "CvaAttributionResult",
    "attribute_cva_capital",
    "project_cva_attribution",
]
