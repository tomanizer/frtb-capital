from __future__ import annotations

import numpy as np

from frtb_rrao._investment_fund_validation import (
    InvestmentFundRuleValues,
    gross_notional_mismatch_mask,
    investment_fund_descriptor_present_mask,
    investment_fund_path_mask,
    validate_investment_fund_rule_values,
)
from frtb_rrao._validation_rules import INVESTMENT_FUND_FLAG_REQUIRED_MESSAGE
from frtb_rrao.data_models import RraoEvidenceType


def test_investment_fund_rule_values_report_path_failure_first() -> None:
    failure = validate_investment_fund_rule_values(
        InvestmentFundRuleValues(
            position_id="fund-pos-001",
            gross_effective_notional=2_500_000.0,
            is_investment_fund_exposure=False,
            evidence_type=RraoEvidenceType.INVESTMENT_FUND_EXPOSURE,
            descriptor_present=False,
            section_205_method_value=None,
            fund_gross_effective_notional=None,
            included_exposure_ratio=None,
            look_through_available=None,
            mandate_allows_rrao_exposures=None,
        ),
        check_descriptor_values=False,
    )

    assert failure is not None
    assert failure.message == INVESTMENT_FUND_FLAG_REQUIRED_MESSAGE
    assert failure.field == "is_investment_fund_exposure"
    assert failure.position_id == "fund-pos-001"


def test_investment_fund_batch_masks_share_descriptor_and_notional_rules() -> None:
    descriptor_present = investment_fund_descriptor_present_mask(
        fund_ids=np.array(["fund-001", None], dtype=object),
        section_205_methods=np.array(["BACKSTOP_FUND_METHOD", None], dtype=object),
        included_exposure_types=np.array(["OTHER_RESIDUAL_RISK", None], dtype=object),
        mandate_evidence_ids=np.array(["mandate-001", None], dtype=object),
        section_205_evidence_ids=np.array(["section-205-001", None], dtype=object),
        fund_gross_effective_notionals=np.array([10_000_000.0, np.nan]),
        included_exposure_ratios=np.array([0.25, np.nan]),
    )
    fund_path = investment_fund_path_mask(
        np.array([True, False]),
        np.array(["INVESTMENT_FUND_EXPOSURE", "GAP_RISK"], dtype=object),
        descriptor_present,
    )

    assert descriptor_present.tolist() == [True, False]
    assert fund_path.tolist() == [True, False]
    assert gross_notional_mismatch_mask(
        is_fund_path=fund_path,
        gross_effective_notionals=np.array([2_500_000.0, 1.0]),
        fund_gross_effective_notionals=np.array([10_000_000.0, np.nan]),
        included_exposure_ratios=np.array([0.25, np.nan]),
    ).tolist() == [False, False]
