from __future__ import annotations

import unittest.mock as mock

import frtb_cva.reference_data as ref
import frtb_cva.sa_cva_reference_data as sa_ref
import pytest
from frtb_cva.data_models import (
    CreditQuality,
    CvaRegulatoryProfile,
    CvaSector,
    HedgeReferenceRelation,
)
from frtb_cva.validation import CvaInputError


class MockSector:
    value = "MOCK_SECTOR"


class MockRelation:
    value = "MOCK_RELATION"


def test_sa_ref_gamma_lookup_symmetric() -> None:
    # Test directly in table
    val_direct = sa_ref.ccs_inter_bucket_correlation("1", "2")
    assert val_direct[0] == 0.10

    # Test right/left symmetric lookup works
    val = sa_ref.ccs_inter_bucket_correlation("2", "1")
    assert val[0] == 0.10

    # Test unmapped key raises
    with pytest.raises(CvaInputError, match="no cross-bucket correlation"):
        sa_ref.ccs_inter_bucket_correlation("99", "1")


def test_sa_ref_normalise_bucket_empty() -> None:
    with pytest.raises(CvaInputError, match="bucket id is required"):
        sa_ref.ccs_delta_risk_weight("  ", CreditQuality.INVESTMENT_GRADE)


def test_sa_ref_vega_risk_weight_negative() -> None:
    with pytest.raises(CvaInputError, match="volatility input must be non-negative"):
        sa_ref.sa_cva_vega_risk_weight(-0.1)


def test_sa_ref_girr_vega_intra_bucket_correlation() -> None:
    val, _ = sa_ref.girr_vega_intra_bucket_correlation("rate", "rate")
    assert val == 1.0
    val2, _ = sa_ref.girr_vega_intra_bucket_correlation(
        sa_ref.GIRR_VEGA_INFLATION_FACTOR,
        sa_ref.GIRR_VEGA_RATE_FACTOR,
    )
    assert val2 == 0.4
    with pytest.raises(CvaInputError, match="no GIRR vega correlation"):
        sa_ref.girr_vega_intra_bucket_correlation("rate", "invalid")


def test_sa_ref_ccs_delta_risk_weight_unmapped() -> None:
    val, _ = sa_ref.ccs_delta_risk_weight("1a", CreditQuality.INVESTMENT_GRADE)
    assert val > 0.0
    with pytest.raises(CvaInputError, match="no CCS delta risk weight"):
        sa_ref.ccs_delta_risk_weight("99", CreditQuality.INVESTMENT_GRADE)


def test_sa_ref_ccs_delta_intra_bucket_correlation() -> None:
    # same_entity
    val1, _ = sa_ref.ccs_delta_intra_bucket_correlation(
        same_entity=True, legally_related=False, same_credit_quality=False, same_tenor=True
    )
    assert val1 == 1.0
    val2, _ = sa_ref.ccs_delta_intra_bucket_correlation(
        same_entity=True, legally_related=False, same_credit_quality=False, same_tenor=False
    )
    assert val2 == 0.9

    # legally_related
    val3, _ = sa_ref.ccs_delta_intra_bucket_correlation(
        same_entity=False, legally_related=True, same_credit_quality=False, same_tenor=True
    )
    assert val3 == 0.9
    val4, _ = sa_ref.ccs_delta_intra_bucket_correlation(
        same_entity=False, legally_related=True, same_credit_quality=False, same_tenor=False
    )
    assert val4 == 0.81

    # same_credit_quality
    val5, _ = sa_ref.ccs_delta_intra_bucket_correlation(
        same_entity=False, legally_related=False, same_credit_quality=True, same_tenor=True
    )
    assert val5 == 0.5
    val6, _ = sa_ref.ccs_delta_intra_bucket_correlation(
        same_entity=False, legally_related=False, same_credit_quality=True, same_tenor=False
    )
    assert val6 == 0.45

    # default
    val7, _ = sa_ref.ccs_delta_intra_bucket_correlation(
        same_entity=False, legally_related=False, same_credit_quality=False, same_tenor=True
    )
    assert val7 == 0.4
    val8, _ = sa_ref.ccs_delta_intra_bucket_correlation(
        same_entity=False, legally_related=False, same_credit_quality=False, same_tenor=False
    )
    assert val8 == 0.36


def test_sa_ref_rcs_delta_risk_weight_unmapped() -> None:
    val, _ = sa_ref.rcs_delta_risk_weight("1")
    assert val > 0.0
    with pytest.raises(CvaInputError, match="no RCS delta risk weight"):
        sa_ref.rcs_delta_risk_weight("99")


def test_sa_ref_rcs_inter_bucket_correlation_unmapped() -> None:
    # coordinate halving
    val_ig_hy, _ = sa_ref.rcs_inter_bucket_correlation("1", "9")  # 1 is IG, 9 is HY/NR
    assert val_ig_hy > 0.0
    with pytest.raises(CvaInputError, match="no RCS table coordinate"):
        sa_ref.rcs_inter_bucket_correlation("99", "1")


def test_sa_ref_equity_delta_risk_weight_unmapped() -> None:
    val, _ = sa_ref.equity_delta_risk_weight("1")
    assert val > 0.0
    with pytest.raises(CvaInputError, match="no equity delta risk weight"):
        sa_ref.equity_delta_risk_weight("99")


def test_sa_ref_equity_vega_rw_scalar_unmapped() -> None:
    val, _ = sa_ref.equity_vega_rw_scalar("1")
    assert val > 0.0
    with pytest.raises(CvaInputError, match="no equity vega RW scalar"):
        sa_ref.equity_vega_rw_scalar("99")


def test_sa_ref_equity_inter_bucket_correlation() -> None:
    # other bucket path
    val1, _ = sa_ref.equity_inter_bucket_correlation("11", "12")
    assert val1 == 0.0
    # pair 12, 13
    val2, _ = sa_ref.equity_inter_bucket_correlation("12", "13")
    assert val2 == 0.75
    # pair containing 12 or 13
    val3, _ = sa_ref.equity_inter_bucket_correlation("12", "1")
    assert val3 == 0.45
    # default
    val4, _ = sa_ref.equity_inter_bucket_correlation("1", "2")
    assert val4 == 0.15


def test_sa_ref_commodity_delta_risk_weight_unmapped() -> None:
    val, _ = sa_ref.commodity_delta_risk_weight("1")
    assert val > 0.0
    with pytest.raises(CvaInputError, match="no commodity delta risk weight"):
        sa_ref.commodity_delta_risk_weight("99")


def test_sa_ref_commodity_inter_bucket_correlation() -> None:
    val, _ = sa_ref.commodity_inter_bucket_correlation("1", "2")
    assert val == 0.2
    # other bucket
    val2, _ = sa_ref.commodity_inter_bucket_correlation("11", "1")
    assert val2 == 0.0


def test_sa_ref_ccs_single_name_bucket_for_sector() -> None:
    val, _ = sa_ref.ccs_single_name_bucket_for_sector(
        CvaSector.SOVEREIGN, CreditQuality.INVESTMENT_GRADE
    )
    assert val == "1a"
    val2, _ = sa_ref.ccs_single_name_bucket_for_sector(
        CvaSector.SOVEREIGN, CreditQuality.HIGH_YIELD
    )
    assert val2 == "1b"

    with pytest.raises(CvaInputError, match="no CCS single-name bucket"):
        sa_ref.ccs_single_name_bucket_for_sector(MockSector(), CreditQuality.INVESTMENT_GRADE)  # type: ignore[arg-type]


def test_sa_ref_resolve_credit_quality_invalid() -> None:
    with pytest.raises(CvaInputError, match="unknown credit quality"):
        sa_ref._resolve_credit_quality("INVALID")


def test_sa_ref_parse_ccs_entity_key_invalid() -> None:
    # less than 2 segments
    with pytest.raises(CvaInputError, match="CCS risk_factor_key must be"):
        sa_ref.parse_ccs_entity_key("entity")

    # 3 segments but not starting with legal:
    with pytest.raises(CvaInputError, match="CCS optional third segment must be"):
        sa_ref.parse_ccs_entity_key("entity|INVESTMENT_GRADE|invalid:group")

    # too many segments
    with pytest.raises(CvaInputError, match="CCS risk_factor_key has too many segments"):
        sa_ref.parse_ccs_entity_key("entity|INVESTMENT_GRADE|legal:group|extra")

    # empty entity id
    with pytest.raises(CvaInputError, match="CCS entity id is required"):
        sa_ref.parse_ccs_entity_key(" |INVESTMENT_GRADE")

    # successful path with optional legal token
    parsed = sa_ref.parse_ccs_entity_key("entity|INVESTMENT_GRADE|legal:group")
    assert parsed == ("entity", CreditQuality.INVESTMENT_GRADE, "group")


# ref.py (reference_data.py) tests


def test_ref_ba_cva_risk_weight_unmapped() -> None:
    val, _ = ref.ba_cva_risk_weight(CvaSector.SOVEREIGN, CreditQuality.INVESTMENT_GRADE)
    assert val == 0.005
    with mock.patch.dict(ref._TABLE_1_RISK_WEIGHTS, {}, clear=True):
        with pytest.raises(CvaInputError, match="no BA-CVA risk weight"):
            ref.ba_cva_risk_weight(CvaSector.SOVEREIGN, CreditQuality.INVESTMENT_GRADE)


def test_ref_ba_cva_hedge_counterparty_correlation_unmapped() -> None:
    val, _ = ref.ba_cva_hedge_counterparty_correlation(HedgeReferenceRelation.DIRECT)
    assert val == 1.0
    with pytest.raises(CvaInputError, match="unsupported hedge reference relation"):
        ref.ba_cva_hedge_counterparty_correlation(MockRelation())  # type: ignore[arg-type]


def test_ref_ba_cva_index_risk_weight_scalar() -> None:
    val, _ = ref.ba_cva_index_risk_weight_scalar()
    assert val == 0.7


def test_ref_compute_non_imm_discount_factor() -> None:
    # maturity <= 0.0
    val1, _ = ref.compute_non_imm_discount_factor(0.0)
    assert val1 == 1.0
    val2, _ = ref.compute_non_imm_discount_factor(-0.5)
    assert val2 == 1.0
    # normal computation
    val3, _ = ref.compute_non_imm_discount_factor(1.0)
    assert 0.0 < val3 < 1.0
    # rate_times_maturity == 0.0 (floating underflow)
    val4, _ = ref.compute_non_imm_discount_factor(1e-323)
    assert val4 == 1.0


def test_ref_girr_delta_risk_weight_rule_special() -> None:
    rule = ref.girr_delta_risk_weight_rule("1y")
    assert rule.risk_weight == 0.0111

    rule_special = ref.girr_delta_risk_weight_rule("INFL")
    assert rule_special.risk_weight == 0.0111

    rule2 = ref.girr_delta_risk_weight_rule("PARALLEL")
    assert rule2.risk_weight == 0.0158

    with pytest.raises(CvaInputError, match="no SA-CVA GIRR delta risk weight"):
        ref.girr_delta_risk_weight_rule("99y")


def test_ref_girr_delta_intra_bucket_correlation_unmapped() -> None:
    val, _ = ref.girr_delta_intra_bucket_correlation("PARALLEL", "INFL")
    assert val == 0.40
    with pytest.raises(CvaInputError, match="no SA-CVA GIRR delta correlation"):
        ref.girr_delta_intra_bucket_correlation("1y", "99y")


def test_ref_girr_delta_tenors() -> None:
    tenors = ref.girr_delta_tenors()
    assert "1y" in tenors
    assert "30y" in tenors


def test_ref_girr_tenor_definition_unmapped() -> None:
    rule = ref.girr_tenor_definition("1y")
    assert rule.maturity_years == 1.0
    with pytest.raises(CvaInputError, match="no SA-CVA GIRR tenor definition"):
        ref.girr_tenor_definition("99y")


def test_ref_resolve_supported_profile_errors() -> None:
    with pytest.raises(CvaInputError, match="unknown CVA regulatory profile"):
        ref._resolve_supported_profile("INVALID")

    assert ref._resolve_supported_profile(CvaRegulatoryProfile.US_NPR20_VB) is (
        CvaRegulatoryProfile.US_NPR20_VB
    )


def test_ref_resolve_sector_errors() -> None:
    with pytest.raises(CvaInputError, match="unknown sector"):
        ref._resolve_sector("INVALID")


def test_ref_resolve_credit_quality_errors() -> None:
    with pytest.raises(CvaInputError, match="unknown credit quality"):
        ref._resolve_credit_quality("INVALID")


def test_ref_require_text_errors() -> None:
    with pytest.raises(CvaInputError, match="non-empty text is required"):
        ref._require_text("  ", "field_name")


# Additional missing function calls for 100% coverage on
# reference_data.py / sa_cva_reference_data.py


def test_missing_sa_ref_helpers() -> None:
    assert sa_ref.fx_delta_risk_weight()[0] == 0.11
    assert sa_ref.fx_inter_bucket_correlation()[0] == 0.6
    assert sa_ref.sa_cva_vega_risk_weight(0.2)[0] > 0.0


def test_missing_ref_helpers() -> None:
    assert ref.citations_for_profile(CvaRegulatoryProfile.BASEL_MAR50_2020)
    assert ref.ba_cva_alpha()[0] == 1.4
    assert ref.ba_cva_beta()[0] == 0.25
    assert ref.ba_cva_rho()[0] == 0.5
    assert ref.ba_cva_discount_scalar()[0] == 0.65
    assert ref.girr_specified_currencies()
    assert ref.girr_is_specified_currency("USD", reporting_currency="USD") is True
    assert ref.girr_is_specified_currency("BRL", reporting_currency="USD") is False
    assert ref.girr_other_currency_risk_weight_scalar()[0] == 1.4
    assert ref.profile_reference_payload(CvaRegulatoryProfile.BASEL_MAR50_2020)
    assert ref.girr_delta_risk_weight("1y")[0] == 0.0111
    assert ref.girr_inter_bucket_correlation()[0] == 0.5

    # resolve_netting_set_discount_factor paths
    val1, _, used1 = ref.resolve_netting_set_discount_factor(
        uses_imm_ead=True, effective_maturity=1.5, supplied_discount_factor=0.9
    )
    assert val1 == 1.0 and not used1
    val2, _, used2 = ref.resolve_netting_set_discount_factor(
        uses_imm_ead=False,
        effective_maturity=1.5,
        supplied_discount_factor=0.9,
        discount_factor_explicit=True,
    )
    assert val2 == 0.9 and used2
    val3, _, used3 = ref.resolve_netting_set_discount_factor(
        uses_imm_ead=False,
        effective_maturity=1.5,
        supplied_discount_factor=0.9,
        discount_factor_explicit=False,
    )
    assert val3 != 0.9 and not used3
