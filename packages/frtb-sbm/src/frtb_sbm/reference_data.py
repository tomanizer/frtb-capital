"""
Reference data for SBM rule profiles.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for reference_data.py, Basel
    MAR21.38-MAR21.43, and SBM-REF-001.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from frtb_common import UnsupportedRegulatoryFeatureError

from frtb_sbm._citations import merge_citation_ids as _merge_citation_ids
from frtb_sbm._text import require_text as _require_text
from frtb_sbm.commodity_reference_data import (
    commodity_bucket_definition,
    commodity_buckets_for_profile,
    commodity_delta_intra_bucket_correlation,
    commodity_delta_risk_weight,
    commodity_inter_bucket_correlation,
)
from frtb_sbm.csr_nonsec_reference_data import (
    csr_nonsec_bucket_definition,
    csr_nonsec_buckets_for_profile,
    csr_nonsec_delta_intra_bucket_correlation,
    csr_nonsec_delta_risk_weight,
    csr_nonsec_inter_bucket_correlation,
    csr_nonsec_validate_delta_inputs,
    csr_nonsec_validate_vega_inputs,
)
from frtb_sbm.data_models import (
    SbmCitation,
    SbmRegulatoryProfile,
    SbmRiskClass,
    SbmScenarioLabel,
)
from frtb_sbm.equity_reference_data import (
    equity_bucket_definition,
    equity_buckets_for_profile,
    equity_delta_intra_bucket_correlation,
    equity_delta_risk_weight,
    equity_inter_bucket_correlation,
)
from frtb_sbm.validation import SbmInputError, require_positive_int

BASEL_MAR21_URL = "https://www.bis.org/basel_framework/chapter/MAR/21.htm"
US_NPR_2_0_URL = "https://www.govinfo.gov/app/details/FR-2026-03-27/2026-05959"

GIRR_DELTA_INTRA_BUCKET_CONSTANT = 0.03
GIRR_VEGA_INTRA_BUCKET_CONSTANT = 0.01
GIRR_VEGA_RISK_WEIGHT_FACTOR = 0.55
GIRR_VEGA_RISK_WEIGHT_CAP = 1.0
GIRR_INTRA_BUCKET_CORRELATION_FLOOR = 0.40
GIRR_INTER_BUCKET_CORRELATION = 0.50
GIRR_SAME_CURVE_CORRELATION = 1.0
GIRR_DIFFERENT_CURVE_CORRELATION = 0.999
GIRR_INFLATION_SAME_TENOR_CORRELATION = 1.0
GIRR_INFLATION_DIFFERENT_TENOR_CORRELATION = 0.40

FX_DELTA_RISK_WEIGHT = 0.15
FX_INTER_BUCKET_CORRELATION = 0.60
FX_INTRA_BUCKET_CORRELATION = 1.0

LIQUID_GIRR_CURRENCIES = frozenset({"EUR", "USD", "GBP", "JPY", "AUD", "CAD", "SEK"})
SQRT2 = math.sqrt(2.0)


@dataclass(frozen=True)
class SbmFxBucketDefinition:
    """Profile-specific FX currency bucket definition."""

    bucket_id: str
    currency: str
    citation_id: str


@dataclass(frozen=True)
class SbmGirrBucketDefinition:
    """Profile-specific GIRR currency bucket definition."""

    bucket_id: str
    currency: str
    citation_id: str


@dataclass(frozen=True)
class SbmGirrTenorDefinition:
    """Profile-specific GIRR tenor label and maturity in years."""

    tenor: str
    maturity_years: float
    citation_id: str


@dataclass(frozen=True)
class SbmGirrRiskWeightRule:
    """Profile-specific GIRR delta risk-weight lookup entry."""

    tenor: str
    risk_weight: float
    citation_id: str


@dataclass(frozen=True)
class SbmGirrSpecialRiskFactorRule:
    """Profile-specific inflation or cross-currency basis risk factor."""

    risk_factor: str
    risk_weight: float
    citation_id: str


@dataclass(frozen=True)
class SbmCorrelationScenarioDefinition:
    """Profile-specific low, medium, or high correlation scenario rule."""

    scenario: SbmScenarioLabel
    multiplier: float
    floor_factor: float | None
    cap: float | None
    citation_id: str


BASEL_CITATIONS: dict[str, SbmCitation] = {
    "basel_mar21_1": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.1",
        url=BASEL_MAR21_URL,
        note="Sensitivities-based method scope and risk-class stack.",
    ),
    "basel_mar21_8": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.8",
        url=BASEL_MAR21_URL,
        note="Risk-factor and bucket assignment boundary.",
    ),
    "basel_mar21_38": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.38-MAR21.41",
        url=BASEL_MAR21_URL,
        note=(
            "GIRR bucket registry keyed to MAR21.41 one-currency-one-bucket rule; "
            "see ADR 0017 for CNH/CNY mapping."
        ),
    ),
    "basel_mar21_39": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.39",
        url=BASEL_MAR21_URL,
        note="Delta buckets, risk weights, and correlation-parameter section lead-in.",
    ),
    "basel_mar21_40": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.40",
        url=BASEL_MAR21_URL,
        note="Liquidity-adjusted calibration scope for prescribed delta weights and correlations.",
    ),
    "basel_mar21_4_intra_bucket": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.4(4)",
        url=BASEL_MAR21_URL,
        note="Intra-bucket capital formula Kb.",
    ),
    "basel_mar21_4_inter_bucket": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.4(5)",
        url=BASEL_MAR21_URL,
        note="Inter-bucket capital formula.",
    ),
    "basel_mar21_curvature": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.5",
        url=BASEL_MAR21_URL,
        note="Curvature risk capital with up/down shock inputs and delta exclusion.",
    ),
    "basel_mar21_6_correlation_scenarios": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.6",
        url=BASEL_MAR21_URL,
        note="Low, medium, and high correlation scenario parameter adjustments.",
    ),
    "basel_mar21_7_scenario_selection": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.7(2)",
        url=BASEL_MAR21_URL,
        note="Select maximum scenario capital for GIRR delta.",
    ),
    "basel_mar21_96": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.96",
        url=BASEL_MAR21_URL,
        note="Curvature buckets, risk weights, and correlation parameters scope.",
    ),
    "basel_mar21_97": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.97",
        url=BASEL_MAR21_URL,
        note="Delta buckets are replicated for curvature unless otherwise specified.",
    ),
    "basel_mar21_98": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.98",
        url=BASEL_MAR21_URL,
        note="FX and equity curvature shock sizes equal the respective delta risk weights.",
    ),
    "basel_mar21_99": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.99",
        url=BASEL_MAR21_URL,
        note=(
            "GIRR, CSR, and commodity curvature shock sizes are parallel shifts based "
            "on the highest prescribed delta risk weight for the relevant bucket."
        ),
    ),
    "basel_mar21_100": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.100",
        url=BASEL_MAR21_URL,
        note="Curvature intra-bucket correlations square the corresponding delta parameters.",
    ),
    "basel_mar21_101": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.101",
        url=BASEL_MAR21_URL,
        note="Curvature inter-bucket correlations square the corresponding delta parameters.",
    ),
    "basel_mar21_41": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.41",
        url=BASEL_MAR21_URL,
        note="Each currency is a separate GIRR delta bucket.",
    ),
    "basel_mar21_42": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.42",
        url=BASEL_MAR21_URL,
        note="GIRR delta risk weights by prescribed tenor.",
    ),
    "basel_mar21_43": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.43",
        url=BASEL_MAR21_URL,
        note="GIRR inflation and cross-currency basis risk weights.",
    ),
    "basel_mar21_44": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.44",
        url=BASEL_MAR21_URL,
        note="Specified-currency sqrt(2) GIRR risk-weight adjustment.",
    ),
    "basel_mar21_45_49": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.45-MAR21.49",
        url=BASEL_MAR21_URL,
        note="GIRR intra-bucket correlation parameters, including inflation and XCCY.",
    ),
    "basel_mar21_50": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.50",
        url=BASEL_MAR21_URL,
        note="GIRR inter-bucket correlation parameter.",
    ),
    "basel_mar21_91": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.91",
        url=BASEL_MAR21_URL,
        note="Vega uses the same bucket definitions for each risk class as delta.",
    ),
    "basel_mar21_92": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.92",
        url=BASEL_MAR21_URL,
        note="Vega liquidity horizon and risk-weight scaling by risk class (Table 13).",
    ),
    "basel_mar21_93": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.93",
        url=BASEL_MAR21_URL,
        note="GIRR vega intra-bucket correlation from option and underlying tenors.",
    ),
    "basel_mar21_90": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.90",
        url=BASEL_MAR21_URL,
        note="Vega risk capital requirement scope.",
    ),
    "basel_mar21_94": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.94",
        url=BASEL_MAR21_URL,
        note=(
            "Non-GIRR vega intra-bucket correlation equals the corresponding "
            "delta correlation times option-tenor correlation, capped at 1."
        ),
    ),
    "basel_mar21_95": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.95",
        url=BASEL_MAR21_URL,
        note="Vega inter-bucket correlations reuse the corresponding delta gammas.",
    ),
    "basel_mar21_14": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.14",
        url=BASEL_MAR21_URL,
        note="FX delta risk-factor definition relative to reporting currency.",
    ),
    "basel_mar21_86": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.86",
        url=BASEL_MAR21_URL,
        note="FX delta bucket assignment by exchange rate versus reporting currency.",
    ),
    "basel_mar21_87": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.87",
        url=BASEL_MAR21_URL,
        note="FX delta uniform 15% risk weight.",
    ),
    "basel_mar21_88": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.88",
        url=BASEL_MAR21_URL,
        note="FX delta sqrt(2) risk-weight reduction for specified and first-order cross pairs.",
    ),
    "basel_mar21_89": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.89",
        url=BASEL_MAR21_URL,
        note="FX delta inter-bucket correlation parameter.",
    ),
    "basel_mar21_12": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.12",
        url=BASEL_MAR21_URL,
        note="Equity delta and vega risk-factor definitions.",
    ),
    "basel_mar21_13": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.13",
        url=BASEL_MAR21_URL,
        note="Commodity delta and vega risk-factor definitions and tenors.",
    ),
    "basel_mar21_72": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.72",
        url=BASEL_MAR21_URL,
        note="Equity delta bucket assignment (Table 9).",
    ),
    "basel_mar21_77": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.77",
        url=BASEL_MAR21_URL,
        note="Equity delta risk weights for spot and repo (Table 10).",
    ),
    "basel_mar21_78": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.78",
        url=BASEL_MAR21_URL,
        note="Equity delta intra-bucket correlation parameters.",
    ),
    "basel_mar21_79": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.79",
        url=BASEL_MAR21_URL,
        note="Equity other-sector bucket absolute-weight aggregation.",
    ),
    "basel_mar21_80": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.80",
        url=BASEL_MAR21_URL,
        note="Equity delta inter-bucket correlation parameters.",
    ),
    "basel_mar21_81": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.81",
        url=BASEL_MAR21_URL,
        note="Commodity delta bucket assignment (Table 11).",
    ),
    "basel_mar21_82": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.82",
        url=BASEL_MAR21_URL,
        note="Commodity delta risk weights (Table 11).",
    ),
    "basel_mar21_83": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.83",
        url=BASEL_MAR21_URL,
        note="Commodity delta intra-bucket correlation parameters (Table 12).",
    ),
    "basel_mar21_85": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.85",
        url=BASEL_MAR21_URL,
        note="Commodity delta inter-bucket correlation parameters.",
    ),
    "basel_mar21_9": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.9",
        url=BASEL_MAR21_URL,
        note="CSR non-securitisation delta risk factors (bond and CDS credit spreads).",
    ),
    "basel_mar21_10": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.10",
        url=BASEL_MAR21_URL,
        note="CSR securitisation non-CTP tranche credit-spread risk factors.",
    ),
    "basel_mar21_11": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.11",
        url=BASEL_MAR21_URL,
        note="CSR securitisation CTP underlying-name credit-spread risk factors.",
    ),
    "basel_mar21_51": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.51",
        url=BASEL_MAR21_URL,
        note="CSR non-securitisation delta bucket assignment (Table 3).",
    ),
    "basel_mar21_53": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.53",
        url=BASEL_MAR21_URL,
        note="CSR non-securitisation delta risk weights (Table 4).",
    ),
    "basel_mar21_54": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.54",
        url=BASEL_MAR21_URL,
        note="CSR non-securitisation delta intra-bucket correlations for buckets 1-15.",
    ),
    "basel_mar21_55": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.55",
        url=BASEL_MAR21_URL,
        note="CSR non-securitisation delta intra-bucket correlations for index buckets 17-18.",
    ),
    "basel_mar21_56": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.56",
        url=BASEL_MAR21_URL,
        note="CSR non-securitisation other-sector bucket absolute-weight aggregation.",
    ),
    "basel_mar21_57": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.57",
        url=BASEL_MAR21_URL,
        note="CSR non-securitisation delta inter-bucket gamma (Table 5).",
    ),
    "basel_mar21_58": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.58",
        url=BASEL_MAR21_URL,
        note="CSR securitisation CTP bucket assignment and intra-bucket correlation rule.",
    ),
    "basel_mar21_59": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.59",
        url=BASEL_MAR21_URL,
        note="CSR securitisation CTP delta risk weights.",
    ),
    "basel_mar21_60": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.60",
        url=BASEL_MAR21_URL,
        note="CSR securitisation CTP other-bucket treatment.",
    ),
    "basel_mar21_61": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.61",
        url=BASEL_MAR21_URL,
        note="CSR securitisation non-CTP bucket assignment.",
    ),
    "basel_mar21_65": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.65",
        url=BASEL_MAR21_URL,
        note="CSR securitisation non-CTP delta risk weights.",
    ),
    "basel_mar21_66": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.66",
        url=BASEL_MAR21_URL,
        note="CSR securitisation non-CTP other-sector risk weight.",
    ),
    "basel_mar21_67": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.67",
        url=BASEL_MAR21_URL,
        note="CSR securitisation non-CTP intra-bucket correlation rule.",
    ),
    "basel_mar21_68": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.68",
        url=BASEL_MAR21_URL,
        note="CSR securitisation non-CTP other-sector aggregation rule.",
    ),
    "basel_mar21_70": SbmCitation(
        source_id="basel_mar21_sensitivities_based_method",
        location="MAR21.70",
        url=BASEL_MAR21_URL,
        note="CSR securitisation non-CTP inter-bucket gamma.",
    ),
}

US_NPR_2_0_CITATIONS: dict[str, SbmCitation] = {
    "us_npr_91_fr_14952_va7a_sbm_scope": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15020, section V.A.7.a",
        url=US_NPR_2_0_URL,
        note=(
            "Standardized non-default capital requirement scope: sensitivities-based "
            "method capital plus residual risk add-on for comparison-profile runs."
        ),
    ),
    "us_npr_91_fr_14952_va7a_girr_buckets": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15020, section V.A.7.a",
        url=US_NPR_2_0_URL,
        note="GIRR delta currency bucket mapping for the NPR comparison slice.",
    ),
    "us_npr_91_fr_14952_va7a_girr_delta_weights": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15020, section V.A.7.a",
        url=US_NPR_2_0_URL,
        note="GIRR delta tenor risk weights used by the NPR comparison slice.",
    ),
    "us_npr_91_fr_14952_va7a_girr_special_factors": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15020, section V.A.7.a",
        url=US_NPR_2_0_URL,
        note="GIRR inflation and cross-currency-basis special risk-factor weights.",
    ),
    "us_npr_91_fr_14952_va7a_girr_sqrt2": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15020, section V.A.7.a",
        url=US_NPR_2_0_URL,
        note="Specified-currency square-root-of-two GIRR risk-weight adjustment.",
    ),
    "us_npr_91_fr_14952_va7a_girr_intra": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15020, section V.A.7.a",
        url=US_NPR_2_0_URL,
        note="GIRR delta intra-bucket tenor, curve, inflation, and XCCY correlations.",
    ),
    "us_npr_91_fr_14952_va7a_girr_inter": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15020, section V.A.7.a",
        url=US_NPR_2_0_URL,
        note="GIRR delta inter-bucket correlation used in the NPR comparison slice.",
    ),
    "us_npr_91_fr_14952_va7a_correlation_scenarios": SbmCitation(
        source_id="us_npr_2_0_91_fr_14952",
        location="91 FR 15020, section V.A.7.a",
        url=US_NPR_2_0_URL,
        note="Low, medium, and high correlation scenario aggregation.",
    ),
}

PROFILE_CITATIONS: dict[SbmRegulatoryProfile, dict[str, SbmCitation]] = {
    SbmRegulatoryProfile.BASEL_MAR21: BASEL_CITATIONS,
    SbmRegulatoryProfile.US_NPR_2_0: US_NPR_2_0_CITATIONS,
}

BASEL_FX_SPECIFIED_CURRENCIES: frozenset[str] = frozenset(
    {
        "USD",
        "EUR",
        "JPY",
        "GBP",
        "AUD",
        "CAD",
        "CHF",
        "MXN",
        "CNY",
        "NZD",
        "RUB",
        "HKD",
        "SGD",
        "TRY",
        "KRW",
        "SEK",
        "ZAR",
        "NOK",
        "INR",
        "BRL",
    }
)

BASEL_FX_BUCKETS: tuple[SbmFxBucketDefinition, ...] = tuple(
    SbmFxBucketDefinition(currency, currency, "basel_mar21_86")
    for currency in sorted(BASEL_FX_SPECIFIED_CURRENCIES)
)

BASEL_GIRR_BUCKETS: tuple[SbmGirrBucketDefinition, ...] = (
    SbmGirrBucketDefinition("1", "EUR", "basel_mar21_38"),
    SbmGirrBucketDefinition("2", "USD", "basel_mar21_38"),
    SbmGirrBucketDefinition("3", "GBP", "basel_mar21_38"),
    SbmGirrBucketDefinition("4", "JPY", "basel_mar21_38"),
    SbmGirrBucketDefinition("5", "AUD", "basel_mar21_38"),
    SbmGirrBucketDefinition("6", "CAD", "basel_mar21_38"),
    SbmGirrBucketDefinition("7", "CHF", "basel_mar21_38"),
    SbmGirrBucketDefinition("8", "CNY", "basel_mar21_38"),
    SbmGirrBucketDefinition("9", "HKD", "basel_mar21_38"),
    SbmGirrBucketDefinition("10", "KRW", "basel_mar21_38"),
    SbmGirrBucketDefinition("11", "MXN", "basel_mar21_38"),
    SbmGirrBucketDefinition("12", "NOK", "basel_mar21_38"),
    SbmGirrBucketDefinition("13", "NZD", "basel_mar21_38"),
    SbmGirrBucketDefinition("14", "SEK", "basel_mar21_38"),
    SbmGirrBucketDefinition("15", "SGD", "basel_mar21_38"),
    SbmGirrBucketDefinition("16", "TRY", "basel_mar21_38"),
    SbmGirrBucketDefinition("17", "CNH", "basel_mar21_38"),
)

BASEL_GIRR_TENORS: tuple[SbmGirrTenorDefinition, ...] = (
    SbmGirrTenorDefinition("3m", 0.25, "basel_mar21_42"),
    SbmGirrTenorDefinition("6m", 0.5, "basel_mar21_42"),
    SbmGirrTenorDefinition("1y", 1.0, "basel_mar21_42"),
    SbmGirrTenorDefinition("2y", 2.0, "basel_mar21_42"),
    SbmGirrTenorDefinition("3y", 3.0, "basel_mar21_42"),
    SbmGirrTenorDefinition("5y", 5.0, "basel_mar21_42"),
    SbmGirrTenorDefinition("10y", 10.0, "basel_mar21_42"),
    SbmGirrTenorDefinition("15y", 15.0, "basel_mar21_42"),
    SbmGirrTenorDefinition("20y", 20.0, "basel_mar21_42"),
    SbmGirrTenorDefinition("30y", 30.0, "basel_mar21_42"),
)

BASEL_GIRR_DELTA_RISK_WEIGHTS: tuple[SbmGirrRiskWeightRule, ...] = (
    SbmGirrRiskWeightRule("3m", 0.017, "basel_mar21_42"),
    SbmGirrRiskWeightRule("6m", 0.017, "basel_mar21_42"),
    SbmGirrRiskWeightRule("1y", 0.016, "basel_mar21_42"),
    SbmGirrRiskWeightRule("2y", 0.013, "basel_mar21_42"),
    SbmGirrRiskWeightRule("3y", 0.012, "basel_mar21_42"),
    SbmGirrRiskWeightRule("5y", 0.011, "basel_mar21_42"),
    SbmGirrRiskWeightRule("10y", 0.011, "basel_mar21_42"),
    SbmGirrRiskWeightRule("15y", 0.011, "basel_mar21_42"),
    SbmGirrRiskWeightRule("20y", 0.011, "basel_mar21_42"),
    SbmGirrRiskWeightRule("30y", 0.011, "basel_mar21_42"),
)

BASEL_GIRR_SPECIAL_RISK_FACTORS: tuple[SbmGirrSpecialRiskFactorRule, ...] = (
    SbmGirrSpecialRiskFactorRule("INFL", 0.016, "basel_mar21_43"),
    SbmGirrSpecialRiskFactorRule("XCCY", 0.016, "basel_mar21_43"),
)

BASEL_CORRELATION_SCENARIOS: tuple[SbmCorrelationScenarioDefinition, ...] = (
    SbmCorrelationScenarioDefinition(
        SbmScenarioLabel.LOW,
        multiplier=0.75,
        floor_factor=0.75,
        cap=None,
        citation_id="basel_mar21_6_correlation_scenarios",
    ),
    SbmCorrelationScenarioDefinition(
        SbmScenarioLabel.MEDIUM,
        multiplier=1.0,
        floor_factor=None,
        cap=None,
        citation_id="basel_mar21_6_correlation_scenarios",
    ),
    SbmCorrelationScenarioDefinition(
        SbmScenarioLabel.HIGH,
        multiplier=1.25,
        floor_factor=None,
        cap=1.0,
        citation_id="basel_mar21_6_correlation_scenarios",
    ),
)

US_NPR_GIRR_BUCKETS: tuple[SbmGirrBucketDefinition, ...] = (
    SbmGirrBucketDefinition("1", "EUR", "us_npr_91_fr_14952_va7a_girr_buckets"),
    SbmGirrBucketDefinition("2", "USD", "us_npr_91_fr_14952_va7a_girr_buckets"),
    SbmGirrBucketDefinition("3", "GBP", "us_npr_91_fr_14952_va7a_girr_buckets"),
    SbmGirrBucketDefinition("4", "JPY", "us_npr_91_fr_14952_va7a_girr_buckets"),
    SbmGirrBucketDefinition("5", "AUD", "us_npr_91_fr_14952_va7a_girr_buckets"),
    SbmGirrBucketDefinition("6", "CAD", "us_npr_91_fr_14952_va7a_girr_buckets"),
    SbmGirrBucketDefinition("7", "CHF", "us_npr_91_fr_14952_va7a_girr_buckets"),
    SbmGirrBucketDefinition("8", "CNY", "us_npr_91_fr_14952_va7a_girr_buckets"),
    SbmGirrBucketDefinition("9", "HKD", "us_npr_91_fr_14952_va7a_girr_buckets"),
    SbmGirrBucketDefinition("10", "KRW", "us_npr_91_fr_14952_va7a_girr_buckets"),
    SbmGirrBucketDefinition("11", "MXN", "us_npr_91_fr_14952_va7a_girr_buckets"),
    SbmGirrBucketDefinition("12", "NOK", "us_npr_91_fr_14952_va7a_girr_buckets"),
    SbmGirrBucketDefinition("13", "NZD", "us_npr_91_fr_14952_va7a_girr_buckets"),
    SbmGirrBucketDefinition("14", "SEK", "us_npr_91_fr_14952_va7a_girr_buckets"),
    SbmGirrBucketDefinition("15", "SGD", "us_npr_91_fr_14952_va7a_girr_buckets"),
    SbmGirrBucketDefinition("16", "TRY", "us_npr_91_fr_14952_va7a_girr_buckets"),
    SbmGirrBucketDefinition("17", "CNH", "us_npr_91_fr_14952_va7a_girr_buckets"),
)

US_NPR_GIRR_TENORS: tuple[SbmGirrTenorDefinition, ...] = (
    SbmGirrTenorDefinition("3m", 0.25, "us_npr_91_fr_14952_va7a_girr_delta_weights"),
    SbmGirrTenorDefinition("6m", 0.5, "us_npr_91_fr_14952_va7a_girr_delta_weights"),
    SbmGirrTenorDefinition("1y", 1.0, "us_npr_91_fr_14952_va7a_girr_delta_weights"),
    SbmGirrTenorDefinition("2y", 2.0, "us_npr_91_fr_14952_va7a_girr_delta_weights"),
    SbmGirrTenorDefinition("3y", 3.0, "us_npr_91_fr_14952_va7a_girr_delta_weights"),
    SbmGirrTenorDefinition("5y", 5.0, "us_npr_91_fr_14952_va7a_girr_delta_weights"),
    SbmGirrTenorDefinition("10y", 10.0, "us_npr_91_fr_14952_va7a_girr_delta_weights"),
    SbmGirrTenorDefinition("15y", 15.0, "us_npr_91_fr_14952_va7a_girr_delta_weights"),
    SbmGirrTenorDefinition("20y", 20.0, "us_npr_91_fr_14952_va7a_girr_delta_weights"),
    SbmGirrTenorDefinition("30y", 30.0, "us_npr_91_fr_14952_va7a_girr_delta_weights"),
)

US_NPR_GIRR_DELTA_RISK_WEIGHTS: tuple[SbmGirrRiskWeightRule, ...] = (
    SbmGirrRiskWeightRule("3m", 0.017, "us_npr_91_fr_14952_va7a_girr_delta_weights"),
    SbmGirrRiskWeightRule("6m", 0.017, "us_npr_91_fr_14952_va7a_girr_delta_weights"),
    SbmGirrRiskWeightRule("1y", 0.016, "us_npr_91_fr_14952_va7a_girr_delta_weights"),
    SbmGirrRiskWeightRule("2y", 0.013, "us_npr_91_fr_14952_va7a_girr_delta_weights"),
    SbmGirrRiskWeightRule("3y", 0.012, "us_npr_91_fr_14952_va7a_girr_delta_weights"),
    SbmGirrRiskWeightRule("5y", 0.011, "us_npr_91_fr_14952_va7a_girr_delta_weights"),
    SbmGirrRiskWeightRule("10y", 0.011, "us_npr_91_fr_14952_va7a_girr_delta_weights"),
    SbmGirrRiskWeightRule("15y", 0.011, "us_npr_91_fr_14952_va7a_girr_delta_weights"),
    SbmGirrRiskWeightRule("20y", 0.011, "us_npr_91_fr_14952_va7a_girr_delta_weights"),
    SbmGirrRiskWeightRule("30y", 0.011, "us_npr_91_fr_14952_va7a_girr_delta_weights"),
)

US_NPR_GIRR_SPECIAL_RISK_FACTORS: tuple[SbmGirrSpecialRiskFactorRule, ...] = (
    SbmGirrSpecialRiskFactorRule(
        "INFL",
        0.016,
        "us_npr_91_fr_14952_va7a_girr_special_factors",
    ),
    SbmGirrSpecialRiskFactorRule(
        "XCCY",
        0.016,
        "us_npr_91_fr_14952_va7a_girr_special_factors",
    ),
)

US_NPR_CORRELATION_SCENARIOS: tuple[SbmCorrelationScenarioDefinition, ...] = (
    SbmCorrelationScenarioDefinition(
        SbmScenarioLabel.LOW,
        multiplier=0.75,
        floor_factor=0.75,
        cap=None,
        citation_id="us_npr_91_fr_14952_va7a_correlation_scenarios",
    ),
    SbmCorrelationScenarioDefinition(
        SbmScenarioLabel.MEDIUM,
        multiplier=1.0,
        floor_factor=None,
        cap=None,
        citation_id="us_npr_91_fr_14952_va7a_correlation_scenarios",
    ),
    SbmCorrelationScenarioDefinition(
        SbmScenarioLabel.HIGH,
        multiplier=1.25,
        floor_factor=None,
        cap=1.0,
        citation_id="us_npr_91_fr_14952_va7a_correlation_scenarios",
    ),
)

PROFILE_GIRR_DELTA_SQRT2_CITATION_IDS: dict[SbmRegulatoryProfile, str] = {
    SbmRegulatoryProfile.BASEL_MAR21: "basel_mar21_44",
    SbmRegulatoryProfile.US_NPR_2_0: "us_npr_91_fr_14952_va7a_girr_sqrt2",
}

PROFILE_GIRR_DELTA_INTRA_BUCKET_CITATION_IDS: dict[SbmRegulatoryProfile, str] = {
    SbmRegulatoryProfile.BASEL_MAR21: "basel_mar21_45_49",
    SbmRegulatoryProfile.US_NPR_2_0: "us_npr_91_fr_14952_va7a_girr_intra",
}

PROFILE_GIRR_DELTA_INTER_BUCKET_CITATION_IDS: dict[SbmRegulatoryProfile, str] = {
    SbmRegulatoryProfile.BASEL_MAR21: "basel_mar21_50",
    SbmRegulatoryProfile.US_NPR_2_0: "us_npr_91_fr_14952_va7a_girr_inter",
}

PROFILE_FX_BUCKETS: dict[SbmRegulatoryProfile, tuple[SbmFxBucketDefinition, ...]] = {
    SbmRegulatoryProfile.BASEL_MAR21: BASEL_FX_BUCKETS,
}

PROFILE_FX_SPECIFIED_CURRENCIES: dict[SbmRegulatoryProfile, frozenset[str]] = {
    SbmRegulatoryProfile.BASEL_MAR21: BASEL_FX_SPECIFIED_CURRENCIES,
}

PROFILE_GIRR_BUCKETS: dict[SbmRegulatoryProfile, tuple[SbmGirrBucketDefinition, ...]] = {
    SbmRegulatoryProfile.BASEL_MAR21: BASEL_GIRR_BUCKETS,
    SbmRegulatoryProfile.US_NPR_2_0: US_NPR_GIRR_BUCKETS,
}

PROFILE_GIRR_TENORS: dict[SbmRegulatoryProfile, tuple[SbmGirrTenorDefinition, ...]] = {
    SbmRegulatoryProfile.BASEL_MAR21: BASEL_GIRR_TENORS,
    SbmRegulatoryProfile.US_NPR_2_0: US_NPR_GIRR_TENORS,
}

PROFILE_GIRR_DELTA_RISK_WEIGHTS: dict[
    SbmRegulatoryProfile,
    tuple[SbmGirrRiskWeightRule, ...],
] = {
    SbmRegulatoryProfile.BASEL_MAR21: BASEL_GIRR_DELTA_RISK_WEIGHTS,
    SbmRegulatoryProfile.US_NPR_2_0: US_NPR_GIRR_DELTA_RISK_WEIGHTS,
}

PROFILE_GIRR_SPECIAL_RISK_FACTORS: dict[
    SbmRegulatoryProfile,
    tuple[SbmGirrSpecialRiskFactorRule, ...],
] = {
    SbmRegulatoryProfile.BASEL_MAR21: BASEL_GIRR_SPECIAL_RISK_FACTORS,
    SbmRegulatoryProfile.US_NPR_2_0: US_NPR_GIRR_SPECIAL_RISK_FACTORS,
}

PROFILE_CORRELATION_SCENARIOS: dict[
    SbmRegulatoryProfile,
    tuple[SbmCorrelationScenarioDefinition, ...],
] = {
    SbmRegulatoryProfile.BASEL_MAR21: BASEL_CORRELATION_SCENARIOS,
    SbmRegulatoryProfile.US_NPR_2_0: US_NPR_CORRELATION_SCENARIOS,
}

PROFILE_GIRR_VEGA_LIQUIDITY_HORIZON_DAYS: dict[SbmRegulatoryProfile, int] = {
    SbmRegulatoryProfile.BASEL_MAR21: 60,
}

PROFILE_VEGA_LIQUIDITY_HORIZON_DAYS: dict[
    SbmRegulatoryProfile,
    dict[SbmRiskClass, int],
] = {
    SbmRegulatoryProfile.BASEL_MAR21: {
        SbmRiskClass.GIRR: 60,
        SbmRiskClass.CSR_NONSEC: 120,
        SbmRiskClass.CSR_SEC_CTP: 120,
        SbmRiskClass.CSR_SEC_NONCTP: 120,
        SbmRiskClass.COMMODITY: 120,
        SbmRiskClass.FX: 40,
    }
}

EQUITY_VEGA_LARGE_CAP_INDEX_LIQUIDITY_HORIZON_DAYS = 20
EQUITY_VEGA_SMALL_CAP_OTHER_LIQUIDITY_HORIZON_DAYS = 60
EQUITY_VEGA_LARGE_CAP_INDEX_BUCKETS = frozenset(
    {"1", "2", "3", "4", "5", "6", "7", "8", "12", "13"}
)
EQUITY_VEGA_SMALL_CAP_OTHER_BUCKETS = frozenset({"9", "10", "11"})

PROFILE_GIRR_VEGA_OPTION_TENORS: dict[
    SbmRegulatoryProfile,
    tuple[SbmGirrTenorDefinition, ...],
] = {
    SbmRegulatoryProfile.BASEL_MAR21: BASEL_GIRR_TENORS,
}


def citations_for_profile(
    profile: SbmRegulatoryProfile | str,
) -> dict[str, SbmCitation]:
    """Return citations for a supported SBM profile."""

    resolved = _resolve_supported_profile(profile)
    return dict(PROFILE_CITATIONS[resolved])


def curvature_citation_ids(profile: SbmRegulatoryProfile | str) -> tuple[str, ...]:
    """Return ordered citation ids for curvature contract validation."""

    citations = citations_for_profile(profile)
    required = (
        "basel_mar21_curvature",
        "basel_mar21_96",
        "basel_mar21_97",
        "basel_mar21_98",
        "basel_mar21_99",
        "basel_mar21_100",
        "basel_mar21_101",
    )
    missing = [citation_id for citation_id in required if citation_id not in citations]
    if missing:
        raise UnsupportedRegulatoryFeatureError(
            f"curvature citations are unavailable for profile={profile!r}"
        )
    return required


def curvature_risk_weight(
    profile: SbmRegulatoryProfile | str,
    *,
    risk_class: SbmRiskClass | str,
    bucket_id: str = "",
    risk_factor: str = "",
    currency: str = "",
    reporting_currency: str = "",
) -> tuple[float, tuple[str, ...]]:
    """Return the cited MAR21.98/MAR21.99 curvature shock size for one factor."""

    resolved_class = _coerce_risk_class(risk_class)
    if resolved_class is SbmRiskClass.GIRR:
        _ensure_girr_delta_supported(profile)
        rule = max(
            PROFILE_GIRR_DELTA_RISK_WEIGHTS[_resolve_supported_profile(profile)],
            key=lambda item: item.risk_weight,
        )
        return rule.risk_weight, ("basel_mar21_99", rule.citation_id)
    if resolved_class is SbmRiskClass.FX:
        weight, citations = fx_delta_risk_weight(
            profile,
            currency=currency or risk_factor or bucket_id,
            reporting_currency=reporting_currency,
        )
        return weight, _merge_citation_ids(("basel_mar21_98",), citations)
    if resolved_class is SbmRiskClass.EQUITY:
        from frtb_sbm.equity_reference_data import EQUITY_SPOT_RISK_FACTOR

        factor = risk_factor or EQUITY_SPOT_RISK_FACTOR
        if factor.strip().upper() != EQUITY_SPOT_RISK_FACTOR:
            raise UnsupportedRegulatoryFeatureError(
                "equity curvature has no capital requirement for equity repo rates (MAR21.12(3))"
            )
        weight, citations = equity_delta_risk_weight(
            profile,
            bucket_id=bucket_id,
            risk_factor=EQUITY_SPOT_RISK_FACTOR,
        )
        return weight, _merge_citation_ids(("basel_mar21_98",), citations)
    if resolved_class is SbmRiskClass.COMMODITY:
        weight, citations = commodity_delta_risk_weight(profile, bucket_id=bucket_id)
        return weight, _merge_citation_ids(("basel_mar21_99",), citations)
    if resolved_class is SbmRiskClass.CSR_NONSEC:
        weight, citations = csr_nonsec_delta_risk_weight(profile, bucket_id=bucket_id)
        return weight, _merge_citation_ids(("basel_mar21_99",), citations)
    if resolved_class is SbmRiskClass.CSR_SEC_CTP:
        from frtb_sbm.csr_sec_ctp_reference_data import csr_sec_ctp_delta_risk_weight

        weight, citations = csr_sec_ctp_delta_risk_weight(profile, bucket_id=bucket_id)
        return weight, _merge_citation_ids(("basel_mar21_99",), citations)
    if resolved_class is SbmRiskClass.CSR_SEC_NONCTP:
        from frtb_sbm.csr_sec_nonctp_reference_data import csr_sec_nonctp_delta_risk_weight

        weight, citations = csr_sec_nonctp_delta_risk_weight(profile, bucket_id=bucket_id)
        return weight, _merge_citation_ids(("basel_mar21_99",), citations)
    raise UnsupportedRegulatoryFeatureError(
        f"curvature risk weights are unsupported for risk_class={resolved_class.value}"
    )


def girr_buckets_for_profile(
    profile: SbmRegulatoryProfile | str,
) -> tuple[SbmGirrBucketDefinition, ...]:
    """Return GIRR bucket definitions for a supported profile."""

    resolved = _resolve_supported_profile(profile)
    return PROFILE_GIRR_BUCKETS[resolved]


def girr_tenors_for_profile(
    profile: SbmRegulatoryProfile | str,
) -> tuple[SbmGirrTenorDefinition, ...]:
    """Return the prescribed GIRR tenor set for a supported profile."""

    resolved = _resolve_supported_profile(profile)
    return PROFILE_GIRR_TENORS[resolved]


def girr_bucket_for_currency(
    profile: SbmRegulatoryProfile | str,
    currency: str,
) -> SbmGirrBucketDefinition:
    """Return the GIRR bucket definition for a currency code."""

    normalised = _require_currency(currency)
    for bucket in girr_buckets_for_profile(profile):
        if bucket.currency == normalised:
            return bucket
    raise SbmInputError(
        f"no GIRR bucket for currency {normalised}",
        field="currency",
    )


def girr_bucket_definition(
    profile: SbmRegulatoryProfile | str,
    bucket_id: str,
) -> SbmGirrBucketDefinition:
    """Return the GIRR bucket definition for a bucket id."""

    normalised = _require_text(bucket_id, "bucket_id")
    for bucket in girr_buckets_for_profile(profile):
        if bucket.bucket_id == normalised:
            return bucket
    raise SbmInputError(
        f"no GIRR bucket definition for bucket_id {normalised}",
        field="bucket_id",
    )


def girr_tenor_definition(
    profile: SbmRegulatoryProfile | str,
    tenor: str,
) -> SbmGirrTenorDefinition:
    """Return the GIRR tenor definition for a canonical tenor label."""

    normalised = _require_text(tenor, "tenor")
    for tenor_definition in girr_tenors_for_profile(profile):
        if tenor_definition.tenor == normalised:
            return tenor_definition
    raise SbmInputError(
        f"no GIRR tenor definition for tenor {normalised}",
        field="tenor",
    )


def girr_delta_risk_weight_rule(
    profile: SbmRegulatoryProfile | str,
    tenor: str,
) -> SbmGirrRiskWeightRule:
    """Return the cited base GIRR delta risk-weight rule for a tenor."""

    normalised = _require_text(tenor, "tenor")
    for rule in PROFILE_GIRR_DELTA_RISK_WEIGHTS[_resolve_supported_profile(profile)]:
        if rule.tenor == normalised:
            return rule
    for special_rule in PROFILE_GIRR_SPECIAL_RISK_FACTORS[_resolve_supported_profile(profile)]:
        if special_rule.risk_factor == normalised:
            return SbmGirrRiskWeightRule(
                tenor=special_rule.risk_factor,
                risk_weight=special_rule.risk_weight,
                citation_id=special_rule.citation_id,
            )
    raise SbmInputError(
        f"no GIRR delta risk weight for tenor {normalised}",
        field="tenor",
    )


def girr_delta_risk_weight(
    profile: SbmRegulatoryProfile | str,
    *,
    tenor: str,
    currency: str,
    reporting_currency: str,
) -> tuple[float, tuple[str, ...]]:
    """Return the cited GIRR delta risk weight and citation ids."""

    _ensure_girr_delta_supported(profile)
    resolved = _resolve_supported_profile(profile)
    rule = girr_delta_risk_weight_rule(profile, tenor)
    normalised_currency = _require_currency(currency)
    normalised_reporting = _require_currency(reporting_currency)
    citation_ids: list[str] = [rule.citation_id]
    risk_weight = rule.risk_weight
    if _apply_sqrt2_adjustment(
        tenor=rule.tenor,
        currency=normalised_currency,
        reporting_currency=normalised_reporting,
    ):
        risk_weight /= SQRT2
        citation_ids.append(PROFILE_GIRR_DELTA_SQRT2_CITATION_IDS[resolved])
    return risk_weight, tuple(citation_ids)


def girr_delta_intra_bucket_correlation(
    profile: SbmRegulatoryProfile | str,
    *,
    tenor1: str,
    tenor2: str,
    same_curve: bool,
) -> tuple[float, tuple[str, ...]]:
    """Return the cited GIRR delta intra-bucket correlation and citation ids."""

    _ensure_girr_delta_supported(profile)
    resolved = _resolve_supported_profile(profile)
    normalised_tenor1 = _require_text(tenor1, "tenor1")
    normalised_tenor2 = _require_text(tenor2, "tenor2")
    citation_ids = (PROFILE_GIRR_DELTA_INTRA_BUCKET_CITATION_IDS[resolved],)

    if normalised_tenor1 == "XCCY" or normalised_tenor2 == "XCCY":
        if normalised_tenor1 == normalised_tenor2:
            return GIRR_SAME_CURVE_CORRELATION, citation_ids
        return 0.0, citation_ids

    if normalised_tenor1 == "INFL" or normalised_tenor2 == "INFL":
        if normalised_tenor1 == normalised_tenor2:
            return GIRR_INFLATION_SAME_TENOR_CORRELATION, citation_ids
        return GIRR_INFLATION_DIFFERENT_TENOR_CORRELATION, citation_ids

    maturity1 = girr_tenor_definition(profile, normalised_tenor1).maturity_years
    maturity2 = girr_tenor_definition(profile, normalised_tenor2).maturity_years
    tenor_correlation = _exponential_tenor_correlation(
        maturity1,
        maturity2,
        constant=GIRR_DELTA_INTRA_BUCKET_CONSTANT,
        floor=GIRR_INTRA_BUCKET_CORRELATION_FLOOR,
    )
    curve_correlation = (
        GIRR_SAME_CURVE_CORRELATION if same_curve else GIRR_DIFFERENT_CURVE_CORRELATION
    )
    return curve_correlation * tenor_correlation, citation_ids


def girr_vega_liquidity_horizon_days(profile: SbmRegulatoryProfile | str) -> int:
    """Return the cited GIRR vega liquidity horizon in days for a profile."""

    return vega_liquidity_horizon_days(
        profile,
        risk_class=SbmRiskClass.GIRR,
    )


def vega_liquidity_horizon_days(
    profile: SbmRegulatoryProfile | str,
    *,
    risk_class: SbmRiskClass | str,
    bucket_id: str = "",
) -> int:
    """Return the cited MAR21.92 Table 13 vega liquidity horizon in days."""

    resolved = _resolve_supported_profile(profile)
    _ensure_vega_supported(profile)
    resolved_class = _coerce_risk_class(risk_class)
    if resolved_class is SbmRiskClass.EQUITY:
        normalised_bucket = equity_bucket_definition(profile, bucket_id).bucket_id
        if normalised_bucket in EQUITY_VEGA_LARGE_CAP_INDEX_BUCKETS:
            return EQUITY_VEGA_LARGE_CAP_INDEX_LIQUIDITY_HORIZON_DAYS
        if normalised_bucket in EQUITY_VEGA_SMALL_CAP_OTHER_BUCKETS:
            return EQUITY_VEGA_SMALL_CAP_OTHER_LIQUIDITY_HORIZON_DAYS
        raise SbmInputError(
            f"no equity vega liquidity horizon for bucket_id {normalised_bucket}",
            field="bucket_id",
        )
    try:
        return PROFILE_VEGA_LIQUIDITY_HORIZON_DAYS[resolved][resolved_class]
    except KeyError as exc:
        raise UnsupportedRegulatoryFeatureError(
            f"vega liquidity horizon is unsupported for risk_class={resolved_class.value}"
        ) from exc


def vega_risk_weight(
    profile: SbmRegulatoryProfile | str,
    *,
    liquidity_horizon_days: int,
) -> tuple[float, tuple[str, ...]]:
    """Return the cited vega risk weight min(100%, 55% * sqrt(LH/10))."""

    _ensure_vega_supported(profile)
    horizon = require_positive_int(liquidity_horizon_days, "liquidity_horizon_days")
    risk_weight = min(
        GIRR_VEGA_RISK_WEIGHT_CAP,
        GIRR_VEGA_RISK_WEIGHT_FACTOR * math.sqrt(horizon / 10.0),
    )
    return risk_weight, ("basel_mar21_92",)


def girr_vega_option_tenors(
    profile: SbmRegulatoryProfile | str,
) -> tuple[SbmGirrTenorDefinition, ...]:
    """Return the prescribed GIRR vega option-tenor set for a supported profile."""

    resolved = _resolve_supported_profile(profile)
    _ensure_girr_vega_supported(profile)
    return PROFILE_GIRR_VEGA_OPTION_TENORS[resolved]


def girr_vega_option_tenor_definition(
    profile: SbmRegulatoryProfile | str,
    option_tenor: str,
) -> SbmGirrTenorDefinition:
    """Return the GIRR vega option-tenor definition for a canonical label."""

    normalised = _require_text(option_tenor, "option_tenor")
    for tenor_definition in girr_vega_option_tenors(profile):
        if tenor_definition.tenor == normalised:
            return tenor_definition
    raise SbmInputError(
        f"no GIRR vega option tenor definition for option_tenor {normalised}",
        field="option_tenor",
    )


def girr_vega_intra_bucket_correlation(
    profile: SbmRegulatoryProfile | str,
    *,
    option_tenor1: str,
    option_tenor2: str,
    tenor1: str,
    tenor2: str,
) -> tuple[float, tuple[str, ...]]:
    """Return min(1, rho_opt * rho_ul) with 1% exponential tenor constants."""

    _ensure_girr_vega_supported(profile)
    rho_opt, _ = vega_option_tenor_correlation(
        profile,
        option_tenor1=option_tenor1,
        option_tenor2=option_tenor2,
    )
    underlying_maturity1 = girr_tenor_definition(profile, tenor1).maturity_years
    underlying_maturity2 = girr_tenor_definition(profile, tenor2).maturity_years
    rho_ul = _exponential_tenor_correlation(
        underlying_maturity1,
        underlying_maturity2,
        constant=GIRR_VEGA_INTRA_BUCKET_CONSTANT,
        floor=None,
    )
    return min(1.0, rho_opt * rho_ul), ("basel_mar21_93",)


def vega_option_tenor_correlation(
    profile: SbmRegulatoryProfile | str,
    *,
    option_tenor1: str,
    option_tenor2: str,
) -> tuple[float, tuple[str, ...]]:
    """Return the MAR21.93 option-tenor correlation term used by vega paths."""

    _ensure_vega_supported(profile)
    option_maturity1 = girr_vega_option_tenor_definition(profile, option_tenor1).maturity_years
    option_maturity2 = girr_vega_option_tenor_definition(profile, option_tenor2).maturity_years
    return (
        _exponential_tenor_correlation(
            option_maturity1,
            option_maturity2,
            constant=GIRR_VEGA_INTRA_BUCKET_CONSTANT,
            floor=None,
        ),
        ("basel_mar21_93",),
    )


def girr_inter_bucket_correlation(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket1: str,
    bucket2: str,
) -> tuple[float, tuple[str, ...]]:
    """Return the cited GIRR inter-bucket correlation and citation ids."""

    _ensure_girr_delta_supported(profile)
    resolved = _resolve_supported_profile(profile)
    normalised_bucket1 = _require_text(bucket1, "bucket1")
    normalised_bucket2 = _require_text(bucket2, "bucket2")
    girr_bucket_definition(profile, normalised_bucket1)
    girr_bucket_definition(profile, normalised_bucket2)
    citation_ids = (PROFILE_GIRR_DELTA_INTER_BUCKET_CITATION_IDS[resolved],)
    if normalised_bucket1 == normalised_bucket2:
        return GIRR_SAME_CURVE_CORRELATION, citation_ids
    return GIRR_INTER_BUCKET_CORRELATION, citation_ids


def fx_buckets_for_profile(
    profile: SbmRegulatoryProfile | str,
) -> tuple[SbmFxBucketDefinition, ...]:
    """Return cited FX bucket definitions for a supported profile."""

    resolved = _resolve_supported_profile(profile)
    _ensure_fx_delta_supported(profile)
    return PROFILE_FX_BUCKETS[resolved]


def fx_specified_currencies_for_profile(
    profile: SbmRegulatoryProfile | str,
) -> frozenset[str]:
    """Return the cited FX specified-currency set for a supported profile."""

    resolved = _resolve_supported_profile(profile)
    _ensure_fx_delta_supported(profile)
    return PROFILE_FX_SPECIFIED_CURRENCIES[resolved]


def normalise_fx_delta_currency_code(currency: str) -> str:
    """Map FX delta currency codes to MAR21.88 canonical bucket codes (ADR 0017)."""

    normalised = _require_currency(currency)
    if normalised == "CNH":
        return "CNY"
    return normalised


def fx_bucket_definition(
    profile: SbmRegulatoryProfile | str,
    bucket_id: str,
) -> SbmFxBucketDefinition:
    """Return the FX bucket definition for a currency bucket id."""

    _ensure_fx_delta_supported(profile)
    normalised = normalise_fx_delta_currency_code(bucket_id)
    for bucket in PROFILE_FX_BUCKETS[_resolve_supported_profile(profile)]:
        if bucket.bucket_id == normalised:
            return bucket
    return SbmFxBucketDefinition(
        bucket_id=normalised,
        currency=normalised,
        citation_id="basel_mar21_86",
    )


def fx_delta_risk_weight(
    profile: SbmRegulatoryProfile | str,
    *,
    currency: str,
    reporting_currency: str,
) -> tuple[float, tuple[str, ...]]:
    """Return the cited FX delta risk weight and citation ids."""

    _ensure_fx_delta_supported(profile)
    normalised_currency = normalise_fx_delta_currency_code(currency)
    normalised_reporting = normalise_fx_delta_currency_code(reporting_currency)
    if normalised_currency == normalised_reporting:
        return 0.0, ("basel_mar21_87",)
    citation_ids: list[str] = ["basel_mar21_87"]
    risk_weight = FX_DELTA_RISK_WEIGHT
    if _apply_fx_sqrt2_adjustment(
        currency=normalised_currency,
        reporting_currency=normalised_reporting,
        profile=profile,
    ):
        risk_weight /= SQRT2
        citation_ids.append("basel_mar21_88")
    return risk_weight, tuple(citation_ids)


def fx_delta_intra_bucket_correlation(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket1: str,
    bucket2: str,
) -> tuple[float, tuple[str, ...]]:
    """Return the cited FX delta intra-bucket correlation and citation ids."""

    _ensure_fx_delta_supported(profile)
    normalised_bucket1 = normalise_fx_delta_currency_code(bucket1)
    normalised_bucket2 = normalise_fx_delta_currency_code(bucket2)
    fx_bucket_definition(profile, normalised_bucket1)
    fx_bucket_definition(profile, normalised_bucket2)
    del normalised_bucket1, normalised_bucket2
    return FX_INTRA_BUCKET_CORRELATION, ("basel_mar21_86",)


def fx_inter_bucket_correlation(
    profile: SbmRegulatoryProfile | str,
    *,
    bucket1: str,
    bucket2: str,
) -> tuple[float, tuple[str, ...]]:
    """Return the cited FX inter-bucket correlation and citation ids."""

    _ensure_fx_delta_supported(profile)
    normalised_bucket1 = normalise_fx_delta_currency_code(bucket1)
    normalised_bucket2 = normalise_fx_delta_currency_code(bucket2)
    fx_bucket_definition(profile, normalised_bucket1)
    fx_bucket_definition(profile, normalised_bucket2)
    if normalised_bucket1 == normalised_bucket2:
        return FX_INTRA_BUCKET_CORRELATION, ("basel_mar21_89",)
    return FX_INTER_BUCKET_CORRELATION, ("basel_mar21_89",)


def correlation_scenarios_for_profile(
    profile: SbmRegulatoryProfile | str,
) -> tuple[SbmCorrelationScenarioDefinition, ...]:
    """Return low, medium, and high correlation scenario definitions."""

    resolved = _resolve_supported_profile(profile)
    return PROFILE_CORRELATION_SCENARIOS[resolved]


def correlation_scenario_definition(
    profile: SbmRegulatoryProfile | str,
    scenario: SbmScenarioLabel | str,
) -> SbmCorrelationScenarioDefinition:
    """Return one correlation scenario definition."""

    resolved_scenario = _coerce_scenario(scenario)
    for definition in correlation_scenarios_for_profile(profile):
        if definition.scenario is resolved_scenario:
            return definition
    raise SbmInputError(
        f"no correlation scenario definition for {resolved_scenario.value}",
        field="scenario",
    )


def apply_correlation_scenario_definition(
    base_correlation: float,
    definition: SbmCorrelationScenarioDefinition,
) -> float:
    """Apply one profile-owned MAR21.6 correlation-scenario rule to a base parameter."""

    if not math.isfinite(base_correlation):
        raise SbmInputError("base_correlation must be finite", field="base_correlation")
    if definition.scenario is SbmScenarioLabel.LOW:
        return max(
            2.0 * base_correlation - 1.0,
            definition.multiplier * base_correlation,
        )
    if definition.scenario is SbmScenarioLabel.HIGH:
        cap = definition.cap if definition.cap is not None else 1.0
        return min(cap, definition.multiplier * base_correlation)
    return definition.multiplier * base_correlation


def apply_correlation_scenario(
    profile: SbmRegulatoryProfile | str,
    *,
    base_correlation: float,
    scenario: SbmScenarioLabel | str,
) -> tuple[float, tuple[str, ...]]:
    """Apply a profile correlation scenario to a base correlation parameter."""

    definition = correlation_scenario_definition(profile, scenario)
    adjusted = apply_correlation_scenario_definition(base_correlation, definition)
    return adjusted, (definition.citation_id,)


def profile_reference_payload(profile: SbmRegulatoryProfile | str) -> dict[str, object]:
    """Return a deterministic, JSON-serialisable payload for profile hashing."""

    resolved = _resolve_supported_profile(profile)
    citations = citations_for_profile(resolved)
    payload: dict[str, object] = {
        "profile": resolved.value,
        "citations": {
            citation_id: {
                "source_id": citation.source_id,
                "location": citation.location,
                "url": citation.url,
                "note": citation.note,
            }
            for citation_id, citation in sorted(citations.items())
        },
    }
    if resolved in PROFILE_GIRR_DELTA_RISK_WEIGHTS:
        payload.update(
            {
                "girr_buckets": [
                    {
                        "bucket_id": bucket.bucket_id,
                        "currency": bucket.currency,
                        "citation_id": bucket.citation_id,
                    }
                    for bucket in girr_buckets_for_profile(resolved)
                ],
                "girr_tenors": [
                    {
                        "tenor": tenor.tenor,
                        "maturity_years": tenor.maturity_years,
                        "citation_id": tenor.citation_id,
                    }
                    for tenor in girr_tenors_for_profile(resolved)
                ],
                "girr_delta_risk_weights": [
                    {
                        "tenor": rule.tenor,
                        "risk_weight": rule.risk_weight,
                        "citation_id": rule.citation_id,
                    }
                    for rule in sorted(
                        PROFILE_GIRR_DELTA_RISK_WEIGHTS[resolved],
                        key=lambda item: item.tenor,
                    )
                ],
                "girr_special_risk_factors": [
                    {
                        "risk_factor": rule.risk_factor,
                        "risk_weight": rule.risk_weight,
                        "citation_id": rule.citation_id,
                    }
                    for rule in PROFILE_GIRR_SPECIAL_RISK_FACTORS[resolved]
                ],
                "correlation_scenarios": [
                    {
                        "scenario": definition.scenario.value,
                        "multiplier": definition.multiplier,
                        "floor_factor": definition.floor_factor,
                        "cap": definition.cap,
                        "citation_id": definition.citation_id,
                    }
                    for definition in correlation_scenarios_for_profile(resolved)
                ],
                "girr_delta_parameters": {
                    "intra_bucket_constant": GIRR_DELTA_INTRA_BUCKET_CONSTANT,
                    "intra_bucket_floor": GIRR_INTRA_BUCKET_CORRELATION_FLOOR,
                    "inter_bucket_correlation": GIRR_INTER_BUCKET_CORRELATION,
                    "intra_bucket_citation_id": (
                        PROFILE_GIRR_DELTA_INTRA_BUCKET_CITATION_IDS[resolved]
                    ),
                    "inter_bucket_citation_id": (
                        PROFILE_GIRR_DELTA_INTER_BUCKET_CITATION_IDS[resolved]
                    ),
                },
            }
        )
    if resolved in PROFILE_GIRR_VEGA_LIQUIDITY_HORIZON_DAYS:
        payload.update(
            {
                "girr_vega_parameters": {
                    "liquidity_horizon_days": PROFILE_GIRR_VEGA_LIQUIDITY_HORIZON_DAYS[resolved],
                    "risk_weight_factor": GIRR_VEGA_RISK_WEIGHT_FACTOR,
                    "risk_weight_cap": GIRR_VEGA_RISK_WEIGHT_CAP,
                    "intra_bucket_constant": GIRR_VEGA_INTRA_BUCKET_CONSTANT,
                    "liquidity_horizon_citation_id": "basel_mar21_92",
                    "intra_bucket_citation_id": "basel_mar21_93",
                },
                "girr_vega_option_tenors": [
                    {
                        "tenor": tenor.tenor,
                        "maturity_years": tenor.maturity_years,
                        "citation_id": tenor.citation_id,
                    }
                    for tenor in girr_vega_option_tenors(resolved)
                ],
            }
        )
    if resolved in PROFILE_VEGA_LIQUIDITY_HORIZON_DAYS:
        payload["non_girr_vega_parameters"] = {
            "liquidity_horizon_days": {
                risk_class.value: horizon
                for risk_class, horizon in sorted(
                    PROFILE_VEGA_LIQUIDITY_HORIZON_DAYS[resolved].items(),
                    key=lambda item: item[0].value,
                )
                if risk_class not in {SbmRiskClass.EQUITY, SbmRiskClass.GIRR}
            },
            "equity_large_cap_index_bucket_ids": sorted(EQUITY_VEGA_LARGE_CAP_INDEX_BUCKETS),
            "equity_large_cap_index_liquidity_horizon_days": (
                EQUITY_VEGA_LARGE_CAP_INDEX_LIQUIDITY_HORIZON_DAYS
            ),
            "equity_small_cap_other_bucket_ids": sorted(EQUITY_VEGA_SMALL_CAP_OTHER_BUCKETS),
            "equity_small_cap_other_liquidity_horizon_days": (
                EQUITY_VEGA_SMALL_CAP_OTHER_LIQUIDITY_HORIZON_DAYS
            ),
            "risk_weight_factor": GIRR_VEGA_RISK_WEIGHT_FACTOR,
            "risk_weight_cap": GIRR_VEGA_RISK_WEIGHT_CAP,
            "intra_bucket_citation_id": "basel_mar21_94",
            "inter_bucket_citation_id": "basel_mar21_95",
        }
    if resolved in PROFILE_FX_BUCKETS:
        payload.update(
            {
                "fx_buckets": [
                    {
                        "bucket_id": bucket.bucket_id,
                        "currency": bucket.currency,
                        "citation_id": bucket.citation_id,
                    }
                    for bucket in fx_buckets_for_profile(resolved)
                ],
                "fx_delta_parameters": {
                    "risk_weight": FX_DELTA_RISK_WEIGHT,
                    "intra_bucket_correlation": FX_INTRA_BUCKET_CORRELATION,
                    "inter_bucket_correlation": FX_INTER_BUCKET_CORRELATION,
                    "risk_weight_citation_id": "basel_mar21_87",
                    "sqrt2_citation_id": "basel_mar21_88",
                    "inter_bucket_citation_id": "basel_mar21_89",
                },
                "fx_specified_currencies": sorted(
                    fx_specified_currencies_for_profile(resolved),
                ),
            }
        )
    if resolved is SbmRegulatoryProfile.BASEL_MAR21:
        payload["curvature_parameters"] = {
            "citation_ids": list(curvature_citation_ids(resolved)),
            "girr_parallel_shift_risk_weight": max(
                rule.risk_weight for rule in PROFILE_GIRR_DELTA_RISK_WEIGHTS[resolved]
            ),
            "fx_equity_rule_citation_id": "basel_mar21_98",
            "parallel_shift_rule_citation_id": "basel_mar21_99",
            "intra_bucket_correlation_citation_id": "basel_mar21_100",
            "inter_bucket_correlation_citation_id": "basel_mar21_101",
        }

        from frtb_sbm.commodity_reference_data import commodity_reference_payload
        from frtb_sbm.csr_nonsec_reference_data import csr_nonsec_reference_payload
        from frtb_sbm.csr_sec_ctp_reference_data import csr_sec_ctp_reference_payload
        from frtb_sbm.csr_sec_nonctp_reference_data import csr_sec_nonctp_reference_payload
        from frtb_sbm.equity_reference_data import equity_reference_payload

        payload.update(equity_reference_payload(resolved))
        payload.update(commodity_reference_payload(resolved))
        payload.update(csr_nonsec_reference_payload(resolved))
        payload.update(csr_sec_nonctp_reference_payload(resolved))
        payload.update(csr_sec_ctp_reference_payload(resolved))
    return payload


def _ensure_girr_supported(profile: SbmRegulatoryProfile | str) -> None:
    resolved = _resolve_supported_profile(profile)
    if resolved is not SbmRegulatoryProfile.BASEL_MAR21:
        raise UnsupportedRegulatoryFeatureError(
            f"GIRR reference data is unsupported for profile {resolved.value}"
        )


def _ensure_girr_delta_supported(profile: SbmRegulatoryProfile | str) -> None:
    resolved = _resolve_supported_profile(profile)
    if resolved not in PROFILE_GIRR_DELTA_RISK_WEIGHTS:
        raise UnsupportedRegulatoryFeatureError(
            f"GIRR delta reference data is unsupported for profile {resolved.value}"
        )


def _ensure_girr_vega_supported(profile: SbmRegulatoryProfile | str) -> None:
    _ensure_girr_supported(profile)


def _ensure_vega_supported(profile: SbmRegulatoryProfile | str) -> None:
    resolved = _resolve_supported_profile(profile)
    if resolved is not SbmRegulatoryProfile.BASEL_MAR21:
        raise UnsupportedRegulatoryFeatureError(
            f"vega reference data is unsupported for profile {resolved.value}"
        )


def _ensure_fx_delta_supported(profile: SbmRegulatoryProfile | str) -> None:
    resolved = _resolve_supported_profile(profile)
    if resolved is not SbmRegulatoryProfile.BASEL_MAR21:
        raise UnsupportedRegulatoryFeatureError(
            f"FX delta reference data is unsupported for profile {resolved.value}"
        )


def _apply_fx_sqrt2_adjustment(
    *,
    currency: str,
    reporting_currency: str,
    profile: SbmRegulatoryProfile | str,
) -> bool:
    if currency == reporting_currency:
        return False
    specified = fx_specified_currencies_for_profile(profile)
    return currency in specified and reporting_currency in specified


def _resolve_supported_profile(profile: SbmRegulatoryProfile | str) -> SbmRegulatoryProfile:
    try:
        resolved = SbmRegulatoryProfile(profile)
    except ValueError as exc:
        raise SbmInputError(
            f"unknown SBM regulatory profile: {profile!r}",
            field="profile_id",
        ) from exc

    if resolved not in PROFILE_CITATIONS:
        raise UnsupportedRegulatoryFeatureError(
            f"SBM profile {resolved.value} is unsupported until mapped and fixture-tested."
        )
    return resolved


def _coerce_risk_class(value: SbmRiskClass | str) -> SbmRiskClass:
    if isinstance(value, SbmRiskClass):
        return value
    try:
        return SbmRiskClass(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in SbmRiskClass)
        raise SbmInputError(
            f"risk_class must be one of: {allowed}",
            field="risk_class",
        ) from exc


def _apply_sqrt2_adjustment(*, tenor: str, currency: str, reporting_currency: str) -> bool:
    if tenor in {"INFL", "XCCY"}:
        return False
    return currency == reporting_currency or currency in LIQUID_GIRR_CURRENCIES


def _exponential_tenor_correlation(
    tenor1_years: float,
    tenor2_years: float,
    *,
    constant: float,
    floor: float | None,
) -> float:
    if tenor1_years <= 0.0 or tenor2_years <= 0.0:
        return GIRR_SAME_CURVE_CORRELATION
    minimum_tenor = min(tenor1_years, tenor2_years)
    exponent = -constant * abs(tenor1_years - tenor2_years) / minimum_tenor
    correlation = math.exp(exponent)
    if floor is None:
        return correlation
    return max(correlation, floor)


def _coerce_scenario(value: SbmScenarioLabel | str) -> SbmScenarioLabel:
    if isinstance(value, SbmScenarioLabel):
        return value
    try:
        return SbmScenarioLabel(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in SbmScenarioLabel)
        raise SbmInputError(
            f"scenario must be one of: {allowed}",
            field="scenario",
        ) from exc


def _require_currency(value: str) -> str:
    normalised = _require_text(value, "currency")
    if len(normalised) != 3 or not normalised.isalpha():
        raise SbmInputError(
            "currency must be a three-letter alphabetic code",
            field="currency",
        )
    return normalised.upper()


__all__ = [
    "BASEL_CORRELATION_SCENARIOS",
    "BASEL_FX_BUCKETS",
    "BASEL_FX_SPECIFIED_CURRENCIES",
    "BASEL_GIRR_BUCKETS",
    "BASEL_GIRR_DELTA_RISK_WEIGHTS",
    "BASEL_GIRR_SPECIAL_RISK_FACTORS",
    "BASEL_GIRR_TENORS",
    "FX_DELTA_RISK_WEIGHT",
    "FX_INTER_BUCKET_CORRELATION",
    "FX_INTRA_BUCKET_CORRELATION",
    "GIRR_DELTA_INTRA_BUCKET_CONSTANT",
    "GIRR_INTER_BUCKET_CORRELATION",
    "GIRR_VEGA_INTRA_BUCKET_CONSTANT",
    "GIRR_VEGA_RISK_WEIGHT_CAP",
    "GIRR_VEGA_RISK_WEIGHT_FACTOR",
    "LIQUID_GIRR_CURRENCIES",
    "PROFILE_GIRR_VEGA_LIQUIDITY_HORIZON_DAYS",
    "PROFILE_VEGA_LIQUIDITY_HORIZON_DAYS",
    "SbmCorrelationScenarioDefinition",
    "SbmFxBucketDefinition",
    "SbmGirrBucketDefinition",
    "SbmGirrRiskWeightRule",
    "SbmGirrSpecialRiskFactorRule",
    "SbmGirrTenorDefinition",
    "apply_correlation_scenario",
    "apply_correlation_scenario_definition",
    "citations_for_profile",
    "commodity_bucket_definition",
    "commodity_buckets_for_profile",
    "commodity_delta_intra_bucket_correlation",
    "commodity_delta_risk_weight",
    "commodity_inter_bucket_correlation",
    "correlation_scenario_definition",
    "correlation_scenarios_for_profile",
    "csr_nonsec_bucket_definition",
    "csr_nonsec_buckets_for_profile",
    "csr_nonsec_delta_intra_bucket_correlation",
    "csr_nonsec_delta_risk_weight",
    "csr_nonsec_inter_bucket_correlation",
    "csr_nonsec_validate_delta_inputs",
    "csr_nonsec_validate_vega_inputs",
    "curvature_citation_ids",
    "curvature_risk_weight",
    "equity_bucket_definition",
    "equity_buckets_for_profile",
    "equity_delta_intra_bucket_correlation",
    "equity_delta_risk_weight",
    "equity_inter_bucket_correlation",
    "fx_bucket_definition",
    "fx_buckets_for_profile",
    "fx_delta_intra_bucket_correlation",
    "fx_delta_risk_weight",
    "fx_inter_bucket_correlation",
    "fx_specified_currencies_for_profile",
    "girr_bucket_definition",
    "girr_bucket_for_currency",
    "girr_buckets_for_profile",
    "girr_delta_intra_bucket_correlation",
    "girr_delta_risk_weight",
    "girr_delta_risk_weight_rule",
    "girr_inter_bucket_correlation",
    "girr_tenor_definition",
    "girr_tenors_for_profile",
    "girr_vega_intra_bucket_correlation",
    "girr_vega_liquidity_horizon_days",
    "girr_vega_option_tenor_definition",
    "girr_vega_option_tenors",
    "profile_reference_payload",
    "vega_liquidity_horizon_days",
    "vega_option_tenor_correlation",
    "vega_risk_weight",
]
