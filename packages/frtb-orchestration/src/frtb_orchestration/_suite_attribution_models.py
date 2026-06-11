"""Suite capital and attribution result records."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from frtb_common.attribution import AttributionMethod, CapitalContribution, ReconciliationStatus
from frtb_common.contribution_bundle import ComponentContributionBundle

from frtb_orchestration._suite_attribution import (
    canonical_component_label as _canonical_component_label,
)
from frtb_orchestration._suite_attribution import (
    within_attribution_tolerance as _within_attribution_tolerance,
)
from frtb_orchestration._validation import OrchestrationInputError
from frtb_orchestration._validation import require_non_empty_text as _require_non_empty_text
from frtb_orchestration._validation import (
    require_non_negative_finite_number as _require_non_negative_finite_number,
)
from frtb_orchestration._validation import require_text_tuple as _require_text_tuple
from frtb_orchestration._validation import require_tuple_of as _require_tuple_of
from frtb_orchestration.cva_summary import CvaCapitalSummary
from frtb_orchestration.ima_summary import ImaCapitalSummary
from frtb_orchestration.standardised import StandardisedApproachCapitalResult


@dataclass(frozen=True)
class SuiteAttributionResult:
    """Validated suite attribution aggregate preserving component bundles unchanged."""

    run_id: str
    suite_total_capital: float
    component_bundles: tuple[ComponentContributionBundle, ...]
    suite_residual: CapitalContribution

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        object.__setattr__(
            self,
            "suite_total_capital",
            _require_non_negative_finite_number(self.suite_total_capital, "suite_total_capital"),
        )
        _require_tuple_of(self.component_bundles, ComponentContributionBundle, "component_bundles")
        if not isinstance(self.suite_residual, CapitalContribution):
            raise OrchestrationInputError(
                "suite_residual must be a CapitalContribution", field="suite_residual"
            )
        if self.suite_residual.method != AttributionMethod.RESIDUAL:
            raise OrchestrationInputError(
                "suite_residual method must be RESIDUAL", field="suite_residual"
            )
        reconciled_total = math.fsum(
            [bundle.component_total for bundle in self.component_bundles]
            + [
                self.suite_residual.contribution or 0.0,
                self.suite_residual.residual or 0.0,
            ]
        )
        if not _within_attribution_tolerance(reconciled_total, self.suite_total_capital):
            raise OrchestrationInputError(
                "suite attribution records must reconcile to suite_total_capital",
                field="suite_total_capital",
            )

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable attribution report.

        Returns
        -------
        dict[str, object]
            Result of the operation.
        """

        return {
            "run_id": self.run_id,
            "suite_total_capital": self.suite_total_capital,
            "component_bundles": [bundle.as_dict() for bundle in self.component_bundles],
            "suite_residual": self.suite_residual.as_dict(),
        }


@dataclass(frozen=True)
class SuiteAttributionComponentReport:
    """Client-facing component section in a suite attribution report."""

    component: str
    component_total: float
    component_input_hash: str
    component_profile_hash: str
    contributions: tuple[CapitalContribution, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "component",
            _canonical_component_label(self.component, field="component"),
        )
        object.__setattr__(
            self,
            "component_total",
            _require_non_negative_finite_number(self.component_total, "component_total"),
        )
        _require_non_empty_text(self.component_input_hash, "component_input_hash")
        _require_non_empty_text(self.component_profile_hash, "component_profile_hash")
        _require_tuple_of(self.contributions, CapitalContribution, "contributions")

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable component attribution section.

        Returns
        -------
        dict[str, object]
            Result of the operation.
        """

        return {
            "component": self.component,
            "component_total": self.component_total,
            "component_input_hash": self.component_input_hash,
            "component_profile_hash": self.component_profile_hash,
            "contribution_count": len(self.contributions),
            "contributions": [contribution.as_dict() for contribution in self.contributions],
        }


@dataclass(frozen=True)
class SuiteAttributionReport:
    """Deterministic suite-level explain report for clients and notebooks."""

    run_id: str
    suite_total_capital: float
    component_set: tuple[str, ...]
    components: tuple[SuiteAttributionComponentReport, ...]
    suite_residual: CapitalContribution
    reconciliation_status: ReconciliationStatus
    residual_reason: str

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        object.__setattr__(
            self,
            "suite_total_capital",
            _require_non_negative_finite_number(self.suite_total_capital, "suite_total_capital"),
        )
        _require_text_tuple(self.component_set, "component_set")
        _require_tuple_of(self.components, SuiteAttributionComponentReport, "components")
        if tuple(component.component for component in self.components) != self.component_set:
            raise OrchestrationInputError(
                "components must be ordered to match component_set",
                field="components",
            )
        if not isinstance(self.suite_residual, CapitalContribution):
            raise OrchestrationInputError(
                "suite_residual must be a CapitalContribution", field="suite_residual"
            )
        if self.suite_residual.method != AttributionMethod.RESIDUAL:
            raise OrchestrationInputError(
                "suite_residual method must be RESIDUAL", field="suite_residual"
            )
        if not isinstance(self.reconciliation_status, ReconciliationStatus):
            try:
                object.__setattr__(
                    self,
                    "reconciliation_status",
                    ReconciliationStatus(self.reconciliation_status),
                )
            except ValueError as exc:
                raise OrchestrationInputError(
                    "reconciliation_status must be a valid ReconciliationStatus",
                    field="reconciliation_status",
                ) from exc
        _require_non_empty_text(self.residual_reason, "residual_reason")
        if self.suite_residual.reconciliation_status != self.reconciliation_status:
            raise OrchestrationInputError(
                "reconciliation_status must match suite_residual reconciliation_status",
                field="reconciliation_status",
            )

    @property
    def contribution_records(self) -> tuple[CapitalContribution, ...]:
        """Return component records followed by the suite residual record.

        Returns
        -------
        tuple[CapitalContribution, ...]
            Result of the operation.
        """

        component_records = tuple(
            contribution
            for component in self.components
            for contribution in component.contributions
        )
        return (*component_records, self.suite_residual)

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-serialisable suite attribution report.

        Returns
        -------
        dict[str, object]
            Result of the operation.
        """

        return {
            "run_id": self.run_id,
            "suite_total_capital": self.suite_total_capital,
            "component_set": list(self.component_set),
            "reconciliation_status": self.reconciliation_status.value,
            "residual_reason": self.residual_reason,
            "components": [component.as_dict() for component in self.components],
            "suite_residual": self.suite_residual.as_dict(),
            "contribution_record_count": len(self.contribution_records),
        }


@dataclass(frozen=True)
class SuiteCapitalResult:
    """Top-of-house FRTB suite capital result.

    Aggregates IMA, Standardised Approach (SBM + DRC + RRAO), and CVA capital
    charges into the deterministic total market risk and CVA capital charge.

    ``total_capital`` equals ``ima_capital + sa_capital + cva_capital``. All
    three components must share the same ``calculation_date``, ``base_currency``,
    and ``suite_profile_family``.

    Sign convention: all capital figures are non-negative charges in
    ``base_currency``.
    """

    run_id: str
    calculation_date: date
    base_currency: str
    suite_profile_family: str
    total_capital: float
    ima_capital: float
    sa_capital: float
    cva_capital: float
    ima_summary: ImaCapitalSummary
    sa_result: StandardisedApproachCapitalResult
    cva_summary: CvaCapitalSummary
    citations: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    attribution_result: SuiteAttributionResult | None = None

    def __post_init__(self) -> None:
        _require_non_empty_text(self.run_id, "run_id")
        if not isinstance(self.calculation_date, date):
            raise OrchestrationInputError(
                "calculation_date must be a date", field="calculation_date"
            )
        _require_non_empty_text(self.base_currency, "base_currency")
        _require_non_empty_text(self.suite_profile_family, "suite_profile_family")
        object.__setattr__(
            self,
            "ima_capital",
            _require_non_negative_finite_number(self.ima_capital, "ima_capital"),
        )
        object.__setattr__(
            self,
            "sa_capital",
            _require_non_negative_finite_number(self.sa_capital, "sa_capital"),
        )
        object.__setattr__(
            self,
            "cva_capital",
            _require_non_negative_finite_number(self.cva_capital, "cva_capital"),
        )
        object.__setattr__(
            self,
            "total_capital",
            _require_non_negative_finite_number(self.total_capital, "total_capital"),
        )
        expected = math.fsum([self.ima_capital, self.sa_capital, self.cva_capital])
        if not math.isclose(self.total_capital, expected, rel_tol=1e-12, abs_tol=1e-12):
            raise OrchestrationInputError(
                "total_capital must reconcile to ima_capital + sa_capital + cva_capital",
                field="total_capital",
            )
        if not isinstance(self.ima_summary, ImaCapitalSummary):
            raise OrchestrationInputError(
                "ima_summary must be an ImaCapitalSummary", field="ima_summary"
            )
        if not isinstance(self.sa_result, StandardisedApproachCapitalResult):
            raise OrchestrationInputError(
                "sa_result must be a StandardisedApproachCapitalResult", field="sa_result"
            )
        if not isinstance(self.cva_summary, CvaCapitalSummary):
            raise OrchestrationInputError(
                "cva_summary must be a CvaCapitalSummary", field="cva_summary"
            )
        _require_text_tuple(self.citations, "citations")
        _require_text_tuple(self.warnings, "warnings")
        if self.attribution_result is not None and not isinstance(
            self.attribution_result, SuiteAttributionResult
        ):
            raise OrchestrationInputError(
                "attribution_result must be a SuiteAttributionResult",
                field="attribution_result",
            )
        if self.attribution_result is not None:
            if not _within_attribution_tolerance(
                self.attribution_result.suite_total_capital, self.total_capital
            ):
                raise OrchestrationInputError(
                    "attribution_result suite_total_capital must match total_capital",
                    field="attribution_result",
                )

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic audit payload for the suite capital result.

        Returns
        -------
        dict[str, object]
            Result of the operation.
        """

        payload: dict[str, object] = {
            "run_id": self.run_id,
            "calculation_date": self.calculation_date.isoformat(),
            "base_currency": self.base_currency,
            "suite_profile_family": self.suite_profile_family,
            "total_capital": self.total_capital,
            "ima_capital": self.ima_capital,
            "sa_capital": self.sa_capital,
            "cva_capital": self.cva_capital,
            "ima_summary": self.ima_summary.as_dict(),
            "sa_result": self.sa_result.as_dict(),
            "cva_summary": _cva_summary_as_dict(self.cva_summary),
            "citations": list(self.citations),
            "warnings": list(self.warnings),
        }
        if self.attribution_result is not None:
            payload["attribution_result"] = self.attribution_result.as_dict()
        return payload


def _cva_summary_as_dict(summary: CvaCapitalSummary) -> dict[str, object]:
    return {
        "package_name": summary.package_name,
        "run_id": summary.run_id,
        "calculation_date": summary.calculation_date.isoformat(),
        "base_currency": summary.base_currency,
        "profile_id": summary.profile_id,
        "method": summary.method,
        "total_cva_capital": summary.total_cva_capital,
        "profile_hash": summary.profile_hash,
        "input_hash": summary.input_hash,
        "citations": list(summary.citations),
        "warnings": list(summary.warnings),
    }


__all__ = [
    "SuiteAttributionComponentReport",
    "SuiteAttributionReport",
    "SuiteAttributionResult",
    "SuiteCapitalResult",
]
