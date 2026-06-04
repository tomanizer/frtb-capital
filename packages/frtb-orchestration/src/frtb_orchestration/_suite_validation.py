"""Suite-level date, currency, and jurisdiction validation helpers."""

from __future__ import annotations

from datetime import date

from frtb_orchestration._validation import OrchestrationInputError
from frtb_orchestration.cva_summary import CvaCapitalSummary
from frtb_orchestration.ima_summary import ImaCapitalSummary
from frtb_orchestration.standardised import (
    StandardisedApproachCapitalResult,
    standardised_jurisdiction_family,
)

# IMA: MAR31-MAR33 regime names; CVA: MAR50 profile names.
_SUITE_EXTRA_PROFILE_FAMILY: dict[str, str] = {
    "FED_NPR_2_0": "US_NPR",
    "ECB_CRR3": "EU_CRR3",
    "PRA_UK_CRR": "BASEL",
    "BASEL_MAR50_2020": "BASEL",
    "US_NPR20_VB": "US_NPR",
    "EU_CRR3_CVA": "EU_CRR3",
    "UK_PRA_CVA": "BASEL",
}


def suite_jurisdiction_family(profile_id: str) -> str:
    """Return the suite-level jurisdiction family for a profile or regime id.
    Parameters
    ----------
    profile_id : str
        Profile id.

    Returns
    -------
    str
        Result of the operation.
    """

    try:
        return standardised_jurisdiction_family(profile_id)
    except OrchestrationInputError:
        family = _SUITE_EXTRA_PROFILE_FAMILY.get(profile_id)
        if family is not None:
            return family
    expected_profiles = sorted(
        set(_SUITE_EXTRA_PROFILE_FAMILY)
        | {"BASEL_MAR21", "BASEL_MAR22", "BASEL_MAR23", "EU_CRR3", "US_NPR_2_0"}
    )
    raise OrchestrationInputError(
        f"profile_id {profile_id!r} is not recognised as a known suite "
        "jurisdiction profile; expected one of: " + ", ".join(expected_profiles),
        field="profile_id",
    )


def assert_consistent_calculation_date(
    ima: ImaCapitalSummary,
    sa: StandardisedApproachCapitalResult,
    cva: CvaCapitalSummary,
) -> None:
    ima_date = as_date(ima.calculation_date)
    sa_date = as_date(sa.calculation_date)
    cva_date = as_date(cva.calculation_date)
    dates = {ima_date, sa_date, cva_date}
    if len(dates) > 1:
        detail = f"IMA={ima_date.isoformat()}, SA={sa_date.isoformat()}, CVA={cva_date.isoformat()}"
        raise OrchestrationInputError(
            "all suite components must share the same calculation_date; "
            f"mixed dates supplied: {detail}",
            field="calculation_date",
        )


def assert_consistent_base_currency(
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


def assert_consistent_jurisdiction_family(
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


def default_suite_run_id(
    ima: ImaCapitalSummary,
    sa: StandardisedApproachCapitalResult,
    cva: CvaCapitalSummary,
) -> str:
    return f"suite:{ima.run_id}:{sa.run_id}:{cva.run_id}"


def as_date(value: date) -> date:
    return value.date() if hasattr(value, "date") else value
