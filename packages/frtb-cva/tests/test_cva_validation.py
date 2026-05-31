from __future__ import annotations

import math

import pytest
from frtb_cva import (
    CreditQuality,
    CvaCounterparty,
    CvaInputError,
    CvaNettingSet,
    CvaSector,
    normalise_ead_amount,
    validate_cva_counterparties,
    validate_cva_netting_sets,
)


def test_duplicate_counterparty_id_fails(sovereign_counterparty) -> None:
    with pytest.raises(CvaInputError, match="duplicate counterparty id"):
        validate_cva_counterparties((sovereign_counterparty, sovereign_counterparty))


def test_missing_region_fails(sample_lineage) -> None:
    counterparty = CvaCounterparty(
        counterparty_id="ctp-1",
        desk_id="desk-a",
        legal_entity="LE-001",
        sector=CvaSector.SOVEREIGN,
        credit_quality=CreditQuality.INVESTMENT_GRADE,
        region="",
        source_row_id="row-1",
        lineage=sample_lineage,
    )
    with pytest.raises(CvaInputError, match="region"):
        validate_cva_counterparties((counterparty,))


def test_negative_ead_fails(sovereign_counterparty, sample_lineage) -> None:
    netting_set = CvaNettingSet(
        netting_set_id="ns-1",
        counterparty_id=sovereign_counterparty.counterparty_id,
        ead=-1.0,
        effective_maturity=2.0,
        discount_factor=0.9,
        currency="USD",
        sign_convention="positive_loss",
        uses_imm_ead=False,
        source_row_id="row-ns-1",
        lineage=sample_lineage,
    )
    with pytest.raises(CvaInputError, match="EAD must be non-negative"):
        validate_cva_netting_sets((netting_set,), counterparties=(sovereign_counterparty,))


def test_non_finite_ead_fails() -> None:
    with pytest.raises(CvaInputError, match="finite"):
        normalise_ead_amount(math.inf)


def test_unknown_counterparty_reference_fails(
    sovereign_counterparty,
    sovereign_netting_set,
) -> None:
    unknown = CvaNettingSet(
        netting_set_id="ns-unknown",
        counterparty_id="missing-ctp",
        ead=1.0,
        effective_maturity=1.0,
        discount_factor=1.0,
        currency="USD",
        sign_convention="positive_loss",
        uses_imm_ead=True,
        source_row_id="row-unknown",
    )
    with pytest.raises(CvaInputError, match="unknown counterparty"):
        validate_cva_netting_sets((unknown,), counterparties=(sovereign_counterparty,))
