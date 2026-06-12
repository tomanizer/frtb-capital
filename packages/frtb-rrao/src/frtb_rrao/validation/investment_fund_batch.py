"""Investment-fund rules for RRAO batch validation."""

from __future__ import annotations

from typing import Any

import numpy as np

from frtb_rrao import _validation_rules as _vr
from frtb_rrao._investment_fund_validation import (
    gross_notional_mismatch_mask,
    invalid_fund_notional_mask,
    invalid_included_exposure_ratio_mask,
    investment_fund_descriptor_present_mask,
    investment_fund_path_mask,
)
from frtb_rrao.data_models import (
    RraoEvidenceType,
    RraoInvestmentFundMethod,
)
from frtb_rrao.validation._batch_common import position_id_at_first, require_text_where
from frtb_rrao.validation._errors import RraoInputError


def validate_investment_fund_batch_fields(batch: Any) -> None:
    """Validate investment-fund specific RRAO batch fields.

    Parameters
    ----------
    batch : RraoPositionBatch
        Canonical RRAO position batch.
    """

    descriptor_present = investment_fund_descriptor_present_mask(
        fund_ids=batch.investment_fund_ids,
        section_205_methods=batch.investment_fund_section_205_methods,
        included_exposure_types=batch.investment_fund_included_exposure_types,
        mandate_evidence_ids=batch.investment_fund_mandate_evidence_ids,
        section_205_evidence_ids=batch.investment_fund_section_205_evidence_ids,
        fund_gross_effective_notionals=batch.investment_fund_gross_effective_notionals,
        included_exposure_ratios=batch.investment_fund_included_exposure_ratios,
    )
    is_fund_path = investment_fund_path_mask(
        batch.is_investment_fund_exposures,
        batch.evidence_types,
        descriptor_present,
    )
    _validate_fund_path_presence(batch, is_fund_path, descriptor_present)
    if not bool(np.any(is_fund_path)):
        return
    _validate_fund_descriptor_fields(batch, is_fund_path)
    _validate_fund_notional_fields(batch, is_fund_path)


def _validate_fund_path_presence(
    batch: Any,
    is_fund_path: np.ndarray,
    descriptor_present: np.ndarray,
) -> None:
    missing_flag = is_fund_path & ~batch.is_investment_fund_exposures
    if bool(np.any(missing_flag)):
        raise RraoInputError(
            _vr.INVESTMENT_FUND_FLAG_REQUIRED_MESSAGE,
            field="is_investment_fund_exposure",
            position_id=position_id_at_first(batch, missing_flag),
        )
    wrong_evidence = is_fund_path & (
        batch.evidence_types != RraoEvidenceType.INVESTMENT_FUND_EXPOSURE.value
    )
    if bool(np.any(wrong_evidence)):
        raise RraoInputError(
            _vr.INVESTMENT_FUND_EVIDENCE_TYPE_REQUIRED_MESSAGE,
            field="evidence_type",
            position_id=position_id_at_first(batch, wrong_evidence),
        )
    missing_descriptor = is_fund_path & ~descriptor_present
    if bool(np.any(missing_descriptor)):
        raise RraoInputError(
            _vr.INVESTMENT_FUND_DESCRIPTOR_REQUIRED_MESSAGE,
            field="investment_fund_descriptor",
            position_id=position_id_at_first(batch, missing_descriptor),
        )


def _validate_fund_descriptor_fields(batch: Any, is_fund_path: np.ndarray) -> None:
    require_text_where(
        batch,
        batch.investment_fund_ids,
        is_fund_path,
        field="investment_fund_descriptor.fund_id",
    )
    require_text_where(
        batch,
        batch.investment_fund_mandate_evidence_ids,
        is_fund_path,
        field="investment_fund_descriptor.mandate_evidence_id",
    )
    require_text_where(
        batch,
        batch.investment_fund_section_205_evidence_ids,
        is_fund_path,
        field="investment_fund_descriptor.section_205_evidence_id",
    )
    wrong_method = is_fund_path & (
        batch.investment_fund_section_205_methods
        != RraoInvestmentFundMethod.BACKSTOP_FUND_METHOD.value
    )
    if bool(np.any(wrong_method)):
        raise RraoInputError(
            _vr.INVESTMENT_FUND_BACKSTOP_METHOD_REQUIRED_MESSAGE,
            field="investment_fund_descriptor.section_205_method",
            position_id=position_id_at_first(batch, wrong_method),
        )
    missing_exposure_type = is_fund_path & (
        batch.investment_fund_included_exposure_types == None  # noqa: E711
    )
    if bool(np.any(missing_exposure_type)):
        raise RraoInputError(
            "invalid investment fund exposure type",
            field="investment_fund_descriptor.included_exposure_type",
            position_id=position_id_at_first(batch, missing_exposure_type),
        )
    if bool(np.any(is_fund_path & batch.investment_fund_look_through_availables)):
        raise RraoInputError(
            _vr.INVESTMENT_FUND_NON_LOOK_THROUGH_MESSAGE,
            field="investment_fund_descriptor.look_through_available",
            position_id=position_id_at_first(
                batch,
                is_fund_path & batch.investment_fund_look_through_availables,
            ),
        )
    mandate_disallowed = is_fund_path & ~batch.investment_fund_mandate_allows_rrao_exposures
    if bool(np.any(mandate_disallowed)):
        raise RraoInputError(
            _vr.INVESTMENT_FUND_MANDATE_ALLOWS_RRAO_MESSAGE,
            field="investment_fund_descriptor.mandate_allows_rrao_exposures",
            position_id=position_id_at_first(batch, mandate_disallowed),
        )


def _validate_fund_notional_fields(batch: Any, is_fund_path: np.ndarray) -> None:
    invalid_fund_notional = invalid_fund_notional_mask(
        is_fund_path,
        batch.investment_fund_gross_effective_notionals,
    )
    if bool(np.any(invalid_fund_notional)):
        raise RraoInputError(
            _vr.FUND_GROSS_NOTIONAL_POSITIVE_MESSAGE,
            field="investment_fund_descriptor.fund_gross_effective_notional",
            position_id=position_id_at_first(batch, invalid_fund_notional),
        )
    ratio = batch.investment_fund_included_exposure_ratios
    invalid_ratio = invalid_included_exposure_ratio_mask(is_fund_path, ratio)
    if bool(np.any(invalid_ratio)):
        raise RraoInputError(
            _vr.INCLUDED_EXPOSURE_RATIO_RANGE_MESSAGE,
            field="investment_fund_descriptor.included_exposure_ratio",
            position_id=position_id_at_first(batch, invalid_ratio),
        )
    mismatch = gross_notional_mismatch_mask(
        is_fund_path=is_fund_path,
        gross_effective_notionals=batch.gross_effective_notionals,
        fund_gross_effective_notionals=batch.investment_fund_gross_effective_notionals,
        included_exposure_ratios=ratio,
    )
    if bool(np.any(mismatch)):
        raise RraoInputError(
            _vr.GROSS_NOTIONAL_MATCHES_FUND_PORTION_MESSAGE,
            field="gross_effective_notional",
            position_id=position_id_at_first(batch, mismatch),
        )


__all__ = ["validate_investment_fund_batch_fields"]
