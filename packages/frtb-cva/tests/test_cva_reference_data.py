from __future__ import annotations

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
    citations_for_profile,
    profile_reference_payload,
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


def test_girr_delta_tables_are_cited() -> None:
    risk_weight, citation_id = girr_delta_risk_weight("5y")
    assert risk_weight == pytest.approx(0.0074)
    assert citation_id == "basel_mar50_56"
    gamma_bc, gamma_citation = girr_inter_bucket_correlation()
    assert gamma_bc == pytest.approx(0.5)
    assert gamma_citation == "basel_mar50_55"


def test_unsupported_profile_fails_closed() -> None:
    with pytest.raises(UnsupportedRegulatoryFeatureError):
        profile_reference_payload(CvaRegulatoryProfile.EU_CRR3_CVA)


def test_missing_risk_weight_key_fails() -> None:
    with pytest.raises(CvaInputError, match="unknown sector"):
        ba_cva_risk_weight("NOT_A_SECTOR", CreditQuality.INVESTMENT_GRADE)
