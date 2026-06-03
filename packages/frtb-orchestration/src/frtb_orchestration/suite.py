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

from frtb_orchestration.cva_summary import CvaCapitalSummary
from frtb_orchestration.ima_summary import ImaCapitalSummary
from frtb_orchestration.standardised import (
    OrchestrationInputError,
    StandardisedApproachCapitalResult,
)

# Suite-level jurisdiction family map. Extends the SA-internal _SA_JURISDICTION_FAMILY
# table to cover IMA regime identifiers and CVA profile identifiers.
# IMA: MAR31-MAR33 regime names; CVA: MAR50 profile names.
_SUITE_PROFILE_FAMILY: dict[str, str] = {
    # SA profiles (ADR 0022)
    "BASEL_MAR21": "BASEL",
    "BASEL_MAR22": "BASEL",
    "BASEL_MAR23": "BASEL",
    "US_NPR_2_0": "US_NPR",
    "EU_CRR3": "EU_CRR3",
    # IMA regimes (MAR31 / NPR 2.0 / CRR3)
    "FED_NPR_2_0": "US_NPR",
    "ECB_CRR3": "EU_CRR3",
    "PRA_UK_CRR": "BASEL",
    # CVA profiles (MAR50)
    "BASEL_MAR50_2020": "BASEL",
    "US_NPR20_VB": "US_NPR",
    "EU_CRR3_CVA": "EU_CRR3",
    "UK_PRA_CVA": "BASEL",
}


def suite_jurisdiction_family(profile_id: str) -> str:
    """Return the suite-level jurisdiction family for a profile or regime id."""

    family = _SUITE_PROFILE_FAMILY.get(profile_id)
    if family is None:
        raise OrchestrationInputError(
            f"profile_id {profile_id!r} is not recognised as a known suite "
            "jurisdiction profile; expected one of: " + ", ".join(sorted(_SUITE_PROFILE_FAMILY)),
            field="profile_id",
        )
    return family


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

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic audit payload for the suite capital result."""

        return {
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


def calculate_suite_capital(
    *,
    ima_summary: ImaCapitalSummary,
    sa_result: StandardisedApproachCapitalResult,
    cva_summary: CvaCapitalSummary,
    run_id: str | None = None,
) -> SuiteCapitalResult:
    """Aggregate IMA, SA, and CVA capital into the top-of-house suite result.

    All three components must share the same calculation date, base currency,
    and regulatory jurisdiction family. Missing, incompatible, or mixed-family
    inputs raise ``OrchestrationInputError``.

    Parameters
    ----------
    ima_summary:
        IMA component capital summary, constructed via ``ImaCapitalSummary``
        or ``recognise_ima_summary``.
    sa_result:
        Composed Standardised Approach result from
        ``compose_standardised_approach_capital``.
    cva_summary:
        CVA capital summary from ``recognise_cva_summary``.
    run_id:
        Optional override for the suite run identifier. When omitted, a
        deterministic id is derived from the component run identifiers.
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

    return SuiteCapitalResult(
        run_id=effective_run_id,
        calculation_date=ima_summary.calculation_date,
        base_currency=ima_summary.base_currency,
        suite_profile_family=suite_family,
        total_capital=total_capital,
        ima_capital=ima_summary.total_ima_capital,
        sa_capital=sa_result.total_capital,
        cva_capital=cva_summary.total_cva_capital,
        ima_summary=ima_summary,
        sa_result=sa_result,
        cva_summary=cva_summary,
        citations=citations,
        warnings=warnings,
    )


def _assert_consistent_calculation_date(
    ima: ImaCapitalSummary,
    sa: StandardisedApproachCapitalResult,
    cva: CvaCapitalSummary,
) -> None:
    ima_date = _as_date(ima.calculation_date)
    sa_date = _as_date(sa.calculation_date)
    cva_date = _as_date(cva.calculation_date)
    dates = {ima_date, sa_date, cva_date}
    if len(dates) > 1:
        detail = f"IMA={ima_date.isoformat()}, SA={sa_date.isoformat()}, CVA={cva_date.isoformat()}"
        raise OrchestrationInputError(
            "all suite components must share the same calculation_date; "
            f"mixed dates supplied: {detail}",
            field="calculation_date",
        )


def _assert_consistent_base_currency(
    ima: ImaCapitalSummary,
    sa: StandardisedApproachCapitalResult,
    cva: CvaCapitalSummary,
) -> None:
    currencies = {ima.base_currency, sa.base_currency, cva.base_currency}
    if len(currencies) > 1:
        detail = f"IMA={ima.base_currency!r}, SA={sa.base_currency!r}, CVA={cva.base_currency!r}"
        raise OrchestrationInputError(
            "all suite components must share the same base_currency; "
            f"mixed currencies supplied: {detail}",
            field="base_currency",
        )


def _assert_consistent_jurisdiction_family(
    ima: ImaCapitalSummary,
    sa: StandardisedApproachCapitalResult,
    cva: CvaCapitalSummary,
) -> str:
    ima_family = suite_jurisdiction_family(ima.profile_id)
    cva_family = suite_jurisdiction_family(cva.profile_id)
    sa_family = sa.jurisdiction_family

    families = {ima_family, sa_family, cva_family}
    if len(families) > 1:
        detail = (
            f"IMA({ima.profile_id!r})={ima_family!r}, "
            f"SA={sa_family!r}, "
            f"CVA({cva.profile_id!r})={cva_family!r}"
        )
        raise OrchestrationInputError(
            "all suite components must share the same regulatory jurisdiction family; "
            f"mixed families supplied: {detail}",
            field="profile_id",
        )
    return families.pop()


def _default_suite_run_id(
    ima: ImaCapitalSummary,
    sa: StandardisedApproachCapitalResult,
    cva: CvaCapitalSummary,
) -> str:
    return f"suite:{ima.run_id}:{sa.run_id}:{cva.run_id}"


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


def _as_date(value: date) -> date:
    return value.date() if hasattr(value, "date") else value


def _require_non_empty_text(value: object, field: str) -> None:
    if not isinstance(value, str) or not value:
        raise OrchestrationInputError(f"{field} must be non-empty text", field=field)


def _require_non_negative_finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OrchestrationInputError(f"{field} must be numeric", field=field)
    number = float(value)
    if not math.isfinite(number):
        raise OrchestrationInputError(f"{field} must be finite", field=field)
    if number < 0.0:
        raise OrchestrationInputError(f"{field} must be non-negative", field=field)
    return number


def _require_text_tuple(value: object, field: str) -> None:
    if not isinstance(value, tuple) or not all(isinstance(item, str) for item in value):
        raise OrchestrationInputError(f"{field} must be a tuple of text values", field=field)


__all__ = [
    "SuiteCapitalResult",
    "calculate_suite_capital",
    "suite_jurisdiction_family",
]
