"""Risk-factor-aware suite view builders.

Orchestration composes risk-factor views over already-resolved component and
result-store metadata. It does not own canonical risk-factor metadata, fetch
result-store payloads, or infer missing contribution methods.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum


class RiskFactorViewStatus(StrEnum):
    """Availability state for one risk-factor view row."""

    AVAILABLE = "available"
    NO_DATA = "no_data"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class RiskFactorCapitalViewRow:
    """Framework-level capital or explicit unavailable state for a risk factor."""

    component: str
    risk_factor_id: str
    mapping_version: str | None
    amount: float | None
    source_row_ids: tuple[str, ...] = ()
    status: RiskFactorViewStatus = RiskFactorViewStatus.AVAILABLE
    reason: str = ""

    def __post_init__(self) -> None:
        if self.status is RiskFactorViewStatus.AVAILABLE and self.amount is None:
            raise ValueError("available risk-factor capital row requires amount")
        if self.status is not RiskFactorViewStatus.AVAILABLE and not self.reason:
            raise ValueError("no-data or unsupported risk-factor capital row requires reason")

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-compatible row for API or Navigator handoff.

        Returns
        -------
        dict[str, object]
            Serialized capital view row.
        """

        return {
            "component": self.component,
            "risk_factor_id": self.risk_factor_id,
            "mapping_version": self.mapping_version,
            "amount": self.amount,
            "source_row_ids": list(self.source_row_ids),
            "status": self.status.value,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class RiskFactorEvidenceViewRow:
    """Evidence or explicit unavailable state for one risk factor."""

    component: str
    risk_factor_id: str
    mapping_version: str | None
    evidence_type: str
    evidence_ids: tuple[str, ...] = ()
    status: RiskFactorViewStatus = RiskFactorViewStatus.AVAILABLE
    reason: str = ""

    def __post_init__(self) -> None:
        if self.status is RiskFactorViewStatus.AVAILABLE and not self.evidence_ids:
            raise ValueError("available risk-factor evidence row requires evidence_ids")
        if self.status is not RiskFactorViewStatus.AVAILABLE and not self.reason:
            raise ValueError("no-data or unsupported risk-factor evidence row requires reason")

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-compatible row for API or Navigator handoff.

        Returns
        -------
        dict[str, object]
            Serialized evidence view row.
        """

        return {
            "component": self.component,
            "risk_factor_id": self.risk_factor_id,
            "mapping_version": self.mapping_version,
            "evidence_type": self.evidence_type,
            "evidence_ids": list(self.evidence_ids),
            "status": self.status.value,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class RiskFactorAggregateView:
    """Capital and evidence rows for one selected risk factor."""

    risk_factor_id: str
    mapping_version: str | None
    capital_rows: tuple[RiskFactorCapitalViewRow, ...]
    evidence_rows: tuple[RiskFactorEvidenceViewRow, ...]

    @property
    def total_available_amount(self) -> float:
        """Sum available contribution amounts without inferring missing methods.

        Returns
        -------
        float
            Sum of available capital contribution amounts.
        """

        return sum(
            row.amount or 0.0
            for row in self.capital_rows
            if row.status is RiskFactorViewStatus.AVAILABLE
        )

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-compatible aggregate view.

        Returns
        -------
        dict[str, object]
            Serialized risk-factor aggregate view.
        """

        return {
            "risk_factor_id": self.risk_factor_id,
            "mapping_version": self.mapping_version,
            "total_available_amount": self.total_available_amount,
            "capital_rows": [row.as_dict() for row in self.capital_rows],
            "evidence_rows": [row.as_dict() for row in self.evidence_rows],
        }


def build_risk_factor_aggregate_view(
    risk_factor_id: str,
    *,
    mapping_version: str | None = None,
    capital_rows: Sequence[RiskFactorCapitalViewRow] = (),
    evidence_rows: Sequence[RiskFactorEvidenceViewRow] = (),
    expected_capital_components: Sequence[str] = (),
) -> RiskFactorAggregateView:
    """Compose a deterministic risk-factor view over resolved component rows.

    Parameters
    ----------
    risk_factor_id
        Selected stable risk-factor identifier.
    mapping_version
        Optional mapping version to attach to generated no-data rows.
    capital_rows
        Already-resolved component contribution or unavailable-state rows.
    evidence_rows
        Already-resolved component evidence rows.
    expected_capital_components
        Components that should appear with explicit no-data rows when no
        capital row exists for the selected risk factor.

    Returns
    -------
    RiskFactorAggregateView
        Deterministic aggregate view for the selected risk factor.
    """

    selected_capital = tuple(
        row for row in capital_rows or () if row.risk_factor_id == risk_factor_id
    )
    selected_evidence = tuple(
        row for row in evidence_rows or () if row.risk_factor_id == risk_factor_id
    )
    present_components = {row.component for row in selected_capital}
    no_data_rows = tuple(
        RiskFactorCapitalViewRow(
            component=component,
            risk_factor_id=risk_factor_id,
            mapping_version=mapping_version,
            amount=None,
            status=RiskFactorViewStatus.NO_DATA,
            reason="no resolved capital contribution rows for selected risk factor",
        )
        for component in expected_capital_components or ()
        if component not in present_components
    )
    return RiskFactorAggregateView(
        risk_factor_id=risk_factor_id,
        mapping_version=mapping_version,
        capital_rows=tuple(
            sorted(
                (*selected_capital, *no_data_rows),
                key=lambda row: (row.component, row.status.value, row.reason),
            )
        ),
        evidence_rows=tuple(
            sorted(
                selected_evidence,
                key=lambda row: (row.component, row.evidence_type, row.status.value),
            )
        ),
    )


__all__ = [
    "RiskFactorAggregateView",
    "RiskFactorCapitalViewRow",
    "RiskFactorEvidenceViewRow",
    "RiskFactorViewStatus",
    "build_risk_factor_aggregate_view",
]
