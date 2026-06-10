"""Shared RRAO investment-fund validation predicates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

import numpy as np
import numpy.typing as npt

from frtb_rrao import _validation_rules as _vr
from frtb_rrao.data_models import RraoEvidenceType, RraoInvestmentFundMethod

BoolArray = npt.NDArray[np.bool_]
GenericArray = npt.NDArray[np.generic]


@dataclass(frozen=True)
class InvestmentFundRuleFailure:
    """First investment-fund validation failure for one canonical row."""

    message: str
    field: str
    position_id: str


@dataclass(frozen=True)
class InvestmentFundRuleValues:
    """Normalized investment-fund validation values for one canonical row."""

    position_id: str
    gross_effective_notional: float
    is_investment_fund_exposure: bool
    evidence_type: RraoEvidenceType
    descriptor_present: bool
    section_205_method_value: str | None
    fund_gross_effective_notional: float | None
    included_exposure_ratio: float | None
    look_through_available: bool | None
    mandate_allows_rrao_exposures: bool | None


def investment_fund_path_mask(
    is_investment_fund_exposures: BoolArray,
    evidence_types: GenericArray,
    descriptor_present: BoolArray,
) -> BoolArray:
    """Return rows subject to investment-fund validation."""

    return cast(
        BoolArray,
        (
            is_investment_fund_exposures
            | (evidence_types == RraoEvidenceType.INVESTMENT_FUND_EXPOSURE.value)
            | descriptor_present
        ),
    )


def investment_fund_descriptor_present_mask(
    *,
    fund_ids: GenericArray,
    section_205_methods: GenericArray,
    included_exposure_types: GenericArray,
    mandate_evidence_ids: GenericArray,
    section_205_evidence_ids: GenericArray,
    fund_gross_effective_notionals: npt.NDArray[np.float64],
    included_exposure_ratios: npt.NDArray[np.float64],
) -> BoolArray:
    """Return rows with any investment-fund descriptor column populated."""

    return cast(
        BoolArray,
        (
            (fund_ids != None)  # noqa: E711
            | (section_205_methods != None)  # noqa: E711
            | (included_exposure_types != None)  # noqa: E711
            | (mandate_evidence_ids != None)  # noqa: E711
            | (section_205_evidence_ids != None)  # noqa: E711
            | ~np.isnan(fund_gross_effective_notionals)
            | ~np.isnan(included_exposure_ratios)
        ),
    )


def invalid_fund_notional_mask(
    is_fund_path: BoolArray,
    fund_gross_effective_notionals: npt.NDArray[np.float64],
) -> BoolArray:
    """Return fund rows whose gross effective notional is absent or non-positive."""

    with np.errstate(invalid="ignore"):
        return is_fund_path & (
            np.isnan(fund_gross_effective_notionals) | (fund_gross_effective_notionals <= 0.0)
        )


def invalid_included_exposure_ratio_mask(
    is_fund_path: BoolArray,
    included_exposure_ratios: npt.NDArray[np.float64],
) -> BoolArray:
    """Return fund rows whose included-exposure ratio is outside the supported range."""

    with np.errstate(invalid="ignore"):
        return is_fund_path & (
            np.isnan(included_exposure_ratios)
            | (included_exposure_ratios <= 0.0)
            | (included_exposure_ratios > 1.0)
        )


def gross_notional_mismatch_mask(
    *,
    is_fund_path: BoolArray,
    gross_effective_notionals: npt.NDArray[np.float64],
    fund_gross_effective_notionals: npt.NDArray[np.float64],
    included_exposure_ratios: npt.NDArray[np.float64],
) -> BoolArray:
    """Return fund rows whose position notional does not match the included fund portion."""

    with np.errstate(invalid="ignore"):
        return cast(
            BoolArray,
            is_fund_path
            & ~np.isclose(
                gross_effective_notionals,
                fund_gross_effective_notionals * included_exposure_ratios,
                rtol=_vr.NOTIONAL_RECONCILIATION_REL_TOL,
                atol=_vr.NOTIONAL_RECONCILIATION_ABS_TOL,
            ),
        )


def validate_investment_fund_rule_values(
    values: InvestmentFundRuleValues,
    *,
    check_descriptor_values: bool = True,
) -> InvestmentFundRuleFailure | None:
    """Return the first shared investment-fund rule failure for one row."""

    is_fund_path = _vr.investment_fund_path_required(
        is_investment_fund_exposure=values.is_investment_fund_exposure,
        evidence_type=values.evidence_type,
        descriptor_present=values.descriptor_present,
    )
    if not is_fund_path:
        return None

    position_id = values.position_id
    if not values.is_investment_fund_exposure:
        return InvestmentFundRuleFailure(
            _vr.INVESTMENT_FUND_FLAG_REQUIRED_MESSAGE,
            "is_investment_fund_exposure",
            position_id,
        )
    if values.evidence_type is not RraoEvidenceType.INVESTMENT_FUND_EXPOSURE:
        return InvestmentFundRuleFailure(
            _vr.INVESTMENT_FUND_EVIDENCE_TYPE_REQUIRED_MESSAGE,
            "evidence_type",
            position_id,
        )
    if not values.descriptor_present:
        return InvestmentFundRuleFailure(
            _vr.INVESTMENT_FUND_DESCRIPTOR_REQUIRED_MESSAGE,
            "investment_fund_descriptor",
            position_id,
        )
    if not check_descriptor_values:
        return None
    if values.section_205_method_value != RraoInvestmentFundMethod.BACKSTOP_FUND_METHOD.value:
        return InvestmentFundRuleFailure(
            _vr.INVESTMENT_FUND_BACKSTOP_METHOD_REQUIRED_MESSAGE,
            "investment_fund_descriptor.section_205_method",
            position_id,
        )
    if values.look_through_available:
        return InvestmentFundRuleFailure(
            _vr.INVESTMENT_FUND_NON_LOOK_THROUGH_MESSAGE,
            "investment_fund_descriptor.look_through_available",
            position_id,
        )
    if not values.mandate_allows_rrao_exposures:
        return InvestmentFundRuleFailure(
            _vr.INVESTMENT_FUND_MANDATE_ALLOWS_RRAO_MESSAGE,
            "investment_fund_descriptor.mandate_allows_rrao_exposures",
            position_id,
        )
    fund_notional = values.fund_gross_effective_notional
    if fund_notional is None or not _vr.fund_gross_notional_is_positive(fund_notional):
        return InvestmentFundRuleFailure(
            _vr.FUND_GROSS_NOTIONAL_POSITIVE_MESSAGE,
            "investment_fund_descriptor.fund_gross_effective_notional",
            position_id,
        )
    ratio = values.included_exposure_ratio
    if ratio is None or not _vr.included_exposure_ratio_is_valid(ratio):
        return InvestmentFundRuleFailure(
            _vr.INCLUDED_EXPOSURE_RATIO_RANGE_MESSAGE,
            "investment_fund_descriptor.included_exposure_ratio",
            position_id,
        )
    if not _vr.gross_notional_matches_included_fund_portion(
        values.gross_effective_notional,
        fund_notional,
        ratio,
    ):
        return InvestmentFundRuleFailure(
            _vr.GROSS_NOTIONAL_MATCHES_FUND_PORTION_MESSAGE,
            "gross_effective_notional",
            position_id,
        )
    return None


__all__ = [
    "InvestmentFundRuleFailure",
    "InvestmentFundRuleValues",
    "gross_notional_mismatch_mask",
    "invalid_fund_notional_mask",
    "invalid_included_exposure_ratio_mask",
    "investment_fund_descriptor_present_mask",
    "investment_fund_path_mask",
    "validate_investment_fund_rule_values",
]
