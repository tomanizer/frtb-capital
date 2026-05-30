"""
Data models for FRTB SBM.

Frozen dataclasses and enums only. Business logic and invariant checks live in
validation, regimes, reference_data, and capital modules.

Regulatory traceability:
    See docs/REGULATORY_TRACEABILITY.md rows for data_models.py, Basel MAR21,
    U.S. NPR 2.0 section V.A.7.a, and SBM-DATA-001.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class SbmRiskClass(StrEnum):
    """Seven SBM risk classes cited by Basel MAR21."""

    GIRR = "GIRR"
    CSR_NONSEC = "CSR_NONSEC"
    CSR_SEC_CTP = "CSR_SEC_CTP"
    CSR_SEC_NONCTP = "CSR_SEC_NONCTP"
    EQUITY = "EQUITY"
    COMMODITY = "COMMODITY"
    FX = "FX"


class SbmRiskMeasure(StrEnum):
    """Delta, vega, and curvature capital paths."""

    DELTA = "DELTA"
    VEGA = "VEGA"
    CURVATURE = "CURVATURE"


class SbmScenarioLabel(StrEnum):
    """Low, medium, and high correlation scenarios."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class SbmSignConvention(StrEnum):
    """Explicit sign conventions for sensitivity amounts."""

    PAY = "PAY"
    RECEIVE = "RECEIVE"
    LONG = "LONG"
    SHORT = "SHORT"


class SbmBucketType(StrEnum):
    """Initial public bucket labels for supported SBM profiles."""

    GIRR = "GIRR"
    CSR = "CSR"
    EQUITY = "EQUITY"
    COMMODITY = "COMMODITY"
    FX = "FX"


class SbmRegulatoryProfile(StrEnum):
    """Supported and planned SBM rule-profile identifiers."""

    BASEL_MAR21 = "BASEL_MAR21"
    US_NPR_2_0 = "US_NPR_2_0"
    EU_CRR3 = "EU_CRR3"
    PRA_UK_CRR = "PRA_UK_CRR"


class SbmBranchType(StrEnum):
    """Branch metadata retained for audit and later attribution."""

    FLOOR = "FLOOR"
    SCENARIO_SELECTION = "SCENARIO_SELECTION"
    CURVATURE_BRANCH = "CURVATURE_BRANCH"
    UNSUPPORTED_FEATURE = "UNSUPPORTED_FEATURE"
    NORMAL = "NORMAL"


@dataclass(frozen=True)
class SbmCitation:
    """A linkable citation identifier and paragraph hint."""

    source_id: str
    location: str
    url: str
    note: str = ""


@dataclass(frozen=True)
class SbmSourceLineage:
    """Source-system lineage for a canonical SBM sensitivity row."""

    source_system: str
    source_file: str
    source_row_id: str
    source_column_map: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class SbmRuleProfile:
    """Versioned SBM rule profile metadata."""

    profile_id: str
    regulator: str
    version: str
    publication_date: date
    effective_date: date | None
    supported_risk_classes: frozenset[SbmRiskClass]
    supported_measures: Mapping[SbmRiskClass, frozenset[SbmRiskMeasure]]
    citations: Mapping[str, SbmCitation]
    content_hash: str


@dataclass(frozen=True)
class SbmRunControls:
    """Optional run controls for audit verbosity and unsupported-feature behavior."""

    audit_verbosity: str = "standard"
    unsupported_feature_behavior: str = "fail_closed"
    retain_scenario_detail: bool = True


@dataclass(frozen=True)
class SbmCalculationContext:
    """Run-level context for an SBM calculation."""

    run_id: str
    calculation_date: date
    base_currency: str
    reporting_currency: str
    profile_id: str
    desk_id: str = ""
    legal_entity: str = ""
    citation_policy: str = "strict"
    run_controls: SbmRunControls | None = None


@dataclass(frozen=True)
class SbmSensitivity:
    """Canonical sensitivity input before weighting and aggregation."""

    sensitivity_id: str
    source_row_id: str
    desk_id: str
    legal_entity: str
    risk_class: SbmRiskClass
    risk_measure: SbmRiskMeasure
    bucket: str
    risk_factor: str
    amount: float
    amount_currency: str
    sign_convention: SbmSignConvention
    lineage: SbmSourceLineage
    position_id: str | None = None
    # Issuer, currency, or other upstream qualifier; rate/vega tenors use tenor fields.
    qualifier: str | None = None
    tenor: str | None = None
    option_tenor: str | None = None
    liquidity_horizon_days: int | None = None
    maturity: str | None = None
    up_shock_amount: float | None = None
    down_shock_amount: float | None = None
    mapping_citation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class WeightedSensitivity:
    """Weighted sensitivity record after cited risk-weight lookup."""

    sensitivity_id: str
    risk_class: SbmRiskClass
    risk_measure: SbmRiskMeasure
    bucket: str
    raw_amount: float
    risk_weight: float
    scaled_amount: float
    citation_ids: tuple[str, ...]
    # Carries issuer/currency qualifier, or the cited tenor key copied for GIRR rows.
    qualifier: str | None = None
    liquidity_horizon_days: int | None = None


@dataclass(frozen=True)
class BucketCapital:
    """Bucket-level capital after intra-bucket aggregation."""

    bucket_id: str
    risk_class: SbmRiskClass
    risk_measure: SbmRiskMeasure
    kb: float
    weighted_sensitivities: tuple[WeightedSensitivity, ...]
    citation_ids: tuple[str, ...]
    scenario: SbmScenarioLabel | None = None
    sb: float | None = None
    floor_applied: bool = False


@dataclass(frozen=True)
class PairwiseCorrelationRecord:
    """Pairwise intra-bucket correlation retained for audit replay."""

    sensitivity_a: str
    sensitivity_b: str
    correlation: float


@dataclass(frozen=True)
class IntraBucketScenarioRecord:
    """Intra-bucket capital and correlation evidence for one scenario."""

    bucket_id: str
    kb: float
    sb: float
    floor_applied: bool
    pairwise_correlations: tuple[PairwiseCorrelationRecord, ...]
    citation_ids: tuple[str, ...]


@dataclass(frozen=True)
class RiskClassScenarioDetail:
    """Full inter- and intra-bucket evidence for one correlation scenario."""

    scenario: SbmScenarioLabel
    capital: float
    inter_bucket_correlations: tuple[tuple[str, str, float], ...]
    alternative_sb_used: bool
    intra_buckets: tuple[IntraBucketScenarioRecord, ...]
    citation_ids: tuple[str, ...]


@dataclass(frozen=True)
class RiskClassCapital:
    """Risk-class capital totals by scenario and selected outcome."""

    risk_class: SbmRiskClass
    selected_capital: float
    buckets: tuple[BucketCapital, ...]
    citation_ids: tuple[str, ...]
    risk_measure: SbmRiskMeasure | None = None
    scenario_totals: Mapping[SbmScenarioLabel, float] | None = None
    selected_scenario: SbmScenarioLabel | None = None
    scenario_details: tuple[RiskClassScenarioDetail, ...] = ()
    scenario_selection: SbmBranchMetadata | None = None


@dataclass(frozen=True)
class SbmRunContextSummary:
    """Run identity and currency context preserved on capital results."""

    run_id: str
    calculation_date: date
    base_currency: str
    reporting_currency: str


@dataclass(frozen=True)
class CurvatureInput:
    """Curvature-specific up/down shock inputs for one sensitivity."""

    sensitivity_id: str
    bucket: str
    up_shock_amount: float
    down_shock_amount: float
    citation_ids: tuple[str, ...]


@dataclass(frozen=True)
class CurvatureResult:
    """Curvature bucket outcome with branch metadata."""

    bucket_id: str
    selected_branch: str
    bucket_capital: float
    citation_ids: tuple[str, ...]
    floor_applied: bool = False


@dataclass(frozen=True)
class SbmWarning:
    """Structured warning metadata for audit and replay."""

    code: str
    message: str
    sensitivity_id: str = ""
    requirement_id: str = ""


@dataclass(frozen=True)
class SbmUnsupportedFeature:
    """Structured unsupported-feature metadata."""

    feature_key: str
    dimension: str
    reason: str
    requirement_id: str = ""


@dataclass(frozen=True)
class SbmReconciliationMetadata:
    """Reconciliation metadata carried on capital results."""

    input_count: int
    rejected_input_count: int
    requirement_ids: tuple[str, ...]
    citation_ids: tuple[str, ...]


@dataclass(frozen=True)
class SbmBranchMetadata:
    """A branch choice that can affect audit or future attribution."""

    branch_id: str
    branch_type: SbmBranchType
    source_id: str
    selected: bool
    reason: str
    citation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class SbmCapitalResult:
    """Public SBM capital result shape."""

    total_capital: float
    risk_classes: tuple[RiskClassCapital, ...]
    profile_id: str
    profile_hash: str
    input_hash: str
    warnings: tuple[str, ...] = ()
    unsupported_flags: tuple[str, ...] = ()
    structured_warnings: tuple[SbmWarning, ...] = ()
    unsupported_features: tuple[SbmUnsupportedFeature, ...] = ()
    reconciliation: SbmReconciliationMetadata | None = None
    run_context: SbmRunContextSummary | None = None
    portfolio_scenario_totals: Mapping[SbmScenarioLabel, float] | None = None
    selected_portfolio_scenario: SbmScenarioLabel | None = None
    portfolio_scenario_selection: SbmBranchMetadata | None = None

    def as_dict(self) -> dict[str, object]:
        """Return the deterministic audit payload for this result."""

        from frtb_sbm.audit import serialize_sbm_result

        return serialize_sbm_result(self)


__all__ = [
    "BucketCapital",
    "CurvatureInput",
    "CurvatureResult",
    "IntraBucketScenarioRecord",
    "PairwiseCorrelationRecord",
    "RiskClassCapital",
    "RiskClassScenarioDetail",
    "SbmBranchMetadata",
    "SbmBranchType",
    "SbmBucketType",
    "SbmCalculationContext",
    "SbmCapitalResult",
    "SbmCitation",
    "SbmReconciliationMetadata",
    "SbmRegulatoryProfile",
    "SbmRiskClass",
    "SbmRiskMeasure",
    "SbmRuleProfile",
    "SbmRunContextSummary",
    "SbmRunControls",
    "SbmScenarioLabel",
    "SbmSensitivity",
    "SbmSignConvention",
    "SbmSourceLineage",
    "SbmUnsupportedFeature",
    "SbmWarning",
    "WeightedSensitivity",
]
