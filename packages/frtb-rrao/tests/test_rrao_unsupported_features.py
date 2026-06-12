from __future__ import annotations

import pytest
from tests.rrao_fixture_helpers import sample_rrao_position as sample_position

from frtb_rrao import (
    RraoClassification,
    RraoEvidenceType,
    RraoInputError,
    RraoRegulatoryProfile,
    classify_rrao_position,
)


def test_partial_investment_fund_path_fails_without_descriptor() -> None:
    with pytest.raises(RraoInputError, match="investment fund descriptor"):
        classify_rrao_position(
            sample_position(
                evidence_type=RraoEvidenceType.INVESTMENT_FUND_EXPOSURE,
                evidence_label="investment fund exposure",
                classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
                is_investment_fund_exposure=True,
            )
        )


def test_pra_investment_fund_path_fails_without_descriptor() -> None:
    with pytest.raises(RraoInputError, match="investment fund descriptor"):
        classify_rrao_position(
            sample_position(
                evidence_type=RraoEvidenceType.INVESTMENT_FUND_EXPOSURE,
                evidence_label="investment fund exposure",
                classification_hint=RraoClassification.OTHER_RESIDUAL_RISK,
                is_investment_fund_exposure=True,
            ),
            profile=RraoRegulatoryProfile.PRA_UK_CRR,
        )
