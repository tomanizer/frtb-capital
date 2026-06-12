"""Compatibility exports for CVA reference-data lookups.

The physical reference-data implementation is split by package-local family:
profile citations, BA-CVA lookups, and SA-CVA GIRR lookups. This module
preserves the original public import path.
"""

from __future__ import annotations

from frtb_cva._ba_reference_data import (
    _TABLE_1_RISK_WEIGHTS as _TABLE_1_RISK_WEIGHTS,
)
from frtb_cva._ba_reference_data import (
    BA_CVA_ALPHA,
    BA_CVA_BETA,
    BA_CVA_INDEX_RW_SCALAR,
    BA_CVA_RHO,
    BASEL_BA_CVA_RISK_WEIGHT_RULES,
    D_BA_CVA,
    NON_IMM_DISCOUNT_RATE,
    BaCvaRiskWeightRule,
    ba_cva_alpha,
    ba_cva_beta,
    ba_cva_discount_scalar,
    ba_cva_hedge_counterparty_correlation,
    ba_cva_index_risk_weight_scalar,
    ba_cva_rho,
    ba_cva_risk_weight,
    compute_non_imm_discount_factor,
    resolve_netting_set_discount_factor,
)
from frtb_cva._girr_reference_data import (
    BASEL_GIRR_DELTA_CORRELATIONS,
    BASEL_GIRR_DELTA_RISK_WEIGHTS,
    BASEL_GIRR_SPECIAL_RISK_FACTORS,
    BASEL_GIRR_TENORS,
    GIRR_INTER_BUCKET_CORRELATION,
    GIRR_OTHER_CURRENCY_RISK_WEIGHT_SCALAR,
    GIRR_SPECIFIED_CURRENCIES,
    SaCvaGirrDeltaRiskWeightRule,
    SaCvaGirrSpecialRiskFactorRule,
    SaCvaGirrTenorDefinition,
    girr_delta_intra_bucket_correlation,
    girr_delta_risk_weight,
    girr_delta_risk_weight_rule,
    girr_delta_tenors,
    girr_inter_bucket_correlation,
    girr_is_specified_currency,
    girr_other_currency_risk_weight_scalar,
    girr_specified_currencies,
    girr_tenor_definition,
)
from frtb_cva._reference_profile_data import (
    BASEL_MAR50_CITATIONS,
    BASEL_PROFILE_CITATIONS,
    citations_for_profile,
    profile_citation_id,
    profile_citation_ids,
    profile_reference_payload,
)
from frtb_cva._reference_profile_data import (
    _require_text as _require_text,
)
from frtb_cva._reference_profile_data import (
    _resolve_credit_quality as _resolve_credit_quality,
)
from frtb_cva._reference_profile_data import (
    _resolve_sector as _resolve_sector,
)
from frtb_cva._reference_profile_data import (
    _resolve_supported_profile as _resolve_supported_profile,
)

__all__ = [
    "BASEL_BA_CVA_RISK_WEIGHT_RULES",
    "BASEL_GIRR_DELTA_CORRELATIONS",
    "BASEL_GIRR_DELTA_RISK_WEIGHTS",
    "BASEL_GIRR_SPECIAL_RISK_FACTORS",
    "BASEL_GIRR_TENORS",
    "BASEL_MAR50_CITATIONS",
    "BASEL_PROFILE_CITATIONS",
    "BA_CVA_ALPHA",
    "BA_CVA_BETA",
    "BA_CVA_INDEX_RW_SCALAR",
    "BA_CVA_RHO",
    "D_BA_CVA",
    "GIRR_INTER_BUCKET_CORRELATION",
    "GIRR_OTHER_CURRENCY_RISK_WEIGHT_SCALAR",
    "GIRR_SPECIFIED_CURRENCIES",
    "NON_IMM_DISCOUNT_RATE",
    "BaCvaRiskWeightRule",
    "SaCvaGirrDeltaRiskWeightRule",
    "SaCvaGirrSpecialRiskFactorRule",
    "SaCvaGirrTenorDefinition",
    "ba_cva_alpha",
    "ba_cva_beta",
    "ba_cva_discount_scalar",
    "ba_cva_hedge_counterparty_correlation",
    "ba_cva_index_risk_weight_scalar",
    "ba_cva_rho",
    "ba_cva_risk_weight",
    "citations_for_profile",
    "compute_non_imm_discount_factor",
    "girr_delta_intra_bucket_correlation",
    "girr_delta_risk_weight",
    "girr_delta_risk_weight_rule",
    "girr_delta_tenors",
    "girr_inter_bucket_correlation",
    "girr_is_specified_currency",
    "girr_other_currency_risk_weight_scalar",
    "girr_specified_currencies",
    "girr_tenor_definition",
    "profile_citation_id",
    "profile_citation_ids",
    "profile_reference_payload",
    "resolve_netting_set_discount_factor",
]
