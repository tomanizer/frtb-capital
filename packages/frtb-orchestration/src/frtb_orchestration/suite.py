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

from frtb_common.contribution_bundle import ComponentContributionBundle

from frtb_orchestration._suite_attribution_builders import (
    aggregate_suite_attribution,
    build_suite_attribution_report,
)
from frtb_orchestration._suite_attribution_models import (
    SuiteAttributionComponentReport,
    SuiteAttributionReport,
    SuiteAttributionResult,
    SuiteCapitalResult,
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
from frtb_orchestration._suite_validation import suite_jurisdiction_family
from frtb_orchestration._validation import OrchestrationInputError
from frtb_orchestration._validation import require_non_empty_text as _require_non_empty_text
from frtb_orchestration.cva_summary import CvaCapitalSummary
from frtb_orchestration.ima_summary import ImaCapitalSummary
from frtb_orchestration.standardised import StandardisedApproachCapitalResult


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
    Parameters
    ----------
    ima_summary : ImaCapitalSummary
        Ima summary.
    sa_result : StandardisedApproachCapitalResult
        Sa result.
    cva_summary : CvaCapitalSummary
        Cva summary.
    run_id : str | None, optional
        Run id.
    component_contribution_bundles : tuple[ComponentContributionBundle, ...], optional
        Component contribution bundles.

    Returns
    -------
    SuiteCapitalResult
        Result of the operation.
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


def _unique_texts(values: list[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


__all__ = [
    "SuiteAttributionComponentReport",
    "SuiteAttributionReport",
    "SuiteAttributionResult",
    "SuiteCapitalResult",
    "aggregate_suite_attribution",
    "build_suite_attribution_report",
    "calculate_suite_capital",
    "suite_jurisdiction_family",
]
