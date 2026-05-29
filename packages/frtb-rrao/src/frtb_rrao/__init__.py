"""Standardised Approach residual risk add-on scaffold."""

from frtb_rrao._version import __version__
from frtb_rrao.capital import build_rrao_capital_lines, build_rrao_subtotals, included_rrao_total
from frtb_rrao.classification import classify_rrao_position, classify_rrao_positions
from frtb_rrao.data_models import (
    RraoCalculationContext,
    RraoCapitalLine,
    RraoCapitalResult,
    RraoCitation,
    RraoClassification,
    RraoClassificationDecision,
    RraoEvidenceType,
    RraoExclusionReason,
    RraoPosition,
    RraoRegulatoryProfile,
    RraoSourceLineage,
    RraoSubtotal,
)
from frtb_rrao.reference_data import (
    RraoEvidenceRule,
    RraoExclusionRule,
    RraoRiskWeightRule,
    citations_for_profile,
    evidence_rule_for,
    evidence_rules_for_profile,
    exclusion_rule_for,
    exclusion_rules_for_profile,
    risk_weight_rule_for,
    risk_weight_rules_for_profile,
)
from frtb_rrao.regimes import (
    RraoRuleProfile,
    get_rrao_rule_profile,
    profile_content_hash,
    resolve_rrao_profile,
)
from frtb_rrao.scaffold import PACKAGE_METADATA, calculate_rrao_capital
from frtb_rrao.validation import (
    RraoInputError,
    normalise_gross_effective_notional,
    validate_rrao_positions,
)

__all__ = [
    "PACKAGE_METADATA",
    "RraoCalculationContext",
    "RraoCapitalLine",
    "RraoCapitalResult",
    "RraoCitation",
    "RraoClassification",
    "RraoClassificationDecision",
    "RraoEvidenceRule",
    "RraoEvidenceType",
    "RraoExclusionReason",
    "RraoExclusionRule",
    "RraoInputError",
    "RraoPosition",
    "RraoRegulatoryProfile",
    "RraoRiskWeightRule",
    "RraoRuleProfile",
    "RraoSourceLineage",
    "RraoSubtotal",
    "__version__",
    "build_rrao_capital_lines",
    "build_rrao_subtotals",
    "calculate_rrao_capital",
    "citations_for_profile",
    "classify_rrao_position",
    "classify_rrao_positions",
    "evidence_rule_for",
    "evidence_rules_for_profile",
    "exclusion_rule_for",
    "exclusion_rules_for_profile",
    "get_rrao_rule_profile",
    "included_rrao_total",
    "normalise_gross_effective_notional",
    "profile_content_hash",
    "resolve_rrao_profile",
    "risk_weight_rule_for",
    "risk_weight_rules_for_profile",
    "validate_rrao_positions",
]
