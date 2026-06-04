"""Top-of-house suite capital aggregation.

Suite capital equals IMA + SA + CVA. Components must share the same
calculation date, base currency, and regulatory jurisdiction family before
aggregation is permitted.

Regulatory basis: MAR10.1 - the capital requirement is the higher of the
previous day's capital measure and the average of the daily measures over the
preceding 60 business days adjusted by a multiplier, plus SES; this module
performs the static additive composition step only and does not apply the
multiplier or the 60-day floor. The IMA, SA, and CVA inputs are expected to
already carry their own multiplier and floor adjustments from their owning
packages.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from frtb_common.attribution import AttributionMethod, CapitalContribution, ReconciliationStatus
from frtb_common.contribution_bundle import ComponentContributionBundle

from frtb_orchestration._suite_attribution import (
    canonical_standardised_component as _canonical_standardised_component,
)
from frtb_orchestration._suite_attribution import (
    require_supported_attribution_component_set as _require_supported_attribution_component_set,
)
from frtb_orchestration._suite_attribution import (
    validate_component_bundles as _validate_component_bundles,
)
from frtb_orchestration._suite_attribution import (
    within_attribution_tolerance as _within_attribution_tolerance,
)
from frtb_orchestration._suite_validation import (
    assert_consistent_base_currency as _assert_consistent_base_currency,
)
from frtb_orchestration._suite_validation import (
    assert_consistent_calculation_date as _assert_consistent_calculation_date,
)
from frtb_orchestration._suite_validation import (
    assert_consistent_jurisdiction_family as _assert_consistent_jurisdiction_family,
)
from frtb_orchestration._suite_validation import (
    default_suite_run_id as _default_suite_run_id,
)
from frtb_orchestration._suite_validation import (
    suite_jurisdiction_family,
)
from frtb_orchestration._validation import (
    OrchestrationInputError,
)
from frtb_orchestration._validation import (
    require_non_empty_text as _require_non_empty_text,
)
from frtb_orchestration._validation import (
    require_non_negative_finite_number as _require_non_negative_finite_number,
)
from frtb_orchestration._validation import (
    require_text_tuple as _require_text_tuple,
)
from frtb_orchestration._validation import (
    require_tuple_of as _require_tuple_of,
)
from frtb_orchestration.cva_summary import CvaCapitalSummary
from frtb_orchestration.ima_summary import ImaCapitalSummary
from frtb_orchestration.standardised import (
    StandardisedApproachCapitalResult,
)


@dataclass(frozen=True)
class SuiteAttributionResult:
    """Suite-level attribution report that preserves component bundles unchanged."""

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
        """Return a JSON-serialisable attribution report."""

        return {
            "run_id": self.run_id,
            "suite_total_capital": self.suite_total_capital,
            "component_bundles": [bundle.as_dict() for bundle in self.component_bundles],
            "suite_residual": self.suite_residual.as_dict(),
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
        """Return a deterministic audit payload for the suite capital result."""

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


def calculate_suite_capital(
    *,
    ima_summary: ImaCapitalSummary,
    sa_result: StandardisedApproachCapitalResult,
    cva_summary: CvaCapitalSummary,
    run_id: str | None = None,
    component_contribution_bundles: tuple[ComponentContributionBundle, ...] = (),
) -> SuiteCapitalResult:
    """Aggregate IMA, SA, and CVA capital into the top-of-house suite result.

    Components must share calculation date, base currency, and jurisdiction
    family. When attribution bundles are supplied, they are validated and
    re-exposed with an explicit suite-level residual record.
    """

    if not isinstance(ima_summary, ImaCapitalSummary):
        raise OrchestrationInputError(
            "ima_summary must be an ImaCapitalSummary; "
            "construct one directly or via recognise_ima_summary",
            field="ima_summary",
        )
    if not isinstance(sa_result, StandardisedApproachCapitalResult):
        raise OrchestrationInputError(
            "sa_result must be a StandardisedApproachCapitalResult from "
            "compose_standardised_approach_capital",
            field="sa_result",
        )
    if not isinstance(cva_summary, CvaCapitalSummary):
        raise OrchestrationInputError(
            "cva_summary must be a CvaCapitalSummary; construct one via recognise_cva_summary",
            field="cva_summary",
        )

    _assert_consistent_calculation_date(ima_summary, sa_result, cva_summary)
    _assert_consistent_base_currency(ima_summary, sa_result, cva_summary)
    suite_family = _assert_consistent_jurisdiction_family(ima_summary, sa_result, cva_summary)

    total_capital = math.fsum(
        [ima_summary.total_ima_capital, sa_result.total_capital, cva_summary.total_cva_capital]
    )
    if not math.isfinite(total_capital):
        raise OrchestrationInputError(
            "suite total_capital must be finite after component aggregation",
            field="total_capital",
        )

    citations = _unique_texts(
        list(ima_summary.citations) + list(sa_result.citations) + list(cva_summary.citations)
    )
    warnings = _unique_texts(
        list(ima_summary.warnings) + list(sa_result.warnings) + list(cva_summary.warnings)
    )

    if run_id is not None:
        _require_non_empty_text(run_id, "run_id")
        effective_run_id = run_id
    else:
        effective_run_id = _default_suite_run_id(ima_summary, sa_result, cva_summary)

    result = _build_suite_capital_result(
        run_id=effective_run_id,
        suite_profile_family=suite_family,
        total_capital=total_capital,
        ima_summary=ima_summary,
        sa_result=sa_result,
        cva_summary=cva_summary,
        citations=citations,
        warnings=warnings,
    )
    if not component_contribution_bundles:
        return result

    attribution_result = aggregate_suite_attribution(
        suite_result=result,
        component_bundles=component_contribution_bundles,
    )
    return _build_suite_capital_result(
        run_id=effective_run_id,
        suite_profile_family=suite_family,
        total_capital=total_capital,
        ima_summary=ima_summary,
        sa_result=sa_result,
        cva_summary=cva_summary,
        citations=citations,
        warnings=warnings,
        attribution_result=attribution_result,
    )


def aggregate_suite_attribution(
    *,
    suite_result: SuiteCapitalResult,
    component_bundles: tuple[ComponentContributionBundle, ...],
    suite_total_capital: float | None = None,
) -> SuiteAttributionResult:
    """Validate and aggregate component contribution bundles at suite level.

    Incoming component bundles and their contained ``CapitalContribution``
    records are preserved unchanged. The returned suite residual explicitly
    reconciles bundle totals to the top-of-house suite capital.
    """

    if not isinstance(suite_result, SuiteCapitalResult):
        raise OrchestrationInputError(
            "suite_result must be a SuiteCapitalResult", field="suite_result"
        )
    _require_tuple_of(component_bundles, ComponentContributionBundle, "component_bundles")
    if suite_total_capital is None:
        effective_suite_total = suite_result.total_capital
    else:
        effective_suite_total = _require_non_negative_finite_number(
            suite_total_capital, "suite_total_capital"
        )
    component_capitals = _expected_component_capitals(suite_result)
    canonical_components = _validate_component_bundles(component_bundles, component_capitals)
    _require_supported_attribution_component_set(canonical_components)

    component_total = math.fsum(bundle.component_total for bundle in component_bundles)
    residual = effective_suite_total - component_total
    residual_status = (
        ReconciliationStatus.RECONCILED
        if _within_attribution_tolerance(residual, 0.0)
        else ReconciliationStatus.PARTIAL_RESIDUAL
    )
    residual_reason = (
        "suite-level residual reconciles component contribution bundles to "
        "top-of-house capital; non-zero residuals represent explicitly "
        "unallocated cross-component interactions"
    )
    if residual_status == ReconciliationStatus.RECONCILED:
        residual_reason = (
            "suite-level residual record retained for audit; component "
            "contribution bundles reconcile exactly to top-of-house capital"
        )

    return SuiteAttributionResult(
        run_id=suite_result.run_id,
        suite_total_capital=effective_suite_total,
        component_bundles=component_bundles,
        suite_residual=CapitalContribution(
            contribution_id=f"{suite_result.run_id}:suite-residual",
            source_id=suite_result.run_id,
            source_level="suite",
            bucket_key=None,
            category="SUITE_RESIDUAL",
            base_amount=effective_suite_total,
            marginal_multiplier=None,
            contribution=None,
            method=AttributionMethod.RESIDUAL,
            residual=residual,
            reason=residual_reason,
            citations=("ADR 0038",),
            reconciliation_status=residual_status,
        ),
    )


def _build_suite_capital_result(
    *,
    run_id: str,
    suite_profile_family: str,
    total_capital: float,
    ima_summary: ImaCapitalSummary,
    sa_result: StandardisedApproachCapitalResult,
    cva_summary: CvaCapitalSummary,
    citations: tuple[str, ...],
    warnings: tuple[str, ...],
    attribution_result: SuiteAttributionResult | None = None,
) -> SuiteCapitalResult:
    return SuiteCapitalResult(
        run_id=run_id,
        calculation_date=ima_summary.calculation_date,
        base_currency=ima_summary.base_currency,
        suite_profile_family=suite_profile_family,
        total_capital=total_capital,
        ima_capital=ima_summary.total_ima_capital,
        sa_capital=sa_result.total_capital,
        cva_capital=cva_summary.total_cva_capital,
        ima_summary=ima_summary,
        sa_result=sa_result,
        cva_summary=cva_summary,
        citations=citations,
        warnings=warnings,
        attribution_result=attribution_result,
    )


def _expected_component_capitals(result: SuiteCapitalResult) -> dict[str, float]:
    component_capitals = {
        "frtb_ima": result.ima_capital,
        "frtb_sa": result.sa_capital,
        "frtb_cva": result.cva_capital,
    }
    for subtotal in result.sa_result.component_subtotals:
        component_capitals[_canonical_standardised_component(subtotal.component.value)] = (
            subtotal.total_capital
        )
    return component_capitals


def _unique_texts(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


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
    "SuiteAttributionResult",
    "SuiteCapitalResult",
    "aggregate_suite_attribution",
    "calculate_suite_capital",
    "suite_jurisdiction_family",
]
