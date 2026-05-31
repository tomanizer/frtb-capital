"""
Data models for FRTB CVA capital.

Frozen dataclasses and enums only. Business logic and invariant checks live in
validation, scope, ba_cva, capital, and audit modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class CvaMethod(StrEnum):
    """Supported and planned CVA calculation methods."""

    BA_CVA_REDUCED = "BA_CVA_REDUCED"
    BA_CVA_FULL = "BA_CVA_FULL"
    SA_CVA = "SA_CVA"
    MIXED_CARVE_OUT = "MIXED_CARVE_OUT"


class SaCvaRiskClass(StrEnum):
    """SA-CVA delta and vega risk classes."""

    GIRR = "GIRR"
    FX = "FX"
    COUNTERPARTY_CREDIT_SPREAD = "COUNTERPARTY_CREDIT_SPREAD"
    REFERENCE_CREDIT_SPREAD = "REFERENCE_CREDIT_SPREAD"
    EQUITY = "EQUITY"
    COMMODITY = "COMMODITY"


class SaCvaRiskMeasure(StrEnum):
    """SA-CVA risk measure."""

    DELTA = "DELTA"
    VEGA = "VEGA"


class SensitivityTag(StrEnum):
    """SA-CVA sensitivity origin tag."""

    CVA = "CVA"
    HDG = "HDG"


class CreditQuality(StrEnum):
    """Counterparty credit-quality bucket for BA-CVA Table 1."""

    INVESTMENT_GRADE = "INVESTMENT_GRADE"
    HIGH_YIELD = "HIGH_YIELD"
    NOT_RATED = "NOT_RATED"


class CvaSector(StrEnum):
    """Counterparty sector bucket for BA-CVA Table 1."""

    SOVEREIGN = "SOVEREIGN"
    LOCAL_GOVERNMENT = "LOCAL_GOVERNMENT"
    FINANCIALS = "FINANCIALS"
    BASIC_MATERIALS_ENERGY_INDUSTRIALS = "BASIC_MATERIALS_ENERGY_INDUSTRIALS"
    CONSUMER_TRANSPORT_ADMIN = "CONSUMER_TRANSPORT_ADMIN"
    TECHNOLOGY_TELECOM = "TECHNOLOGY_TELECOM"
    HEALTH_UTILITIES_PROFESSIONAL = "HEALTH_UTILITIES_PROFESSIONAL"
    OTHER = "OTHER"


class BaCvaHedgeType(StrEnum):
    """Eligible BA-CVA hedge instrument types."""

    SINGLE_NAME_CDS = "SINGLE_NAME_CDS"
    SINGLE_NAME_CONTINGENT_CDS = "SINGLE_NAME_CONTINGENT_CDS"
    INDEX_CDS = "INDEX_CDS"


class HedgeEligibility(StrEnum):
    """Hedge eligibility outcome."""

    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"
    EXCLUDED = "EXCLUDED"


class HedgeReferenceRelation(StrEnum):
    """Reference-entity relation for indirect BA-CVA hedge recognition."""

    DIRECT = "DIRECT"
    LEGAL_RELATION = "LEGAL_RELATION"
    SAME_SECTOR_AND_REGION = "SAME_SECTOR_AND_REGION"


class CvaRegulatoryProfile(StrEnum):
    """Supported and planned CVA rule-profile identifiers."""

    BASEL_MAR50_2020 = "BASEL_MAR50_2020"
    US_NPR20_VB = "US_NPR20_VB"
    EU_CRR3_CVA = "EU_CRR3_CVA"
    UK_PRA_CVA = "UK_PRA_CVA"


@dataclass(frozen=True)
class CvaCitation:
    """A linkable citation identifier and paragraph hint."""

    source_id: str
    paragraph: str
    url: str
    note: str = ""


@dataclass(frozen=True)
class CvaSourceLineage:
    """Source-system lineage for a canonical CVA record."""

    source_system: str
    source_file: str
    source_row_id: str
    source_column_map: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class CvaCounterparty:
    """Canonical counterparty before BA-CVA capital calculation."""

    counterparty_id: str
    desk_id: str
    legal_entity: str
    sector: CvaSector
    credit_quality: CreditQuality
    region: str
    source_row_id: str
    lineage: CvaSourceLineage | None = None


@dataclass(frozen=True)
class CvaNettingSet:
    """Canonical netting-set exposure row for BA-CVA."""

    netting_set_id: str
    counterparty_id: str
    ead: float
    effective_maturity: float
    discount_factor: float
    currency: str
    sign_convention: str
    uses_imm_ead: bool
    source_row_id: str
    carved_out_to_ba_cva: bool = False
    discount_factor_explicit: bool = False
    lineage: CvaSourceLineage | None = None


@dataclass(frozen=True)
class CvaHedge:
    """Canonical CVA hedge record."""

    hedge_id: str
    source_row_id: str
    counterparty_id: str
    hedge_type: BaCvaHedgeType
    notional: float
    remaining_maturity: float
    discount_factor: float
    reference_sector: CvaSector
    reference_region: str
    reference_relation: HedgeReferenceRelation
    eligibility: HedgeEligibility
    is_internal: bool
    internal_desk_counterparty_id: str | None = None
    sa_cva_risk_class: SaCvaRiskClass | None = None
    eligibility_evidence_id: str | None = None
    rejection_reason: str | None = None
    lineage: CvaSourceLineage | None = None


@dataclass(frozen=True)
class SaCvaSensitivity:
    """Portfolio-aggregate SA-CVA sensitivity before weighting."""

    sensitivity_id: str
    risk_class: SaCvaRiskClass
    risk_measure: SaCvaRiskMeasure
    sensitivity_tag: SensitivityTag
    bucket_id: str
    risk_factor_key: str
    amount: float
    amount_currency: str
    sign_convention: str
    source_row_id: str
    tenor: str | None = None
    volatility_input: float | None = None
    hedge_id: str | None = None
    lineage: CvaSourceLineage | None = None


@dataclass(frozen=True)
class SaCvaRiskFactorKey:
    """Deterministic portfolio risk-factor key for SA-CVA aggregation."""

    risk_class: SaCvaRiskClass
    risk_measure: SaCvaRiskMeasure
    bucket_id: str
    risk_factor_key: str
    tenor: str | None = None


@dataclass(frozen=True)
class CvaRunControls:
    """Run-level controls for audit verbosity and intermediate retention."""

    audit_verbosity: str = "standard"
    retain_intermediate_details: bool = True
    unsupported_feature_behaviour: str = "fail_closed"


@dataclass(frozen=True)
class CvaCalculationContext:
    """Run-level context for a CVA capital calculation."""

    run_id: str
    calculation_date: date
    base_currency: str
    profile: CvaRegulatoryProfile
    method: CvaMethod = CvaMethod.BA_CVA_REDUCED
    sa_cva_approved: bool = False
    materiality_threshold_elected: bool = False
    carve_out_netting_set_ids: tuple[str, ...] = ()
    desk_id: str = ""
    legal_entity: str = ""
    citation_policy: str = "strict"
    run_controls: CvaRunControls | None = None


@dataclass(frozen=True)
class BaCvaStandAloneLine:
    """Netting-set stand-alone BA-CVA contribution."""

    netting_set_id: str
    counterparty_id: str
    sector: CvaSector
    credit_quality: CreditQuality
    ead: float
    effective_maturity: float
    discount_factor: float
    alpha: float
    risk_weight: float
    standalone_capital: float
    currency: str
    source_row_id: str
    citations: tuple[str, ...]
    uses_imm_ead: bool = False
    discount_factor_supplied: bool = True


BaCvaNettingSetLine = BaCvaStandAloneLine


@dataclass(frozen=True)
class BaCvaCounterpartyCapital:
    """Counterparty stand-alone BA-CVA capital."""

    counterparty_id: str
    standalone_capital: float
    netting_set_ids: tuple[str, ...]
    sector: CvaSector
    credit_quality: CreditQuality
    region: str
    citations: tuple[str, ...]


@dataclass(frozen=True)
class BaCvaReducedPortfolioResult:
    """Reduced BA-CVA portfolio aggregation result."""

    k_portfolio: float
    k_reduced: float
    sum_scva: float
    sum_scva_squared: float
    rho: float
    d_ba_cva: float
    alpha: float
    counterparty_capitals: tuple[BaCvaCounterpartyCapital, ...]
    netting_set_lines: tuple[BaCvaStandAloneLine, ...]
    citations: tuple[str, ...]


@dataclass(frozen=True)
class SaCvaWeightedSensitivity:
    """Weighted SA-CVA sensitivity with gross and net preservation."""

    risk_factor_key: SaCvaRiskFactorKey
    gross_cva_amount: float
    gross_hedge_amount: float
    net_amount: float
    risk_weight: float
    weighted_cva: float
    weighted_hedge: float
    weighted_net: float
    citations: tuple[str, ...]


@dataclass(frozen=True)
class SaCvaBucketCapital:
    """SA-CVA bucket capital with aggregation branch metadata."""

    bucket_id: str
    risk_class: SaCvaRiskClass
    risk_measure: SaCvaRiskMeasure
    k_b: float
    s_b: float
    sensitivity_ids: tuple[str, ...]
    citations: tuple[str, ...]
    branch_metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class SaCvaRiskClassCapital:
    """SA-CVA risk-class capital pre- and post-multiplier."""

    risk_class: SaCvaRiskClass
    risk_measure: SaCvaRiskMeasure
    pre_multiplier_capital: float
    post_multiplier_capital: float
    m_cva: float
    bucket_capitals: tuple[SaCvaBucketCapital, ...]
    citations: tuple[str, ...]


@dataclass(frozen=True)
class CvaCapitalResult:
    """Public CVA capital result shape."""

    run_id: str
    calculation_date: date
    base_currency: str
    profile_id: str
    profile_hash: str
    input_hash: str
    method: CvaMethod
    total_cva_capital: float
    ba_cva_reduced: BaCvaReducedPortfolioResult | None
    ba_cva_counterparty_capitals: tuple[BaCvaCounterpartyCapital, ...]
    ba_cva_netting_set_lines: tuple[BaCvaStandAloneLine, ...]
    sa_cva_risk_class_capitals: tuple[SaCvaRiskClassCapital, ...]
    citations: tuple[str, ...]
    warnings: tuple[str, ...] = ()
    unsupported_flags: tuple[str, ...] = ()
    audit_metadata: tuple[tuple[str, str], ...] = ()

    def as_dict(self) -> dict[str, object]:
        """Return the deterministic audit payload for this result."""

        from frtb_cva.audit import serialize_cva_result

        return serialize_cva_result(self)


__all__ = [
    "BaCvaCounterpartyCapital",
    "BaCvaHedgeType",
    "BaCvaNettingSetLine",
    "BaCvaReducedPortfolioResult",
    "BaCvaStandAloneLine",
    "CreditQuality",
    "CvaCalculationContext",
    "CvaCapitalResult",
    "CvaCitation",
    "CvaCounterparty",
    "CvaHedge",
    "CvaMethod",
    "CvaNettingSet",
    "CvaRegulatoryProfile",
    "CvaRunControls",
    "CvaSector",
    "CvaSourceLineage",
    "HedgeEligibility",
    "HedgeReferenceRelation",
    "SaCvaBucketCapital",
    "SaCvaRiskClass",
    "SaCvaRiskClassCapital",
    "SaCvaRiskFactorKey",
    "SaCvaRiskMeasure",
    "SaCvaSensitivity",
    "SaCvaWeightedSensitivity",
    "SensitivityTag",
]
