"""
Data models for FRTB RRAO.

Frozen dataclasses and enums only. Business logic and invariant checks live in
validation, classification, capital, and audit modules.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for data_models.py, Basel MAR23,
    U.S. NPR 2.0 proposed section __.211, and EU Article 325u comparison
    scope.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class RraoClassification(StrEnum):
    """Canonical RRAO classification outcome."""

    EXOTIC = "EXOTIC"
    OTHER_RESIDUAL_RISK = "OTHER_RESIDUAL_RISK"
    SUPERVISOR_DIRECTED = "SUPERVISOR_DIRECTED"
    EXCLUDED = "EXCLUDED"
    UNSUPPORTED = "UNSUPPORTED"


class RraoEvidenceType(StrEnum):
    """Evidence categories used to classify residual-risk positions."""

    EXOTIC_UNDERLYING = "EXOTIC_UNDERLYING"
    GAP_RISK = "GAP_RISK"
    CORRELATION_RISK = "CORRELATION_RISK"
    BEHAVIOURAL_RISK = "BEHAVIOURAL_RISK"
    CTP_THREE_OR_MORE_UNDERLYINGS = "CTP_THREE_OR_MORE_UNDERLYINGS"
    NON_REPLICABLE_OPTIONALITY = "NON_REPLICABLE_OPTIONALITY"
    NO_MATURITY_OPTIONALITY = "NO_MATURITY_OPTIONALITY"
    NO_STRIKE_OR_BARRIER_OPTIONALITY = "NO_STRIKE_OR_BARRIER_OPTIONALITY"
    MULTIPLE_STRIKE_OR_BARRIER_OPTIONALITY = "MULTIPLE_STRIKE_OR_BARRIER_OPTIONALITY"
    INVESTMENT_FUND_EXPOSURE = "INVESTMENT_FUND_EXPOSURE"
    PATH_DEPENDENT_OPTION = "PATH_DEPENDENT_OPTION"
    FORWARD_START_UNDETERMINED_STRIKE_OPTION = "FORWARD_START_UNDETERMINED_STRIKE_OPTION"
    OPTION_ON_OPTION = "OPTION_ON_OPTION"
    DISCONTINUOUS_PAYOFF_OPTION = "DISCONTINUOUS_PAYOFF_OPTION"
    HOLDER_MODIFIABLE_OPTION = "HOLDER_MODIFIABLE_OPTION"
    FINITE_EXERCISE_DATES_OPTION = "FINITE_EXERCISE_DATES_OPTION"
    CROSS_CURRENCY_SETTLED_OPTION = "CROSS_CURRENCY_SETTLED_OPTION"
    MULTI_UNDERLYING_OPTION = "MULTI_UNDERLYING_OPTION"
    BEHAVIOURAL_OPTION = "BEHAVIOURAL_OPTION"
    SUPERVISOR_DIRECTIVE = "SUPERVISOR_DIRECTIVE"
    EXPLICIT_EXCLUSION = "EXPLICIT_EXCLUSION"


class RraoExclusionReason(StrEnum):
    """Cited reasons for zero-capital excluded RRAO lines."""

    LISTED = "LISTED"
    CCP_OR_QCCP_CLEARABLE = "CCP_OR_QCCP_CLEARABLE"
    TWO_OR_FEWER_UNDERLYINGS_NON_PATH_DEPENDENT_OPTION = (
        "TWO_OR_FEWER_UNDERLYINGS_NON_PATH_DEPENDENT_OPTION"
    )
    EXACT_THIRD_PARTY_BACK_TO_BACK = "EXACT_THIRD_PARTY_BACK_TO_BACK"
    DELIVERABLE_HEDGE_PAIR = "DELIVERABLE_HEDGE_PAIR"
    GOVERNMENT_OR_GSE_DEBT = "GOVERNMENT_OR_GSE_DEBT"
    FALLBACK_CAPITAL_REQUIREMENT = "FALLBACK_CAPITAL_REQUIREMENT"
    INTERNAL_DESK_TRANSACTION = "INTERNAL_DESK_TRANSACTION"
    AGENCY_DETERMINED_EXCLUSION = "AGENCY_DETERMINED_EXCLUSION"
    EU_ARTICLE_3_DELIVERABLE_RANGE = "EU_ARTICLE_3_DELIVERABLE_RANGE"
    EU_ARTICLE_3_RELATIVE_IMPLIED_VOLATILITY = "EU_ARTICLE_3_RELATIVE_IMPLIED_VOLATILITY"
    EU_ARTICLE_3_INDEX_OPTION_CORRELATION = "EU_ARTICLE_3_INDEX_OPTION_CORRELATION"
    EU_ARTICLE_3_CIU_INDEX_OPTION_CORRELATION = "EU_ARTICLE_3_CIU_INDEX_OPTION_CORRELATION"
    EU_ARTICLE_3_DIVIDEND_RISK = "EU_ARTICLE_3_DIVIDEND_RISK"


class RraoRegulatoryProfile(StrEnum):
    """Supported and planned RRAO rule-profile identifiers."""

    BASEL_MAR23 = "BASEL_MAR23"
    US_NPR_2_0 = "US_NPR_2_0"
    EU_CRR3 = "EU_CRR3"
    PRA_UK_CRR = "PRA_UK_CRR"


class RraoInvestmentFundMethod(StrEnum):
    """Supported investment-fund treatment methods for RRAO inclusion."""

    BACKSTOP_FUND_METHOD = "BACKSTOP_FUND_METHOD"
    HYPOTHETICAL_PORTFOLIO = "HYPOTHETICAL_PORTFOLIO"
    TRACKED_INDEX = "TRACKED_INDEX"
    LOOK_THROUGH = "LOOK_THROUGH"


class RraoInvestmentFundExposureType(StrEnum):
    """RRAO treatment for the included investment-fund exposure portion."""

    EXOTIC_EXPOSURE = "EXOTIC_EXPOSURE"
    OTHER_RESIDUAL_RISK = "OTHER_RESIDUAL_RISK"


@dataclass(frozen=True)
class RraoCitation:
    """A linkable citation identifier and paragraph hint."""

    source_id: str
    paragraph: str
    url: str
    note: str = ""


@dataclass(frozen=True)
class RraoSourceLineage:
    """Source-system lineage for a canonical RRAO position."""

    source_system: str
    source_file: str
    source_row_id: str
    source_column_map: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class RraoInvestmentFundDescriptor:
    """Evidence for U.S. NPR investment-fund RRAO inclusion."""

    fund_id: str
    section_205_method: RraoInvestmentFundMethod
    included_exposure_type: RraoInvestmentFundExposureType
    mandate_evidence_id: str
    section_205_evidence_id: str
    fund_gross_effective_notional: float
    included_exposure_ratio: float
    look_through_available: bool = False
    mandate_allows_rrao_exposures: bool = True


@dataclass(frozen=True)
class RraoPosition:
    """Canonical residual-risk position before classification and capital."""

    position_id: str
    source_row_id: str
    desk_id: str
    legal_entity: str
    gross_effective_notional: float
    currency: str
    evidence_type: RraoEvidenceType
    evidence_label: str
    lineage: RraoSourceLineage | None
    classification_hint: RraoClassification | None = None
    exclusion_reason: RraoExclusionReason | None = None
    exclusion_evidence_id: str | None = None
    supervisor_directive_id: str | None = None
    underlying_count: int | None = None
    is_path_dependent: bool | None = None
    has_maturity: bool | None = None
    has_strike_or_barrier: bool | None = None
    has_multiple_strikes_or_barriers: bool | None = None
    is_ctp_hedge: bool = False
    is_investment_fund_exposure: bool = False
    investment_fund_descriptor: RraoInvestmentFundDescriptor | None = None
    notional_source: str = "reported"
    citations: tuple[str, ...] = ()


@dataclass(frozen=True)
class RraoCalculationContext:
    """Run-level context for a future RRAO calculation."""

    run_id: str
    calculation_date: date
    base_currency: str
    profile: RraoRegulatoryProfile
    desk_id: str = ""
    legal_entity: str = ""
    citation_policy: str = "strict"


@dataclass(frozen=True)
class RraoClassificationDecision:
    """Cited classification or exclusion decision for one position."""

    position_id: str
    classification: RraoClassification
    evidence_type: RraoEvidenceType
    reason_code: str
    risk_weight_key: str
    citations: tuple[str, ...]
    exclusion_reason: RraoExclusionReason | None = None
    exclusion_evidence_id: str | None = None
    supervisor_directive_id: str | None = None


@dataclass(frozen=True)
class RraoCapitalLine:
    """Line-level RRAO contribution."""

    position_id: str
    classification: RraoClassification
    evidence_type: RraoEvidenceType
    gross_effective_notional: float
    risk_weight: float
    add_on: float
    currency: str
    is_excluded: bool
    reason_code: str
    citations: tuple[str, ...]
    desk_id: str = ""
    legal_entity: str = ""
    source_row_id: str = ""
    exclusion_reason: RraoExclusionReason | None = None
    exclusion_evidence_id: str | None = None


@dataclass(frozen=True)
class RraoSubtotal:
    """Deterministic explain subtotal."""

    subtotal_key: str
    subtotal_type: str
    gross_effective_notional: float
    add_on: float
    position_ids: tuple[str, ...]


@dataclass(frozen=True)
class RraoCapitalResult:
    """Public RRAO capital result shape."""

    run_id: str
    calculation_date: date
    base_currency: str
    profile_id: str
    profile_hash: str
    input_hash: str
    lines: tuple[RraoCapitalLine, ...]
    excluded_lines: tuple[RraoCapitalLine, ...]
    subtotals: tuple[RraoSubtotal, ...]
    total_rrao: float
    citations: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        """Return the deterministic audit payload for this result."""

        from frtb_rrao.audit import serialize_rrao_result

        return serialize_rrao_result(self)


__all__ = [
    "RraoCalculationContext",
    "RraoCapitalLine",
    "RraoCapitalResult",
    "RraoCitation",
    "RraoClassification",
    "RraoClassificationDecision",
    "RraoEvidenceType",
    "RraoExclusionReason",
    "RraoInvestmentFundDescriptor",
    "RraoInvestmentFundExposureType",
    "RraoInvestmentFundMethod",
    "RraoPosition",
    "RraoRegulatoryProfile",
    "RraoSourceLineage",
    "RraoSubtotal",
]
