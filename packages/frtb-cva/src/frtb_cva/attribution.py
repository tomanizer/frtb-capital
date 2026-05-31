"""
Analytical Euler attribution for supported CVA branches (ADR 0012).
"""

from __future__ import annotations

from dataclasses import dataclass

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
    """Return analytical contributions where the branch is stable and linear."""

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
                        method="analytical_euler",
                        branch="ba_cva_standalone_linear",
                        residual=0.0,
                        citations=line.citations,
                    )
                )
        if result.method is CvaMethod.BA_CVA_REDUCED and result.ba_cva_reduced is not None:
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
                            method="analytical_euler",
                            branch="sa_cva_bucket_allocated",
                            residual=0.0,
                            citations=bucket.citations,
                        )
                    )
            unsupported.append(
                f"sa_cva_risk_class_sqrt:{risk_class_capital.risk_class.value}"
            )

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


__all__ = [
    "CvaAttributionContribution",
    "CvaAttributionResult",
    "attribute_cva_capital",
]
