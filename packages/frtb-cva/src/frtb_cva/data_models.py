"""
Data models for FRTB CVA capital.

Frozen dataclasses and enums only. Business logic and invariant checks live in
validation, scope, ba_cva, capital, and audit modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from frtb_common import CalculationScope


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
    """Delta and vega measures used in MAR50 SA-CVA bucket and risk-class aggregation."""

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


class SaCvaHedgePurpose(StrEnum):
    """SA-CVA hedge purpose under Basel MAR50.38."""

    COUNTERPARTY_CREDIT_SPREAD = "COUNTERPARTY_CREDIT_SPREAD"
    EXPOSURE_COMPONENT = "EXPOSURE_COMPONENT"


class SaCvaHedgeInstrumentType(StrEnum):
    """SA-CVA hedge instrument classification for whole-transaction audit."""

    CREDIT_SPREAD_INSTRUMENT = "CREDIT_SPREAD_INSTRUMENT"
    INTEREST_RATE = "INTEREST_RATE"
    FOREIGN_EXCHANGE = "FOREIGN_EXCHANGE"
    EQUITY = "EQUITY"
    COMMODITY = "COMMODITY"
    OTHER_EXPOSURE_COMPONENT = "OTHER_EXPOSURE_COMPONENT"


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


class SaCvaIndexTreatment(StrEnum):
    """Qualified-index routing for SA-CVA sensitivities (MAR50.50)."""

    SINGLE_NAME = "SINGLE_NAME"
    QUALIFIED_INDEX = "QUALIFIED_INDEX"
    LOOK_THROUGH_REQUIRED = "LOOK_THROUGH_REQUIRED"


class CvaRegulatoryProfile(StrEnum):
    """Supported CVA rule-profile identifiers."""

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
    org_scope: CalculationScope | None = None


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
    exposure_time_series_id: str = ""
    lineage: CvaSourceLineage | None = None
    org_scope: CalculationScope | None = None


@dataclass(frozen=True)
class CvaHedge:
    """Canonical CVA hedge record."""

    hedge_id: str
    source_row_id: str
    counterparty_id: str
    hedge_type: BaCvaHedgeType | None
    notional: float
    remaining_maturity: float
    discount_factor: float
    reference_sector: CvaSector
    reference_credit_quality: CreditQuality
    reference_region: str
    reference_relation: HedgeReferenceRelation
    eligibility: HedgeEligibility
    is_internal: bool
    discount_factor_explicit: bool = False
    internal_desk_counterparty_id: str | None = None
    sa_cva_risk_class: SaCvaRiskClass | None = None
    sa_cva_hedge_purpose: SaCvaHedgePurpose | None = None
    sa_cva_hedge_instrument_type: SaCvaHedgeInstrumentType | None = None
    whole_transaction_evidence_id: str | None = None
    market_risk_ima_eligible: bool | None = None
    market_risk_ima_exclusion_reason: str | None = None
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
    index_treatment: SaCvaIndexTreatment | None = None
    index_max_sector_weight: float | None = None
    index_homogeneous_sector_quality: bool = False
    index_dominant_sector: CvaSector | None = None
    index_remap_bucket_id: str | None = None
    volatility_surface_id: str = ""
    volatility_surface_point_id: str = ""
    shock_id: str = ""
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
    sa_cva_sensitivity_scope_evidence_id: str | None = None
    desk_id: str = ""
    legal_entity: str = ""
    citation_policy: str = "strict"
    run_controls: CvaRunControls | None = None
    calculation_scope: CalculationScope | None = None


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
    exposure_time_series_id: str = ""
    org_scope: CalculationScope | None = None


# Public audit alias retained for netting-set line records in orchestration docs.
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
    org_scope: CalculationScope | None = None


@dataclass(frozen=True)
class BaCvaHedgeRecognitionLine:
    """Per-hedge BA-CVA recognition audit line."""

    hedge_id: str
    counterparty_id: str
    hedge_type: BaCvaHedgeType
    eligibility: HedgeEligibility
    reference_relation: HedgeReferenceRelation
    r_hc: float
    risk_weight: float
    snh_contribution: float
    hma_contribution: float
    index_contribution: float
    reason_code: str
    citations: tuple[str, ...]


@dataclass(frozen=True)
class BaCvaFullPortfolioResult:
    """Full BA-CVA portfolio result with hedge recognition (MAR50.17-MAR50.26)."""

    k_full: float
    k_hedged: float
    k_reduced: float
    k_portfolio_hedged: float
    ih: float
    beta: float
    beta_floor_binding: bool
    rho: float
    d_ba_cva: float
    reduced: BaCvaReducedPortfolioResult
    hedge_lines: tuple[BaCvaHedgeRecognitionLine, ...]
    counterparty_adjusted_standalone: tuple[tuple[str, float], ...]
    citations: tuple[str, ...]


@dataclass(frozen=True)
class CvaMethodComponentTotal:
    """Component capital total for mixed-method assembly."""

    method: CvaMethod
    total_capital: float
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
    source_sensitivity_ids: tuple[str, ...]
    citations: tuple[str, ...]
    volatility_surface_ids: tuple[str, ...] = ()
    volatility_surface_point_ids: tuple[str, ...] = ()
    shock_ids: tuple[str, ...] = ()


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
    volatility_surface_ids: tuple[str, ...] = ()
    volatility_surface_point_ids: tuple[str, ...] = ()
    shock_ids: tuple[str, ...] = ()


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
    ba_cva_full: BaCvaFullPortfolioResult | None
    ba_cva_counterparty_capitals: tuple[BaCvaCounterpartyCapital, ...]
    ba_cva_netting_set_lines: tuple[BaCvaStandAloneLine, ...]
    sa_cva_risk_class_capitals: tuple[SaCvaRiskClassCapital, ...]
    citations: tuple[str, ...]
    input_hash_algorithm: str = "json-row-v1"
    method_components: tuple[CvaMethodComponentTotal, ...] = ()
    warnings: tuple[str, ...] = ()
    unsupported_flags: tuple[str, ...] = ()
    audit_metadata: tuple[tuple[str, str], ...] = ()
    calculation_scope: CalculationScope | None = None

    def as_dict(self) -> dict[str, object]:
        """Return the deterministic audit payload for this result.

        Returns
        -------
        dict[str, object]
            JSON-serializable audit payload for this capital result.
        """

        from frtb_cva.audit import serialize_cva_result

        return serialize_cva_result(self)


__all__ = [
    "BaCvaCounterpartyCapital",
    "BaCvaFullPortfolioResult",
    "BaCvaHedgeRecognitionLine",
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
    "CvaMethodComponentTotal",
    "CvaNettingSet",
    "CvaRegulatoryProfile",
    "CvaRunControls",
    "CvaSector",
    "CvaSourceLineage",
    "HedgeEligibility",
    "HedgeReferenceRelation",
    "SaCvaBucketCapital",
    "SaCvaHedgeInstrumentType",
    "SaCvaHedgePurpose",
    "SaCvaIndexTreatment",
    "SaCvaRiskClass",
    "SaCvaRiskClassCapital",
    "SaCvaRiskFactorKey",
    "SaCvaRiskMeasure",
    "SaCvaSensitivity",
    "SaCvaWeightedSensitivity",
    "SensitivityTag",
]
