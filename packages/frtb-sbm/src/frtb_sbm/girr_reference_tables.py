"""GIRR reference-data tables for SBM.

Regulatory traceability:
    Basel MAR21.38-MAR21.50, matching U.S. NPR 2.0 comparison-profile
    citations, and PRA PS1/26 Appendix 1 / PRA2026/1 Articles 325ae-325ag.
"""

from __future__ import annotations

import math
from dataclasses import replace

from frtb_sbm.data_models import SbmRegulatoryProfile
from frtb_sbm.reference_citations_eu_crr3 import eu_crr3_citation_id_for_basel
from frtb_sbm.reference_types import (
    SbmGirrBucketDefinition,
    SbmGirrRiskWeightRule,
    SbmGirrSpecialRiskFactorRule,
    SbmGirrTenorDefinition,
)

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

LIQUID_GIRR_CURRENCIES = frozenset({"EUR", "USD", "GBP", "JPY", "AUD", "CAD", "SEK"})
SQRT2 = math.sqrt(2.0)

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

EU_CRR3_GIRR_BUCKETS: tuple[SbmGirrBucketDefinition, ...] = tuple(
    replace(bucket, citation_id=eu_crr3_citation_id_for_basel(bucket.citation_id))
    for bucket in BASEL_GIRR_BUCKETS
)

EU_CRR3_GIRR_TENORS: tuple[SbmGirrTenorDefinition, ...] = tuple(
    replace(tenor, citation_id=eu_crr3_citation_id_for_basel(tenor.citation_id))
    for tenor in BASEL_GIRR_TENORS
)

EU_CRR3_GIRR_DELTA_RISK_WEIGHTS: tuple[SbmGirrRiskWeightRule, ...] = tuple(
    replace(rule, citation_id=eu_crr3_citation_id_for_basel(rule.citation_id))
    for rule in BASEL_GIRR_DELTA_RISK_WEIGHTS
)

EU_CRR3_GIRR_SPECIAL_RISK_FACTORS: tuple[SbmGirrSpecialRiskFactorRule, ...] = tuple(
    replace(rule, citation_id=eu_crr3_citation_id_for_basel(rule.citation_id))
    for rule in BASEL_GIRR_SPECIAL_RISK_FACTORS
)

PRA_UK_CRR_GIRR_BUCKETS: tuple[SbmGirrBucketDefinition, ...] = (
    SbmGirrBucketDefinition("1", "EUR", "pra_uk_crr_325ae_girr_buckets"),
    SbmGirrBucketDefinition("2", "USD", "pra_uk_crr_325ae_girr_buckets"),
    SbmGirrBucketDefinition("3", "GBP", "pra_uk_crr_325ae_girr_buckets"),
    SbmGirrBucketDefinition("4", "JPY", "pra_uk_crr_325ae_girr_buckets"),
    SbmGirrBucketDefinition("5", "AUD", "pra_uk_crr_325ae_girr_buckets"),
    SbmGirrBucketDefinition("6", "CAD", "pra_uk_crr_325ae_girr_buckets"),
    SbmGirrBucketDefinition("7", "CHF", "pra_uk_crr_325ae_girr_buckets"),
    SbmGirrBucketDefinition("8", "CNY", "pra_uk_crr_325ae_girr_buckets"),
    SbmGirrBucketDefinition("9", "HKD", "pra_uk_crr_325ae_girr_buckets"),
    SbmGirrBucketDefinition("10", "KRW", "pra_uk_crr_325ae_girr_buckets"),
    SbmGirrBucketDefinition("11", "MXN", "pra_uk_crr_325ae_girr_buckets"),
    SbmGirrBucketDefinition("12", "NOK", "pra_uk_crr_325ae_girr_buckets"),
    SbmGirrBucketDefinition("13", "NZD", "pra_uk_crr_325ae_girr_buckets"),
    SbmGirrBucketDefinition("14", "SEK", "pra_uk_crr_325ae_girr_buckets"),
    SbmGirrBucketDefinition("15", "SGD", "pra_uk_crr_325ae_girr_buckets"),
    SbmGirrBucketDefinition("16", "TRY", "pra_uk_crr_325ae_girr_buckets"),
    SbmGirrBucketDefinition("17", "CNH", "pra_uk_crr_325ae_girr_buckets"),
)

PRA_UK_CRR_GIRR_TENORS: tuple[SbmGirrTenorDefinition, ...] = (
    SbmGirrTenorDefinition("3m", 0.25, "pra_uk_crr_325ae_girr_delta_weights"),
    SbmGirrTenorDefinition("6m", 0.5, "pra_uk_crr_325ae_girr_delta_weights"),
    SbmGirrTenorDefinition("1y", 1.0, "pra_uk_crr_325ae_girr_delta_weights"),
    SbmGirrTenorDefinition("2y", 2.0, "pra_uk_crr_325ae_girr_delta_weights"),
    SbmGirrTenorDefinition("3y", 3.0, "pra_uk_crr_325ae_girr_delta_weights"),
    SbmGirrTenorDefinition("5y", 5.0, "pra_uk_crr_325ae_girr_delta_weights"),
    SbmGirrTenorDefinition("10y", 10.0, "pra_uk_crr_325ae_girr_delta_weights"),
    SbmGirrTenorDefinition("15y", 15.0, "pra_uk_crr_325ae_girr_delta_weights"),
    SbmGirrTenorDefinition("20y", 20.0, "pra_uk_crr_325ae_girr_delta_weights"),
    SbmGirrTenorDefinition("30y", 30.0, "pra_uk_crr_325ae_girr_delta_weights"),
)

PRA_UK_CRR_GIRR_DELTA_RISK_WEIGHTS: tuple[SbmGirrRiskWeightRule, ...] = (
    SbmGirrRiskWeightRule("3m", 0.017, "pra_uk_crr_325ae_girr_delta_weights"),
    SbmGirrRiskWeightRule("6m", 0.017, "pra_uk_crr_325ae_girr_delta_weights"),
    SbmGirrRiskWeightRule("1y", 0.016, "pra_uk_crr_325ae_girr_delta_weights"),
    SbmGirrRiskWeightRule("2y", 0.013, "pra_uk_crr_325ae_girr_delta_weights"),
    SbmGirrRiskWeightRule("3y", 0.012, "pra_uk_crr_325ae_girr_delta_weights"),
    SbmGirrRiskWeightRule("5y", 0.011, "pra_uk_crr_325ae_girr_delta_weights"),
    SbmGirrRiskWeightRule("10y", 0.011, "pra_uk_crr_325ae_girr_delta_weights"),
    SbmGirrRiskWeightRule("15y", 0.011, "pra_uk_crr_325ae_girr_delta_weights"),
    SbmGirrRiskWeightRule("20y", 0.011, "pra_uk_crr_325ae_girr_delta_weights"),
    SbmGirrRiskWeightRule("30y", 0.011, "pra_uk_crr_325ae_girr_delta_weights"),
)

PRA_UK_CRR_GIRR_SPECIAL_RISK_FACTORS: tuple[SbmGirrSpecialRiskFactorRule, ...] = (
    SbmGirrSpecialRiskFactorRule("INFL", 0.016, "pra_uk_crr_325ae_girr_special_factors"),
    SbmGirrSpecialRiskFactorRule("XCCY", 0.016, "pra_uk_crr_325ae_girr_special_factors"),
)

PROFILE_GIRR_DELTA_SQRT2_CITATION_IDS: dict[SbmRegulatoryProfile, str] = {
    SbmRegulatoryProfile.BASEL_MAR21: "basel_mar21_44",
    SbmRegulatoryProfile.US_NPR_2_0: "us_npr_91_fr_14952_va7a_girr_sqrt2",
    SbmRegulatoryProfile.EU_CRR3: eu_crr3_citation_id_for_basel("basel_mar21_44"),
    SbmRegulatoryProfile.PRA_UK_CRR: "pra_uk_crr_325ae_girr_sqrt2",
}

PROFILE_GIRR_DELTA_INTRA_BUCKET_CITATION_IDS: dict[SbmRegulatoryProfile, str] = {
    SbmRegulatoryProfile.BASEL_MAR21: "basel_mar21_45_49",
    SbmRegulatoryProfile.US_NPR_2_0: "us_npr_91_fr_14952_va7a_girr_intra",
    SbmRegulatoryProfile.EU_CRR3: eu_crr3_citation_id_for_basel("basel_mar21_45_49"),
    SbmRegulatoryProfile.PRA_UK_CRR: "pra_uk_crr_325af_girr_intra",
}

PROFILE_GIRR_DELTA_INTER_BUCKET_CITATION_IDS: dict[SbmRegulatoryProfile, str] = {
    SbmRegulatoryProfile.BASEL_MAR21: "basel_mar21_50",
    SbmRegulatoryProfile.US_NPR_2_0: "us_npr_91_fr_14952_va7a_girr_inter",
    SbmRegulatoryProfile.EU_CRR3: eu_crr3_citation_id_for_basel("basel_mar21_50"),
    SbmRegulatoryProfile.PRA_UK_CRR: "pra_uk_crr_325ag_girr_inter",
}

PROFILE_GIRR_BUCKETS: dict[SbmRegulatoryProfile, tuple[SbmGirrBucketDefinition, ...]] = {
    SbmRegulatoryProfile.BASEL_MAR21: BASEL_GIRR_BUCKETS,
    SbmRegulatoryProfile.US_NPR_2_0: US_NPR_GIRR_BUCKETS,
    SbmRegulatoryProfile.EU_CRR3: EU_CRR3_GIRR_BUCKETS,
    SbmRegulatoryProfile.PRA_UK_CRR: PRA_UK_CRR_GIRR_BUCKETS,
}

PROFILE_GIRR_TENORS: dict[SbmRegulatoryProfile, tuple[SbmGirrTenorDefinition, ...]] = {
    SbmRegulatoryProfile.BASEL_MAR21: BASEL_GIRR_TENORS,
    SbmRegulatoryProfile.US_NPR_2_0: US_NPR_GIRR_TENORS,
    SbmRegulatoryProfile.EU_CRR3: EU_CRR3_GIRR_TENORS,
    SbmRegulatoryProfile.PRA_UK_CRR: PRA_UK_CRR_GIRR_TENORS,
}

PROFILE_GIRR_DELTA_RISK_WEIGHTS: dict[
    SbmRegulatoryProfile,
    tuple[SbmGirrRiskWeightRule, ...],
] = {
    SbmRegulatoryProfile.BASEL_MAR21: BASEL_GIRR_DELTA_RISK_WEIGHTS,
    SbmRegulatoryProfile.US_NPR_2_0: US_NPR_GIRR_DELTA_RISK_WEIGHTS,
    SbmRegulatoryProfile.EU_CRR3: EU_CRR3_GIRR_DELTA_RISK_WEIGHTS,
    SbmRegulatoryProfile.PRA_UK_CRR: PRA_UK_CRR_GIRR_DELTA_RISK_WEIGHTS,
}

PROFILE_GIRR_SPECIAL_RISK_FACTORS: dict[
    SbmRegulatoryProfile,
    tuple[SbmGirrSpecialRiskFactorRule, ...],
] = {
    SbmRegulatoryProfile.BASEL_MAR21: BASEL_GIRR_SPECIAL_RISK_FACTORS,
    SbmRegulatoryProfile.US_NPR_2_0: US_NPR_GIRR_SPECIAL_RISK_FACTORS,
    SbmRegulatoryProfile.EU_CRR3: EU_CRR3_GIRR_SPECIAL_RISK_FACTORS,
    SbmRegulatoryProfile.PRA_UK_CRR: PRA_UK_CRR_GIRR_SPECIAL_RISK_FACTORS,
}


__all__ = [
    "BASEL_GIRR_BUCKETS",
    "BASEL_GIRR_DELTA_RISK_WEIGHTS",
    "BASEL_GIRR_SPECIAL_RISK_FACTORS",
    "BASEL_GIRR_TENORS",
    "EU_CRR3_GIRR_BUCKETS",
    "EU_CRR3_GIRR_DELTA_RISK_WEIGHTS",
    "EU_CRR3_GIRR_SPECIAL_RISK_FACTORS",
    "EU_CRR3_GIRR_TENORS",
    "GIRR_DELTA_INTRA_BUCKET_CONSTANT",
    "GIRR_DIFFERENT_CURVE_CORRELATION",
    "GIRR_INFLATION_DIFFERENT_TENOR_CORRELATION",
    "GIRR_INFLATION_SAME_TENOR_CORRELATION",
    "GIRR_INTER_BUCKET_CORRELATION",
    "GIRR_INTRA_BUCKET_CORRELATION_FLOOR",
    "GIRR_SAME_CURVE_CORRELATION",
    "GIRR_VEGA_INTRA_BUCKET_CONSTANT",
    "GIRR_VEGA_RISK_WEIGHT_CAP",
    "GIRR_VEGA_RISK_WEIGHT_FACTOR",
    "LIQUID_GIRR_CURRENCIES",
    "PRA_UK_CRR_GIRR_BUCKETS",
    "PRA_UK_CRR_GIRR_DELTA_RISK_WEIGHTS",
    "PRA_UK_CRR_GIRR_SPECIAL_RISK_FACTORS",
    "PRA_UK_CRR_GIRR_TENORS",
    "PROFILE_GIRR_BUCKETS",
    "PROFILE_GIRR_DELTA_INTER_BUCKET_CITATION_IDS",
    "PROFILE_GIRR_DELTA_INTRA_BUCKET_CITATION_IDS",
    "PROFILE_GIRR_DELTA_RISK_WEIGHTS",
    "PROFILE_GIRR_DELTA_SQRT2_CITATION_IDS",
    "PROFILE_GIRR_SPECIAL_RISK_FACTORS",
    "PROFILE_GIRR_TENORS",
    "SQRT2",
    "US_NPR_GIRR_BUCKETS",
    "US_NPR_GIRR_DELTA_RISK_WEIGHTS",
    "US_NPR_GIRR_SPECIAL_RISK_FACTORS",
    "US_NPR_GIRR_TENORS",
]
