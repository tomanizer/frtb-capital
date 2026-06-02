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
        sign_convention="non_negative",
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
        sign_convention="non_negative",
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
        sign_convention="non_negative",
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


def test_invalid_netting_set_sign_convention_fails(sovereign_counterparty, sample_lineage) -> None:
    netting_set = CvaNettingSet(
        netting_set_id="ns-bad-sign",
        counterparty_id=sovereign_counterparty.counterparty_id,
        ead=1.0,
        effective_maturity=1.0,
        discount_factor=1.0,
        currency="USD",
        sign_convention="bananas",
        uses_imm_ead=True,
        source_row_id="row-ns-bad-sign",
        lineage=sample_lineage,
    )
    with pytest.raises(CvaInputError, match="sign_convention"):
        validate_cva_netting_sets((netting_set,), counterparties=(sovereign_counterparty,))


def test_invalid_sensitivity_sign_convention_fails() -> None:
    sensitivity = SaCvaSensitivity(
        sensitivity_id="s-bad-sign",
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="USD",
        risk_factor_key="5y",
        tenor="5y",
        amount=1.0,
        amount_currency="USD",
        sign_convention="bananas",
        source_row_id="row-s",
    )
    with pytest.raises(CvaInputError, match="sign_convention"):
        validate_sa_cva_sensitivities((sensitivity,))


def test_normalise_ead_amount_errors() -> None:
    with pytest.raises(CvaInputError, match="source_sign_convention"):
        normalise_ead_amount(100.0, source_sign_convention="invalid_convention")  # type: ignore[arg-type]

    assert normalise_ead_amount(-100.0, source_sign_convention="signed_absolute") == 100.0


def test_normalise_sensitivity_amount_errors() -> None:
    from frtb_cva.validation import normalise_sensitivity_amount

    with pytest.raises(CvaInputError, match="source_sign_convention"):
        normalise_sensitivity_amount(100.0, source_sign_convention="invalid_convention")  # type: ignore[arg-type]


def test_validate_cva_counterparties_direct_fail() -> None:
    c = CvaCounterparty(
        counterparty_id="c1",
        desk_id="d1",
        legal_entity="le",
        sector=CvaSector.SOVEREIGN,
        credit_quality=CreditQuality.INVESTMENT_GRADE,
        region="EMEA",
        source_row_id="r1",
    )
    with pytest.raises(CvaInputError, match="iterable"):
        validate_cva_counterparties(c)

    with pytest.raises(CvaInputError, match="iterable"):
        validate_cva_counterparties(123)

    with pytest.raises(CvaInputError, match="only CvaCounterparty objects"):
        validate_cva_counterparties((123,))


def test_validate_cva_netting_sets_direct_fail(sovereign_counterparty) -> None:
    from frtb_cva.validation import validate_cva_netting_sets

    ns = CvaNettingSet(
        netting_set_id="ns-1",
        counterparty_id="ctp-1",
        ead=1.0,
        effective_maturity=1.0,
        discount_factor=1.0,
        currency="USD",
        sign_convention="non_negative",
        uses_imm_ead=True,
        source_row_id="row-1",
    )
    with pytest.raises(CvaInputError, match="iterable"):
        validate_cva_netting_sets(ns)
    with pytest.raises(CvaInputError, match="iterable"):
        validate_cva_netting_sets(123)
    with pytest.raises(CvaInputError, match="only CvaNettingSet objects"):
        validate_cva_netting_sets((123,), counterparties=(sovereign_counterparty,))


def test_validate_cva_hedges_direct_fail() -> None:
    from frtb_cva import (
        BaCvaHedgeType,
        CvaHedge,
        HedgeEligibility,
        HedgeReferenceRelation,
        validate_cva_hedges,
    )

    h = CvaHedge(
        hedge_id="h1",
        source_row_id="r1",
        counterparty_id="c1",
        hedge_type=BaCvaHedgeType.SINGLE_NAME_CDS,
        notional=100.0,
        remaining_maturity=1.0,
        discount_factor=1.0,
        reference_sector=CvaSector.SOVEREIGN,
        reference_credit_quality=CreditQuality.INVESTMENT_GRADE,
        reference_region="EMEA",
        reference_relation=HedgeReferenceRelation.DIRECT,
        eligibility=HedgeEligibility.ELIGIBLE,
        eligibility_evidence_id="ev1",
        is_internal=False,
    )
    with pytest.raises(CvaInputError, match="iterable"):
        validate_cva_hedges(h)
    with pytest.raises(CvaInputError, match="iterable"):
        validate_cva_hedges(123)
    with pytest.raises(CvaInputError, match="only CvaHedge objects"):
        validate_cva_hedges((123,))


def test_validate_sa_cva_sensitivities_direct_fail() -> None:
    sens = SaCvaSensitivity(
        sensitivity_id="s1",
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="USD",
        risk_factor_key="5y",
        tenor="5y",
        amount=1.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-s",
    )
    with pytest.raises(CvaInputError, match="iterable"):
        validate_sa_cva_sensitivities(sens)
    with pytest.raises(CvaInputError, match="iterable"):
        validate_sa_cva_sensitivities(123)
    with pytest.raises(CvaInputError, match="only SaCvaSensitivity objects"):
        validate_sa_cva_sensitivities((123,))


def test_validate_calculation_context_errors() -> None:
    from frtb_cva import (
        CvaCalculationContext,
        CvaMethod,
        CvaRegulatoryProfile,
        validate_calculation_context,
    )

    with pytest.raises(CvaInputError, match="context must be a CvaCalculationContext"):
        validate_calculation_context(123)

    with pytest.raises(CvaInputError, match="profile"):
        validate_calculation_context(
            CvaCalculationContext(
                run_id="r1",
                calculation_date=None,  # type: ignore
                base_currency="USD",
                profile="invalid_profile",  # type: ignore
                method=CvaMethod.BA_CVA_REDUCED,
            )
        )

    with pytest.raises(CvaInputError, match="method"):
        validate_calculation_context(
            CvaCalculationContext(
                run_id="r1",
                calculation_date=None,  # type: ignore
                base_currency="USD",
                profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
                method="invalid_method",  # type: ignore
            )
        )

    with pytest.raises(CvaInputError, match="materiality-threshold alternative is unsupported"):
        validate_calculation_context(
            CvaCalculationContext(
                run_id="r1",
                calculation_date=None,  # type: ignore
                base_currency="USD",
                profile=CvaRegulatoryProfile.BASEL_MAR50_2020,
                method=CvaMethod.BA_CVA_REDUCED,
                materiality_threshold_elected=True,
            )
        )


def test_validate_netting_set_errors(sovereign_counterparty) -> None:
    ns_neg_maturity = CvaNettingSet(
        netting_set_id="ns-neg-mat",
        counterparty_id=sovereign_counterparty.counterparty_id,
        ead=1.0,
        effective_maturity=-1.0,
        discount_factor=1.0,
        currency="USD",
        sign_convention="non_negative",
        uses_imm_ead=True,
        source_row_id="row-ns",
    )
    with pytest.raises(CvaInputError, match="effective maturity must be non-negative"):
        validate_cva_netting_sets((ns_neg_maturity,), counterparties=(sovereign_counterparty,))

    ns_neg_df = CvaNettingSet(
        netting_set_id="ns-neg-df",
        counterparty_id=sovereign_counterparty.counterparty_id,
        ead=1.0,
        effective_maturity=1.0,
        discount_factor=-0.5,
        currency="USD",
        sign_convention="non_negative",
        uses_imm_ead=True,
        source_row_id="row-ns",
    )
    with pytest.raises(CvaInputError, match="discount factor must be positive"):
        validate_cva_netting_sets((ns_neg_df,), counterparties=(sovereign_counterparty,))

    ns_bad_imm = CvaNettingSet(
        netting_set_id="ns-bad-imm",
        counterparty_id=sovereign_counterparty.counterparty_id,
        ead=1.0,
        effective_maturity=1.0,
        discount_factor=1.0,
        currency="USD",
        sign_convention="non_negative",
        uses_imm_ead="yes",  # type: ignore
        source_row_id="row-ns",
    )
    with pytest.raises(CvaInputError, match="uses_imm_ead must be a bool"):
        validate_cva_netting_sets((ns_bad_imm,), counterparties=(sovereign_counterparty,))

    ns_bad_carve = CvaNettingSet(
        netting_set_id="ns-bad-carve",
        counterparty_id=sovereign_counterparty.counterparty_id,
        ead=1.0,
        effective_maturity=1.0,
        discount_factor=1.0,
        currency="USD",
        sign_convention="non_negative",
        uses_imm_ead=True,
        carved_out_to_ba_cva="no",  # type: ignore
        source_row_id="row-ns",
    )
    with pytest.raises(CvaInputError, match="carved_out_to_ba_cva must be a bool"):
        validate_cva_netting_sets((ns_bad_carve,), counterparties=(sovereign_counterparty,))

    ns_bad_df_exp = CvaNettingSet(
        netting_set_id="ns-bad-df-exp",
        counterparty_id=sovereign_counterparty.counterparty_id,
        ead=1.0,
        effective_maturity=1.0,
        discount_factor=1.0,
        currency="USD",
        sign_convention="non_negative",
        uses_imm_ead=True,
        discount_factor_explicit="yes",  # type: ignore
        source_row_id="row-ns",
    )
    with pytest.raises(CvaInputError, match="discount_factor_explicit must be a bool"):
        validate_cva_netting_sets((ns_bad_df_exp,), counterparties=(sovereign_counterparty,))


def test_validate_hedge_errors() -> None:
    from frtb_cva import (
        BaCvaHedgeType,
        CvaHedge,
        HedgeEligibility,
        HedgeReferenceRelation,
        validate_cva_hedges,
    )

    h_neg_notional = CvaHedge(
        hedge_id="h-neg-notional",
        source_row_id="row-h",
        counterparty_id="ctp-1",
        hedge_type=BaCvaHedgeType.SINGLE_NAME_CDS,
        notional=-100.0,
        remaining_maturity=1.0,
        discount_factor=1.0,
        reference_sector=CvaSector.SOVEREIGN,
        reference_credit_quality=CreditQuality.INVESTMENT_GRADE,
        reference_region="EMEA",
        reference_relation=HedgeReferenceRelation.DIRECT,
        eligibility=HedgeEligibility.ELIGIBLE,
        eligibility_evidence_id="ev1",
        is_internal=False,
    )
    with pytest.raises(CvaInputError, match="notional must be non-negative"):
        validate_cva_hedges((h_neg_notional,))

    h_bad_df_exp = CvaHedge(
        hedge_id="h-bad-df-exp",
        source_row_id="row-h",
        counterparty_id="ctp-1",
        hedge_type=BaCvaHedgeType.SINGLE_NAME_CDS,
        notional=100.0,
        remaining_maturity=1.0,
        discount_factor=1.0,
        discount_factor_explicit="yes",  # type: ignore
        reference_sector=CvaSector.SOVEREIGN,
        reference_credit_quality=CreditQuality.INVESTMENT_GRADE,
        reference_region="EMEA",
        reference_relation=HedgeReferenceRelation.DIRECT,
        eligibility=HedgeEligibility.ELIGIBLE,
        eligibility_evidence_id="ev1",
        is_internal=False,
    )
    with pytest.raises(CvaInputError, match="discount_factor_explicit must be a bool"):
        validate_cva_hedges((h_bad_df_exp,))

    h_bad_internal = CvaHedge(
        hedge_id="h-bad-internal",
        source_row_id="row-h",
        counterparty_id="ctp-1",
        hedge_type=BaCvaHedgeType.SINGLE_NAME_CDS,
        notional=100.0,
        remaining_maturity=1.0,
        discount_factor=1.0,
        reference_sector=CvaSector.SOVEREIGN,
        reference_credit_quality=CreditQuality.INVESTMENT_GRADE,
        reference_region="EMEA",
        reference_relation=HedgeReferenceRelation.DIRECT,
        eligibility=HedgeEligibility.ELIGIBLE,
        eligibility_evidence_id="ev1",
        is_internal="yes",  # type: ignore
    )
    with pytest.raises(CvaInputError, match="is_internal must be a bool"):
        validate_cva_hedges((h_bad_internal,))


def test_validate_sa_cva_sensitivity_errors() -> None:
    s_neg_vol = SaCvaSensitivity(
        sensitivity_id="s-neg-vol",
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.VEGA,
        volatility_input=-0.1,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="USD",
        risk_factor_key="5y",
        tenor="5y",
        amount=1.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-s",
    )
    with pytest.raises(CvaInputError, match="volatility input must be non-negative"):
        validate_sa_cva_sensitivities((s_neg_vol,))

    s_no_vol = SaCvaSensitivity(
        sensitivity_id="s-no-vol",
        risk_class=SaCvaRiskClass.GIRR,
        risk_measure=SaCvaRiskMeasure.VEGA,
        volatility_input=None,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="USD",
        risk_factor_key="5y",
        tenor="5y",
        amount=1.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-s",
    )
    with pytest.raises(CvaInputError, match="vega sensitivities must specify volatility_input"):
        validate_sa_cva_sensitivities((s_no_vol,))

    s_bad_weight = SaCvaSensitivity(
        sensitivity_id="s-bad-weight",
        risk_class=SaCvaRiskClass.EQUITY,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="12",
        risk_factor_key="INDEX",
        tenor="5y",
        amount=1.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-s",
        index_max_sector_weight=1.5,
    )
    with pytest.raises(
        CvaInputError, match=r"index_max_sector_weight must be between 0\.0 and 1\.0"
    ):
        validate_sa_cva_sensitivities((s_bad_weight,))

    s_bad_sec = SaCvaSensitivity(
        sensitivity_id="s-bad-sec",
        risk_class=SaCvaRiskClass.EQUITY,
        risk_measure=SaCvaRiskMeasure.DELTA,
        sensitivity_tag=SensitivityTag.CVA,
        bucket_id="12",
        risk_factor_key="INDEX",
        tenor="5y",
        amount=1.0,
        amount_currency="USD",
        sign_convention="positive_loss",
        source_row_id="row-s",
        index_dominant_sector="invalid_sector",  # type: ignore
    )
    with pytest.raises(CvaInputError, match="invalid index dominant sector"):
        validate_sa_cva_sensitivities((s_bad_sec,))


def test_validate_lineage_errors() -> None:
    from frtb_cva import CvaCounterparty, CvaSourceLineage

    c_bad_lineage = CvaCounterparty(
        counterparty_id="c1",
        desk_id="d1",
        legal_entity="le",
        sector=CvaSector.SOVEREIGN,
        credit_quality=CreditQuality.INVESTMENT_GRADE,
        region="EMEA",
        source_row_id="r1",
        lineage="invalid_lineage",  # type: ignore
    )
    with pytest.raises(CvaInputError, match="invalid source lineage"):
        validate_cva_counterparties((c_bad_lineage,))

    lineage_bad_map = CvaSourceLineage(
        source_system="sys",
        source_file="file.csv",
        source_row_id="row-1",
        source_column_map=(("a", "b", "c"),),  # type: ignore
    )
    c_bad_map = CvaCounterparty(
        counterparty_id="c1",
        desk_id="d1",
        legal_entity="le",
        sector=CvaSector.SOVEREIGN,
        credit_quality=CreditQuality.INVESTMENT_GRADE,
        region="EMEA",
        source_row_id="r1",
        lineage=lineage_bad_map,
    )
    with pytest.raises(CvaInputError, match="source column map entries must be field pairs"):
        validate_cva_counterparties((c_bad_map,))


def test_finite_float_errors() -> None:
    from frtb_cva.validation import _finite_float

    with pytest.raises(CvaInputError, match="value must be numeric"):
        _finite_float("abc", field="test")
