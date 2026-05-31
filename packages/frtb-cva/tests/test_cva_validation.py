from __future__ import annotations

import math

import pytest
from frtb_cva import (
    CreditQuality,
    CvaCounterparty,
    CvaInputError,
    CvaNettingSet,
    CvaSector,
    SaCvaRiskClass,
    SaCvaRiskMeasure,
    SaCvaSensitivity,
    SensitivityTag,
    normalise_ead_amount,
    validate_cva_counterparties,
    validate_cva_netting_sets,
    validate_sa_cva_sensitivities,
)
from frtb_cva.sa_cva import calculate_sa_cva_capital
from frtb_cva.validation import validate_m_cva_multiplier


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


def test_girr_delta_sensitivity_without_tenor_fails() -> None:
    sensitivity = SaCvaSensitivity(
        sensitivity_id="s-no-tenor",
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="USD",
        risk_factor_key="5y",
        tenor=None,
        amount=1.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-s",
    )
    with pytest.raises(CvaInputError, match="tenor"):
        validate_sa_cva_sensitivities((sensitivity,))


def test_hdg_sensitivity_without_hedge_id_fails() -> None:
    sensitivity = SaCvaSensitivity(
        sensitivity_id="s-hdg-no-ref",
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.HDG,
        bucket_id="USD",
        risk_factor_key="5y",
        tenor="5y",
        amount=1.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-s",
        hedge_id=None,
    )
    with pytest.raises(CvaInputError, match="hedge_id"):
        validate_sa_cva_sensitivities((sensitivity,))


def test_netting_set_explicit_df_unity_passes_without_recompute(sovereign_counterparty) -> None:
    """When discount_factor_explicit=True, DF=1.0 must be used verbatim (review finding #3)."""
    from frtb_cva import calculate_netting_set_standalone

    netting_set = CvaNettingSet(
        netting_set_id="ns-df-explicit",
        counterparty_id=sovereign_counterparty.counterparty_id,
        ead=1_000_000.0,
        effective_maturity=5.0,
        discount_factor=1.0,
        discount_factor_explicit=True,
        currency="USD",
        sign_convention="positive_loss",
        uses_imm_ead=False,
        source_row_id="row-ns-df-explicit",
    )
    line = calculate_netting_set_standalone(netting_set, sovereign_counterparty)
    assert line.discount_factor == pytest.approx(1.0)
    assert line.discount_factor_supplied is True


def test_m_cva_multiplier_must_be_finite_and_positive() -> None:
    sensitivity = SaCvaSensitivity(
        sensitivity_id="sens-girr-5y",
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="USD",
        risk_factor_key="5y",
        tenor="5y",
        amount=1_000_000.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-sens-girr-5y",
    )
    with pytest.raises(CvaInputError, match="finite"):
        calculate_sa_cva_capital((sensitivity,), m_cva=float("nan"))
    with pytest.raises(CvaInputError, match="positive"):
        calculate_sa_cva_capital((sensitivity,), m_cva=0.0)
    assert validate_m_cva_multiplier(1.0) == pytest.approx(1.0)
