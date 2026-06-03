from __future__ import annotations

import pytest

from frtb_rrao import (
    RraoClassification,
    RraoEvidenceType,
    RraoInputError,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
    classify_rrao_position,
)


def sample_lineage() -> RraoSourceLineage:
    return RraoSourceLineage(
        source_system="synthetic-risk",
        source_file="rrao.csv",
        source_row_id="row-001",
    )


def sample_position(**overrides: object) -> RraoPosition:
    fields = {
        "position_id": "pos-001",
        "source_row_id": "row-001",
        "desk_id": "rates-exotics",
        "legal_entity": "LE-001",
        "gross_effective_notional": 1_000_000.0,
        "currency": "USD",
        "evidence_type": RraoEvidenceType.EXOTIC_UNDERLYING,
        "evidence_label": "weather derivative",
        "classification_hint": RraoClassification.EXOTIC,
        "lineage": sample_lineage(),
    }
    fields.update(overrides)
    return RraoPosition(**fields)  # type: ignore[arg-type]


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
