from __future__ import annotations

import frtb_cva._ba_reference_data as ba_reference_data
import frtb_cva._girr_reference_data as girr_reference_data
import frtb_cva._reference_profile_data as reference_profile_data
import frtb_cva._sa_cva_reference_payloads as sa_cva_reference_payloads
import frtb_cva.reference_data as reference_data
import frtb_cva.sa_cva_reference_data as sa_cva_reference_data
import pytest
from frtb_common import UnsupportedRegulatoryFeatureError
from frtb_cva import (
    CreditQuality,
    CvaInputError,
    CvaRegulatoryProfile,
    CvaSector,
    ba_cva_alpha,
    ba_cva_discount_scalar,
    ba_cva_rho,
    ba_cva_risk_weight,
    compute_non_imm_discount_factor,
    girr_delta_risk_weight,
    girr_inter_bucket_correlation,
)
from frtb_cva.reference_data import (
    BASEL_BA_CVA_RISK_WEIGHT_RULES,
    GIRR_OTHER_CURRENCY_RISK_WEIGHT_SCALAR,
    citations_for_profile,
    girr_is_specified_currency,
    girr_other_currency_risk_weight_scalar,
    profile_citation_id,
    profile_reference_payload,
)


def test_reference_data_shims_export_split_implementations() -> None:
    assert reference_data.ba_cva_risk_weight is ba_reference_data.ba_cva_risk_weight
    assert reference_data.girr_delta_risk_weight is girr_reference_data.girr_delta_risk_weight
    assert (
        reference_data.profile_reference_payload is reference_profile_data.profile_reference_payload
    )
    assert (
        sa_cva_reference_data.sa_cva_reference_payload
        is sa_cva_reference_payloads.sa_cva_reference_payload
    )


def test_table_1_entries_have_citations() -> None:
    citations = citations_for_profile(CvaRegulatoryProfile.BASEL_MAR50_2020)
    for rule in BASEL_BA_CVA_RISK_WEIGHT_RULES:
        assert rule.citation_id in citations


def test_sovereign_ig_risk_weight() -> None:
    risk_weight, citation_id = ba_cva_risk_weight(
        CvaSector.SOVEREIGN,
        CreditQuality.INVESTMENT_GRADE,
    )
    assert risk_weight == pytest.approx(0.005)
    assert citation_id == "basel_mar50_16"


def test_financial_hy_risk_weight() -> None:
    risk_weight, _ = ba_cva_risk_weight(CvaSector.FINANCIALS, CreditQuality.HIGH_YIELD)
    assert risk_weight == pytest.approx(0.12)


def test_ba_cva_scalars() -> None:
    assert ba_cva_alpha()[0] == pytest.approx(1.4)
    assert ba_cva_rho()[0] == pytest.approx(0.5)
    assert ba_cva_discount_scalar()[0] == pytest.approx(0.65)


def test_non_imm_discount_factor() -> None:
    discount_factor, citation_id = compute_non_imm_discount_factor(2.5)
    assert discount_factor == pytest.approx(0.9400247793232364, rel=1e-9)
    assert citation_id == "basel_mar50_15_4"


def test_girr_other_currency_scalar_is_cited() -> None:
    scalar, citation_id = girr_other_currency_risk_weight_scalar()
    assert scalar == pytest.approx(GIRR_OTHER_CURRENCY_RISK_WEIGHT_SCALAR)
    assert citation_id == "basel_mar50_57"
    assert girr_is_specified_currency("USD", reporting_currency="USD")
    assert not girr_is_specified_currency("CHF", reporting_currency="USD")
    assert girr_is_specified_currency("CHF", reporting_currency="CHF")


def test_girr_delta_tables_are_cited() -> None:
    risk_weight, citation_id = girr_delta_risk_weight("5y")
    assert risk_weight == pytest.approx(0.0074)
    assert citation_id == "basel_mar50_56"
    gamma_bc, gamma_citation = girr_inter_bucket_correlation()
    assert gamma_bc == pytest.approx(0.5)
    assert gamma_citation == "basel_mar50_55"


@pytest.mark.parametrize(
    ("profile", "ba_citation_id", "sa_citation_id"),
    [
        (
            CvaRegulatoryProfile.US_NPR20_VB,
            "us_npr20_vb_ba_cva",
            "us_npr20_vb_sa_cva",
        ),
        (
            CvaRegulatoryProfile.EU_CRR3_CVA,
            "eu_crr3_article_384",
            "eu_crr3_articles_383a_383z",
        ),
        (
            CvaRegulatoryProfile.UK_PRA_CVA,
            "uk_pra_cva_risk_ba",
            "uk_pra_cva_risk_sa",
        ),
    ],
)
def test_non_basel_profile_reference_payloads_are_profile_specific(
    profile: CvaRegulatoryProfile,
    ba_citation_id: str,
    sa_citation_id: str,
) -> None:
    risk_weight, citation_id = ba_cva_risk_weight(
        CvaSector.SOVEREIGN,
        CreditQuality.INVESTMENT_GRADE,
        profile=profile,
    )
    assert risk_weight == pytest.approx(0.005)
    assert citation_id == ba_citation_id

    girr_risk_weight, girr_citation_id = girr_delta_risk_weight("5y", profile=profile)
    assert girr_risk_weight == pytest.approx(0.0074)
    assert girr_citation_id == sa_citation_id

    payload = profile_reference_payload(profile)
    assert payload["profile"] == profile.value
    assert ba_citation_id in payload["citations"]
    assert sa_citation_id in payload["citations"]
    assert "basel_mar50_16" not in payload["citations"]
    ba_cva = payload["ba_cva"]
    sa_cva_girr_delta = payload["sa_cva_girr_delta"]
    assert ba_cva["rho_citation_id"] == ba_citation_id
    assert sa_cva_girr_delta["inter_bucket_correlation_citation_id"] == sa_citation_id


def test_non_basel_profile_citation_mapping_fails_when_unmapped() -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError, match="unmapped"):
        profile_citation_id("basel_mar50_999", CvaRegulatoryProfile.EU_CRR3_CVA)


def test_profile_citation_mapping_fails_when_profile_map_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        reference_profile_data,
        "PROFILE_CITATION_ID_MAP",
        {
            profile: citation_map
            for profile, citation_map in reference_profile_data.PROFILE_CITATION_ID_MAP.items()
            if profile is not CvaRegulatoryProfile.EU_CRR3_CVA
        },
    )

    with pytest.raises(UnsupportedRegulatoryFeatureError, match="no citation map defined"):
        profile_citation_id("basel_mar50_16", CvaRegulatoryProfile.EU_CRR3_CVA)


def test_eu_crr3_profile_citations_include_article_381_scope() -> None:
    citations = citations_for_profile(CvaRegulatoryProfile.EU_CRR3_CVA)
    assert "eu_crr3_article_381" in citations
    assert "Article 381" in citations["eu_crr3_article_381"].paragraph


def test_missing_risk_weight_key_fails() -> None:
    with pytest.raises(CvaInputError, match="unknown sector"):
        ba_cva_risk_weight("NOT_A_SECTOR", CreditQuality.INVESTMENT_GRADE)
